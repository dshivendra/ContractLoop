# Final evidence report — Phase 1

Synthetic reference gate: **PASS**. This establishes the bounded local kernel acceptance gate under the documented trust assumptions. It does not complete the full architecture or demonstrate enterprise impact.

Baseline commit: `f5c1f70aa2784173ca62af8bc46b95b81c855384` (new repository containing the supplied handoff). Python 3.12.14. No pre-existing project or baseline test suite was available. No external repository, deployment or financial data was accessed.

## Reuse completed

- Original Loop Engine v0.8.8 dataclasses are preserved byte-for-byte and integrated through an untrusted-claim adapter.
- Contract Loop graph/catalog and original structural validator are included. Its evidence envelopes have a claim adapter.
- Installed Pydantic, JSON Schema validation, SQLite and standard-library cryptography/testing are integrated.
- Legacy success is UNKNOWN without observations and FAILURE against incorrect trusted state; this is covered by integration tests.

## Executed checks

| Command | Exit | Observed result |
|---|---|---|
| `python -m unittest discover -v` | 0 | 40 tests passed; 0 failures/errors |
| `python integrations/contract_loop_reference/validate_graph_package.py` | 0 | 73 nodes / 142 edges; 694 skills / 567 agents; 9 steps / 7 contracts structurally valid |
| `python tools/validate_schema.py` | 0 | Draft 2020-12 schema valid; roundtrip accepted; empty conditions rejected |
| `python -m vcp` | 0 | Three legacy completed claims produce SUCCESS / FAILURE / UNKNOWN; all 3 replay |
| `python tools/run_acceptance.py` | 0 | Full gate PASS; commands, benchmark and mutation evidence persisted |

Initial validation: `python -m unittest discover -v` exited 1: 36 tests, 35 passing and one test error. The temporal test reused an approved contract version, correctly triggering immutable identity rejection. The test now creates a new version for revisions; a separate test verifies same-version revisions remain rejected. The next run passed 36/36. Four added bounded-input/baseline/stage tests bring the final run to 40/40.

Independent checks include the full binary Kleene tables, 480 classifier/coverage/fault combinations, 40 seeded financial row mutations, golden/adversarial fixtures, restart replay and seven source mutations detected by assertion failures. No code statement/branch coverage percentage was measured.

## Synthetic benchmark

14 distinct scenarios × 5 repetitions = 70 runs. Five repetitions primarily support latency measurement, not independent statistical confidence.

| Metric | Result / denominator |
|---|---|
| Expected verdict matches | 70 / 70 |
| False success | 0 / 65 expected non-success runs |
| False failure | 0 / 5 expected-success runs |
| UNKNOWN | 25 / 70 total runs |
| Demonstrated violation detection | 40 / 40 |
| Resolved condition coverage | 430 / 560 condition slots |
| Durable verification latency | median 13.64 ms; p95 23.96 ms; max 69.76 ms |
| Exact verdict replay | 70 / 70; five injected-fault runs require the same injected fault |
| External verification calls | 0; local CPU/storage cost not priced |
| Historical invariant detection | Unimplemented; not measured |

Latency includes contract validation and SQLite audit persistence and excludes fixture construction/collection. All test data are synthetic INR integer minor units. False-success results are not a guarantee about real enterprises or arbitrary contracts.

## Mutation evidence

| Deliberate source mutation | Detected by independent assertion |
|---|---|
| violation-becomes-success | Yes |
| missing-evidence-success | Yes |
| failure-criterion-wrong-polarity | Yes |
| executor-overrides-verifier | Yes |
| skip-scope-check | Yes |
| accept-stale-evidence | Yes |
| skip-evidence-signature | Yes |

## Evidence paths

- `evidence/acceptance_results.json`: actual commands, exit codes, complete unittest logs, mutation logs, benchmark rows, runtime versions and source hashes.
- `evidence/benchmark.sqlite`: immutable contract and all verification input/result bundles; audit head `ef1a55b12fe98b67305104e409d94b9ae92c3f45042927ea2e0e8e6a0916bd26`.
- `evidence/fixtures/`: authoritative synthetic databases for each scenario.
- `evidence/snapshots/<sha256>.json`: content-addressed source artifacts referenced by evidence artifact_hash.
- `evidence/approved_contract.json` and `CONTRACT_SCHEMA.json`: reference contract and generated portable structural schema.
- `evidence/initial/`: retained earlier acceptance run; final results are at evidence root.
- `integrations/source_provenance.json`: archive hashes for inspected reuse packages.

## Files and requirement status

Added `pyproject.toml`, `.gitignore`, `README.md`, the 12 required architecture/specification/schema files, this report, `INTEGRATION_REPORT.md`, `vcp/` kernel/collector/integrations, `tests/test_kernel.py`, `tools/` acceptance/schema checks, `integrations/` reference catalog/provenance and `evidence/`. `HANDOFF.md` remains the baseline input. No unrelated user files were edited.

Phase 1 core gate and documentation: passed for the supported reference slice. Full requirement and invariant statuses, including partial/deferred requirements, are enumerated in REQUIREMENTS_TRACEABILITY.md and SYSTEM_INVARIANTS.md. Structural schema validation is not semantic intent alignment.

## Limits and next decision

Trust is local: public fixture HMAC keys, collector/kernel/runtime, authoritative fixture setup and database host are in the TCB. Same-process or database-admin attackers are not isolated. Full-chain replacement/truncation cannot be detected without an external checkpoint. This prototype does not provide production tenant isolation, a trusted clock or live state discovery.

Only V3 point observations are implemented. Historical preconditions, always/eventual/stability/deadline checks and higher requested assurance return UNKNOWN. Authorization is an observed fixture fact, not preventive enforcement. Fault replay needs the same recorded injected RuntimeError; ordinary replay intentionally rejects changed computation. No hard OS execution time/memory sandbox, cloud/LLM adapter, executor, recovery, composition, attestation, expiry/revocation or monitoring is implemented.

Recommended next decision: review and freeze this Phase 1 gate, then separately authorize a narrow Phase 2 adapter with concrete state, action and ownership boundaries. Phase 2 was not started.
