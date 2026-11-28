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

Completion audit corrections in engine 0.1.1 preserve the frozen semantics:
incompatible same-source snapshots cannot be combined; bank-only records cannot
be ignored; blank currencies cannot be authoritative money observations; UNKNOWN
conditions cannot claim sufficient assurance. Each defect was reproduced before
its fix and has a regression plus targeted mutation. No approval requirement or
success condition was weakened. Read-only replay and standard-library trace
coverage improve reproducibility without new dependencies. Historical records
retain their original engine version.


## ADR: Owner-authorized local controlled-loop MVP after Phase 1 merge

The owner requested completion of ContractLoop after the kernel gate passed and
PR #1 merged. Extend the product with a local synthetic execution loop, while
preserving the verifier's point semantics and all historical evidence. Use one
SQLite transaction boundary for controlled effects, receipts and audit, rather than
claiming exactly-once external actions. Keep executor claims untrusted. Approve
whole execution contracts and dependency plans; never let generated drafts approve
themselves. Attest only an independently verified, fresh current snapshot. Preserve
historical verdicts while separately expiring/revoking certificates. Limit
composition to one tenant/resource store, and mark production identity, arbitrary
temporal predicates and external compensation as unsupported. Leave shipping and
ontology integrations paused. Source, regression, mutation and replay evidence
must accompany these scope additions; no automatic merge is introduced.
