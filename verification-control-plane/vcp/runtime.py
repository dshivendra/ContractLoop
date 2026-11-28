"""Durable controlled loop for the local synthetic SQLite adapter.

Effects, receipts, counters and action audit events commit in one SQLite transaction.
There is no claim of exactly-once effects outside this database/adapter boundary.
"""
from contextlib import contextmanager
import hmac
import json
import time
import uuid
from pathlib import Path

from .engine import VerificationEngine
from .logic import Truth, conjunction, evaluate
from .models import Claim, Run, Verdict
from .reconciliation import collect, observation_facts, read_snapshot
from .runtime_models import (Action, Attestation, Context, ExecutionApproval, ExecutionContract,
                             LoopResult, Principal, Receipt, RevisionProposal, Task)
from .security import approved, canonical, digest, sign
from .storage import ContractRepository, Ledger


TRANSITIONS={
 'draft':{'validation','cancelled','timed_out'},'validation':{'approval_pending','rejected','cancelled','timed_out'},
 'approval_pending':{'authorized','rejected','cancelled','timed_out'},'authorized':{'pre_verification','cancelled','timed_out'},
 'pre_verification':{'executing','blocked','suspended','timed_out','cancelled'},
 'executing':{'observing','recovering','blocked','suspended','timed_out','cancelled'},
 'observing':{'post_verification','collecting_evidence','suspended','timed_out','cancelled'},
 'post_verification':{'completed','recovering','collecting_evidence','blocked','timed_out','cancelled'},
 'collecting_evidence':{'observing','escalated','timed_out','cancelled'},
 'recovering':{'executing','escalated','blocked','timed_out','cancelled'},
 'suspended':{'pre_verification','observing','escalated','cancelled','timed_out'},
 'completed':set(),'rejected':set(),'blocked':set(),'escalated':set(),'timed_out':set(),'cancelled':set()}


def authorize(principal,tenant,roles):
    if principal.tenant!=tenant or principal.role not in roles:raise PermissionError('tenant/role denied')


def approve_execution(contract,policy,principal,now):
    contract=ExecutionContract.model_validate_json(contract.model_dump_json())
    authorize(principal,contract.kernel.tenant,{'owner'})
    if principal.actor!=policy.approver or not approved(contract.kernel,contract.kernel_approval,policy,now):
        raise PermissionError('owner or kernel approval invalid')
    body=dict(contract_hash=digest(contract),actor=principal.actor,approved_at=now)
    return ExecutionApproval(**body,signature=sign(body,policy.approval_key))


def execution_approved(contract,approval,policy,now):
    body=approval.model_dump(exclude={'signature'})
    return (approval.actor==policy.approver and approval.approved_at<=now
            and approval.contract_hash==digest(contract)
            and approved(contract.kernel,contract.kernel_approval,policy,now)
            and hmac.compare_digest(approval.signature,sign(body,policy.approval_key)))


def snapshot(db):
    return {t:tuple(tuple(r) for r in db.execute('SELECT * FROM '+t+' ORDER BY rowid'))
            for t in ('meta','manifest','source','bank','destination')}


class LoopStore:
    def __init__(self,path,tenant):
        self.path=Path(path).resolve();self.tenant=tenant
        ledger=Ledger(self.path)
        try:
            db=ledger.db
            db.executescript('''
            CREATE TABLE IF NOT EXISTS loop_compositions (hash TEXT PRIMARY KEY, payload TEXT NOT NULL, approval TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS loop_config (tenant TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS loop_contracts (hash TEXT PRIMARY KEY, payload TEXT NOT NULL, approval TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS loop_tasks (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS loop_receipts (task_id TEXT, key TEXT, action_hash TEXT, payload TEXT, PRIMARY KEY(task_id,key));
            CREATE TABLE IF NOT EXISTS loop_attestations (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS loop_revocations (id TEXT PRIMARY KEY, reason TEXT NOT NULL);
            ''')
            for table in ('loop_compositions','loop_contracts','loop_receipts','loop_attestations','loop_revocations'):
                for operation in ('UPDATE','DELETE'):
                    db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'immutable loop record'); END")
            db.execute('BEGIN IMMEDIATE')
            rows=db.execute('SELECT tenant FROM loop_config').fetchall()
            if rows and rows!=[(tenant,)]:raise PermissionError('database belongs to a different tenant')
            if not rows:db.execute('INSERT INTO loop_config VALUES (?)',(tenant,))
            if 'revision' not in [r[1] for r in db.execute('PRAGMA table_info(meta)')]:
                db.execute('ALTER TABLE meta ADD COLUMN revision INTEGER NOT NULL DEFAULT 1')
            db.execute('COMMIT')
        except BaseException:
            if ledger.db.in_transaction:ledger.db.execute('ROLLBACK')
            raise
        finally:ledger.close()

    @contextmanager
    def transaction(self):
        ledger=Ledger(self.path)
        try:
            ledger.db.execute('BEGIN IMMEDIATE')
            rows=ledger.db.execute('SELECT tenant FROM loop_config').fetchall()
            if rows!=[(self.tenant,)]:raise PermissionError('tenant database changed')
            ledger.check()
            yield ledger
            ledger.db.execute('COMMIT')
        except BaseException:
            if ledger.db.in_transaction:ledger.db.execute('ROLLBACK')
            raise
        finally:ledger.close()

    def task(self,db,task_id):
        row=db.execute('SELECT payload FROM loop_tasks WHERE id=?',(task_id,)).fetchone()
        if not row:raise KeyError('task not found')
        return Task.model_validate_json(row[0])

    def contract(self,db,task):
        row=db.execute('SELECT payload,approval FROM loop_contracts WHERE hash=?',(task.contract_hash,)).fetchone()
        if not row:raise KeyError('approved execution contract not found')
        return ExecutionContract.model_validate_json(row[0]),ExecutionApproval.model_validate_json(row[1])

    def save_task(self,db,task):
        db.execute('UPDATE loop_tasks SET payload=? WHERE id=?',(task.model_dump_json(),task.id))

    def event(self,ledger,task,kind,actor,now,data):
        ledger.append_in_transaction('loop-event',uuid.uuid4().hex,dict(tenant=self.tenant,task_id=task.id,
            execution_id=task.execution_id,contract_hash=task.contract_hash,kind=kind,actor=actor,at=now,data=data,state=task.model_dump(mode='json')))


class SQLiteReconciliationAdapter:
    def apply(self,db):
        source=db.execute('SELECT * FROM source ORDER BY id').fetchall()
        bank={r[0]:r for r in db.execute('SELECT * FROM bank')}
        db.execute('DELETE FROM destination')
        for identity,amount,currency,account in source:
            matched=identity in bank and tuple(bank[identity][1:3])==(amount,currency)
            db.execute('INSERT INTO destination VALUES (?,?,?,?,?)',
                       (identity,amount,currency,account,'matched' if matched else 'unmatched'))
        db.execute("UPDATE meta SET state_version='state/' || (revision+1), revision=revision+1")


class ActionGateway:
    def __init__(self,store,policy,clock=None,adapter=None):
        self.store=store;self.policy=policy;self.clock=clock or (lambda:int(time.time()))
        self.adapter=adapter or SQLiteReconciliationAdapter()

    def execute(self,action,principal):
        action=Action.model_validate_json(action.model_dump_json())
        authorize(principal,self.store.tenant,{'executor'})
        now=self.clock()
        with self.store.transaction() as ledger:
            db=ledger.db;task=self.store.task(db,action.task_id);contract,approval=self.store.contract(db,task)
            if not execution_approved(contract,approval,self.policy,now):raise PermissionError('execution approval invalid')
            if ((action.tenant,action.execution_id,action.contract_hash,action.resource,action.executor)
                    !=(task.tenant,task.execution_id,task.contract_hash,contract.kernel.resource,principal.actor)
                    or principal.actor not in contract.allowed_executors or action.kind not in contract.allowed_actions):
                raise PermissionError('action outside approved scope')
            old=db.execute('SELECT action_hash,payload FROM loop_receipts WHERE task_id=? AND key=?',
                           (task.id,action.idempotency_key)).fetchone()
            if old:
                if old[0]!=digest(action):raise ValueError('idempotency key reused with different request')
                return Receipt.model_validate_json(old[1])
            if task.lifecycle not in ('executing','recovering'):raise ValueError('task is not executing')
            if now>contract.deadline or now-task.started_at>contract.max_duration_seconds:raise TimeoutError('execution deadline')
            if task.actions>=contract.max_actions or task.attempts>=contract.max_attempts or task.budget_units>=contract.max_budget_units:
                raise RuntimeError('execution budget exhausted')
            before=snapshot(db)
            if before['meta'][0][1]!=action.resource:raise PermissionError('resource identity changed')
            if before['meta'][0][0]!=action.expected_state_version or digest(before)!=action.expected_snapshot_hash:
                raise ValueError('concurrent state change detected')
            facts=observation_facts(before,contract.kernel.baseline_reference)
            if conjunction(evaluate(x,facts) for x in contract.preconditions)!=Truth.TRUE:
                raise PermissionError('preconditions not established')
            task=task.model_copy(update=dict(actions=task.actions+1,attempts=task.attempts+1,budget_units=task.budget_units+1,last_executor=principal.actor))
            db.execute('SAVEPOINT effect')
            status,error='applied',''
            try:
                pre_truth=conjunction(evaluate(x,facts) for x in contract.invariants)
                if pre_truth==Truth.UNKNOWN:raise RuntimeError('runtime invariant unobservable before action')
                if pre_truth==Truth.FALSE:raise ArithmeticError('runtime invariant violated before action')
                self.adapter.apply(db)
                after=snapshot(db)
                if any(after[t]!=before[t] for t in ('source','bank','manifest')) or after['meta'][0][1]!=action.resource:
                    raise ArithmeticError('prohibited input/resource side effect')
                post=observation_facts(after,contract.kernel.baseline_reference)
                post_truth=conjunction(evaluate(x,post) for x in contract.invariants)
                if post_truth==Truth.UNKNOWN:raise RuntimeError('runtime invariant unobservable after action')
                if post_truth==Truth.FALSE:raise ArithmeticError('runtime invariant violated after action')
            except ArithmeticError as exc:
                db.execute('ROLLBACK TO effect');status,error='violation',str(exc)
                task=task.model_copy(update={'historical_violation':True})
            except Exception as exc:
                db.execute('ROLLBACK TO effect');status,error='failed',type(exc).__name__
            finally:db.execute('RELEASE effect')
            after=snapshot(db)
            receipt=Receipt(action_hash=digest(action),idempotency_key=action.idempotency_key,status=status,
                            before_hash=digest(before),after_hash=digest(after),state_version=after['meta'][0][0],error=error)
            db.execute('INSERT INTO loop_receipts VALUES (?,?,?,?)',(task.id,action.idempotency_key,digest(action),receipt.model_dump_json()))
            self.store.save_task(db,task);self.store.event(ledger,task,'action',principal.actor,now,dict(action=action.model_dump(mode='json'),receipt=receipt.model_dump(mode='json')))
        return self._acknowledge(receipt)

    def _acknowledge(self,receipt):return receipt


class LoopController:
    def __init__(self,store,policy,clock=None,gateway=None,attestation_key=None):
        self.store=store;self.policy=policy;self.clock=clock or (lambda:int(time.time()))
        self.gateway=gateway or ActionGateway(store,policy,self.clock)
        self.attestation_key=attestation_key or policy.approval_key
        self.controller=Principal(tenant=store.tenant,actor='loop-controller',role='controller')
        self.verifier=Principal(tenant=store.tenant,actor='independent-verifier',role='verifier')

    def create(self,task_id,execution_id,contract,approval,principal):
        authorize(principal,self.store.tenant,{'owner'})
        contract=ExecutionContract.model_validate_json(contract.model_dump_json())
        approval=ExecutionApproval.model_validate_json(approval.model_dump_json())
        now=self.clock()
        if contract.kernel.tenant!=self.store.tenant or principal.actor!=self.policy.approver or not execution_approved(contract,approval,self.policy,now):
            raise PermissionError('valid owner approval required')
        collectors={self.controller.actor,self.verifier.actor,self.policy.approver}|{name for c in self.policy.collectors for name in (c.collector,c.source)}
        if collectors.intersection(contract.allowed_executors):raise PermissionError('executor and collector authority must differ')
        if now>contract.deadline:raise ValueError('deadline already elapsed')
        task=Task(tenant=self.store.tenant,id=task_id,execution_id=execution_id,contract_hash=digest(contract),lifecycle='draft',started_at=now)
        with self.store.transaction() as ledger:
            db=ledger.db
            existing=db.execute('SELECT payload,approval FROM loop_contracts WHERE hash=?',(task.contract_hash,)).fetchone()
            record=(contract.model_dump_json(),approval.model_dump_json())
            if existing and existing!=record:raise ValueError('immutable execution contract collision')
            if not existing:db.execute('INSERT INTO loop_contracts VALUES (?,?,?)',(task.contract_hash,*record))
            old=db.execute('SELECT payload FROM loop_tasks WHERE id=?',(task.id,)).fetchone()
            if old:
                previous=Task.model_validate_json(old[0])
                if (previous.execution_id,previous.contract_hash)!=(execution_id,task.contract_hash):raise ValueError('task identity collision')
                return previous
            from .composition import load
            load(self,ledger,task,contract)
            db.execute('INSERT INTO loop_tasks VALUES (?,?)',(task.id,task.model_dump_json()))
            self.store.event(ledger,task,'created',principal.actor,now,{})
        return task

    def register_composition(self,plan,approval,principal):
        from .composition import register
        return register(self,plan,approval,principal)

    def _dependency_plan(self,task_id):
        from .composition import load
        with self.store.transaction() as ledger:
            task=self.store.task(ledger.db,task_id);contract,_=self.store.contract(ledger.db,task)
            return load(self,ledger,task,contract),contract

    def _prepare_dependencies(self,task_id,principal):
        from .composition import applicability
        plan,contract=self._dependency_plan(task_id)
        if not plan:return None
        for dep,applies in applicability(plan,contract,read_snapshot(self.store.path)):
            if applies==Truth.UNKNOWN:return 'UNKNOWN'
            if applies==Truth.FALSE:continue
            child=self.get(dep.task_id,self.controller)
            if child.contract_hash!=dep.contract_hash:raise PermissionError('child contract changed')
            result=self.run(child.id,principal)
            if result.outcome!='SUCCESS':return result.outcome
        return None

    def _composition_outcome(self,task_id):
        from .composition import applicability,global_truth
        plan,contract=self._dependency_plan(task_id)
        if not plan:return 'SUCCESS'
        state=read_snapshot(self.store.path)
        truth=global_truth(plan,contract,state)
        if truth!=Truth.TRUE:return 'FAILURE' if truth==Truth.FALSE else 'UNKNOWN'
        for dep,applies in applicability(plan,contract,state):
            if applies==Truth.UNKNOWN:return 'UNKNOWN'
            if applies==Truth.FALSE:continue
            task,child_contract,_=self._contract(dep.task_id)
            if task.contract_hash!=dep.contract_hash:raise PermissionError('child contract changed')
            if task.lifecycle!='completed' or task.verdict!='SUCCESS' or task.historical_violation:return task.verdict
            # The parent's action may change this shared resource. Reobserve
            # children under their own explicit evidence collection allowance.
            try:
                with self.store.transaction() as ledger:
                    self._supported_bundle(ledger,task,child_contract,snapshot(ledger.db),self.clock())
            except PermissionError:
                try:result=self.verify(task.id,self.verifier)
                except (RuntimeError,PermissionError):return 'UNKNOWN'
                if result.outcome!='SUCCESS':return result.outcome
        return 'SUCCESS'

    def _attested_dependencies(self,ledger,task,contract,state,now):
        from .composition import applicability,global_truth,load
        plan=load(self,ledger,task,contract)
        if not plan:return ()
        if global_truth(plan,contract,state)!=Truth.TRUE:raise PermissionError('global predicate not established')
        states=[]
        for dep,applies in applicability(plan,contract,state):
            if applies==Truth.UNKNOWN:raise PermissionError('dependency applicability unknown')
            if applies==Truth.FALSE:continue
            child=self.store.task(ledger.db,dep.task_id);child_contract,_=self.store.contract(ledger.db,child)
            if child.contract_hash!=dep.contract_hash or child.lifecycle!='completed' or child.verdict!='SUCCESS' or child.historical_violation:
                raise PermissionError('dependency not independently successful')
            bundle=self._supported_bundle(ledger,child,child_contract,state,now)
            valid_until=min(child_contract.deadline,*(e['observed_at']+next(b.max_age_seconds for b in child_contract.kernel.bindings if b.fact==e['fact']) for e in bundle['evidence']))
            # Nested dependencies are pinned in their approved plans as well.
            states.extend(self._attested_dependencies(ledger,child,child_contract,state,now))
            states.append(dict(valid_until=valid_until,task_id=child.id,contract_hash=child.contract_hash,snapshot_hash=digest(state),state_version=state['meta'][0][0]))
        return tuple({x['task_id']:x for x in states}.values())

    def get(self,task_id,principal):
        authorize(principal,self.store.tenant,{'owner','controller','reader','verifier','executor'})
        with self.store.transaction() as ledger:return self.store.task(ledger.db,task_id)

    def transition(self,task_id,target,principal):
        authorize(principal,self.store.tenant,{'controller'})
        with self.store.transaction() as ledger:
            task=self.store.task(ledger.db,task_id)
            if target not in TRANSITIONS[task.lifecycle]:raise ValueError('undefined lifecycle transition')
            updates={'lifecycle':target}
            if target in ('timed_out','cancelled','escalated','rejected'):updates['verdict']='UNKNOWN'
            if target=='blocked':updates['verdict']='FAILURE' if task.historical_violation else 'UNKNOWN'
            task=task.model_copy(update=updates);self.store.save_task(ledger.db,task)
            self.store.event(ledger,task,'transition',principal.actor,self.clock(),{'to':target})
            return task

    def cancel(self,task_id,principal):
        authorize(principal,self.store.tenant,{'owner'})
        return self.transition(task_id,'cancelled',self.controller)

    def _contract(self,task_id):
        with self.store.transaction() as ledger:
            task=self.store.task(ledger.db,task_id);return task,*self.store.contract(ledger.db,task)

    def _bump(self,task_id,field,maximum):
        with self.store.transaction() as ledger:
            task=self.store.task(ledger.db,task_id)
            if getattr(task,field)>=maximum:return False
            task=task.model_copy(update={field:getattr(task,field)+1});self.store.save_task(ledger.db,task)
            self.store.event(ledger,task,'budget',self.controller.actor,self.clock(),{field:getattr(task,field)})
            return True

    def _recover(self,task_id,contract):
        with self.store.transaction() as ledger:
            task=self.store.task(ledger.db,task_id)
            if task.historical_violation or task.recoveries>=contract.max_recoveries:return False
            if 'recovering' not in TRANSITIONS[task.lifecycle]:raise ValueError('recovery transition denied')
            task=task.model_copy(update={'recoveries':task.recoveries+1,'lifecycle':'recovering'})
            self.store.save_task(ledger.db,task)
            self.store.event(ledger,task,'recovery-authorized',self.controller.actor,self.clock(),{'attempt':task.recoveries})
            return True

    def verify(self,task_id,principal):
        authorize(principal,self.store.tenant,{'verifier'})
        task,contract,approval=self._contract(task_id)
        if task.lifecycle not in ('post_verification','completed'):raise PermissionError('task is not in a verifiable lifecycle')
        if not execution_approved(contract,approval,self.policy,self.clock()):raise PermissionError('execution approval invalid')
        if not self._bump(task_id,'collections',contract.max_collections):raise RuntimeError('evidence collection budget exhausted')
        state=read_snapshot(self.store.path)
        run=Run(tenant=task.tenant,task_id=task.id,execution_id=task.execution_id,executor=task.last_executor or contract.allowed_executors[0],
                contract_hash=digest(contract.kernel),resource=contract.kernel.resource,state_version=state['meta'][0][0])
        evidence=collect(self.store.path,contract.kernel,run,self.policy,observed_at=self.clock())
        ledger=Ledger(self.store.path)
        try:verdict=VerificationEngine(self.policy,ledger).verify(contract.kernel,contract.kernel_approval,run,evidence,
                         Claim(execution_status='completed' if task.actions else 'unknown',message='Independent controlled-loop observation'),self.clock())
        finally:ledger.close()
        outcome='FAILURE' if task.historical_violation else verdict.verdict
        if outcome=='SUCCESS':outcome=self._composition_outcome(task_id)
        with self.store.transaction() as ledger:
            current=self.store.task(ledger.db,task_id)
            current=current.model_copy(update={'verdict':outcome});self.store.save_task(ledger.db,current)
            self.store.event(ledger,current,'verified',principal.actor,self.clock(),{'verdict':outcome,'kernel_verdict_id':verdict.id})
        return LoopResult(task=current,kernel_verdict=verdict,outcome=outcome,reason='historical invariant violation' if task.historical_violation else 'independent outcome verification')

    def run(self,task_id,principal):
        authorize(principal,self.store.tenant,{'owner','controller'})
        task,contract,_=self._contract(task_id)
        if task.lifecycle in ('completed','blocked','rejected','escalated','timed_out','cancelled'):
            return LoopResult(task=task,outcome=task.verdict,reason='durable terminal task')
        dependency_outcome=self._prepare_dependencies(task_id,principal)
        if dependency_outcome:
            with self.store.transaction() as ledger:
                task=self.store.task(ledger.db,task_id)
                task=task.model_copy(update={'lifecycle':'blocked','verdict':dependency_outcome});self.store.save_task(ledger.db,task)
                self.store.event(ledger,task,'dependency-blocked',self.controller.actor,self.clock(),{'verdict':dependency_outcome})
            return LoopResult(task=task,outcome=dependency_outcome,reason='required dependency did not establish success')
        while True:
            task=self.get(task_id,self.controller);now=self.clock()
            if now>contract.deadline or now-task.started_at>contract.max_duration_seconds:
                if 'timed_out' in TRANSITIONS[task.lifecycle]:task=self.transition(task_id,'timed_out',self.controller)
                return LoopResult(task=task,outcome='UNKNOWN',reason='deadline exceeded')
            next_state={'draft':'validation','validation':'approval_pending','approval_pending':'authorized',
                        'authorized':'pre_verification','pre_verification':'executing','recovering':'executing',
                        'observing':'post_verification','collecting_evidence':'observing'}
            if task.lifecycle in next_state:
                self.transition(task_id,next_state[task.lifecycle],self.controller);continue
            if task.lifecycle=='suspended':return LoopResult(task=task,outcome='UNKNOWN',reason='suspended')
            if task.lifecycle=='executing':
                state=read_snapshot(self.store.path)
                # A deterministic attempt key survives a crash after commit/before acknowledgement.
                with self.store.transaction() as ledger:
                    rows=ledger.db.execute('SELECT payload FROM loop_receipts WHERE task_id=? ORDER BY rowid DESC LIMIT 1',(task.id,)).fetchall()
                receipt=Receipt.model_validate_json(rows[0][0]) if rows and task.attempts>task.recoveries else None
                action=Action(tenant=task.tenant,task_id=task.id,execution_id=task.execution_id,contract_hash=task.contract_hash,
                              resource=contract.kernel.resource,executor=contract.allowed_executors[0],expected_state_version=state['meta'][0][0],
                              expected_snapshot_hash=digest(state),idempotency_key='attempt/'+str(task.attempts+1))
                try:
                    if receipt is None:receipt=self.gateway.execute(action,Principal(tenant=task.tenant,actor=action.executor,role='executor'))
                except TimeoutError:
                    task=self.transition(task_id,'timed_out',self.controller)
                    return LoopResult(task=task,outcome='UNKNOWN',reason='deadline exceeded')
                except (PermissionError,ValueError,RuntimeError) as exc:
                    task=self.transition(task_id,'blocked',self.controller)
                    return LoopResult(task=task,outcome='UNKNOWN',reason=str(exc))
                if receipt.status=='violation':
                    task=self.transition(task_id,'blocked',self.controller)
                    return LoopResult(task=task,outcome='FAILURE',reason=receipt.error)
                if receipt.status=='failed':
                    if self._recover(task_id,contract):continue
                    task=self.transition(task_id,'blocked',self.controller)
                    return LoopResult(task=task,outcome='UNKNOWN',reason='bounded recovery exhausted')
                self.transition(task_id,'observing',self.controller);continue
            if task.lifecycle=='post_verification':
                try:result=self.verify(task_id,self.verifier)
                except Exception as exc:
                    task=self.get(task_id,self.controller)
                    with self.store.transaction() as ledger:
                        self.store.event(ledger,task,'verification-fault',self.verifier.actor,self.clock(),{'type':type(exc).__name__})
                    result=LoopResult(task=task,outcome='UNKNOWN',reason='independent verification fault')
                if self.clock()>contract.deadline or self.clock()-result.task.started_at>contract.max_duration_seconds:
                    task=self.transition(task_id,'timed_out',self.controller)
                    return LoopResult(task=task,outcome='UNKNOWN',reason='verification exceeded execution deadline')
                if result.outcome=='FAILURE' and not result.task.historical_violation and self._recover(task_id,contract):continue
                if result.outcome=='UNKNOWN' and result.task.collections<contract.max_collections:
                    self.transition(task_id,'collecting_evidence',self.controller);continue
                terminal='escalated' if result.outcome=='UNKNOWN' else 'completed'
                if terminal=='escalated':self.transition(task_id,'collecting_evidence',self.controller)
                task=self.transition(task_id,terminal,self.controller)
                return result.model_copy(update={'task':task})
            raise ValueError('unhandled lifecycle')

    def _supported_bundle(self,ledger,task,contract,state,now):
        bundles=[r['payload'] for r in ledger.records() if r['kind']=='verification'
                 and r['payload']['run']['task_id']==task.id
                 and r['payload']['run']['execution_id']==task.execution_id]
        if not bundles:raise PermissionError('supporting verifier record missing')
        bundle=bundles[-1]
        verdict=VerificationEngine(self.policy,ledger).replay_bundle(bundle)
        if (verdict.verdict!='SUCCESS' or bundle['run']['contract_hash']!=digest(contract.kernel)
                or not bundle['evidence'] or any(e['artifact_hash']!=digest(state) for e in bundle['evidence'])):
            raise PermissionError('state drifted since verification')
        ages={b.fact:b.max_age_seconds for b in contract.kernel.bindings}
        if any(not 0<=now-e['observed_at']<=ages[e['fact']] for e in bundle['evidence']):
            raise PermissionError('supporting evidence expired')
        if now>contract.deadline:raise PermissionError('execution authorization expired')
        return bundle

    def attest(self,task_id,principal):
        authorize(principal,self.store.tenant,{'verifier'})
        with self.store.transaction() as ledger:
            task=self.store.task(ledger.db,task_id);contract,approval=self.store.contract(ledger.db,task)
            now=self.clock()
            if not execution_approved(contract,approval,self.policy,now):raise PermissionError('invalid approval')
            if task.lifecycle!='completed' or task.verdict!='SUCCESS' or task.historical_violation:
                raise PermissionError('only independently verified success can be attested')
            state=snapshot(ledger.db);bundle=self._supported_bundle(ledger,task,contract,state,now)
            dependencies=self._attested_dependencies(ledger,task,contract,state,now)
            observed_at=min(e['observed_at'] for e in bundle['evidence'])
            evidence_expiry=min(e['observed_at']+next(b.max_age_seconds for b in contract.kernel.bindings if b.fact==e['fact'])
                                for e in bundle['evidence'])
            body=dict(tenant=task.tenant,task_id=task.id,execution_id=task.execution_id,contract_hash=task.contract_hash,
                      kernel_contract_hash=digest(contract.kernel),verdict_id=bundle['verdict']['id'],snapshot_hash=digest(state),
                      state_version=state['meta'][0][0],observed_at=observed_at,dependencies=dependencies,
                      issued_at=now,expires_at=min(now+contract.attestation_ttl_seconds,contract.deadline,evidence_expiry,*(d['valid_until'] for d in dependencies)),signer=principal.actor)
            body['id']=digest(body)
            attestation=Attestation(**body,signature=sign(body,self.attestation_key))
            old=ledger.db.execute('SELECT payload FROM loop_attestations WHERE id=?',(attestation.id,)).fetchone()
            if not old:ledger.db.execute('INSERT INTO loop_attestations VALUES (?,?)',(attestation.id,attestation.model_dump_json()))
            self.store.event(ledger,task,'attestation-issued',principal.actor,now,attestation.model_dump(mode='json'))
        return attestation

    def attestation_status(self,attestation_id,principal):
        authorize(principal,self.store.tenant,{'verifier','owner','reader'})
        with self.store.transaction() as ledger:
            row=ledger.db.execute('SELECT payload FROM loop_attestations WHERE id=?',(attestation_id,)).fetchone()
            if not row:raise KeyError('attestation not found')
            att=Attestation.model_validate_json(row[0]);body=att.model_dump(exclude={'signature'})
            if att.tenant!=principal.tenant or not hmac.compare_digest(att.signature,sign(body,self.attestation_key)):
                raise PermissionError('invalid attestation')
            if ledger.db.execute('SELECT 1 FROM loop_revocations WHERE id=?',(att.id,)).fetchone():return 'REVOKED'
            if self.clock()>att.expires_at:return 'EXPIRED'
            dependency_invalid=any(self.store.task(ledger.db,d.task_id).verdict!='SUCCESS' for d in att.dependencies)
            if dependency_invalid or digest(snapshot(ledger.db))!=att.snapshot_hash:
                ledger.db.execute('INSERT INTO loop_revocations VALUES (?,?)',(att.id,'state drift'))
                task=self.store.task(ledger.db,att.task_id)
                self.store.event(ledger,task,'attestation-revoked',self.verifier.actor,self.clock(),{'id':att.id,'reason':'state drift'})
                return 'REVOKED'
            return 'VALID'

    def monitor(self,principal):
        authorize(principal,self.store.tenant,{'verifier'})
        with self.store.transaction() as ledger:
            ids=[r[0] for r in ledger.db.execute('SELECT id FROM loop_attestations ORDER BY id')]
        return {identity:self.attestation_status(identity,principal) for identity in ids}

    def revoke(self,attestation_id,reason,principal):
        authorize(principal,self.store.tenant,{'owner','verifier'})
        with self.store.transaction() as ledger:
            row=ledger.db.execute('SELECT payload FROM loop_attestations WHERE id=?',(attestation_id,)).fetchone()
            if not row:raise KeyError('attestation not found')
            att=Attestation.model_validate_json(row[0]);task=self.store.task(ledger.db,att.task_id)
            if not ledger.db.execute('SELECT 1 FROM loop_revocations WHERE id=?',(att.id,)).fetchone():
                ledger.db.execute('INSERT INTO loop_revocations VALUES (?,?)',(att.id,reason))
                self.store.event(ledger,task,'attestation-revoked',principal.actor,self.clock(),{'id':att.id,'reason':reason})

    def propose_revision(self,task_id,rationale,evidence_ids,principal):
        authorize(principal,self.store.tenant,{'owner','controller','verifier'})
        task,_,_=self._contract(task_id)
        proposal=RevisionProposal(id=uuid.uuid4().hex,tenant=task.tenant,base_contract_hash=task.contract_hash,
                                  rationale=rationale,evidence_ids=tuple(evidence_ids))
        with self.store.transaction() as ledger:
            self.store.event(ledger,task,'revision-proposed',principal.actor,self.clock(),proposal.model_dump(mode='json'))
        return proposal
