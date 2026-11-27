# Lifecycle boundary

Phase 1 does not run tasks. The handoff's execution lifecycle is deferred intact.
There is no implicit transition from executor completion to verified success.

| Phase 1 operation | Actor / guard | Side effect / persistence | Failure / concurrency / idempotency |
|---|---|---|---|
| Validate draft | Kernel; schema, mappings, bounded satisfiability | None | ValidationError; pure |
| Approve | Synthetic owner authority; pinned policy | Signed approval envelope | PermissionError; signature deterministic |
| Register approved version | ContractRepository; valid envelope and scope | Immutable contract audit row | Collision rejects; SQLite BEGIN IMMEDIATE; identical payload idempotent |
| Observe | Independent reader; existing fixture and resource/state match | Signed observation envelopes | Collection exception; snapshot read transaction; no writes |
| Calculate | Kernel; approved contract and scoped run | Diagnostic result only | Invalid trust raises; missing/fault produces U |
| Issue result | Verifier; chain valid and append durable | Verification bundle in ledger | Append failure returns no verdict; content-addressed identity |
| Replay | Trusted replay runner; pinned versions | None | Chain or result mismatch rejects |

Undefined runtime transitions are unavailable: there is no transition API to accept
or silently perform them. Future states retained by design: draft, validation,
approval pending, authorized, pre-verification, executing, observing, suspended,
post-verification, collecting evidence, recovering, escalated, blocked, rejected,
timed out, cancelled, completed. Implementing those requires Phase 2 actor/guard,
budget, side-effect, durable transition and restart acceptance tests.
`execution_status` in Claim and Verdict is reported status, not a lifecycle state.
`verdict` is independently computed. `attestation_status` is always not-issued.
