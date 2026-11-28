# Delivered controlled-loop scope and production boundary

Phase 1 passed its synthetic acceptance gate and was merged in PR #1. The owner
then authorized completing ContractLoop. The delivered 0.2.0 local MVP wraps the
unchanged independent kernel with approved execution, durable lifecycle/gateway,
CAS/idempotency, atomic effect receipts, bounded recovery, conditional dependency
DAGs, independent parent verification, signed expiring attestations, sampled drift
revocation, context/draft compilation, a loopback API/CLI and unapproved learning
proposals. LOOP_MVP_REPORT.md and LOOP_API.md define the supported behavior.

The default recipe is synthetic SQLite reconciliation. The combined acceptance
command is `python tools/run_acceptance.py --output NEW_EMPTY_DIRECTORY`. It runs
kernel and runtime tests, schemas, benchmarks, mutations and replay, and records
actual source hashes. Historical Phase 1 reports and evidence are preserved.

Remaining production engineering requires an explicitly chosen real adapter and
its authoritative state, identity/key custody, isolated authorities, operational
quotas/monitoring, external effect idempotency/compensation and distributed resource
semantics. General natural-language compilation and arbitrary temporal verification
remain unsupported. No production service or cloud infrastructure is deployed.
Optional ontology integration and autonomous shipping remain paused.
