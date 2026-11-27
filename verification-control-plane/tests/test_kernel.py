import itertools
import json
from pathlib import Path
import random
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pydantic import ValidationError

from vcp.engine import VerificationEngine, classify
from vcp.logic import Truth, conjunction, disjunction, evaluate, negate
from vcp.models import All, AnyOf, Claim, Compare, Contract, Not
from vcp.reconciliation import (FACTS, NOW, collect, create_fixture, reference_contract,
                                run_for, synthetic_policy)
from vcp.security import approve, canonical, digest, seal_evidence
from vcp.storage import ContractRepository, Ledger


class LogicTests(unittest.TestCase):
    def test_exhaustive_kleene_tables(self):
        # Independent truth table indexed F,U,T, not implementation helpers.
        values = [Truth.FALSE,Truth.UNKNOWN,Truth.TRUE]
        and_table = [[0,0,0],[0,1,1],[0,1,2]]
        or_table = [[0,1,2],[1,1,2],[2,2,2]]
        for i,j in itertools.product(range(3),repeat=2):
            self.assertEqual(conjunction([values[i],values[j]]),values[and_table[i][j]])
            self.assertEqual(disjunction([values[i],values[j]]),values[or_table[i][j]])
        for i in range(3):
            self.assertEqual(negate(values[i]),values[2-i])

    def test_no_vacuous_empty_composition(self):
        self.assertEqual(conjunction([]),Truth.UNKNOWN)
        self.assertEqual(disjunction([]),Truth.UNKNOWN)
        for model in (All,AnyOf):
            with self.assertRaises(ValidationError): model(items=())

    def test_verdict_oracle_all_three_value_combinations(self):
        for count in range(1,5):
            for row in itertools.product(list(Truth),repeat=count):
                for sufficient,fault in itertools.product((True,False),repeat=2):
                    expected = "FAILURE" if Truth.FALSE in row else (
                        "SUCCESS" if all(t == Truth.TRUE for t in row) and sufficient and not fault else "UNKNOWN")
                    self.assertEqual(classify(row,sufficient,["fault"] if fault else []),expected)

    def test_typed_leaf_and_nested_expressions(self):
        c = Compare(fact="amount",op="ge",expected=10)
        self.assertEqual(evaluate(c,{"amount":10}),Truth.TRUE)
        self.assertEqual(evaluate(c,{"amount":9}),Truth.FALSE)
        self.assertEqual(evaluate(c,{"amount":True}),Truth.UNKNOWN)
        self.assertEqual(evaluate(c,{}),Truth.UNKNOWN)
        expr=All(items=(c,AnyOf(items=(Not(item=Compare(fact="ok",expected=False)),Compare(fact="other",expected=True)))))
        self.assertEqual(evaluate(expr,{"amount":10,"ok":True}),Truth.TRUE)

    def test_no_string_execution_or_coercion(self):
        for value in (1.5,None,[],{}):
            with self.assertRaises(ValidationError): Compare(fact="x",expected=value)
        with self.assertRaises(ValidationError): Compare(fact="x",op="eval",expected=True)
        with self.assertRaises(ValidationError): Compare(fact="x",op="ge",expected=True)


class KernelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.policy=synthetic_policy()
        self.contract=reference_contract(self.policy)
        self.approval=approve(self.contract,self.policy,NOW-1)
        self.run=run_for(self.contract)
        self.ledger=Ledger(self.root/"audit.sqlite")
        self.engine=VerificationEngine(self.policy,self.ledger)
        self.claim=Claim(execution_status="completed",message="Executor says all done")
        self.fixture=self.root/"fixture.sqlite"
        create_fixture(self.fixture)
        self.evidence=collect(self.fixture,self.contract,self.run)

    def tearDown(self):
        self.ledger.close()
        self.tmp.cleanup()

    def verify(self,evidence=None,claim=None,now=NOW):
        return self.engine.verify(self.contract,self.approval,self.run,
                                  self.evidence if evidence is None else evidence,claim or self.claim,now)

    def revise(self,mutator,new_version=True):
        data=self.contract.model_dump(mode="json")
        if new_version:
            data["version"] += 1
        mutator(data)
        self.contract=Contract.model_validate(data)
        self.approval=approve(self.contract,self.policy,NOW-1)
        self.run=run_for(self.contract)
        self.evidence=collect(self.fixture,self.contract,self.run)

    def forged(self,record,**changes):
        data=record.model_dump(mode="json",exclude={"signature","content_hash"})
        data.update(changes)
        return seal_evidence(data,self.policy.collectors[0].key)

    def test_correct_execution_success(self):
        v=self.verify()
        self.assertEqual(v.verdict,"SUCCESS")
        self.assertEqual(v.execution_status,"completed")
        self.assertEqual(v.attestation_status,"not-issued")
        self.assertEqual(v.contract_hash,digest(self.contract))
        self.assertEqual(len(v.assessments),len(FACTS))
        self.assertTrue(all(a.evidence_ids for a in v.assessments))

    def test_false_completion_and_partial_demonstrated(self):
        for variant in ("false_success","partial","duplicate","source_missing","wrong_match","wrong_destination","wrong_currency","unauthorized"):
            with self.subTest(variant=variant):
                path=self.root/(variant+".sqlite")
                create_fixture(path,variant)
                evidence=collect(path,self.contract,self.run)
                self.assertEqual(self.verify(evidence).verdict,"FAILURE")

    def test_missing_evidence_is_unknown(self):
        self.assertEqual(self.verify(()).verdict,"UNKNOWN")
        for index in range(len(self.evidence)):
            with self.subTest(missing=index):
                self.assertEqual(self.verify(self.evidence[:index]+self.evidence[index+1:]).verdict,"UNKNOWN")

    def test_partial_claim_without_outcome_evidence_unknown(self):
        self.assertEqual(self.verify((),Claim(execution_status="partial",message="stopped")).verdict,"UNKNOWN")

    def test_claim_cannot_change_outcome(self):
        for status in ("completed","failed","partial","unknown"):
            self.assertEqual(self.verify(claim=Claim(execution_status=status,message="claim")).verdict,"SUCCESS")

    def test_stale_future_and_recollection(self):
        self.assertEqual(self.verify(now=NOW+61).verdict,"UNKNOWN")
        self.assertEqual(self.verify(now=NOW+60).verdict,"SUCCESS")
        future=tuple(self.forged(e,observed_at=NOW+1) for e in self.evidence)
        self.assertEqual(self.verify(future).verdict,"UNKNOWN")
        fresh=collect(self.fixture,self.contract,self.run,observed_at=NOW+62)
        self.assertEqual(self.verify(fresh,now=NOW+62).verdict,"SUCCESS")

    def test_tampered_evidence_rejected(self):
        record=self.evidence[0].model_copy(update={"value":False})
        v=self.verify((record,)+self.evidence[1:])
        self.assertEqual(v.verdict,"UNKNOWN")
        self.assertTrue(any("content-tampering" in x for x in v.rejected_evidence))

    def test_fabricated_signature_rejected(self):
        record=self.evidence[0].model_copy(update={"signature":"0"*64})
        self.assertEqual(self.verify((record,)+self.evidence[1:]).verdict,"UNKNOWN")

    def test_cross_scope_and_replay_rejected(self):
        for field in ("tenant","task_id","execution_id","contract_hash","resource","state_version"):
            with self.subTest(field=field):
                other=self.forged(self.evidence[0],**{field:"other"})
                self.assertEqual(self.verify((other,)+self.evidence[1:]).verdict,"UNKNOWN")

    def test_independence_and_binding(self):
        for fields in ({"collector":self.run.executor},{"source":"invented"},{"method":"agent-output"}):
            other=self.forged(self.evidence[0],**fields)
            self.assertEqual(self.verify((other,)+self.evidence[1:]).verdict,"UNKNOWN")
        dependent_run=self.run.model_copy(update={"executor":"independent-reader"})
        v=self.engine.verify(self.contract,self.approval,dependent_run,self.evidence,self.claim,NOW)
        self.assertEqual(v.verdict,"UNKNOWN")

    def test_conflicting_authenticated_evidence_unknown(self):
        other=self.forged(self.evidence[0],id="conflict",value=False)
        v=self.verify(self.evidence+(other,))
        self.assertEqual(v.verdict,"UNKNOWN")
        self.assertIn(self.evidence[0].fact+":conflict",v.rejected_evidence)

    def test_same_id_equivocation_unknown_and_duplicate_idempotent(self):
        other=self.forged(self.evidence[0],value=False)
        self.assertEqual(self.verify(self.evidence+(other,)).verdict,"UNKNOWN")
        self.assertEqual(self.verify(self.evidence+self.evidence).verdict,"SUCCESS")

    def test_missing_guard_with_or_true_still_unknown(self):
        def change(d):
            d["conditions"][0]["expression"]={"kind":"any","items":[
                {"kind":"compare","fact":FACTS[0],"expected":True},
                {"kind":"compare","fact":FACTS[1],"expected":True}]}
        self.revise(change)
        evidence=tuple(e for e in self.evidence if e.fact != FACTS[0])
        self.assertEqual(self.verify(evidence).verdict,"UNKNOWN")

    def test_failure_criteria_correct_polarity(self):
        def change(d):
            d["conditions"][0]["role"]="failure"
            d["conditions"][0]["expression"]["expected"]=False
        self.revise(change)
        self.assertEqual(self.verify().verdict,"SUCCESS")
        path=self.root/"bad-source.sqlite"
        create_fixture(path,"source_missing")
        self.assertEqual(self.verify(collect(path,self.contract,self.run)).verdict,"FAILURE")

    def test_violation_overrides_missing_other_evidence(self):
        bad=self.forged(self.evidence[0],value=False)
        self.assertEqual(self.verify((bad,)).verdict,"FAILURE")

    def test_errors_never_success(self):
        with patch("vcp.engine.evaluate",side_effect=RuntimeError("fault")):
            v=self.verify()
            self.assertEqual(v.verdict,"UNKNOWN")
            self.assertEqual(len(v.faults),len(FACTS))
        with patch("vcp.engine.resolve",side_effect=OSError("unavailable")):
            self.assertEqual(self.verify().verdict,"UNKNOWN")

    def test_temporal_and_assurance_unsupported_unknown(self):
        for temporal in ("always","eventual","stability","deadline"):
            self.revise(lambda d:d["conditions"][0].update(temporal=temporal))
            self.assertEqual(self.verify().verdict,"UNKNOWN")
        self.revise(lambda d:d.update(required_assurance="production"))
        self.assertEqual(self.verify().verdict,"UNKNOWN")

    def test_evidence_budget_enforced(self):
        self.revise(lambda d:d.update(max_evidence=1))
        self.assertEqual(self.verify().verdict,"UNKNOWN")

    def test_unbounded_input_iterator_is_bounded(self):
        consumed=[]
        def stream():
            while True:
                consumed.append(1)
                yield self.evidence[0]
        self.assertEqual(self.verify(stream()).verdict,"UNKNOWN")
        self.assertEqual(len(consumed),self.contract.max_evidence+1)

    def test_ast_depth_budget(self):
        data=self.contract.model_dump(mode="json")
        expr=data["conditions"][0]["expression"]
        for _ in range(34): expr={"kind":"not","item":expr}
        data["conditions"][0]["expression"]=expr
        with self.assertRaises(ValidationError): Contract.model_validate(data)

    def test_historical_preconditions_and_unsupported_stages_unknown(self):
        for stage in ("V0","V1","V2","V4"):
            self.revise(lambda d:d["conditions"][0].update(stage=stage))
            self.assertEqual(self.verify().verdict,"UNKNOWN")

    def test_source_baseline_drift_detected(self):
        db=sqlite3.connect(self.fixture)
        db.execute("UPDATE source SET amount_minor=1 WHERE id='T1'")
        db.execute("UPDATE destination SET amount_minor=1 WHERE id='T1'")
        db.execute("UPDATE bank SET amount_minor=1 WHERE id='T1'")
        db.commit();db.close()
        self.assertEqual(self.verify(collect(self.fixture,self.contract,self.run)).verdict,"FAILURE")

    def test_unapproved_or_tampered_contract_rejected(self):
        for approval in (self.approval.model_copy(update={"signature":"bad"}),
                         self.approval.model_copy(update={"approved_at":NOW+1})):
            with self.assertRaises(PermissionError):
                self.engine.verify(self.contract,approval,self.run,self.evidence,self.claim,NOW)
        altered=self.contract.model_copy(update={"objective":"silently changed"})
        with self.assertRaises(PermissionError):
            self.engine.verify(altered,self.approval,self.run,self.evidence,self.claim,NOW)

    def test_contract_model_copy_bypass_is_revalidated(self):
        altered=self.contract.model_copy(update={"conditions":()})
        with self.assertRaises(ValidationError):
            self.engine.verify(altered,self.approval,self.run,self.evidence,self.claim,NOW)

    def test_approved_version_immutable(self):
        self.verify()
        self.revise(lambda d:d.update(objective="new semantics same version"),new_version=False)
        with self.assertRaisesRegex(ValueError,"immutable identity"):
            self.verify()

    def test_approval_not_executor_modifiable(self):
        altered=self.contract.model_copy(update={"approver":self.run.executor})
        with self.assertRaises(PermissionError): approve(altered,self.policy,NOW)

    def test_replay_restart_canonical_and_order_independence(self):
        first=self.verify()
        second=self.verify(tuple(reversed(self.evidence)))
        self.assertEqual(first,second)
        self.assertEqual(len(self.ledger.records()),2)
        self.ledger.close()
        self.ledger=Ledger(self.root/"audit.sqlite")
        self.engine=VerificationEngine(self.policy,self.ledger)
        self.assertEqual(self.engine.replay(),(first,))
        self.assertEqual(digest(self.contract),digest(json.loads(self.contract.model_dump_json())))

    def test_audit_updates_and_deletes_rejected(self):
        self.verify()
        for sql in ("UPDATE ledger SET payload='{}'","DELETE FROM ledger"):
            with self.assertRaises(sqlite3.IntegrityError): self.ledger.db.execute(sql)
        self.ledger.check()

    def test_detect_admin_tampering_and_replay_logic_mutation(self):
        self.verify()
        with patch("vcp.engine.classify",return_value="FAILURE"):
            with self.assertRaisesRegex(ValueError,"replay mismatch"): self.engine.replay()
        self.ledger.db.execute("DROP TRIGGER no_update")
        self.ledger.db.execute("UPDATE ledger SET payload='{}' WHERE seq=1")
        with self.assertRaises(ValueError): self.ledger.check()

    def test_audit_fault_returns_no_issued_success(self):
        with patch.object(self.ledger,"append",side_effect=sqlite3.OperationalError("disk full")):
            with self.assertRaises(sqlite3.OperationalError): self.verify()

    def test_no_empty_contradictory_tautological_contracts(self):
        mutations=[lambda d:d.update(conditions=[]),
                   lambda d:[c.update(role="constraint") for c in d["conditions"] if c["role"]=="success"],
                   lambda d:d["conditions"].append(dict(d["conditions"][0],id="contradiction",expression={"kind":"compare","fact":FACTS[0],"expected":False})),
                   lambda d:d.update(bindings=d["bindings"][:-1]),
                   lambda d:d["conditions"].append(d["conditions"][0])]
        for mutation in mutations:
            data=self.contract.model_dump(mode="json");mutation(data)
            with self.assertRaises(ValidationError): Contract.model_validate(data)
        data=self.contract.model_dump(mode="json")
        data["conditions"]= [data["conditions"][-1],dict(data["conditions"][0],expression={"kind":"any","items":[
            {"kind":"compare","fact":"x","expected":True},{"kind":"compare","fact":"x","expected":False}]})]
        data["bindings"]=[dict(data["bindings"][0],fact="x"),data["bindings"][-1]]
        with self.assertRaises(ValidationError): Contract.model_validate(data)

    def test_generated_financial_oracle(self):
        # Independent row-level oracle for fixed independent fixture semantics.
        # Does not call collector's observation_facts to establish expected outcome.
        rng=random.Random(19)
        for case in range(40):
            path=self.root/f"generated-{case}.sqlite";create_fixture(path)
            amount=rng.choice((10000,9999,10001,-10000))
            account=rng.choice(("CMS-A","CMS-WRONG"))
            status=rng.choice(("matched","unmatched"))
            db=sqlite3.connect(path)
            db.execute("UPDATE destination SET amount_minor=?,account=?,status=? WHERE id='T1'",(amount,account,status))
            db.commit();db.close()
            expected="SUCCESS" if amount==10000 and account=="CMS-A" and status=="matched" else "FAILURE"
            self.assertEqual(self.verify(collect(path,self.contract,self.run)).verdict,expected)


class IntegrationTests(unittest.TestCase):
    def test_legacy_loop_models_and_claim_adapter(self):
        from vcp.integrations.legacy_loop_models import Observation
        from vcp.integrations.legacy import import_loop_observation
        old=Observation("o1","r1","c1",("done",),("ev1",),True)
        report=import_loop_observation(old)
        self.assertEqual(report.claim.execution_status,"completed")
        self.assertEqual(report.authoritative_evidence_count,0)
        self.assertEqual(report.legacy_run_id,"r1")

    def test_graph_envelope_claim_adapter(self):
        from vcp.integrations.legacy import import_graph_result
        p=dict(evidence_id="e1",run_id="r1",contract_id="c1",contract_version=1,layer_id="L1",attempt=1,
               artifact_digest="a",checks=[dict(passed=True)],producer={},timestamp="2026-11-27T00:00:00Z")
        self.assertEqual(import_graph_result(p).claim.execution_status,"completed")
        p["checks"]=[]
        self.assertEqual(import_graph_result(p).claim.execution_status,"unknown")
        p["checks"]=[dict(passed="true")]
        with self.assertRaises(ValueError): import_graph_result(p)

    def test_legacy_false_success_requires_fresh_evidence(self):
        from vcp.integrations.legacy import import_loop_observation
        from vcp.integrations.legacy_loop_models import Observation
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);create_fixture(root/"fixture.sqlite","false_success")
            c=reference_contract();p=synthetic_policy();r=run_for(c)
            claim=import_loop_observation(Observation("o","r","c",("done",),(),True)).claim
            ledger=Ledger(root/"audit.sqlite")
            try:
                engine=VerificationEngine(p,ledger);a=approve(c,p,NOW-1)
                self.assertEqual(engine.verify(c,a,r,(),claim,NOW).verdict,"UNKNOWN")
                self.assertEqual(engine.verify(c,a,r,collect(root/"fixture.sqlite",c,r),claim,NOW).verdict,"FAILURE")
            finally: ledger.close()


if __name__ == "__main__": unittest.main()
