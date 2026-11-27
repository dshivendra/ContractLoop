# Architecture

Frozen handoff semantics remain unchanged. This implementation selects the bounded
Phase 1 slice: approved contract → authenticated point observations → independent
verification → durable result. `HANDOFF.md` retains the complete frozen architecture.

| Boundary | Implementation | Authority |
|---|---|---|
| Contract | Pydantic immutable typed AST, finite consistency check | Trusted synthetic approver |
| Approval | HMAC binds the complete contract hash and approval time | Fixture owner key |
| Observation | Read-only SQLite snapshot collector | Trusted adapter/fixture, separate executor identity |
| Evidence | Hash/HMAC, scoped bindings, freshness, fact/snapshot conflict checks | Trusted collector key and policy |
| Verification | Strong Kleene predicates and mandatory guards | Deterministic kernel |
| Persistence | SQLite append-only API, triggers, hash chain | Trusted database host |
| Legacy bridge | Loop Engine/graph output → Claim | Untrusted report only |

The kernel is domain-independent over strict boolean, integer and string facts.
Reconciliation meaning lives in a replaceable collector, never in verdict logic.
Artifacts are JSON; approved versions and result records cannot be replaced through
the repository API. One SQLite database serializes ledger appends. There is no
executor, action side effect, orchestration engine, deployment or web UI.

All classes, modules, collection signatures and keys execute inside one trusted
local process for this experiment. Logical separation does not provide process,
credential, tenant or OS isolation. External uncontrolled actions and malicious
administrators are outside the demonstrated assurance boundary.
