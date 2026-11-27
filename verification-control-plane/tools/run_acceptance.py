"""Reproducible offline acceptance, synthetic benchmark and targeted mutations."""
import argparse
import hashlib
from importlib.metadata import version, PackageNotFoundError
import json
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from vcp.engine import VerificationEngine
from vcp import ENGINE_VERSION
from vcp.models import Claim, Contract
from vcp.reconciliation import NOW, collect, create_fixture, read_snapshot, reference_contract, run_for, synthetic_policy
from vcp.security import approve, canonical, digest, seal_evidence
from vcp.storage import Ledger


def run_command(command,cwd=ROOT):
    started=time.perf_counter()
    result=subprocess.run(command,cwd=cwd,text=True,capture_output=True,timeout=60)
    return dict(command=command,exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr,
                elapsed_seconds=time.perf_counter()-started)


def mutation_checks():
    mutations=[
      ("violation-becomes-success","vcp/engine.py",'return "FAILURE"','return "SUCCESS"',"KernelTests.test_false_completion_and_partial_demonstrated"),
      ("missing-evidence-success","vcp/engine.py",'if faults or not sufficient or Truth.UNKNOWN in mandatory:','if faults:',"KernelTests.test_missing_evidence_is_unknown"),
      ("failure-criterion-wrong-polarity","vcp/engine.py",'mandatory.append(negate(truth) if c.role == "failure" else truth)','mandatory.append(truth)',"KernelTests.test_failure_criteria_correct_polarity"),
      ("executor-overrides-verifier","vcp/engine.py",'outcome = classify(mandatory,sufficient,faults)','outcome = "SUCCESS" if claim.execution_status == "completed" else classify(mandatory,sufficient,faults)',"KernelTests.test_false_completion_and_partial_demonstrated"),
      ("skip-scope-check","vcp/evidence.py",'if scope != expected:','if False:',"KernelTests.test_cross_scope_and_replay_rejected"),
      ("accept-stale-evidence","vcp/evidence.py",'if not 0 <= now - record.observed_at <= binding.max_age_seconds:','if False:',"KernelTests.test_stale_future_and_recollection"),
      ("skip-evidence-signature","vcp/evidence.py",'if not hmac.compare_digest(sign(dict(body, content_hash=record.content_hash), candidates[0].key), record.signature):','if False:',"KernelTests.test_fabricated_signature_rejected"),
      ("mix-inconsistent-snapshots","vcp/evidence.py",'if key in incoherent:','if False:',"test_completion.CompletionRegressions.test_mixed_failing_snapshots_cannot_establish_success"),
      ("ignore-bank-only-rows","vcp/reconciliation.py",'matching_correct=bool(matched and exact_ids and bank_ids_covered),unmatched_classified=bool(unmatched and exact_ids and bank_ids_covered),','matching_correct=bool(matched and exact_ids),unmatched_classified=bool(unmatched and exact_ids),',"test_completion.CompletionRegressions.test_bank_only_transaction_cannot_be_silently_ignored"),
      ("overstate-unknown-assurance","vcp/engine.py",'assurance_complete = sufficient and assurance_ok and not faults and Truth.UNKNOWN not in mandatory','assurance_complete = True',"test_completion.CompletionRegressions.test_unsupported_condition_does_not_claim_sufficient_assurance"),
      ("accept-empty-currency","vcp/reconciliation.py",'if any(type(r[1]) is not int or type(r[2]) is not str or not r[2].strip() for r in (*source,*bank,*dest)):','if False:',"test_completion.CompletionRegressions.test_empty_currency_is_not_valid_financial_evidence"),
    ]
    results=[]
    for name,path,old,new,test in mutations:
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)
            shutil.copytree(ROOT/"vcp",dest/"vcp",ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT/"tests",dest/"tests",ignore=shutil.ignore_patterns("__pycache__"))
            target=dest/path;text=target.read_text()
            if text.count(old) != 1: raise ValueError("mutation anchor not unique: "+name)
            target.write_text(text.replace(old,new,1))
            target=("tests."+test if test.startswith("test_completion.") else "tests.test_kernel."+test)
            result=run_command([sys.executable,"-m","unittest","-v",target],dest)
            # A test assertion must fail; import/crash infrastructure errors do not count.
            detected=result["exit_code"] != 0 and "FAIL:" in result["stderr"] and "ERROR:" not in result["stderr"]
            results.append(dict(name=name,detected=detected,**result))
    return results


def benchmark(output):
    policy=synthetic_policy();contract=reference_contract(policy);approval=approve(contract,policy,NOW-1)
    ledger=Ledger(output/"benchmark.sqlite")
    engine=VerificationEngine(policy,ledger)
    claim=Claim(execution_status="completed",message="Executor claims complete")
    scenarios={"correct":"SUCCESS",**{v:"FAILURE" for v in (
        "false_success","partial","duplicate","source_missing","wrong_match","wrong_destination","wrong_currency","unauthorized","extra_bank")},
        **{v:"UNKNOWN" for v in ("missing","stale","conflict","fabricated","fault","mixed_snapshots")}}
    rows=[]
    try:
        fixture_dir=output/"fixtures";fixture_dir.mkdir(exist_ok=True)
        snapshot_dir=output/"snapshots";snapshot_dir.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            for name,expected in scenarios.items():
                path=fixture_dir/(name+".sqlite")
                create_fixture(path,name if name in scenarios and expected == "FAILURE" else "correct")
                snapshot=read_snapshot(path)
                (snapshot_dir/(digest(snapshot)+".json")).write_text(canonical(snapshot)+"\n")
                if name == "mixed_snapshots":
                    mixed_paths=[]
                    for variant in ("false_success","wrong_match"):
                        other=fixture_dir/("mixed-"+variant+".sqlite");create_fixture(other,variant)
                        s=read_snapshot(other);(snapshot_dir/(digest(s)+".json")).write_text(canonical(s)+"\n")
                        mixed_paths.append(other)
                for repeat in range(5):
                    run=run_for(contract,"bench/"+name+"/"+str(repeat),"exec/"+str(repeat))
                    evidence=collect(path,contract,run)
                    if name == "missing": evidence=()
                    if name == "stale": evidence=collect(path,contract,run,observed_at=NOW-61)
                    if name == "fabricated": evidence=(evidence[0].model_copy(update={"signature":"0"*64}),)+evidence[1:]
                    if name == "conflict":
                        body=evidence[0].model_dump(mode="json",exclude={"content_hash","signature"})
                        body.update(id="conflicting-observation",value=False)
                        evidence += (seal_evidence(body,policy.collectors[0].key),)
                    if name == "mixed_snapshots":
                        batches=[collect(p,contract,run) for p in mixed_paths]
                        evidence=tuple(next(e for b in batches for e in b if e.fact==fact and e.value is True)
                                       for fact in (e.fact for e in evidence))
                    start=time.perf_counter_ns()
                    if name == "fault":
                        with patch("vcp.engine.evaluate",side_effect=RuntimeError("injected")):
                            verdict=engine.verify(contract,approval,run,evidence,claim,NOW)
                    else: verdict=engine.verify(contract,approval,run,evidence,claim,NOW)
                    elapsed=(time.perf_counter_ns()-start)/1e6
                    rows.append(dict(scenario=name,repeat=repeat,expected=expected,actual=verdict.verdict,
                                     latency_ms=elapsed,verdict_id=verdict.id,
                                     conditions_observed=sum(a.truth != "UNKNOWN" for a in verdict.assessments),
                                     condition_count=len(verdict.assessments)))
        # Fault injection is a verifier infrastructure condition. Replay fault runs
        # under the same declared injection; replay each stored record independently.
        records=ledger.records()
        replay_count=0
        from vcp.models import Approval, Evidence, Run
        for record in records:
            if record["kind"] != "verification": continue
            b=record["payload"]
            args=(Contract.model_validate(b["contract"]),Approval.model_validate(b["approval"]),Run.model_validate(b["run"]),
                  tuple(Evidence.model_validate(e) for e in b["evidence"]),Claim.model_validate(b["claim"]),b["now"])
            if b["run"]["task_id"].startswith("bench/fault/"):
                with patch("vcp.engine.evaluate",side_effect=RuntimeError("injected")): v=engine.compute(*args)
            else: v=engine.compute(*args)
            if v.model_dump(mode="json") != b["verdict"]: raise AssertionError("benchmark replay mismatch")
            replay_count+=1
        chain=ledger.check()
    finally: ledger.close()
    plan=dict(schema_version=1,engine_version=ENGINE_VERSION,
              fault_injections={"bench/fault/"+str(i):"predicate-runtime-error" for i in range(5)})
    (output/"fault_plan.json").write_text(json.dumps(plan,indent=2)+"\n")
    non_success=[r for r in rows if r["expected"] != "SUCCESS"]
    success=[r for r in rows if r["expected"] == "SUCCESS"]
    violations=[r for r in rows if r["expected"] == "FAILURE"]
    latencies=sorted(r["latency_ms"] for r in rows)
    metrics=dict(cases=len(rows),matches=sum(r["expected"]==r["actual"] for r in rows),
                 false_success=dict(numerator=sum(r["actual"]=="SUCCESS" for r in non_success),denominator=len(non_success)),
                 false_failure=dict(numerator=sum(r["actual"]=="FAILURE" for r in success),denominator=len(success)),
                 unknown=dict(numerator=sum(r["actual"]=="UNKNOWN" for r in rows),denominator=len(rows)),
                 demonstrated_violation_detection=dict(numerator=sum(r["actual"]=="FAILURE" for r in violations),denominator=len(violations)),
                 evidence_condition_coverage=dict(numerator=sum(r["conditions_observed"] for r in rows),denominator=sum(r["condition_count"] for r in rows)),
                 verification_latency_ms=dict(median=statistics.median(latencies),p95=latencies[int(.95*(len(latencies)-1))],maximum=max(latencies)),
                 replayed=replay_count,audit_head=chain,external_calls=0,cost="Local CPU/storage; monetary cost not measured",
                 historical_invariant_detection="not implemented; not measured",
                 replay_fault_assumption="The five injected-fault cases require the same injected RuntimeError for exact replay")
    return dict(metrics=metrics,rows=rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=ROOT/"evidence",
                        help="New, empty directory for this run; never overwrites historical evidence")
    args=parser.parse_args()
    output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    # Refuse to overwrite existing audit history. Reproduce in a fresh extraction.
    if any(output.iterdir()):
        raise SystemExit("output directory must be empty; choose a new --output directory")
    schema=Contract.model_json_schema();schema["$schema"]="https://json-schema.org/draft/2020-12/schema"
    (output/"CONTRACT_SCHEMA.json").write_text(json.dumps(schema,indent=2)+"\n")
    (output/"approved_contract.json").write_text(reference_contract().model_dump_json(indent=2)+"\n")
    commands=[run_command([sys.executable,"tools/run_coverage.py","--output",str(output/"coverage")]),
              run_command([sys.executable,"integrations/contract_loop_reference/validate_graph_package.py"]),
              run_command([sys.executable,"tools/validate_schema.py"])]
    mutations=mutation_checks()
    bench=benchmark(output)
    commands.append(run_command([sys.executable,"tools/replay_audit.py","--database",str(output/"benchmark.sqlite"),
                                 "--fault-plan",str(output/"fault_plan.json")]))
    installed={}
    for name in ("pydantic","jsonschema","pytest","hypothesis","z3-solver","cel-python","temporalio","langgraph","opentelemetry-api"):
        try: installed[name]=version(name)
        except PackageNotFoundError: installed[name]=None
    baseline=run_command(["git","rev-parse","HEAD"])
    manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/"vcp").rglob("*.py"))}
    result=dict(baseline_commit=baseline["stdout"].strip(),engine_version=ENGINE_VERSION,
                python=platform.python_version(),dependencies=installed,
                coverage=json.loads((output/"coverage/coverage.json").read_text()),
                commands=commands,mutations=mutations,benchmark=bench,source_sha256=manifest,
                status="PASS" if all(c["exit_code"]==0 for c in commands) and all(m["detected"] for m in mutations)
                       and bench["metrics"]["matches"]==bench["metrics"]["cases"] else "FAIL")
    (output/"acceptance_results.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(dict(status=result["status"],mutations_detected=sum(x["detected"] for x in mutations),
                          mutation_count=len(mutations),**bench["metrics"]),indent=2))
    return 0 if result["status"]=="PASS" else 1


if __name__=="__main__": raise SystemExit(main())
