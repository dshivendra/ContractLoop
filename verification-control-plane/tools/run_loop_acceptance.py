"""Execute and persist controlled-loop scenarios plus isolated safety mutations."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from vcp import RUNTIME_VERSION
from vcp.audit import audit_loop
from vcp.loop_cli import open_loop
from vcp.planning import compile_execution,compile_kernel,discover_context
from vcp.reconciliation import NOW,create_fixture
from vcp.runtime import SQLiteReconciliationAdapter,approve_execution
from vcp.runtime_models import Intent,Principal
from vcp.security import approve


class NoEffect(SQLiteReconciliationAdapter):
    def apply(self,db):pass


class Transient(SQLiteReconciliationAdapter):
    def __init__(self):self.calls=0
    def apply(self,db):
        self.calls+=1
        if self.calls==1:raise OSError('synthetic transient')
        super().apply(db)


class Violation(SQLiteReconciliationAdapter):
    def apply(self,db):super().apply(db);db.execute('DELETE FROM source')


class Unavailable(SQLiteReconciliationAdapter):
    def apply(self,db):raise OSError('synthetic unavailable')


def benchmark(output):
    rows=[]
    scenarios={'happy':'SUCCESS','false_claim':'FAILURE','transient':'SUCCESS','violation':'FAILURE','unavailable':'UNKNOWN','cancelled':'UNKNOWN','deadline':'UNKNOWN'}
    for name,expected in scenarios.items():
        for repeat in range(3):
            path=output/(name+'-'+str(repeat)+'.sqlite');create_fixture(path,'partial')
            clock=[NOW];loop=open_loop(path,lambda:clock[0]);owner=Principal(tenant='demo',actor='fixture-owner',role='owner')
            intent=Intent(id='kernel-'+name,tenant='demo',owner=owner.actor,objective='Reconcile the synthetic batch',recipe='synthetic-reconciliation')
            kernel=compile_kernel(intent,discover_context(path,'demo'),loop.policy)
            contract=compile_execution(kernel,approve(kernel,loop.policy,NOW),'executor',NOW+120)
            loop.create('task','execution',contract,approve_execution(contract,loop.policy,owner,NOW),owner)
            adapters={'false_claim':NoEffect,'transient':Transient,'violation':Violation,'unavailable':Unavailable}
            if name in adapters:loop.gateway.adapter=adapters[name]()
            if name=='cancelled':loop.cancel('task',owner)
            if name=='deadline':clock[0]+=121
            result=loop.run('task',owner)
            validity='not-issued'
            if result.outcome=='SUCCESS':
                att=loop.attest('task',loop.verifier);validity=loop.attestation_status(att.id,owner)
            audit=audit_loop(path,loop.policy)
            rows.append(dict(scenario=name,repeat=repeat,expected=expected,actual=result.outcome,lifecycle=result.task.lifecycle,
                             actions=result.task.actions,recoveries=result.task.recoveries,collections=result.task.collections,
                             historical_violation=result.task.historical_violation,attestation=validity,audit=audit))
    return rows


def mutation_checks():
    mutations=[
        ('role-bypass',"if principal.tenant!=tenant or principal.role not in roles:","if False:",'tests.test_runtime.RuntimeTests.test_undefined_and_executor_transitions_are_rejected'),
        ('cas-bypass',"if before['meta'][0][0]!=action.expected_state_version or digest(before)!=action.expected_snapshot_hash:","if False:",'tests.test_runtime.RuntimeTests.test_cas_detects_external_change_even_without_version_increment'),
        ('budget-bypass',"if task.actions>=contract.max_actions or task.attempts>=contract.max_attempts or task.budget_units>=contract.max_budget_units:","if False:",'tests.test_runtime.RuntimeTests.test_action_and_cost_budgets_bound_recovery'),
        ('freshness-bypass',"if any(not 0<=now-e['observed_at']<=ages[e['fact']] for e in bundle['evidence']):","if False:",'tests.test_runtime_guards.RuntimeGuardTests.test_stale_evidence_cannot_be_renewed_without_reobservation'),
        ('drift-bypass',"if dependency_invalid or digest(snapshot(ledger.db))!=att.snapshot_hash:","if False:",'tests.test_runtime.RuntimeTests.test_attestation_expires_and_revokes_without_rewriting_verdict'),
        ('expiry-bypass',"if self.clock()>att.expires_at:return 'EXPIRED'","if False:return 'EXPIRED'",'tests.test_runtime.RuntimeTests.test_attestation_expires_and_revokes_without_rewriting_verdict'),
        ('dependency-bypass',"if dependency_outcome:","if False:",'tests.test_composition.CompositionTests.test_failed_dependency_prevents_parent_execution'),
        ('unknown-is-violation',"if pre_truth==Truth.UNKNOWN:raise RuntimeError('runtime invariant unobservable before action')","if pre_truth==Truth.UNKNOWN:raise ArithmeticError('runtime invariant unobservable before action')",'tests.test_runtime_guards.RuntimeGuardTests.test_unknown_invariant_is_unknown_and_rolled_back'),
    ]
    rows=[]
    for name,old,new,test in mutations:
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)
            for package in ('vcp','tests'):shutil.copytree(ROOT/package,dest/package,ignore=shutil.ignore_patterns('__pycache__'))
            file=dest/'vcp/runtime.py';source=file.read_text()
            if source.count(old)!=1:raise ValueError('mutation anchor not unique: '+name)
            file.write_text(source.replace(old,new,1))
            run=subprocess.run([sys.executable,'-m','unittest','-v',test],cwd=dest,capture_output=True,text=True,timeout=30)
            rows.append(dict(name=name,test=test,exit_code=run.returncode,detected=run.returncode!=0 and 'FAIL:' in run.stderr and 'ERROR:' not in run.stderr,stdout=run.stdout,stderr=run.stderr))
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    if any(output.iterdir()):raise SystemExit('output must be new and empty')
    rows=benchmark(output);mutations=mutation_checks()
    passed=all(x['expected']==x['actual'] and x['audit']['runtime_consistent'] for x in rows) and all(x['detected'] for x in mutations)
    result=dict(runtime_version=RUNTIME_VERSION,status='PASS' if passed else 'FAIL',cases=len(rows),matches=sum(x['expected']==x['actual'] for x in rows),
                mutations_detected=sum(x['detected'] for x in mutations),mutation_count=len(mutations),rows=rows,mutations=mutations,
                source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'vcp').rglob('*.py'))},
                limitations=['Synthetic local SQLite resource only','Sampled boundary and point predicates, not continuous historical invariants','Public fixture keys; same-process logical roles','No real infrastructure, money, external adapters or LLM calls'])
    (output/'loop_acceptance.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','mutations','source_sha256','limitations')}))
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
