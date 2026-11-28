"""Run the local synthetic ContractLoop MVP without cloud services."""
import argparse
import json
import os
from pathlib import Path
import secrets
import sys
import time
import threading
from .api import make_server
from .audit import audit_loop
from .engine import VerificationEngine
from .planning import compile_execution,compile_kernel,discover_context
from .reconciliation import create_fixture,synthetic_policy
from .runtime import LoopController,LoopStore,approve_execution
from .runtime_models import Intent,Principal
from .security import approve,digest
from .storage import Ledger


def open_loop(database,clock=None):
    return LoopController(LoopStore(database,'demo'),synthetic_policy(),clock)


def demo(directory,now=None):
    directory=Path(directory)
    if directory.exists() and any(directory.iterdir()):raise ValueError('demo output must be empty')
    directory.mkdir(parents=True,exist_ok=True)
    database=directory/'loop.sqlite';create_fixture(database,'partial')
    now=int(time.time()) if now is None else now
    loop=open_loop(database,lambda:now)
    owner=Principal(tenant='demo',actor='fixture-owner',role='owner')
    intent=Intent(id='reconcile-demo',tenant='demo',owner=owner.actor,objective='Reconcile the synthetic batch exactly',recipe='synthetic-reconciliation')
    context=discover_context(database,'demo');kernel=compile_kernel(intent,context,loop.policy)
    contract=compile_execution(kernel,approve(kernel,loop.policy,now),'executor',now+120)
    approval=approve_execution(contract,loop.policy,owner,now)
    loop.create('demo-task','demo-execution',contract,approval,owner)
    result=loop.run('demo-task',owner);att=loop.attest('demo-task',loop.verifier)
    ledger=Ledger(database,read_only=True)
    try:
        head=ledger.check();replayed=VerificationEngine(loop.policy,ledger).replay()
        records=ledger.records()
    finally:ledger.close()
    report={'mode':'local-synthetic','outcome':result.outcome,'task':result.task.model_dump(mode='json'),
            'attestation':att.model_dump(mode='json'),'validity':loop.attestation_status(att.id,owner),
            'audit_head':head,'audit_records':len(records),'replayed_verdicts':len(replayed),'snapshot_hash':att.snapshot_hash}
    for filename,value in [('intent.json',intent),('context.json',context),('contract.json',contract),('approval.json',approval),('result.json',report),('trajectory.json',records)]:
        if hasattr(value,'model_dump'):value=value.model_dump(mode='json')
        (directory/filename).write_text(json.dumps(value,indent=2)+'\n')
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    subs=parser.add_subparsers(dest='command',required=True)
    p=subs.add_parser('demo');p.add_argument('--directory',type=Path,required=True)
    p=subs.add_parser('credentials');p.add_argument('--output',type=Path,required=True)
    p=subs.add_parser('serve');p.add_argument('--database',type=Path,required=True);p.add_argument('--tokens',type=Path,required=True);p.add_argument('--port',type=int,default=8765)
    p=subs.add_parser('status');p.add_argument('--database',type=Path,required=True);p.add_argument('--task',default='demo-task')
    p=subs.add_parser('monitor');p.add_argument('--database',type=Path,required=True)
    p=subs.add_parser('audit');p.add_argument('--database',type=Path,required=True)
    args=parser.parse_args(argv)
    if args.command=='demo':print(json.dumps(demo(args.directory),indent=2));return 0
    if args.command=='credentials':
        tokens={role:secrets.token_urlsafe(32) for role in ('owner','verifier','reader','executor')}
        fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as stream:json.dump(tokens,stream,indent=2)
        print(json.dumps({'credentials_file':str(args.output),'mode':'local-synthetic'}));return 0
    if not args.database.is_file():parser.error('existing synthetic loop database required')
    if args.command=='audit':
        report=audit_loop(args.database,synthetic_policy())
        print(json.dumps(report));return 0
    loop=open_loop(args.database)
    if args.command=='monitor':print(json.dumps(loop.monitor(loop.verifier)));return 0
    if args.command=='status':
        print(loop.get(args.task,Principal(tenant='demo',actor='local-reader',role='reader')).model_dump_json(indent=2));return 0
    roles=json.loads(args.tokens.read_text());tokens={}
    for role,token in roles.items():
        if role not in ('owner','verifier','reader','executor'):raise ValueError('unsupported API role')
        if not isinstance(token,str) or token in tokens:raise ValueError('invalid or repeated token')
        tokens[token]=Principal(tenant='demo',actor='fixture-owner' if role=='owner' else 'executor' if role=='executor' else 'independent-'+role,role=role)
    server=make_server(loop,tokens,args.port)
    print(json.dumps({'url':'http://127.0.0.1:'+str(server.server_port),'mode':'local-synthetic'}),flush=True)
    stopped=threading.Event()
    def monitor():
        while not stopped.wait(1):
            try:loop.monitor(loop.verifier)
            except Exception as exc:
                print(json.dumps({'monitor':'fault','type':type(exc).__name__}),file=sys.stderr,flush=True)
    worker=threading.Thread(target=monitor,daemon=True);worker.start()
    try:server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:pass
    finally:stopped.set();worker.join(timeout=5);server.server_close()
    return 0


if __name__=='__main__':raise SystemExit(main())
