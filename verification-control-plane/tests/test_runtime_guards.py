from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
import unittest
from unittest.mock import patch
from vcp.audit import audit_loop
from vcp.models import Compare
from vcp.reconciliation import read_snapshot
from vcp.runtime import ActionGateway
from vcp.security import digest
from tests.test_runtime import RuntimeFixture


class RuntimeGuardTests(RuntimeFixture,unittest.TestCase):
    def test_concurrent_identical_actions_commit_once(self):
        self.executing();action=self.action()
        def execute(_):return ActionGateway(self.store,self.policy,self.clock).execute(action,self.executor)
        with ThreadPoolExecutor(max_workers=4) as pool:receipts=list(pool.map(execute,range(4)))
        self.assertTrue(all(r==receipts[0] for r in receipts))
        self.assertEqual(self.loop.get('task',self.owner).actions,1)
        self.assertEqual(audit_loop(self.path,self.policy)['committed_actions'],1)

    def test_unknown_invariant_is_unknown_and_rolled_back(self):
        self.make_task('uncertain',invariants=(Compare(fact='authorized',expected='wrong-type'),))
        before=digest(read_snapshot(self.path));result=self.loop.run('uncertain',self.owner)
        self.assertEqual(result.outcome,'UNKNOWN');self.assertFalse(result.task.historical_violation)
        self.assertEqual(digest(read_snapshot(self.path)),before)

    def test_duration_expiry_does_not_replay_as_success(self):
        self.make_task('short',max_duration_seconds=1)
        self.now+=2;result=self.loop.run('short',self.owner)
        self.assertEqual(result.outcome,'UNKNOWN');self.assertEqual(result.task.lifecycle,'timed_out')
        self.assertEqual(self.loop.run('short',self.owner).outcome,'UNKNOWN')

    def test_verification_completing_after_deadline_cannot_complete_successfully(self):
        real=self.loop.verify
        def slow(*args):
            result=real(*args);self.now+=121;return result
        with patch.object(self.loop,'verify',side_effect=slow):result=self.loop.run('task',self.owner)
        self.assertEqual(result.task.lifecycle,'timed_out');self.assertEqual(result.task.verdict,'UNKNOWN')
        with self.assertRaises(PermissionError):self.loop.attest('task',self.loop.verifier)

    def test_stale_evidence_cannot_be_renewed_without_reobservation(self):
        self.make_task('freshness',deadline=self.now+10000)
        self.loop.run('freshness',self.owner)
        self.now+=max(b.max_age_seconds for b in self.contract.kernel.bindings)+1
        with self.assertRaises(PermissionError):self.loop.attest('freshness',self.loop.verifier)

    def test_drift_before_attestation_cannot_be_certified(self):
        self.loop.run('task',self.owner)
        db=sqlite3.connect(self.path);db.execute('DELETE FROM destination');db.commit();db.close()
        with self.assertRaises(PermissionError):self.loop.attest('task',self.loop.verifier)
        self.assertEqual(self.loop.get('task',self.owner).verdict,'SUCCESS')

    def test_monitor_is_repeatable_and_preserves_historical_verdict(self):
        self.loop.run('task',self.owner);att=self.loop.attest('task',self.loop.verifier)
        self.assertEqual(self.loop.monitor(self.loop.verifier)[att.id],'VALID')
        self.loop.revoke(att.id,'review requested',self.owner)
        self.assertEqual(self.loop.monitor(self.loop.verifier)[att.id],'REVOKED')
        self.assertEqual(self.loop.monitor(self.loop.verifier)[att.id],'REVOKED')
        self.assertTrue(audit_loop(self.path,self.policy)['runtime_consistent'])

    def test_mutated_runtime_projection_is_rejected_by_readonly_audit(self):
        self.loop.run('task',self.owner)
        before=self.path.read_bytes()
        self.assertTrue(audit_loop(self.path,self.policy)['runtime_consistent'])
        self.assertEqual(self.path.read_bytes(),before)
        db=sqlite3.connect(self.path)
        row=json.loads(db.execute("SELECT payload FROM loop_tasks WHERE id='task'").fetchone()[0]);row['actions']=0
        db.execute("UPDATE loop_tasks SET payload=? WHERE id='task'",(json.dumps(row),));db.commit();db.close()
        with self.assertRaisesRegex(ValueError,'trajectory'):audit_loop(self.path,self.policy)

    def test_attestation_signature_tampering_is_rejected(self):
        self.loop.run('task',self.owner);att=self.loop.attest('task',self.loop.verifier)
        db=sqlite3.connect(self.path);db.execute('DROP TRIGGER loop_attestations_no_update')
        payload=att.model_dump(mode='json');payload['expires_at']+=1000
        db.execute('UPDATE loop_attestations SET payload=? WHERE id=?',(json.dumps(payload),att.id));db.commit();db.close()
        with self.assertRaises(PermissionError):self.loop.attestation_status(att.id,self.owner)

    def test_cancelled_task_cannot_be_reclassified_as_success(self):
        self.loop.cancel('task',self.owner)
        with self.assertRaises(PermissionError):self.loop.verify('task',self.loop.verifier)
        self.assertEqual(self.loop.run('task',self.owner).outcome,'UNKNOWN')

    def test_execution_cannot_take_owner_or_verifier_identity(self):
        from vcp.runtime import approve_execution
        for actor in ('fixture-owner','independent-verifier','independent-reader','loop-controller'):
            contract=self.contract.model_copy(update={'allowed_executors':(actor,)})
            approval=approve_execution(contract,self.policy,self.owner,self.now)
            with self.assertRaises(PermissionError):self.loop.create('reserved-'+actor,'reserved-execution',contract,approval,self.owner)

    def test_adapter_cannot_modify_bank_inputs(self):
        from vcp.runtime import SQLiteReconciliationAdapter
        class BankEdit(SQLiteReconciliationAdapter):
            def apply(self,db):
                super().apply(db);db.execute("UPDATE bank SET amount_minor=0")
        self.loop.gateway.adapter=BankEdit();before=digest(read_snapshot(self.path))
        result=self.loop.run('task',self.owner)
        self.assertEqual(result.outcome,'FAILURE');self.assertTrue(result.task.historical_violation)
        self.assertEqual(digest(read_snapshot(self.path)),before)
