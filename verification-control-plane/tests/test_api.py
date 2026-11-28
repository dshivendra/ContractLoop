import http.client
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import signal
import select
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from vcp.api import make_server
from vcp.loop_cli import demo,main
from tests.test_runtime import RuntimeFixture


class APITests(RuntimeFixture,unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.tokens={'o'*40:self.owner,'v'*40:self.loop.verifier,'e'*40:self.executor,
                     'r'*40:self.owner.model_copy(update={'actor':'reader','role':'reader'})}
        self.server=make_server(self.loop,self.tokens)
        self.worker=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':0.01},daemon=True);self.worker.start()

    def tearDown(self):
        self.server.shutdown();self.worker.join(timeout=5);self.server.server_close();super().tearDown()

    def request(self,method,path,body=None,token='o'*40,raw=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        headers={'Content-Type':'application/json'}
        if token:headers['Authorization']='Bearer '+token
        encoded=raw if raw is not None else json.dumps(body) if body is not None else None
        try:
            connection.request(method,path,body=encoded,headers=headers)
            response=connection.getresponse();return response.status,json.loads(response.read())
        finally:connection.close()

    def test_api_run_attest_monitor_and_replayable_audit(self):
        code,result=self.request('POST','/tasks/task/run',{})
        self.assertEqual(code,200);self.assertEqual(result['outcome'],'SUCCESS')
        code,att=self.request('POST','/tasks/task/attest',{},'v'*40)
        self.assertEqual(code,200)
        self.assertEqual(self.request('GET','/attestations/'+att['id'])[1]['validity'],'VALID')
        code,audit=self.request('GET','/audit',token='r'*40)
        self.assertEqual(code,200);self.assertGreater(len(audit['records']),10)
        db=sqlite3.connect(self.path);db.execute('DELETE FROM destination');db.commit();db.close()
        self.assertEqual(self.request('POST','/monitor',{},'v'*40)[1][att['id']],'REVOKED')

    def test_tokens_cannot_be_replaced_by_request_role(self):
        self.assertEqual(self.request('POST','/tasks/task/run',{'role':'owner'},'e'*40)[0],403)
        self.assertEqual(self.request('POST','/tasks/task/attest',{},'o'*40)[0],403)
        self.assertEqual(self.request('GET','/tasks/task',token='wrong')[0],403)
        self.assertEqual(self.request('GET','/tasks/task',token=None)[0],403)
        self.assertEqual(self.request('GET','/health',token=None)[0],200)

    def test_invalid_and_oversized_inputs_fail_closed(self):
        self.assertEqual(self.request('POST','/tasks',raw='{"task_id":"a","task_id":"b"}')[0],400)
        self.assertEqual(self.request('POST','/tasks',raw='x'*65537)[0],400)
        self.assertEqual(self.request('POST','/tasks',raw='[]')[0],400)
        self.assertEqual(self.request('POST','/tasks',raw='{')[0],400)
        self.assertEqual(self.request('GET','/missing')[0],404)
        self.assertEqual(self.request('POST','/tasks/nope/run',{})[0],404)

    def test_draft_approval_create_flow_is_explicit_and_owner_authorized(self):
        intent={'id':'new-kernel','tenant':'demo','owner':'fixture-owner','objective':'Reconcile the fixture','recipe':'synthetic-reconciliation'}
        code,draft=self.request('POST','/draft',{'intent':intent})
        self.assertEqual(code,200);self.assertNotIn('approval',draft)
        self.assertEqual(self.request('POST','/approve',{'kernel':draft['kernel'],'executor':'executor','deadline':self.now+120},'r'*40)[0],403)
        code,approved=self.request('POST','/approve',{'kernel':draft['kernel'],'executor':'executor','deadline':self.now+120})
        self.assertEqual(code,200)
        code,task=self.request('POST','/tasks',dict(task_id='new',execution_id='new-execution',**approved))
        self.assertEqual(code,200);self.assertEqual(task['lifecycle'],'draft')
        self.assertEqual(self.request('POST','/tasks/new/cancel',{})[1]['lifecycle'],'cancelled')

    def test_infrastructure_fault_is_not_api_success(self):
        with patch.object(self.loop,'get',side_effect=OSError('secret path')):
            code,body=self.request('GET','/tasks/task')
        self.assertEqual(code,503);self.assertNotIn('secret',json.dumps(body))

    def test_api_requires_strong_tenant_bound_token_configuration(self):
        with self.assertRaises(ValueError):make_server(self.loop,{'short':self.owner})
        with self.assertRaises(ValueError):make_server(self.loop,{'s'*40:self.owner.model_copy(update={'tenant':'other'})})


class CLITests(unittest.TestCase):
    def test_demo_artifacts_restart_audit_status_monitor_and_exclusive_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'demo';report=demo(target)
            self.assertEqual(report['outcome'],'SUCCESS');self.assertEqual(report['validity'],'VALID')
            self.assertEqual(json.loads((target/'result.json').read_text())['audit_head'],report['audit_head'])
            with self.assertRaises(ValueError):demo(target)
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(['audit','--database',str(target/'loop.sqlite')]),0)
            self.assertEqual(json.loads(output.getvalue())['replayed_verdicts'],1)
            for command in ('status','monitor'):
                with redirect_stdout(io.StringIO()):self.assertEqual(main([command,'--database',str(target/'loop.sqlite')]),0)
            tokens=Path(tmp)/'tokens.json'
            with redirect_stdout(io.StringIO()):self.assertEqual(main(['credentials','--output',str(tokens)]),0)
            self.assertEqual(tokens.stat().st_mode&0o777,0o600)
            self.assertEqual(len(set(json.loads(tokens.read_text()).values())),4)
            with self.assertRaises(FileExistsError):main(['credentials','--output',str(tokens)])

    def test_cli_server_automatically_revokes_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'demo';report=demo(target)
            tokens=Path(tmp)/'tokens.json'
            with redirect_stdout(io.StringIO()):main(['credentials','--output',str(tokens)])
            proc=subprocess.Popen([sys.executable,'-m','vcp.loop_cli','serve','--database',str(target/'loop.sqlite'),'--tokens',str(tokens),'--port','0'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                self.assertTrue(select.select([proc.stdout],[],[],5)[0],'server failed to start')
                address=json.loads(proc.stdout.readline())['url']
                self.assertTrue(address.startswith('http://127.0.0.1:'))
                db=sqlite3.connect(target/'loop.sqlite');db.execute('DELETE FROM destination');db.commit()
                deadline=time.monotonic()+5;revoked=False
                while time.monotonic()<deadline:
                    revoked=bool(db.execute('SELECT 1 FROM loop_revocations WHERE id=?',(report['attestation']['id'],)).fetchone())
                    if revoked:break
                    time.sleep(0.05)
                db.close();self.assertTrue(revoked,'service monitor did not revoke drift')
            finally:
                proc.send_signal(signal.SIGINT)
                try:proc.communicate(timeout=5)
                except subprocess.TimeoutExpired:proc.kill();proc.communicate()
            self.assertEqual(proc.returncode,0)
