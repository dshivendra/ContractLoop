# Available components and integration decisions

Checked the current workspace and ancestor AGENTS.md locations. No project,
repository, tests, or applicable AGENTS.md was present. A local minimal Python
project was initialized. Baseline commit:
`f5c1f70aa2784173ca62af8bc46b95b81c855384` (supplied HANDOFF.md only).
No external repository was selected, accessed or modified.

Earlier user-owned packages were found by title search, materialized and inspected.
The existing source files, evaluator, storage, evidence schema and graph bindings
were reviewed before choosing the bridge. Original archive hashes are retained in
`integrations/source_provenance.json`.

| Available component | Observed capability | Actual integration |
|---|---|---|
| Loop Engine v0.8.8 route execution proof | Frozen Observation/Evidence dataclasses; independent evaluator; JSON persistence | Original models.py copied byte-for-byte into vcp/integrations; typed Observation → ImportedClaim adapter, with integration tests |
| Contract Loop complete graph v1 | 73 nodes, 142 edges, 694 catalog skills, 567 agent rows, 7 contracts, 9 workflow steps | Preserved reference package and its structural validator; graph evidence envelope → ImportedClaim adapter |
| Pydantic 2.13.4 | Installed runtime | Frozen schemas, exact scalar types, validation, recursive AST and generated JSON Schema |
| jsonschema 4.26.0 | Installed QA dependency | Draft 2020-12 schema check and independent structural validation of generated contracts |
| Python 3.12.14 stdlib SQLite | Installed runtime | Transactional read-only collector, durable ledger, append-only triggers and replay |
| hashlib / hmac / unittest | Python stdlib | Content hashes/provenance, golden/generated tests, isolated mutations |
| pytest, Hypothesis | Not installed | unittest and exhaustive/seeded cases used; no claim of Hypothesis coverage |
| CEL, z3-solver | Python packages not installed | Restricted AST and bounded exact comparison-cell validation; no installation |
| Temporal, LangGraph, OpenTelemetry API | Python packages not installed | Deferred; Phase 1 has no durable execution or distributed observability need |
| OPA executable | Not found on PATH | Deferred; no action-policy boundary in Phase 1 |
| GitHub, AWS and other connected providers | Tool metadata exposed | Not connected to kernel or queried for production data; later adapters require concrete contracts |

Catalog structure validation passed with the original script. Its counts establish
metadata consistency only: they do not prove any catalog skill/agent is installed,
executable, safe, or compatible with this kernel. No catalog-driven agents were spawned.
Other versions of Loop Engine were not exhaustively audited; the identified v0.8.8
and complete graph package were the bounded reuse candidates for this request.

The old evaluator excludes some untrusted source names but does not authenticate
each claim; its JsonStore overwrites named JSON files. The graph envelope has
artifact digests and producer metadata but no required authenticated approval/trust
binding. These are concrete reasons to reuse their data formats without delegating
verdict or authoritative evidence authority to them. Every legacy report remains a
claim until the independent collector reads current authoritative fixture state.
