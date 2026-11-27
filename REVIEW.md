# ContractLoop review priorities

The implemented project is under `verification-control-plane/`. Review behavior
against its HANDOFF.md and FORMAL_SEMANTICS.md. Scope is the Phase 1 synthetic
verification kernel; execution gateways and production integrations are deferred.

Prioritize defects that could produce false SUCCESS: executor claims overriding
outcome evidence; unapproved contract changes; incorrect failure-criterion polarity;
missing/unauthenticated/conflicting/stale evidence accepted; cross-tenant/run/state
replay; unsafe comparisons or vacuous success; unverifiable temporal guarantees;
mutable audit records; audit failures that still return issued success.

Check that each outcome references its exact contract, policy, source evidence,
assumptions and assurance. Preserve independent golden/oracle and mutation checks.
Review the actual source and tests; historical acceptance JSON is not proof of the
current change. Public fixture keys establish no production security claim.

For CI/policy changes check permissions, action pins, untrusted PR input, required
status coverage, fresh per-run evidence, and separation of review from approval.
No automatic merging is part of this pilot. Codex policy decisions are
advisory in observe mode and do not enforce GitHub human review by themselves.

Report a concrete trigger, violated contract/invariant, relevant code and a
reproducible check. Distinguish demonstrated defects from suggestions. Avoid
requests for broad rewrites or cosmetic churn unrelated to correctness.
