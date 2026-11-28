from typing import Annotated, Literal
from pydantic import Field, model_validator
from .models import Approval, Compare, Contract, Expression, Model, Name, Verdict

Positive=Annotated[int,Field(strict=True,ge=1,le=1000000)]
Nonnegative=Annotated[int,Field(strict=True,ge=0)]
Lifecycle=Literal['draft','validation','approval_pending','authorized','pre_verification',
                  'executing','observing','post_verification','collecting_evidence','recovering',
                  'suspended','escalated','blocked','rejected','timed_out','cancelled','completed']


class Principal(Model):
    tenant:Name
    actor:Name
    role:Literal['owner','controller','executor','collector','verifier','reader']


class Intent(Model):
    id:Name
    tenant:Name
    owner:Name
    objective:Name
    recipe:Literal['synthetic-reconciliation']


class Context(Model):
    tenant:Name
    resource:Name
    state_version:Name
    snapshot_hash:Name
    baseline_reference:Name


class ExecutionContract(Model):
    schema_version:Literal['execution/1']='execution/1'
    runtime_version:Literal['controlled-loop/0.2.0']='controlled-loop/0.2.0'
    kernel:Contract
    kernel_approval:Approval
    allowed_executors:Annotated[tuple[Name,...],Field(min_length=1)]
    allowed_actions:Annotated[tuple[Literal['reconcile'],...],Field(min_length=1)]=('reconcile',)
    preconditions:tuple[Expression,...]=(Compare(fact='source_complete',expected=True),Compare(fact='authorized',expected=True))
    invariants:tuple[Expression,...]=(Compare(fact='source_complete',expected=True),Compare(fact='authorized',expected=True))
    max_actions:Positive=3
    max_attempts:Positive=3
    max_recoveries:Annotated[int,Field(strict=True,ge=0,le=100)]=1
    max_collections:Positive=2
    max_budget_units:Positive=3
    max_duration_seconds:Positive=120
    deadline:Nonnegative
    attestation_ttl_seconds:Positive=60
    composition_hash:Name|None=None

    @model_validator(mode='after')
    def bounded_predicates(self):
        from .logic import leaves
        from .reconciliation import FACTS
        stack=[(x,1) for x in (*self.preconditions,*self.invariants)];count=0
        while stack:
            x,depth=stack.pop();count+=1
            if count>128 or depth>32:raise ValueError('runtime expression budget')
            if x.kind=='not':stack.append((x.item,depth+1))
            elif x.kind in ('all','any'):stack.extend((item,depth+1) for item in x.items)
        if any(a.fact not in FACTS for x in (*self.preconditions,*self.invariants) for a in leaves(x)):
            raise ValueError('unobservable runtime predicate')
        if not self.preconditions or not self.invariants:raise ValueError('explicit runtime guards required')
        return self


class ExecutionApproval(Model):
    contract_hash:Name
    actor:Name
    approved_at:Nonnegative
    signature:Name


class Task(Model):
    tenant:Name
    id:Name
    execution_id:Name
    contract_hash:Name
    lifecycle:Lifecycle
    started_at:Nonnegative
    actions:Nonnegative=0
    attempts:Nonnegative=0
    recoveries:Nonnegative=0
    collections:Nonnegative=0
    budget_units:Nonnegative=0
    historical_violation:bool=False
    last_executor:Name|None=None
    verdict:Literal['SUCCESS','FAILURE','UNKNOWN']='UNKNOWN'


class Action(Model):
    tenant:Name
    task_id:Name
    execution_id:Name
    contract_hash:Name
    kind:Literal['reconcile']='reconcile'
    resource:Name
    executor:Name
    expected_state_version:Name
    expected_snapshot_hash:Name
    idempotency_key:Name


class Receipt(Model):
    action_hash:Name
    idempotency_key:Name
    status:Literal['applied','failed','violation']
    before_hash:Name
    after_hash:Name
    state_version:Name
    error:str=''


class LoopResult(Model):
    task:Task
    kernel_verdict:Verdict|None=None
    outcome:Literal['SUCCESS','FAILURE','UNKNOWN']
    reason:str
    attestation_id:Name|None=None


class Attestation(Model):
    id:Name
    tenant:Name
    task_id:Name
    execution_id:Name
    contract_hash:Name
    kernel_contract_hash:Name
    verdict_id:Name
    snapshot_hash:Name
    state_version:Name
    observed_at:Nonnegative
    dependencies:tuple['DependencyState',...]=()
    issued_at:Nonnegative
    expires_at:Nonnegative
    signer:Name
    signature:Name


class Dependency(Model):
    task_id:Name
    contract_hash:Name
    when:Expression|None=None


class Composition(Model):
    tenant:Name
    parent_task_id:Name
    parent_kernel_hash:Name
    dependencies:Annotated[tuple[Dependency,...],Field(min_length=1,max_length=32)]
    global_invariants:tuple[Expression,...]=()

    @model_validator(mode='after')
    def unique_children(self):
        names=[x.task_id for x in self.dependencies]
        if self.parent_task_id in names or len(names)!=len(set(names)):raise ValueError('cyclic or repeated dependency')
        from .logic import leaves
        from .reconciliation import FACTS
        expressions=(*self.global_invariants,*(x.when for x in self.dependencies if x.when is not None))
        stack=[(x,1) for x in expressions];count=0
        while stack:
            expr,depth=stack.pop();count+=1
            if depth>32 or count>128:raise ValueError('composition predicate budget')
            if expr.kind=='not':stack.append((expr.item,depth+1))
            elif expr.kind in ('all','any'):stack.extend((x,depth+1) for x in expr.items)
        if any(x.fact not in FACTS for expr in expressions for x in leaves(expr)):
            raise ValueError('unobservable composition predicate')
        return self


class DependencyState(Model):
    valid_until:Nonnegative
    task_id:Name
    contract_hash:Name
    snapshot_hash:Name
    state_version:Name


Attestation.model_rebuild()


class RevisionProposal(Model):
    id:Name
    tenant:Name
    base_contract_hash:Name
    rationale:Name
    evidence_ids:tuple[Name,...]
    status:Literal['unapproved']='unapproved'
