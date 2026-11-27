"""Codex PR controller: scoped repair receipts and deterministic observation policy.

Runs outside the model. It never approves or merges a pull request.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request


def git(root,*args):
    return subprocess.check_output(["git","-C",str(root),*args])


def api(repo,path,method="GET",body=None):
    if not re.fullmatch(r"[\w.-]+/[\w.-]+",repo): raise ValueError("invalid repository")
    data=None if body is None else json.dumps(body).encode()
    request=urllib.request.Request("https://api.github.com/repos/"+repo+"/"+path,data=data,method=method,
        headers={"Authorization":"Bearer "+os.environ["GH_TOKEN"],"Accept":"application/vnd.github+json",
                 "X-GitHub-Api-Version":"2022-11-28","Content-Type":"application/json"})
    with urllib.request.urlopen(request,timeout=30) as response:
        return json.loads(response.read(8_000_000))


def validate_pr(pr,repo,expected):
    if not re.fullmatch(r"[0-9a-f]{40}",expected): raise ValueError("expected head must be full SHA")
    if pr["state"]!="open" or pr["head"]["sha"]!=expected: raise ValueError("closed or stale pull request")
    if pr["head"]["repo"]["full_name"]!=repo: raise ValueError("fork repairs/reviews not enabled")
    if pr["base"]["ref"]!="main": raise ValueError("only main-targeting pull requests supported")
    return pr


def repair_path(path,policy):
    p=PurePosixPath(path)
    return (isinstance(path,str) and not p.is_absolute() and ".." not in p.parts
            and str(p)==path and path.startswith(policy["allowed_repair_prefix"])
            and p.suffix==".py" and not any(x.startswith(".") for x in p.parts))


def bind_receipt(receipt,repo,number,head):
    if (receipt.get("repository"),receipt.get("pr"),receipt.get("head_sha"))!=(repo,int(number),head):
        raise ValueError("receipt does not match authorized workflow target")
    return receipt


def validate_receipt(receipt,policy):
    if set(receipt)!={"version","repository","pr","head_sha","changes","changed_lines"} or receipt["version"]!=1:
        raise ValueError("invalid receipt envelope")
    if not re.fullmatch(r"[0-9a-f]{40}",receipt["head_sha"]): raise ValueError("invalid receipt head")
    if type(receipt["pr"])is not int or receipt["pr"]<1: raise ValueError("invalid PR number")
    changes=receipt["changes"]
    if not isinstance(changes,list) or not 1<=len(changes)<=policy["max_files"]: raise ValueError("file budget")
    if type(receipt["changed_lines"]) is not int or not 0<receipt["changed_lines"]<=policy["max_changed_lines"]:
        raise ValueError("line budget")
    seen=set()
    for c in changes:
        if set(c)!={"path","content","sha256"} or not repair_path(c["path"],policy): raise ValueError("repair scope")
        if c["path"] in seen: raise ValueError("duplicate path")
        seen.add(c["path"])
        if not isinstance(c["content"],str): raise ValueError("UTF-8 Python text required")
        data=c["content"].encode()
        if len(data)>policy["max_file_bytes"] or hashlib.sha256(data).hexdigest()!=c["sha256"]:
            raise ValueError("content integrity/size")
    return receipt


def export_repair(root,repo,pr,head,policy):
    if git(root,"rev-parse","HEAD").decode().strip()!=head: raise ValueError("agent moved HEAD")
    if git(root,"diff","--name-only","--diff-filter=DR",head): raise ValueError("deletions/renames not supported")
    names=git(root,"diff","--no-ext-diff","--no-textconv","--name-only","-z",head).decode().split("\0")
    names+=git(root,"ls-files","--others","--exclude-standard","-z").decode().split("\0")
    names=sorted(set(filter(None,names)))
    if not names: return None
    changed=0
    for row in git(root,"diff","--no-ext-diff","--no-textconv","--numstat",head).decode().splitlines():
        a,b,_=row.split("\t",2)
        if not a.isdigit() or not b.isdigit(): raise ValueError("binary repair")
        changed+=int(a)+int(b)
    changes=[]
    untracked=set(git(root,"ls-files","--others","--exclude-standard","-z").decode().split("\0"))
    for name in names:
        if not repair_path(name,policy): raise ValueError("repair outside allowed Python scope")
        path=root/name
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()): raise ValueError("symlink repair")
        content=path.read_text()
        if name in untracked: changed+=len(content.splitlines())
        changes.append(dict(path=name,content=content,sha256=hashlib.sha256(content.encode()).hexdigest()))
    return validate_receipt(dict(version=1,repository=repo,pr=pr,head_sha=head,changes=changes,changed_lines=changed),policy)


def apply_repair(root,receipt,policy):
    validate_receipt(receipt,policy)
    if git(root,"rev-parse","HEAD").decode().strip()!=receipt["head_sha"]: raise ValueError("validation checkout is stale")
    if git(root,"status","--porcelain"): raise ValueError("validation checkout must be clean")
    for change in receipt["changes"]:
        path=root/change["path"]
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()): raise ValueError("symlink target")
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(change["content"])
    # Independently recount after applying: agent-provided line count is not trusted.
    exported=export_repair(root,receipt["repository"],receipt["pr"],receipt["head_sha"],policy)
    if exported!=receipt: raise ValueError("repair receipt/diff mismatch")


def policy_decision(checks,head,policy):
    expected=policy["required_checks"]
    outcomes=[]
    for name in expected:
        runs=[c for c in checks if c.get("name")==name and c.get("head_sha")==head
              and c.get("app",{}).get("slug")=="github-actions"]
        latest=max(runs,key=lambda c:c.get("id",0)) if runs else None
        outcomes.append(latest)
    if any(c and c.get("status")=="completed" and c.get("conclusion") in ("failure","cancelled","timed_out","action_required") for c in outcomes):
        state="BLOCKED"
    elif any(not c or c.get("status")!="completed" or c.get("conclusion")!="success" for c in outcomes):
        state="UNKNOWN"
    else: state="NEEDS_HUMAN"
    return dict(decision=state,mode=policy["mode"],head_sha=head,human_approval_required=True,auto_merge=False)


def publish_repair(receipt,policy,run_id):
    validate_receipt(receipt,policy)
    repo,number,head=receipt["repository"],receipt["pr"],receipt["head_sha"]
    pr=validate_pr(api(repo,f"pulls/{number}"),repo,head)
    parent=api(repo,"git/commits/"+head)
    tree=api(repo,"git/trees","POST",dict(base_tree=parent["tree"]["sha"],tree=[dict(path=c["path"],mode="100644",type="blob",content=c["content"]) for c in receipt["changes"]]))
    commit=api(repo,"git/commits","POST",dict(message=f"Codex bounded repair for PR #{number}",tree=tree["sha"],parents=[head]))
    validate_pr(api(repo,f"pulls/{number}"),repo,head)
    if not re.fullmatch(r"[0-9]+",run_id): raise ValueError("invalid run ID")
    branch=f"codex-fix/pr-{number}-{run_id}"
    api(repo,"git/refs","POST",dict(ref="refs/heads/"+branch,sha=commit["sha"]))
    result=api(repo,"pulls","POST",dict(title=f"Codex repair for #{number}",head=branch,base=pr["head"]["ref"],draft=True,
        body=f"One bounded Codex repair against `{head}`. A fresh job passed the original Phase 1 acceptance gate before this PR was opened. Review the diff and merge this repair into the original PR branch before merging the original PR into main. No automated approval or merge is granted. Run evidence: https://github.com/{repo}/actions/runs/{run_id}"))
    return dict(url=result["html_url"],commit=commit["sha"],base_sha=head)


def main():
    p=argparse.ArgumentParser();p.add_argument("command",choices=["prepare","export","apply","publish"])
    p.add_argument("--policy",type=Path,required=True);p.add_argument("--root",type=Path,default=Path.cwd())
    p.add_argument("--receipt",type=Path,required=True);args=p.parse_args()
    policy=json.loads(args.policy.read_text())
    if policy["mode"]!="observe" or policy["auto_merge"] or not policy["human_approval_required"]:
        raise ValueError("this controller only supports observe mode and human approval")
    if args.command!="prepare":
        bind_receipt(json.loads(args.receipt.read_text()),os.environ["GITHUB_REPOSITORY"],
                     os.environ["PR_NUMBER"],os.environ["EXPECTED_HEAD"])
    if args.command=="prepare":
        repo=os.environ["GITHUB_REPOSITORY"];number=os.environ["PR_NUMBER"];head=os.environ["EXPECTED_HEAD"]
        if not re.fullmatch(r"[1-9][0-9]*",number): raise ValueError("invalid PR")
        pr=validate_pr(api(repo,"pulls/"+number),repo,head)
        checks=api(repo,"commits/"+head+"/check-runs?per_page=100")["check_runs"]
        print(json.dumps(policy_decision(checks,head,policy)))
        with open(os.environ["GITHUB_OUTPUT"],"a") as f:
            f.write("head="+head+"\nbase="+pr["base"]["sha"]+"\n")
        args.receipt.write_text(json.dumps(dict(repository=repo,pr=int(number),head_sha=head)))
    elif args.command=="export":
        context=json.loads(args.receipt.read_text());receipt=export_repair(args.root,policy=policy,repo=context["repository"],pr=context["pr"],head=context["head_sha"])
        args.receipt.write_text(json.dumps(receipt,indent=2))
        if receipt is None: raise SystemExit("No repair proposed; nothing will be published")
    elif args.command=="apply": apply_repair(args.root,json.loads(args.receipt.read_text()),policy)
    else: print(json.dumps(publish_repair(json.loads(args.receipt.read_text()),policy,os.environ["GITHUB_RUN_ID"])))


if __name__=="__main__": main()
