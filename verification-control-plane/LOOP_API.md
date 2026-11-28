# Local ContractLoop JSON API

Every endpoint except `GET /health` requires a server-configured bearer token.
A JSON object's `role` or `tenant` cannot elevate the authenticated principal.
The server holds fixture approval/collector keys. An owner token explicitly
requesting `/approve` authorizes signing that draft; compilation alone never signs.

| Method and path | Role | Input / output |
|---|---|---|
| GET /health | Public | Local synthetic service status |
| POST /draft | Owner | `{intent: {id,tenant,owner,objective,recipe:"synthetic-reconciliation"}}` → context and unsigned kernel draft |
| POST /approve | Owner | `{kernel,executor,deadline,limits?:{…}}` → immutable execution contract and signed approval |
| POST /tasks | Owner | `{task_id,execution_id,contract,approval}` → durable draft task |
| GET /tasks/{id} | Authenticated tenant role | Durable lifecycle, verdict and consumed budgets |
| POST /tasks/{id}/run | Owner/controller | `{}` → bounded execution/observation/recovery result |
| POST /tasks/{id}/cancel | Owner | `{}` → durable cancellation |
| POST /tasks/{id}/verify | Verifier | `{}` → independently collected kernel verdict; consumes evidence allowance |
| POST /tasks/{id}/attest | Verifier | `{}` → signed certificate only for completed verified SUCCESS |
| POST /tasks/{id}/actions | Executor | Full typed `Action` envelope → receipt; must match route task and approved scope |
| POST /tasks/{id}/proposals | Owner/controller/verifier | `{rationale,evidence_ids?:[]}` → unapproved revision proposal |
| POST /compositions | Owner | `{plan,approval}` → registered plan hash before parent creation |
| GET /attestations/{id} | Owner/reader/verifier | Current VALID / EXPIRED / REVOKED; detected drift durably revokes |
| POST /attestations/{id}/revoke | Owner/verifier | `{reason}` → durable revocation |
| POST /monitor | Verifier | `{}` → sampled current validity of every certificate |
| GET /audit | Owner/reader/verifier | Checked append-only chain and trajectory records |

Requests have a 64-KiB body limit, five-second socket read timeout and duplicate
JSON-key rejection. Chunked bodies are unsupported. Errors use HTTP 400 (invalid
input/transition), 403 (authentication/authorization), 404 (unknown resource),
409 (runtime guard), or 503 (infrastructure fault, never success). Bodies and bearer
tokens are not logged. Mutations through this server are serialized. Independent
SQLite gateway clients still use transaction locks, CAS and idempotency receipts.

## Explicit approval workflow

1. Obtain a draft with `/draft`; review context and all typed predicates.
2. Send that kernel to `/approve` with an authorized owner token, an allowed
   executor and a Unix epoch deadline. `limits` contains `ExecutionContract`
   execution controls, including max_actions, max_attempts, max_recoveries,
   max_collections, max_budget_units and attestation_ttl_seconds.
3. Submit the returned contract and approval to `/tasks` with new task/execution IDs.
4. Send `{}` to `/tasks/{id}/run`; inspect both lifecycle and verdict.
5. A verifier token can issue an attestation with `/tasks/{id}/attest`.
6. Read validity or sample `/monitor`; history is preserved when validity changes.

Typed schemas are committed as `CONTRACT_SCHEMA.json`, `EXECUTION_SCHEMA.json`,
`COMPOSITION_SCHEMA.json` and `ATTESTATION_SCHEMA.json`. Semantic checks additionally
run in the Pydantic models and runtime. Canonical hashes cover immutable content;
approval envelopes are separate. An action idempotency key binds its whole request,
not only an executor's description.

## Approved composition

The Python API exposes `Composition`, `Dependency`, `approve_composition` and
`LoopController.register_composition`. A plan pins existing child task contract
hashes and the future parent's kernel hash. The owner signs the plan, registers
it, then binds its hash into the parent's signed `ExecutionContract`.

Plans form an immutable, bounded DAG: children exist before parents, duplicate or
self dependencies are rejected, depth is at most eight and traversal is bounded.
Conditional dependencies require a typed TRUE/FALSE applicability result; UNKNOWN
blocks execution. Parent verification separately evaluates its own kernel and
sampled global predicates, then refreshes child proofs within their evidence
budgets. Exhausted allowances yield UNKNOWN. Certificates bind child contract,
snapshot and validity bounds. Every member uses the same SQLite resource; this
is not a distributed transaction protocol.
