# Acceptance test specification

Run `python -m unittest discover -v` and `python tools/run_acceptance.py` as in README.
Tests read synthetic fixtures independently from executor claims; expected business
outcomes are fixed in golden cases and a separate row-level generated-case oracle.

| Case | Expected | Test/evidence |
|---|---|---|
| Correct outcome and trusted complete facts | SUCCESS | correct_execution_success |
| Executor claims success, wrong amount/state | FAILURE | false_completion_and_partial_demonstrated |
| Missing mandatory evidence | UNKNOWN | missing_evidence_is_unknown |
| Partial observed destination | FAILURE | golden partial fixture |
| Partial claim without observations | UNKNOWN | partial_claim_without_outcome_evidence_unknown |
| Empty/tautological/contradictory/misbound contracts | Reject | no_empty_contradictory_tautological_contracts |
| Contract/evidence tampering or fabricated signature | Reject contract / UNKNOWN fact | tamper and signature tests |
| Stale/future evidence; fresh recollection | UNKNOWN; fresh SUCCESS | stale_future_and_recollection |
| Authenticated disagreement / ID equivocation | UNKNOWN | conflict and equivocation tests |
| Verifier faults | UNKNOWN unless another violation established | errors_never_success |
| Failure criterion true | FAILURE | failure_criteria_correct_polarity |
| Recovery/historical/production assurance inferred from snapshot | Never SUCCESS | temporal/stage/assurance tests |
| Source changed together with output | FAILURE via approved baseline | source_baseline_drift_detected |
| Infinite observation iterable | Bounded read; UNKNOWN | unbounded_input_iterator_is_bounded |
| Legacy passing report imported | Claim only; needs fresh evidence | IntegrationTests |
| Restart and reordered inputs | Exact deterministic replay / idempotent writes | replay_restart_canonical_and_order_independence |

Mutation runner copies source and tests into temporary directories, changes one
behavior, runs a focused independent acceptance test and requires an assertion
failure. Import/infrastructure errors do not count as detection. Mutations: false
violation → success; missing facts → success; inverted failure polarity; executor
override; skipped scope; skipped freshness; skipped signature. This is a targeted
seven-mutation campaign, not exhaustive mutation coverage.

Benchmark: 14 distinct scenarios × 5 repeated runs = 70 evaluations. Repetition is
for latency; it is not 70 independent business scenarios. Three-valued classifier
oracle covers 480 combinations; generated reconciliation test covers 40 seeded
destination mutations. Historical invariant detection, execution controls, process
crash effects, full concurrent mutations, production tenant boundaries and actual
attestation validity are deliberately untested/deferred.
