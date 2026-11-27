Inspect the candidate diff and identify one concrete defect that can be corrected
without changing approved verification semantics. Make one bounded repair only in
Python files below verification-control-plane/vcp/. Do not change tests, schema,
workflows, policy or historical evidence. Do not install dependencies, use network
services, commit, push, approve or merge. Do not modify .git or bypass sandboxing.
Read AGENTS.md, REVIEW.md and the frozen handoff. Maximum: 10 files and 400 changed
lines. If no safe correction is evident, change nothing and explain why.
Return the specified JSON describing the repair and remaining findings. Your
completion claim is not authoritative: a separate fresh job validates the exported
changes with the original tests before a separate job may open a repair PR.
