from dataclasses import replace
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from vcp.models import Compare
from vcp.planning import compile_execution, compile_kernel, discover_context
from vcp.reconciliation import NOW, create_fixture, read_snapshot, synthetic_policy
from vcp.runtime import (ActionGateway, LoopController, LoopStore, SQLiteReconciliationAdapter,
                         approve_execution)
from vcp.runtime_models import Action, Intent, Principal
from vcp.security import approve, digest
from vcp.storage import Ledger


class RuntimeFixture:
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'fixture.sqlite'
        create_fixture(self.path,'partial');self.now=NOW;self.clock=lambda:self.now
        self.policy=synthetic_policy()
        self.owner=Principal(tenant='demo',actor='fixture-owner',role='owner')
        self.executor=Principal(tenant='demo',actor='executor',role='executor')
        self.store=LoopStore(self.path,'demo')
        self.loop=LoopController(self.store,self.policy,self.clock)
        self.make_task()

    def tearDown(self):self.tmp.cleanup()

    def make_task(self,task_id='task',**limits):
        intent=Intent(id='reconcile-'+task_id,tenant='demo',owner=self.owner.actor,
                      objective='Reconcile this synthetic batch',recipe='synthetic-reconciliation')
        context=discover_context(self.path,'demo');kernel=compile_kernel(intent,context,self.policy)
        self.contract=compile_execution(kernel,approve(kernel,self.policy,self.now),'executor',limits.pop('deadline',self.now+120),**limits)
        self.approval=approve_execution(self.contract,self.policy,self.owner,self.now)
        return self.loop.create(task_id,'execution-'+task_id,self.contract,self.approval,self.owner)

    def executing(self,task_id='task'):
        for state in ('validation','approval_pending','authorized','pre_verification','executing'):
            self.loop.transition(task_id,state,self.loop.controller)

    def action(self,key='key',task_id='task'):
        task=self.loop.get(task_id,self.owner);s=read_snapshot(self.path)
        return Action(tenant='demo',task_id=task_id,execution_id=task.execution_id,contract_hash=task.contract_hash,
                      resource=self.contract.kernel.resource,executor='executor',expected_state_version=s['meta'][0][0],
                      expected_snapshot_hash=digest(s),idempotency_key=key)


class RuntimeTests(RuntimeFixture,unittest.TestCase):
    def test_end_to_end_runs_action_observes_verifies_and_attests(self):
        result=self.loop.run('task',self.owner)
        self.assertEqual(result.outcome,'SUCCESS');self.assertEqual(result.task.lifecycle,'completed')
        self.assertEqual(result.task.actions,1);self.assertEqual(result.task.collections,1)
        self.assertEqual(result.kernel_verdict.execution_status,'completed')
        att=self.loop.attest('task',self.loop.verifier)
        self.assertEqual(self.loop.attestation_status(att.id,self.owner),'VALID')
        self.assertEqual(att.contract_hash,digest(self.contract))
        ledger=Ledger(self.path)
        try:self.assertEqual(len(ledger.records()),len({x['identity'] for x in ledger.records()}));ledger.check()
        finally:ledger.close()

    def test_undefined_and_executor_transitions_are_rejected(self):
        with self.assertRaises(ValueError):self.loop.transition('task','completed',self.loop.controller)
        with self.assertRaises(PermissionError):self.loop.transition('task','validation',self.executor)

    def test_cross_tenant_and_wrong_actor_rejected(self):
        with self.assertRaises(PermissionError):self.loop.get('task',Principal(tenant='other',actor='fixture-owner',role='owner'))
        with self.assertRaises(PermissionError):LoopStore(self.path,'other')
        self.executing()
        with self.assertRaises(PermissionError):self.loop.gateway.execute(self.action(),self.executor.model_copy(update={'actor':'attacker'}))
        self.assertEqual(self.loop.get('task',self.owner).actions,0)

    def test_changed_contract_or_approval_cannot_create_task(self):
        altered=self.contract.model_copy(update={'max_actions':999})
        with self.assertRaises(PermissionError):self.loop.create('bad','bad',altered,self.approval,self.owner)

    def test_unapproved_or_mutated_task_identity_not_replaced(self):
        self.assertEqual(self.loop.create('task','execution-task',self.contract,self.approval,self.owner).id,'task')
        with self.assertRaises(ValueError):self.loop.create('task','changed',self.contract,self.approval,self.owner)

    def test_executor_cannot_issue_verdict_or_attestation(self):
        with self.assertRaises(PermissionError):self.loop.verify('task',self.executor)
        with self.assertRaises(PermissionError):self.loop.attest('task',self.executor)
        with self.assertRaises(PermissionError):self.loop.attest('task',self.loop.verifier)

    def test_cas_detects_external_change_even_without_version_increment(self):
        self.executing();action=self.action();before=read_snapshot(self.path)
        db=sqlite3.connect(self.path);db.execute("UPDATE destination SET account='CHANGED' WHERE id='T1'");db.commit();db.close()
        with self.assertRaisesRegex(ValueError,'concurrent'):self.loop.gateway.execute(action,self.executor)
        self.assertEqual(read_snapshot(self.path)['meta'],before['meta'])
        self.assertEqual(self.loop.get('task',self.owner).actions,0)

    def test_receipt_replay_is_idempotent_and_cannot_change_payload(self):
        self.executing();action=self.action();receipt=self.loop.gateway.execute(action,self.executor)
        again=ActionGateway(LoopStore(self.path,'demo'),self.policy,self.clock).execute(action,self.executor)
        self.assertEqual(receipt,again);self.assertEqual(self.loop.get('task',self.owner).actions,1)
        with self.assertRaisesRegex(ValueError,'idempotency'):
            self.loop.gateway.execute(action.model_copy(update={'expected_state_version':'other'}),self.executor)

    def test_crash_after_commit_resumes_without_duplicate_effect(self):
        self.executing();action=self.action()
        with patch.object(self.loop.gateway,'_acknowledge',side_effect=OSError('lost acknowledgement')):
            with self.assertRaises(OSError):self.loop.gateway.execute(action,self.executor)
        restarted=LoopController(LoopStore(self.path,'demo'),self.policy,self.clock)
        result=restarted.run('task',self.owner)
        self.assertEqual(result.outcome,'SUCCESS');self.assertEqual(result.task.actions,1)

    def test_effect_and_audit_commit_atomically(self):
        self.executing();action=self.action();before=digest(read_snapshot(self.path))
        with patch.object(LoopStore,'event',side_effect=sqlite3.OperationalError('audit disk full')):
            with self.assertRaises(sqlite3.OperationalError):self.loop.gateway.execute(action,self.executor)
        self.assertEqual(digest(read_snapshot(self.path)),before)
        self.assertEqual(self.loop.get('task',self.owner).actions,0)
        self.assertEqual(self.loop.gateway.execute(action,self.executor).status,'applied')

    def test_runtime_invariant_violation_rolls_back_and_is_sticky(self):
        class Bad(SQLiteReconciliationAdapter):
            def apply(self,db):
                super().apply(db);db.execute('DELETE FROM source')
        self.loop.gateway.adapter=Bad();before=digest(read_snapshot(self.path))
        result=self.loop.run('task',self.owner)
        self.assertEqual(result.outcome,'FAILURE');self.assertTrue(result.task.historical_violation)
        self.assertEqual(digest(read_snapshot(self.path)),before)
        self.loop.gateway.adapter=SQLiteReconciliationAdapter()
        self.assertEqual(self.loop.run('task',self.owner).outcome,'FAILURE')
        with self.assertRaises(PermissionError):self.loop.attest('task',self.loop.verifier)

    def test_transient_failure_recovers_with_approved_budget(self):
        class Transient(SQLiteReconciliationAdapter):
            calls=0
            def apply(self,db):
                self.calls+=1
                if self.calls==1:raise OSError('transient')
                super().apply(db)
        self.loop.gateway.adapter=Transient()
        result=self.loop.run('task',self.owner)
        self.assertEqual(result.outcome,'SUCCESS');self.assertEqual(result.task.actions,2)
        self.assertEqual(result.task.recoveries,1)

    def test_restart_after_failed_attempt_honors_recovery_limit(self):
        self.make_task('limited',max_recoveries=0)
        class Broken(SQLiteReconciliationAdapter):
            def apply(self,db):raise OSError('unavailable')
        self.loop.gateway.adapter=Broken();self.executing('limited')
        receipt=self.loop.gateway.execute(self.action(task_id='limited'),self.executor)
        self.assertEqual(receipt.status,'failed')
        result=LoopController(self.store,self.policy,self.clock).run('limited',self.owner)
        self.assertEqual(result.outcome,'UNKNOWN');self.assertEqual(result.task.actions,1)
        self.assertEqual(result.task.lifecycle,'blocked')

    def test_false_executor_success_cannot_override_independent_state(self):
        class Liar(SQLiteReconciliationAdapter):
            def apply(self,db):pass
        self.loop.gateway.adapter=Liar()
        result=self.loop.run('task',self.owner)
        self.assertEqual(result.outcome,'FAILURE');self.assertEqual(result.task.recoveries,1)

    def test_action_and_cost_budgets_bound_recovery(self):
        self.make_task('limited',max_actions=1,max_budget_units=1)
        class Broken(SQLiteReconciliationAdapter):
            def apply(self,db):raise OSError('unavailable')
        self.loop.gateway.adapter=Broken()
        result=self.loop.run('limited',self.owner)
        self.assertEqual(result.outcome,'UNKNOWN');self.assertEqual(result.task.actions,1)
        self.assertEqual(result.task.budget_units,1)

    def test_deadline_and_cancellation_are_durable(self):
        self.loop.cancel('task',self.owner)
        self.assertEqual(self.loop.run('task',self.owner).task.lifecycle,'cancelled')
        self.make_task('late');self.now+=121
        self.assertEqual(self.loop.run('late',self.owner).task.lifecycle,'timed_out')
        self.assertEqual(self.loop.get('late',self.owner).actions,0)

    def test_evidence_faults_are_bounded_and_remain_unknown(self):
        with patch('vcp.runtime.collect',side_effect=OSError('collector down')):
            result=self.loop.run('task',self.owner)
        self.assertEqual(result.outcome,'UNKNOWN');self.assertEqual(result.task.lifecycle,'escalated')
        self.assertEqual(result.task.collections,2)

    def test_attestation_expires_and_revokes_without_rewriting_verdict(self):
        self.loop.run('task',self.owner);att=self.loop.attest('task',self.loop.verifier)
        self.now=att.expires_at+1
        self.assertEqual(self.loop.attestation_status(att.id,self.owner),'EXPIRED')
        self.now=NOW
        db=sqlite3.connect(self.path);db.execute('DELETE FROM destination');db.commit();db.close()
        self.assertEqual(self.loop.attestation_status(att.id,self.owner),'REVOKED')
        self.assertEqual(self.loop.get('task',self.owner).verdict,'SUCCESS')

    def test_explicit_revocation_and_tenant_checks(self):
        self.loop.run('task',self.owner);att=self.loop.attest('task',self.loop.verifier)
        with self.assertRaises(PermissionError):self.loop.revoke(att.id,'invalid',self.executor)
        self.loop.revoke(att.id,'owner revoked',self.owner)
        self.assertEqual(self.loop.attestation_status(att.id,self.owner),'REVOKED')

    def test_learning_proposes_but_does_not_rewrite_contract(self):
        before=self.loop.get('task',self.owner).contract_hash
        proposal=self.loop.propose_revision('task','Tighten evidence policy',(),self.owner)
        self.assertEqual(proposal.status,'unapproved')
        self.assertEqual(self.loop.get('task',self.owner).contract_hash,before)


if __name__=='__main__':unittest.main()
