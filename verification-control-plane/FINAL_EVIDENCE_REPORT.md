# Final evidence report — Phase 1 completion

**Supported Phase 1 gate: PASS**, engine `vcp-kernel/0.1.1`. Four reproduced
correctness/validation defects are fixed, independent regressions are added, and
standalone read-only replay and measured line coverage are delivered. Shipping
automation stays paused. Later phases and production hardening remain deferred.

The frozen architecture and success requirements were preserved. The previous
engine could accept a combination of observations that no single source snapshot
satisfied; this violated the existing trustworthy-evidence requirement. The
collector also ignored bank-only rows and accepted blank currency fields, while
UNKNOWN evaluations could overstate assurance. These are implementation fixes to
existing conditions, not relaxed contracts or additional product scope.

## Reproduced defects and corrections

| Defect | Pre-fix evidence | Correction / regression |
|---|---|---|
| Mixed failing snapshots produce false SUCCESS | Both full batches FAIL; selecting TRUE facts across false_success and wrong_match yielded SUCCESS | Quarantine authenticated source/resource/state groups with multiple snapshot hashes; mixed bundle now UNKNOWN |
| Bank-only input silently ignored | Adding BANK-ONLY produced SUCCESS with no classification | Matching/classification require coverage of all bank IDs; now FAILURE |
| UNKNOWN with sufficient-assurance label | An unsupported always condition returned UNKNOWN with synthetic-point assurance | Any UNKNOWN mandatory condition forces insufficient assurance |
| Empty currency accepted as financial evidence | Collector accepted a bank row with currency='' | Reject non-integer money and empty/whitespace-only currency observations |

`python -m unittest tests.test_completion.CompletionRegressions -v` initially
exited 1 with three assertion failures (the first three rows). The separate
empty-currency regression also exited 1 before its fix. All are now passing.
The implementation-change baseline was local commit
`9929b50`; remote PR head before this completion pass was
`fb9e0a03a2c1ba5a5b91f909cbf1722859bf23d7`. The original empty-project handoff
baseline remains `f5c1f70aa2784173ca62af8bc46b95b81c855384`.

## Final executed validation

- Kernel/integration/regression tests: **52 passed**, zero failures/errors.
- Exact benchmark outcomes: **80/80**, from 16 distinct scenarios repeated five times.
- Targeted source mutations detected: **11/11** by assertion failures.
- Executable-line coverage: **749/801 (93.51%)** using CPython trace over tests and demo. No branch coverage claim.
- Draft 2020-12 schema validation, committed-model schema equality and original graph structural validation passed.
- Separate read-only replay CLI reproduced every verification result, including five explicitly reinstated fixture faults.
- Additional regression checks cover distinct-source independence, signature poisoning, coherent re-observation, exact engine version, twelve concurrent durable ledger appends and read-only write rejection.

| Command | Exit |
|---|---|
| `python tools/run_coverage.py --output /workspace/scratch/11d07626f374/phase1-final-validation/coverage` | 0 |
| `python integrations/contract_loop_reference/validate_graph_package.py` | 0 |
| `python tools/validate_schema.py` | 0 |
| `python tools/replay_audit.py --database /workspace/scratch/11d07626f374/phase1-final-validation/benchmark.sqlite --fault-plan /workspace/scratch/11d07626f374/phase1-final-validation/fault_plan.json` | 0 |

The top-level executed command was
`python tools/run_acceptance.py --output /workspace/scratch/11d07626f374/phase1-final-validation`
(exit 0). Exact subprocess output and failures from mutation experiments are in
`evidence/completion/acceptance_results.json`. Independent classifier tests retain
480 truth/coverage/fault combinations; forty seeded financial row mutations retain
a separate hardcoded expected-outcome oracle. These are bounded synthetic tests,
not a proof for arbitrary contracts or real organizations.

## Metrics

| Metric | Actual result |
|---|---|
| False success | 0/75 expected non-success runs |
| False failure | 0/5 expected-success runs |
| UNKNOWN | 30/80 total runs |
| Demonstrated violation detection | 45/45 |
| Resolved evidence-condition slots | 470/640 |
| Durable verification latency | median 13.59 ms; p95 20.03 ms; maximum 30.17 ms |
| External benchmark calls / monetary cost | 0 external calls; local CPU/storage cost not priced |
| Historical invariant detection | Deferred; not measured |

## Reproduce and inspect

```bash
cd verification-control-plane
python -m pip install -e '.[qa]'
python tools/run_acceptance.py --output /tmp/phase1-new-run
python tools/replay_audit.py --database /tmp/phase1-new-run/benchmark.sqlite --fault-plan /tmp/phase1-new-run/fault_plan.json
python -m vcp
```

Choose a fresh empty output directory. The gate never overwrites committed prior
history. Evidence paths:

- `evidence/completion/acceptance_results.json`: actual commands, logs, mutations, rows and source hashes.
- `evidence/completion/coverage/coverage.json`: exact line-coverage denominators and missed lines per kernel module.
- `evidence/completion/benchmark.sqlite`: immutable approved contract and all eighty evaluation bundles.
- `evidence/completion/fixtures/` and `snapshots/`: authoritative synthetic state and content-addressed artifacts.
- `evidence/completion/fault_plan.json`: explicit trusted fixture fault assumptions for replay.
- `evidence/baseline/FINAL_EVIDENCE_REPORT_v0.1.0.md`: retained original report; original evidence databases remain unchanged.
- `FILE_MANIFEST.json`: SHA-256 manifest of the current Phase 1 files except itself, SQLite coordination sidecars and git internals.

Current completion audit head: `20396228c703e523234b0f889d961effb72bd9e06e69ffd69e88702f62ea1499`.

## Requirement status and limitations

All twelve required design/schema artifacts are present. Phase 1 code, golden and
adversarial acceptance, traceability, deterministic replay, mutation experiments
and synthetic measurements are complete for the declared supported slice. No
known Phase 1 code defect remains from this gate. Detailed implemented/partial/
deferred statuses remain in REQUIREMENTS_TRACEABILITY.md and SYSTEM_INVARIANTS.md.

The trusted local host, code, collector, fixture author, policy keys, clock and
state-version inputs remain the TCB. Fixture keys are public. There is no hostile
same-process isolation, external audit checkpoint or production tenant boundary.
Snapshot coherence checks provenance consistency, not the factual honesty of a
compromised collector. Eleven targeted mutations are not exhaustive mutation
coverage; executable-line coverage is not branch/path coverage.

Only V3 point evaluation is supported. Historical preconditions, temporal windows,
live state discovery, action authorization/enforcement, recovery, external effect
idempotency, composition, attestations, expiry/revocation, NL compilation and
production integrations remain outside Phase 1. The previous 0.1.0 audit records
are immutable and pinned to that older engine; new code rejects their exact
replay rather than rewriting past results. The original report's zero observed
false successes applied only to its original fixture set; the expanded audit
exposed defects that those tests did not cover.

Shipping automation is not activated or expanded by this work. The PR remains a
reviewable change; human review/merge and authorization for any later phase are
separate from the completed Phase 1 engineering gate.
