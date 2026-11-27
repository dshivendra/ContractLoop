# Architectural decisions

| Decision | Concrete reason | Alternative / consequence |
|---|---|---|
| Reuse installed Pydantic 2.13.4 | Immutable validation and JSON Schema already available | No handwritten JSON parsing/type coercion |
| SQLite and stdlib HMAC/hash | Durable local audit and explicit provenance checks without network | Host/key holders remain in TCB; no asymmetric attestation |
| Restricted comparison AST | Eight reference facts only need eq/ne/ge/le plus AND/OR/NOT | CEL not installed; do not install a broader expression language speculatively |
| Exact bounded comparison satisfiability | Reject contradictions including nested boolean combinations | At most 100,000 scalar cells, 128 atoms, 256 nodes, depth 32; larger contracts rejected for revision |
| unittest plus deterministic generated tests | pytest/Hypothesis unavailable; tests can run now | No Hypothesis shrinking, no claim of full property-testing coverage |
| Reuse original Loop Engine dataclasses | Existing user-owned reports can enter the new boundary | Original evaluator's string source checks and overwriteable JsonStore cannot establish current assurance |
| Preserve graph catalog and validate structure | Existing IDs/bindings remain reviewable | Catalog entries are not installed tools or verified agent implementations |
| JSON Schema QA uses installed jsonschema | Cross-check actual generated schema independently | Semantic approval/consistency checks remain Python validation |
| Historical checks remain UNKNOWN | A snapshot cannot establish a past invariant or precondition | Runtime and temporal state observation deferred |

No semantic architecture changes were made. Implementation limits are explicit.
Z3, TLA+/TLC, OPA, Temporal, PostgreSQL, OpenTelemetry, LangGraph/MCP and
in-toto/Sigstore were not integrated: no Phase 1 acceptance requirement currently
needs those runtimes. See availability evidence in `INTEGRATION_REPORT.md`.
