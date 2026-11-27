import json
from pathlib import Path
import tempfile
from .engine import VerificationEngine
from .integrations.legacy import import_loop_observation
from .integrations.legacy_loop_models import Observation
from .reconciliation import NOW, collect, create_fixture, reference_contract, run_for, synthetic_policy
from .security import approve
from .storage import Ledger


def main():
    policy=synthetic_policy();contract=reference_contract(policy)
    approval=approve(contract,policy,NOW-1)
    claim=import_loop_observation(Observation("legacy-done","legacy-run","reconcile",("complete",),(),True)).claim
    results=[]
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);ledger=Ledger(root/"audit.sqlite");engine=VerificationEngine(policy,ledger)
        try:
            for name in ("correct","false_success","missing"):
                path=root/(name+".sqlite");create_fixture(path,"false_success" if name=="false_success" else "correct")
                run=run_for(contract,"demo/"+name,"demo-exec/"+name)
                evidence=() if name=="missing" else collect(path,contract,run)
                verdict=engine.verify(contract,approval,run,evidence,claim,NOW)
                results.append(dict(scenario=name,executor=claim.execution_status,verifier=verdict.verdict,
                                    attestation=verdict.attestation_status))
            replayed=len(engine.replay())
        finally: ledger.close()
    print(json.dumps(dict(results=results,replayed=replayed),indent=2))


if __name__=="__main__": main()
