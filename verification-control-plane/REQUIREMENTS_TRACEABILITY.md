# Requirements traceability

## Current controlled-loop extension

The Phase 1 mappings below remain historical kernel traceability. The current
runtime requirements→implementation→tests mapping is:

| Requirement | Source | Regression evidence |
|---|---|---|
| Draft/context/approval | planning.py, runtime_models.py, runtime.py | test_api draft/approval flow; changed-contract rejection |
| Controlled action and durable recovery | runtime.py, storage.py | test_runtime CAS, idempotency, lost ACK, atomic rollback, bounded retry |
| Invariants, budgets, termination | runtime.py | test_runtime and test_runtime_guards UNKNOWN/violation, timeout, duration, budget tests |
| Composition and global predicates | composition.py, runtime.py | test_composition parent proof, conditional/failed dependencies, global violation |
| Attestation and revocation | runtime.py | freshness, drift, expiry, tampering and monitor tests |
| API and audit | api.py, audit.py, loop_cli.py | test_api auth/body/input/CLI; test_runtime_guards trajectory tampering |
| Learning governance | runtime.py | revision proposal remains unapproved and hash unchanged |

LOOP_MVP_REPORT.md records production boundaries and final machine evidence.

## Verification kernel reference

| Requirement | Implementation | Evidence / status |
|---|---|---|
| Inspect baseline/reuse | Empty workspace inspected; handoff baseline commit; two earlier source packages reviewed | INTEGRATION_REPORT; implemented |
| Typed immutable approved contracts | models.py, security.py, storage.py | Schema QA + approval/immutability tests; implemented |
| Restricted predicates / non-vacuity / contradictions | logic.py finite comparison-cell satisfiability | LogicTests + contract rejection tests; implemented within budgets |
| Correct three-value and failure polarity | classify, evaluate, negate | Exhaustive truth/classification oracle + targeted mutation; implemented |
| Trusted outcome evidence distinct from claims | evidence.py; read-only reconciliation collector | Golden, legacy integration, signature and isolation tests; implemented |
| Independent financial reference | Per-currency minor units, pinned source hash, IDs/matching/destination facts | Nine adversarial fixture variants + mixed-snapshot adversary + 40 generated destination cases; implemented |
| Durable audit and replay | Ledger / VerificationEngine | Restart, tamper detection, benchmark input/result replay; implemented with stated fault assumptions |
| Tamper/fabrication/staleness/conflict/error handling | Validation and UNKNOWN guard | Named kernel tests; implemented |
| Independent verdict logic validation | 480 mandatory-classification combinations, Kleene table, eleven isolated source mutations | run_acceptance.py / acceptance_results.json; implemented |
| Bounded evidence/expressions | count, AST depth/nodes, satisfiability cap | Budget and infinite iterator tests; implemented; hard time/memory sandbox deferred |
| Coverage / latency / cost metrics | 80-run benchmark (16 scenarios × 5 repetitions) with full denominators | Final report and executable-line coverage; branch coverage and monetary cost unmeasured |
| Required design artifacts | Named Markdown files + generated CONTRACT_SCHEMA.json | Included |
| V0 natural-language intent/feasibility validation | Owner rationale and alignment reference only | Partial; machine semantic intent validation Phase 4 deferred |
| Full domain model and all typed runtime ports | Phase 1 schemas and concrete APIs only | Domain/interface specs map every concept; later runtime models deferred |
| Runtime authorization/lifecycle/recovery | No execution authority | Phase 2 deferred |
| Parent/global verification/attestation/revocation | No such result issued | Phase 3 deferred |
| Production integration / tenant enforcement | No real infrastructure accessed | Phase 5 deferred |

Phase 1 acceptance gate is the synthetic kernel gate, not completion of all frozen
architecture requirements. No placeholder path is marked implemented. Success on
these fixtures does not establish correctness for arbitrary business contracts.

Completion evidence: `evidence/completion/acceptance_results.json` and its
`coverage/coverage.json` supersede the original baseline measurements. The
read-only replay command, explicit fault plan, four reproduced defect fixes,
regression tests and source hashes close the remaining Phase 1 engineering items.
Later-phase rows remain deferred, not failed or represented as implemented.
