from itertools import islice
from . import ENGINE_VERSION
from .models import Approval, Assessment, Claim, Contract, Evidence, Run, Verdict
from .logic import Truth, evaluate, leaves, negate
from .evidence import resolve
from .security import approved, digest
from .storage import ContractRepository


def classify(mandatory, sufficient, faults):
    if Truth.FALSE in mandatory:
        return "FAILURE"
    if faults or not sufficient or Truth.UNKNOWN in mandatory:
        return "UNKNOWN"
    return "SUCCESS" if mandatory else "UNKNOWN"


class VerificationEngine:
    def __init__(self, policy, ledger):
        self.policy = policy
        self.ledger = ledger

    def compute(self, contract, approval, run, evidence, claim, now):
        # Reparse even frozen Pydantic instances: model_copy can bypass validation.
        contract = Contract.model_validate_json(contract.model_dump_json())
        run = Run.model_validate_json(run.model_dump_json())
        evidence = tuple(Evidence.model_validate_json(x.model_dump_json())
                         for x in islice(evidence,contract.max_evidence+1))
        approval = Approval.model_validate_json(approval.model_dump_json())
        claim = Claim.model_validate_json(claim.model_dump_json())
        if not approved(contract, approval, self.policy, now):
            raise PermissionError("contract approval/hash/policy invalid")
        if (run.tenant,run.contract_hash,run.resource) != (contract.tenant,digest(contract),contract.resource):
            raise PermissionError("run not bound to contract")
        faults = []
        if len(evidence) > contract.max_evidence:
            facts,support,rejected = {},{},("evidence-budget-exceeded",)
            faults.append("evidence-budget-exceeded")
        else:
            try:
                facts,support,rejected = resolve(evidence,contract,run,self.policy,now)
            except Exception as error:
                facts,support,rejected = {},{},()
                faults.append("evidence-verifier:" + type(error).__name__)
        assessments, mandatory = [],[]
        for c in contract.conditions:
            ids = tuple(sorted({eid for atom in leaves(c.expression) for eid in support.get(atom.fact,())}))
            try:
                truth = evaluate(c.expression,facts)
                if c.temporal != "point" or c.stage != "V3" or c.role == "precondition":
                    truth = Truth.UNKNOWN
                    reason = "temporal/stage observation unsupported in Phase 1"
                else:
                    reason = "restricted deterministic predicate"
            except Exception as error:
                truth,reason = Truth.UNKNOWN,"predicate fault"
                faults.append(c.id + ":" + type(error).__name__)
            mandatory.append(negate(truth) if c.role == "failure" else truth)
            assessments.append(Assessment(condition_id=c.id,truth=truth.value,evidence_ids=ids,reason=reason))
        sufficient = all(b.fact in facts for b in contract.bindings)
        assurance_ok = contract.required_assurance == "synthetic-point"
        if not assurance_ok:
            mandatory.append(Truth.UNKNOWN)
        outcome = classify(mandatory,sufficient,faults)
        body = dict(tenant=run.tenant,task_id=run.task_id,execution_id=run.execution_id,
                    contract_hash=run.contract_hash,contract_version=contract.version,
                    engine_version=ENGINE_VERSION,policy_hash=self.policy.fingerprint,evaluated_at=now,
                    execution_status=claim.execution_status,verdict=outcome,
                    assurance="synthetic-point" if sufficient and assurance_ok and not faults else "insufficient",
                    trust_assumptions=tuple(contract.assumptions)+self.policy.assumptions,
                    assessments=tuple(assessments),rejected_evidence=rejected,faults=tuple(faults))
        # Convert nested models before hashing; verdict ID binds all returned fields.
        serialized = {k:([a.model_dump(mode="json") for a in v] if k == "assessments" else v) for k,v in body.items()}
        return Verdict(id=digest(serialized),**body)

    def verify(self, contract, approval, run, evidence, claim, now):
        contract = Contract.model_validate_json(contract.model_dump_json())
        evidence = tuple(islice(evidence,contract.max_evidence+1))
        verdict = self.compute(contract,approval,run,evidence,claim,now)
        self.ledger.check()
        ContractRepository(self.ledger).put(contract,approval,self.policy,now)
        bundle = dict(contract=contract.model_dump(mode="json"),approval=approval.model_dump(mode="json"),
                      run=run.model_dump(mode="json"),evidence=[x.model_dump(mode="json") for x in sorted(evidence,key=lambda e:(e.id,digest(e)))],
                      claim=claim.model_dump(mode="json"),now=now,engine_version=ENGINE_VERSION,policy_hash=self.policy.fingerprint,
                      verdict=verdict.model_dump(mode="json"))
        # No verdict is returned if durable audit append fails.
        self.ledger.append("verification",digest(bundle),bundle)
        return verdict

    def replay(self):
        self.ledger.check()
        replayed = []
        for record in self.ledger.records():
            if record["kind"] != "verification":
                continue
            b = record["payload"]
            if b["engine_version"] != ENGINE_VERSION or b["policy_hash"] != self.policy.fingerprint:
                raise ValueError("replay version/policy unavailable")
            result = self.compute(Contract.model_validate(b["contract"]),Approval.model_validate(b["approval"]),
                                  Run.model_validate(b["run"]),tuple(Evidence.model_validate(e) for e in b["evidence"]),
                                  Claim.model_validate(b["claim"]),b["now"])
            if result.model_dump(mode="json") != b["verdict"]:
                raise ValueError("replay mismatch")
            replayed.append(result)
        return tuple(replayed)
