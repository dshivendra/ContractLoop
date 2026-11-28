import unittest
from vcp.composition import approve_composition
from vcp.models import Compare
from vcp.planning import compile_execution, compile_kernel, discover_context
from vcp.runtime import approve_execution
from vcp.runtime_models import Composition, Dependency, Intent
from vcp.security import approve,digest
from tests.test_runtime import RuntimeFixture


class CompositionTests(RuntimeFixture,unittest.TestCase):
    def parent(self,when=None,global_invariants=(),**limits):
        child=self.loop.get('task',self.owner)
        intent=Intent(id='parent-kernel',tenant='demo',owner=self.owner.actor,objective='Verify the parent batch',recipe='synthetic-reconciliation')
        kernel=compile_kernel(intent,discover_context(self.path,'demo'),self.policy)
        plan=Composition(tenant='demo',parent_task_id='parent',parent_kernel_hash=digest(kernel),
                         dependencies=(Dependency(task_id='task',contract_hash=child.contract_hash,when=when),),global_invariants=global_invariants)
        approval=approve_composition(plan,self.policy,self.owner,self.now)
        key=self.loop.register_composition(plan,approval,self.owner)
        contract=compile_execution(kernel,approve(kernel,self.policy,self.now),'executor',self.now+120,composition_hash=key,**limits)
        self.loop.create('parent','parent-execution',contract,approve_execution(contract,self.policy,self.owner,self.now),self.owner)
        return plan


    def test_parent_has_own_verification_and_fresh_child_proof(self):
        self.parent()
        result=self.loop.run('parent',self.owner)
        self.assertEqual(result.outcome,'SUCCESS')
        self.assertEqual(result.task.actions,1)
        self.assertEqual(self.loop.get('task',self.owner).collections,2)
        att=self.loop.attest('parent',self.loop.verifier)
        self.assertEqual([d.task_id for d in att.dependencies],['task'])
        self.assertEqual(self.loop.attestation_status(att.id,self.owner),'VALID')


    def test_failed_dependency_prevents_parent_execution(self):
        self.parent();self.loop.cancel('task',self.owner)
        result=self.loop.run('parent',self.owner)
        self.assertEqual(result.outcome,'UNKNOWN');self.assertEqual(result.task.actions,0)


    def test_false_condition_skips_child_but_parent_still_verifies(self):
        self.parent(when=Compare(fact='authorized',expected=False))
        self.assertEqual(self.loop.run('parent',self.owner).outcome,'SUCCESS')
        self.assertEqual(self.loop.get('task',self.owner).actions,0)
        self.assertEqual(self.loop.attest('parent',self.loop.verifier).dependencies,())


    def test_unknown_condition_never_becomes_vacuous_success(self):
        self.parent(when=Compare(fact='authorized',expected='wrong-type'))
        result=self.loop.run('parent',self.owner)
        self.assertEqual(result.outcome,'UNKNOWN');self.assertEqual(result.task.actions,0)


    def test_global_violation_blocks_parent_despite_child_success(self):
        self.parent(global_invariants=(Compare(fact='authorized',expected=False),))
        result=self.loop.run('parent',self.owner)
        self.assertEqual(result.outcome,'FAILURE')
        self.assertEqual(self.loop.get('task',self.owner).verdict,'SUCCESS')
        with self.assertRaises(PermissionError):self.loop.attest('parent',self.loop.verifier)


    def test_plan_binding_and_child_pin_cannot_be_changed(self):
        plan=self.parent()
        changed=plan.model_copy(update={'parent_task_id':'other'})
        with self.assertRaises(PermissionError):
            self.loop.register_composition(changed,approve_composition(plan,self.policy,self.owner,self.now),self.owner)
        with self.assertRaises(ValueError):
            Composition(tenant='demo',parent_task_id='task',parent_kernel_hash='hash',dependencies=(Dependency(task_id='task',contract_hash='hash'),))
