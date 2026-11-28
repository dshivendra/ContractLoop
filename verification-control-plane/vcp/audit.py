"""Read-only replay and consistency checks for the local runtime's trajectory."""
import json
from .engine import VerificationEngine
from .runtime import TRANSITIONS,execution_approved
from .runtime_models import Action,ExecutionApproval,ExecutionContract,Receipt,Task
from .security import digest
from .storage import Ledger


def audit_loop(path,policy):
    ledger=Ledger(path,read_only=True)
    try:
        head=ledger.check();verdicts=VerificationEngine(policy,ledger).replay()
        contracts={}
        for key,payload,approval in ledger.db.execute('SELECT * FROM loop_contracts'):
            contract=ExecutionContract.model_validate_json(payload);approval=ExecutionApproval.model_validate_json(approval)
            if key!=digest(contract) or not execution_approved(contract,approval,policy,approval.approved_at):
                raise ValueError('runtime contract approval mismatch')
            contracts[key]=contract
        states={};receipts={};events=0
        for record in ledger.records():
            if record['kind']!='loop-event':continue
            event=record['payload'];task=Task.model_validate(event['state']);events+=1
            if (task.tenant,task.id,task.execution_id,task.contract_hash)!=(event['tenant'],event['task_id'],event['execution_id'],event['contract_hash']):
                raise ValueError('event scope mismatch')
            contract=contracts[task.contract_hash]
            if task.tenant!=policy.tenant:raise ValueError('audit tenant mismatch')
            previous=states.get(task.id)
            if previous is None:
                if event['kind']!='created' or task.lifecycle!='draft' or any((task.actions,task.attempts,task.recoveries,task.collections,task.budget_units)):
                    raise ValueError('trajectory must start from draft')
            else:
                if (task.execution_id,task.contract_hash)!=(previous.execution_id,previous.contract_hash):raise ValueError('task identity changed')
                if task.lifecycle!=previous.lifecycle:
                    if event['kind']=='dependency-blocked':
                        if task.lifecycle!='blocked' or task.actions:raise ValueError('dependency block mismatch')
                    elif task.lifecycle not in TRANSITIONS[previous.lifecycle]:raise ValueError('illegal audited transition')
                if previous.historical_violation and not task.historical_violation:raise ValueError('historical violation erased')
                for field in ('actions','attempts','recoveries','collections','budget_units'):
                    if getattr(task,field)<getattr(previous,field):raise ValueError('runtime budget counter decreased')
            if (task.actions>contract.max_actions or task.attempts>contract.max_attempts or task.recoveries>contract.max_recoveries
                    or task.collections>contract.max_collections or task.budget_units>contract.max_budget_units):raise ValueError('runtime budget exceeded')
            if event['kind']=='action':
                action=Action.model_validate(event['data']['action']);receipt=Receipt.model_validate(event['data']['receipt'])
                if action.task_id!=task.id or action.contract_hash!=task.contract_hash or digest(action)!=receipt.action_hash:
                    raise ValueError('action receipt binding mismatch')
                key=(task.id,receipt.idempotency_key)
                if key in receipts:raise ValueError('duplicate committed action')
                receipts[key]=receipt
            states[task.id]=task
        actual={row[0]:Task.model_validate_json(row[1]) for row in ledger.db.execute('SELECT * FROM loop_tasks')}
        if actual!=states:raise ValueError('task state differs from audited trajectory')
        stored={(r[0],r[1]):Receipt.model_validate_json(r[3]) for r in ledger.db.execute('SELECT * FROM loop_receipts')}
        if stored!=receipts:raise ValueError('receipt store differs from audited effects')
        return dict(head=head,tasks=len(states),events=events,committed_actions=len(receipts),replayed_verdicts=len(verdicts),runtime_consistent=True)
    finally:ledger.close()
