"""Approved dependency DAGs over one tenant's local SQLite resource.

Children never prove the parent predicate. Global predicates are sampled at the
parent verification point; no distributed or historical invariant is inferred.
"""
import hmac
from .logic import Truth, conjunction, evaluate
from .reconciliation import observation_facts
from .runtime_models import Composition, ExecutionApproval
from .security import digest, sign


def approve_composition(plan,policy,principal,now):
    plan=Composition.model_validate_json(plan.model_dump_json())
    if principal.role!='owner' or principal.actor!=policy.approver or principal.tenant!=plan.tenant or plan.tenant!=policy.tenant:
        raise PermissionError('composition owner denied')
    body=dict(contract_hash=digest(plan),actor=principal.actor,approved_at=now)
    return ExecutionApproval(**body,signature=sign(body,policy.approval_key))


def register(controller,plan,approval,principal):
    plan=Composition.model_validate_json(plan.model_dump_json())
    expected=approve_composition(plan,controller.policy,principal,approval.approved_at)
    if (approval.approved_at>controller.clock() or approval.contract_hash!=expected.contract_hash
            or approval.actor!=expected.actor or not hmac.compare_digest(approval.signature,expected.signature)):
        raise PermissionError('composition approval invalid')
    with controller.store.transaction() as ledger:
        # Every child already exists and every child plan is immutable. A new
        # parent cannot be inserted into an existing ancestor's approved graph.
        if ledger.db.execute('SELECT 1 FROM loop_tasks WHERE id=?',(plan.parent_task_id,)).fetchone():
            raise ValueError('register plan before creating its parent')
        visited=set()
        def walk(task_id,depth):
            if depth>8 or len(visited)>64:raise ValueError('dependency graph budget')
            if task_id==plan.parent_task_id:raise ValueError('dependency cycle')
            if task_id in visited:return
            visited.add(task_id)
            task=controller.store.task(ledger.db,task_id);contract,_=controller.store.contract(ledger.db,task)
            if contract.composition_hash:
                nested=load(controller,ledger,task,contract)
                for dependency in nested.dependencies:walk(dependency.task_id,depth+1)
        for child in plan.dependencies:
            task=controller.store.task(ledger.db,child.task_id)
            if task.contract_hash!=child.contract_hash:raise PermissionError('child contract pin mismatch')
            walk(child.task_id,1)
        key=digest(plan);payload=plan.model_dump_json()
        old=ledger.db.execute('SELECT payload,approval FROM loop_compositions WHERE hash=?',(key,)).fetchone()
        record=(payload,approval.model_dump_json())
        if old and old!=record:raise ValueError('immutable composition collision')
        if not old:ledger.db.execute('INSERT INTO loop_compositions VALUES (?,?,?)',(key,*record))
        ledger.append_in_transaction('composition',key,dict(plan=plan.model_dump(mode='json'),approval=approval.model_dump(mode='json')))
    return key


def load(controller,ledger,task,contract):
    if not contract.composition_hash:return None
    row=ledger.db.execute('SELECT payload,approval FROM loop_compositions WHERE hash=?',(contract.composition_hash,)).fetchone()
    if not row:raise PermissionError('approved composition missing')
    plan=Composition.model_validate_json(row[0]);approval=ExecutionApproval.model_validate_json(row[1])
    body=approval.model_dump(exclude={'signature'})
    if (plan.tenant!=task.tenant or plan.parent_task_id!=task.id or plan.parent_kernel_hash!=digest(contract.kernel)
            or digest(plan)!=contract.composition_hash or approval.contract_hash!=digest(plan)
            or approval.actor!=controller.policy.approver or approval.approved_at>controller.clock()
            or not hmac.compare_digest(approval.signature,sign(body,controller.policy.approval_key))):
        raise PermissionError('composition scope/approval mismatch')
    return plan


def applicability(plan,contract,state):
    facts=observation_facts(state,contract.kernel.baseline_reference)
    return [(dep,Truth.TRUE if dep.when is None else evaluate(dep.when,facts)) for dep in plan.dependencies]


def global_truth(plan,contract,state):
    if not plan.global_invariants:return Truth.TRUE
    facts=observation_facts(state,contract.kernel.baseline_reference)
    return conjunction(evaluate(x,facts) for x in plan.global_invariants)
