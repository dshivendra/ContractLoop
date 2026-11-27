from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest
from unittest.mock import patch

from tests import test_kernel as fixtures
from vcp.reconciliation import collect, create_fixture
from vcp.storage import Ledger


class CompletionRegressions(unittest.TestCase):
    setUp=fixtures.KernelTests.setUp
    tearDown=fixtures.KernelTests.tearDown
    verify=fixtures.KernelTests.verify
    revise=fixtures.KernelTests.revise
    forged=fixtures.KernelTests.forged

    def mixed_snapshots(self):
        batches=[]
        for variant in ('false_success','wrong_match'):
            path=self.root/(variant+'.sqlite');create_fixture(path,variant)
            batch=collect(path,self.contract,self.run)
            self.assertEqual(self.verify(batch).verdict,'FAILURE')
            batches.append(batch)
        return tuple(next(e for b in batches for e in b if e.fact==fact and e.value is True)
                     for fact in (e.fact for e in self.evidence))

    def test_mixed_failing_snapshots_cannot_establish_success(self):
        mixed=self.mixed_snapshots()
        self.assertGreater(len({e.artifact_hash for e in mixed}),1)
        result=self.verify(mixed)
        self.assertEqual(result.verdict,'UNKNOWN')
        self.assertEqual(result.assurance,'insufficient')
        self.assertEqual(len(result.rejected_evidence),len(mixed))
        self.assertTrue(all('snapshot-conflict' in x for x in result.rejected_evidence))

    def test_unauthenticated_snapshot_cannot_poison_coherent_facts(self):
        forged=self.forged(self.evidence[0],id='untrusted',artifact_hash='a'*64)
        forged=forged.model_copy(update={'signature':'0'*64})
        self.assertEqual(self.verify(self.evidence+(forged,)).verdict,'SUCCESS')

    def test_distinct_sources_can_have_distinct_snapshot_hashes(self):
        other=replace(self.policy.collectors[0],source='independent-second-source',collector='second-reader')
        self.policy=replace(self.policy,collectors=self.policy.collectors+(other,))
        self.engine.policy=self.policy
        def revise(d):
            d['trust_policy_hash']=self.policy.fingerprint
            d['bindings'][0].update(source=other.source,collector=other.collector)
        self.revise(revise)
        record=self.forged(self.evidence[0],source=other.source,collector=other.collector,artifact_hash='a'*64)
        self.assertEqual(self.verify((record,)+self.evidence[1:]).verdict,'SUCCESS')

    def test_same_snapshot_reobserved_within_freshness_is_compatible(self):
        fresh=self.forged(self.evidence[0],id='re-observed',observed_at=self.evidence[0].observed_at-1)
        self.assertEqual(self.verify(self.evidence+(fresh,)).verdict,'SUCCESS')

    def test_bank_only_transaction_cannot_be_silently_ignored(self):
        db=sqlite3.connect(self.fixture)
        db.execute("INSERT INTO bank VALUES ('BANK-ONLY',900,'INR')")
        db.commit();db.close()
        self.assertEqual(self.verify(collect(self.fixture,self.contract,self.run)).verdict,'FAILURE')

    def test_empty_currency_is_not_valid_financial_evidence(self):
        db=sqlite3.connect(self.fixture)
        db.execute("INSERT INTO bank VALUES ('T3',700,'')")
        db.commit();db.close()
        with self.assertRaisesRegex(ValueError,'currency'):
            collect(self.fixture,self.contract,self.run)

    def test_unsupported_condition_does_not_claim_sufficient_assurance(self):
        self.revise(lambda d:d['conditions'][0].update(temporal='always'))
        result=self.verify()
        self.assertEqual(result.verdict,'UNKNOWN')
        self.assertEqual(result.assurance,'insufficient')

    def test_wrong_fact_type_has_insufficient_assurance(self):
        record=self.forged(self.evidence[0],value=1)
        result=self.verify((record,)+self.evidence[1:])
        self.assertEqual(result.verdict,'UNKNOWN')
        self.assertEqual(result.assurance,'insufficient')

    def test_parallel_audit_appends_are_serialized_and_durable(self):
        path=self.root/'audit.sqlite'
        def write(i):
            ledger=Ledger(path)
            try:return ledger.append('concurrency-test',str(i),dict(i=i))
            finally:ledger.close()
        with ThreadPoolExecutor(max_workers=4) as pool:
            hashes=list(pool.map(write,range(12)))
        self.assertEqual(len(set(hashes)),12)
        self.assertEqual(len(self.ledger.records()),12)
        self.ledger.check()

    def test_replay_rejects_different_engine_version(self):
        self.verify()
        with patch('vcp.engine.ENGINE_VERSION','unsupported-version'):
            with self.assertRaisesRegex(ValueError,'version/policy'):self.engine.replay()

    def test_read_only_ledger_and_replay_cli(self):
        self.verify();before=self.ledger.check()
        reader=Ledger(self.root/'audit.sqlite',read_only=True)
        try:
            self.assertEqual(reader.check(),before)
            with self.assertRaises(PermissionError):reader.append('forbidden','1',{})
        finally:reader.close()
        script=Path(__file__).resolve().parents[1]/'tools/replay_audit.py'
        result=subprocess.run([sys.executable,str(script),'--database',str(self.root/'audit.sqlite')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['replayed'],1)
        self.assertEqual(self.ledger.check(),before)

    def test_fault_replay_requires_explicit_matching_experiment_plan(self):
        with patch('vcp.engine.evaluate',side_effect=RuntimeError('injected')):self.verify()
        script=Path(__file__).resolve().parents[1]/'tools/replay_audit.py'
        command=[sys.executable,str(script),'--database',str(self.root/'audit.sqlite')]
        without=subprocess.run(command,capture_output=True,text=True)
        self.assertNotEqual(without.returncode,0)
        from vcp import ENGINE_VERSION
        plan=self.root/'faults.json'
        plan.write_text(json.dumps(dict(schema_version=1,engine_version=ENGINE_VERSION,
                                       fault_injections={self.run.task_id:'predicate-runtime-error'})))
        result=subprocess.run(command+['--fault-plan',str(plan)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['fault_injections_reinstated'],1)
