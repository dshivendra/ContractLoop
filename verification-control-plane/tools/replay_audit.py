"""Read-only replay for the synthetic policy; fault assumptions are explicit inputs."""
import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from vcp import ENGINE_VERSION
from vcp.engine import VerificationEngine
from vcp.reconciliation import synthetic_policy
from vcp.storage import Ledger


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database",type=Path,required=True)
    parser.add_argument("--fault-plan",type=Path,help="Trusted synthetic experiment fault plan; omitted means no injected faults")
    args=parser.parse_args()
    plan={}
    if args.fault_plan:
        data=json.loads(args.fault_plan.read_text())
        if (set(data)!={"schema_version","engine_version","fault_injections"}
                or data["schema_version"]!=1 or data["engine_version"]!=ENGINE_VERSION
                or not isinstance(data["fault_injections"],dict)
                or any(v!="predicate-runtime-error" for v in data["fault_injections"].values())):
            raise ValueError("unsupported fault plan")
        plan=data["fault_injections"]
    ledger=Ledger(args.database,read_only=True)
    try:
        head=ledger.check();engine=VerificationEngine(synthetic_policy(),ledger)
        count,injected,used=0,0,set()
        for record in ledger.records():
            if record["kind"]!="verification":continue
            bundle=record["payload"];task=bundle["run"]["task_id"]
            context=(patch("vcp.engine.evaluate",side_effect=RuntimeError("injected"))
                     if task in plan else nullcontext())
            with context:engine.replay_bundle(bundle)
            count+=1
            if task in plan:injected+=1;used.add(task)
        if used!=set(plan):raise ValueError("fault plan contains absent tasks")
        print(json.dumps(dict(engine_version=ENGINE_VERSION,replayed=count,audit_head=head,
                              fault_injections_reinstated=injected),indent=2))
    finally:ledger.close()


if __name__=="__main__":main()
