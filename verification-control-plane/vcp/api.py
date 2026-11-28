"""Loopback-only JSON API. Tokens map to server-owned principals.

The synthetic policy keys remain public fixture keys: authentication protects the
local demo interface, not a production deployment or a malicious process owner.
"""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import hmac
import json
import threading
from urllib.parse import unquote,urlsplit
from pydantic import ValidationError
from .models import Contract
from .planning import compile_execution,compile_kernel,discover_context
from .runtime import approve_execution,authorize
from .runtime_models import (Action,Composition,ExecutionApproval,ExecutionContract,Intent,Principal)
from .security import approve

MAX_BODY=65536


def make_server(controller,tokens,port=0):
    """tokens is a trusted token→Principal mapping, never populated from requests."""
    tokens={token:Principal.model_validate_json(principal.model_dump_json()) for token,principal in tokens.items()}
    if not tokens or any(len(token)<32 for token in tokens):raise ValueError('strong explicit API tokens required')
    if any(p.tenant!=controller.store.tenant for p in tokens.values()):raise ValueError('token tenant mismatch')
    control_lock=threading.RLock()

    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.0'

        def log_message(self,*args):pass  # Never log bearer tokens or request bodies.

        def reply(self,status,body):
            data=json.dumps(body,separators=(',',':')).encode()
            self.send_response(status);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)

        def principal(self):
            value=self.headers.get('Authorization','')
            if not value.startswith('Bearer '):raise PermissionError('authentication required')
            candidate=value[7:]
            for token,principal in tokens.items():
                if hmac.compare_digest(candidate,token):return principal
            raise PermissionError('authentication required')

        def body(self):
            if self.headers.get('Transfer-Encoding'):raise ValueError('transfer encoding unsupported')
            if self.headers.get_content_type()!='application/json':raise ValueError('JSON content type required')
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=MAX_BODY:raise ValueError('request body size')
            data=self.rfile.read(length)
            if len(data)!=length:raise ValueError('incomplete request body')
            def unique(items):
                result={}
                for k,v in items:
                    if k in result:raise ValueError('duplicate JSON key')
                    result[k]=v
                return result
            parsed=json.loads(data,object_pairs_hook=unique)
            if not isinstance(parsed,dict):raise ValueError('JSON object required')
            return parsed

        def handle_request(self):
            try:
                parts=[unquote(x) for x in urlsplit(self.path).path.strip('/').split('/')]
                if self.command=='GET' and parts==['health']:
                    return self.reply(200,{'status':'ok','mode':'local-synthetic'})
                p=self.principal()
                with control_lock:
                    result=self.route(parts,p)
                if hasattr(result,'model_dump'):result=result.model_dump(mode='json')
                self.reply(200,result)
            except PermissionError:self.reply(403,{'error':'authentication or authorization denied'})
            except KeyError:self.reply(404,{'error':'resource not found'})
            except (ValueError,ValidationError,TypeError):self.reply(400,{'error':'invalid request or state transition'})
            except (RuntimeError,TimeoutError):self.reply(409,{'error':'operation blocked by runtime guard'})
            except Exception:self.reply(503,{'error':'operation unavailable; success not established'})

        def route(self,parts,p):
            if self.command=='GET':
                if len(parts)==2 and parts[0]=='tasks':return controller.get(parts[1],p)
                if len(parts)==2 and parts[0]=='attestations':return {'validity':controller.attestation_status(parts[1],p)}
                if parts==['audit']:
                    authorize(p,controller.store.tenant,{'owner','reader','verifier'})
                    with controller.store.transaction() as ledger:return {'head':ledger.check(),'records':ledger.records()}
            if self.command=='POST':
                body=self.body()
                if parts==['draft']:
                    authorize(p,controller.store.tenant,{'owner'})
                    intent=Intent.model_validate(body['intent'])
                    if intent.owner!=p.actor:raise PermissionError('owner mismatch')
                    context=discover_context(controller.store.path,p.tenant)
                    return {'context':context.model_dump(mode='json'),'kernel':compile_kernel(intent,context,controller.policy).model_dump(mode='json')}
                if parts==['approve']:
                    authorize(p,controller.store.tenant,{'owner'})
                    kernel=Contract.model_validate(body['kernel'])
                    if kernel.owner!=p.actor or p.actor!=controller.policy.approver:raise PermissionError('owner mismatch')
                    contract=compile_execution(kernel,approve(kernel,controller.policy,controller.clock()),body['executor'],body['deadline'],**body.get('limits',{}))
                    approval=approve_execution(contract,controller.policy,p,controller.clock())
                    return {'contract':contract.model_dump(mode='json'),'approval':approval.model_dump(mode='json')}
                if parts==['tasks']:
                    return controller.create(body['task_id'],body['execution_id'],ExecutionContract.model_validate(body['contract']),
                                             ExecutionApproval.model_validate(body['approval']),p)
                if parts==['monitor']:return controller.monitor(p)
                if parts==['compositions']:
                    return {'hash':controller.register_composition(Composition.model_validate(body['plan']),ExecutionApproval.model_validate(body['approval']),p)}
                if len(parts)==3 and parts[0]=='tasks':
                    task_id,operation=parts[1:]
                    if operation=='run':return controller.run(task_id,p)
                    if operation=='cancel':return controller.cancel(task_id,p)
                    if operation=='verify':return controller.verify(task_id,p)
                    if operation=='attest':return controller.attest(task_id,p)
                    if operation=='proposals':return controller.propose_revision(task_id,body['rationale'],body.get('evidence_ids',()),p)
                    if operation=='actions':
                        action=Action.model_validate(body)
                        if action.task_id!=task_id:raise PermissionError('route/action mismatch')
                        return controller.gateway.execute(action,p)
                if len(parts)==3 and parts[0]=='attestations' and parts[2]=='revoke':
                    controller.revoke(parts[1],body['reason'],p);return {'validity':'REVOKED'}
            raise KeyError('route')

        do_GET=handle_request
        do_POST=handle_request

        def setup(self):
            super().setup();self.connection.settimeout(5)

    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.daemon_threads=True
    server.timeout=1
    return server
