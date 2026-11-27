import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('ship',ROOT/'ship.py')
ship=importlib.util.module_from_spec(spec);spec.loader.exec_module(ship)
POLICY=json.loads((ROOT/'policy.json').read_text())


class PolicyTests(unittest.TestCase):
    def check(self,name,conclusion='success',head='a'*40,number=1,app='github-actions'):
        return dict(name=name,head_sha=head,id=number,status='completed',conclusion=conclusion,app=dict(slug=app))

    def test_green_ci_still_requires_human(self):
        runs=[self.check(n) for n in POLICY['required_checks']]
        d=ship.policy_decision(runs,'a'*40,POLICY)
        self.assertEqual(d['decision'],'NEEDS_HUMAN')
        self.assertTrue(d['human_approval_required']);self.assertFalse(d['auto_merge'])

    def test_missing_or_stale_checks_unknown(self):
        for runs in ([],[self.check(n,head='b'*40) for n in POLICY['required_checks']],
                     [self.check(n,app='untrusted') for n in POLICY['required_checks']]):
            self.assertEqual(ship.policy_decision(runs,'a'*40,POLICY)['decision'],'UNKNOWN')

    def test_failure_blocks_despite_other_missing_check(self):
        self.assertEqual(ship.policy_decision([self.check(POLICY['required_checks'][0],'failure')],'a'*40,POLICY)['decision'],'BLOCKED')

    def test_latest_check_cannot_reuse_old_green(self):
        runs=[self.check(n) for n in POLICY['required_checks']]
        runs.append(self.check(POLICY['required_checks'][0],'failure',number=2))
        self.assertEqual(ship.policy_decision(runs,'a'*40,POLICY)['decision'],'BLOCKED')

    def test_paths_and_policy_boundary(self):
        for path in ('../vcp/x.py','/tmp/x.py','verification-control-plane/vcp/../tests/x.py',
                     '.github/workflows/x.py','verification-control-plane/tests/x.py',
                     'verification-control-plane/vcp/.hidden.py','verification-control-plane/vcp/a.json'):
            self.assertFalse(ship.repair_path(path,POLICY),path)
        self.assertTrue(ship.repair_path('verification-control-plane/vcp/example.py',POLICY))

    def test_receipt_hash_scope_and_budgets(self):
        content='x=2\n'
        r=dict(version=1,repository='owner/repo',pr=1,head_sha='a'*40,changed_lines=2,
               changes=[dict(path='verification-control-plane/vcp/x.py',content=content,sha256=hashlib.sha256(content.encode()).hexdigest())])
        self.assertEqual(ship.validate_receipt(r,POLICY),r)
        for mutation in (lambda x:x.update(changed_lines=401),lambda x:x.update(head_sha='bad'),
                         lambda x:x['changes'][0].update(sha256='bad'),
                         lambda x:x['changes'][0].update(path='.github/workflows/x.py'),
                         lambda x:x['changes'].append(x['changes'][0]),lambda x:x.update(auto_merge=True)):
            bad=copy.deepcopy(r);mutation(bad)
            with self.assertRaises(ValueError):ship.validate_receipt(bad,POLICY)

    def test_pr_must_be_open_same_repo_and_exact_head(self):
        p=dict(state='open',head=dict(sha='a'*40,repo=dict(full_name='owner/repo')),base=dict(ref='main'))
        self.assertEqual(ship.validate_pr(p,'owner/repo','a'*40),p)
        for mutation in (lambda x:x.update(state='closed'),lambda x:x['head'].update(sha='b'*40),
                         lambda x:x['head']['repo'].update(full_name='fork/repo'),lambda x:x['base'].update(ref='release')):
            bad=copy.deepcopy(p);mutation(bad)
            with self.assertRaises(ValueError):ship.validate_pr(bad,'owner/repo','a'*40)

    def test_receipt_cannot_change_workflow_target(self):
        r=dict(repository='owner/repo',pr=1,head_sha='a'*40)
        self.assertEqual(ship.bind_receipt(r,'owner/repo','1','a'*40),r)
        for field,value in (('repository','other/repo'),('pr',2),('head_sha','b'*40)):
            with self.assertRaises(ValueError):ship.bind_receipt(dict(r,**{field:value}),'owner/repo','1','a'*40)


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.file=self.root/'verification-control-plane/vcp/example.py'
        self.file.parent.mkdir(parents=True);self.file.write_text('value=1\n')
        self.cmd('init','-q');self.cmd('config','user.name','Test');self.cmd('config','user.email','test@local')
        self.cmd('add','.');self.cmd('commit','-qm','baseline');self.head=self.cmd('rev-parse','HEAD').strip()

    def tearDown(self):self.tmp.cleanup()
    def cmd(self,*args):return subprocess.check_output(['git','-C',str(self.root),*args]).decode()
    def export(self):return ship.export_repair(self.root,'owner/repo',1,self.head,POLICY)

    def test_export_apply_roundtrip_recounts_actual_diff(self):
        self.file.write_text('value=2\n');r=self.export()
        self.cmd('restore','.');ship.apply_repair(self.root,r,POLICY)
        self.assertEqual(self.file.read_text(),'value=2\n')
        self.assertEqual(r['changed_lines'],2)

    def test_modified_tests_rejected(self):
        f=self.root/'verification-control-plane/tests/test_x.py';f.parent.mkdir();f.write_text('pass\n')
        with self.assertRaises(ValueError):self.export()

    def test_symlinks_and_deletion_rejected(self):
        self.file.unlink()
        with self.assertRaises(ValueError):self.export()
        self.file.symlink_to('/tmp/nonexistent-codex-fixture')
        with self.assertRaises(ValueError):self.export()

    def test_no_change_is_not_a_repair(self):self.assertIsNone(self.export())

    def test_manifest_cannot_underreport_line_budget(self):
        self.file.write_text('value=2\n');r=self.export();r['changed_lines']=1
        self.cmd('restore','.')
        with self.assertRaisesRegex(ValueError,'diff mismatch'):ship.apply_repair(self.root,r,POLICY)

    def test_stale_checkout_rejected(self):
        self.file.write_text('value=2\n');r=self.export();self.cmd('add','.');self.cmd('commit','-qm','moved')
        with self.assertRaises(ValueError):ship.apply_repair(self.root,r,POLICY)

    def test_changed_source_pr_prevents_publish(self):
        self.file.write_text('value=2\n');r=self.export()
        p=dict(state='open',head=dict(sha='b'*40,repo=dict(full_name='owner/repo')),base=dict(ref='main'))
        with patch.object(ship,'api',return_value=p) as api:
            with self.assertRaises(ValueError):ship.publish_repair(r,POLICY,'123')
            self.assertEqual(api.call_count,1)

    def test_publish_only_opens_separate_draft_repair(self):
        self.file.write_text('value=2\n');r=self.export()
        p=dict(state='open',head=dict(sha=self.head,ref='feature',repo=dict(full_name='owner/repo')),base=dict(ref='main'))
        responses=[p,dict(tree=dict(sha='base-tree')),dict(sha='new-tree'),dict(sha='new-commit'),p,{},dict(html_url='https://github.com/owner/repo/pull/2')]
        with patch.object(ship,'api',side_effect=responses) as api:
            result=ship.publish_repair(r,POLICY,'123')
            self.assertEqual(result['commit'],'new-commit')
            calls=api.call_args_list
            self.assertEqual(calls[-2].args[1:3],('git/refs','POST'))
            self.assertEqual(calls[-2].args[3]['ref'],'refs/heads/codex-fix/pr-1-123')
            self.assertTrue(calls[-1].args[3]['draft'])
            self.assertEqual(calls[-1].args[3]['base'],'feature')
            self.assertFalse(any('/merge' in c.args[1] or 'PATCH' in c.args for c in calls))

    def test_head_race_aborts_before_branch_creation(self):
        self.file.write_text('value=2\n');r=self.export()
        p=dict(state='open',head=dict(sha=self.head,ref='feature',repo=dict(full_name='owner/repo')),base=dict(ref='main'))
        stale=copy.deepcopy(p);stale['head']['sha']='b'*40
        responses=[p,dict(tree=dict(sha='base-tree')),dict(sha='new-tree'),dict(sha='new-commit'),stale]
        with patch.object(ship,'api',side_effect=responses) as api:
            with self.assertRaises(ValueError):ship.publish_repair(r,POLICY,'123')
            self.assertFalse(any(c.args[1]=='git/refs' for c in api.call_args_list))


if __name__=='__main__':unittest.main()
