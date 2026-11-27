# Implementation plan and phase boundary

Phase 1 implementation delivered: immutable Pydantic contracts/approval, restricted
AST and bounded consistency validation, tri-valued verification, signed scoped
evidence/freshness/conflict resolution, durable SQLite audit, legacy claim adapters,
synthetic reconciliation collector, independent acceptance and mutation campaign.

Run evidence and remaining limitations are in FINAL_EVIDENCE_REPORT.md. Before any
Phase 2 authorization, review the synthetic gate and agree the first real adapter's
authoritative data, ownership, trust boundaries, input baseline and acceptance checks.
Do not automatically proceed beyond Phase 1.

Future work retained without implementation: Phase 2 durable lifecycle/action
gateway, preventive authorization, budgets, CAS/idempotency and recovery; Phase 3
composition/global outcomes and attestations with expiry/revocation; Phase 4 context
and natural-language compilation with independent validation; Phase 5 organization
adapters/API/isolation/production hardening. No cloud/LLM/orchestrator selection is
required until a concrete test justifies it.

Semantic change requires the handoff's deficiency, reproducible failing scenario,
impacted invariants, alternatives, compatibility assessment, tests and owner approval.
Adding dependencies or adapters must preserve the contract hash and truth semantics.

Phase 1 completion audit (engine 0.1.1): the remaining reproduced evidence and
collector defects are fixed; standalone readonly replay, explicit fault plans,
line coverage and updated reproducible evidence are delivered. No outstanding
Phase 1 code defect is known from the completed gate. See FINAL_EVIDENCE_REPORT.md
for actual results and exact limitations. Shipping automation remains paused;
review/merge and later phases are separate decisions.
