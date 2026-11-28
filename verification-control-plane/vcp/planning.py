"""Deterministic draft compiler and context discovery for the registered recipe.

Compilation never approves a contract. Unrecognized recipes are rejected by the
typed Intent rather than guessed by a model. Free-form NL compilation is optional.
"""
from .models import Contract
from .reconciliation import read_snapshot, reference_contract
from .runtime_models import Context, ExecutionContract, Intent
from .security import digest


def discover_context(path,tenant):
    state=read_snapshot(path)
    if len(state['meta'])!=1:raise ValueError('invalid resource metadata')
    return Context(tenant=tenant,resource=state['meta'][0][1],state_version=state['meta'][0][0],
                   snapshot_hash=digest(state),baseline_reference='sha256:'+digest(tuple(sorted(state['source']))))


def compile_kernel(intent,context,policy):
    intent=Intent.model_validate_json(intent.model_dump_json())
    context=Context.model_validate_json(context.model_dump_json())
    if intent.tenant!=context.tenant or intent.tenant!=policy.tenant or intent.owner!=policy.approver:
        raise PermissionError('intent ownership/context mismatch')
    data=reference_contract(policy).model_dump(mode='json')
    data.update(id=intent.id,tenant=intent.tenant,owner=intent.owner,approver=policy.approver,
                objective=intent.objective,resource=context.resource,baseline_reference=context.baseline_reference,
                intent_alignment_reference='intent/'+intent.id)
    return Contract.model_validate(data)


def compile_execution(kernel,kernel_approval,executor,deadline,**limits):
    return ExecutionContract(kernel=kernel,kernel_approval=kernel_approval,allowed_executors=(executor,),deadline=deadline,**limits)
