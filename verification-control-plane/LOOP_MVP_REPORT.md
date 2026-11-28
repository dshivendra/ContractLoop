# ContractLoop local MVP completion

The owner requested completion of ContractLoop after the Phase 1 gate passed and
PR #1 merged. Package 0.2.0 adds a functioning controlled execution runtime around
the existing kernel. Shipping automation and optional ontology work remain paused.

## Delivered implementation

| Requirement | Concrete implementation |
|---|---|
| Intent and context | Typed registered reconciliation recipe; transactional snapshot discovery; draft compilation separated from approval |
| Contract governance | Full immutable execution content hash, owner HMAC approval, pinned kernel approval and runtime version |
| Control and execution | Durable allowed transitions, tenant/actor/action/resource gates, deadline/duration/action/attempt/compute bounds |
| Effects and crash recovery | Single SQLite transaction for effect, counters, deterministic request receipt and hash-chained action event; restart reuses committed receipts |
| Invariants and prohibited effects | Before/after typed guards, input/resource mutation rejection, rollback to savepoint, sticky demonstrated violation |
| Observation and verification | Independent signed read-only collector and existing three-valued verifier; claim never establishes success |
| Resolution | Authorized bounded retries; bounded evidence collection; durable cancellation, timeout, blocked/escalated outcomes |
| Composition | Approved bounded dependency DAG, conditional applicability, child contract pins, independent parent predicates and sampled global predicates |
| Attestation | Signed scope/snapshot/verdict binding; atomic current-state issuance; freshness, authorization and child expiry bounds |
| Monitoring | On-demand and one-second service polling; durable drift/manual revocation; historical verdict preserved |
| Audit and learning | Append-only action/state trajectory, exact kernel replay and read-only runtime projection consistency checks; revision proposals stay unapproved |
| Usability | Runnable CLI demo, artifacts, status/audit/monitor commands, local authenticated JSON API and committed schemas |

## Validation

The machine-readable final evidence lives in `evidence/loop-mvp/`; the combined
acceptance gate records commands, exit codes, coverage, source hashes, mutations
and benchmark results. `loop_acceptance.json` contains runtime scenarios and
read-only trajectory audit results; `benchmark.sqlite` contains kernel records.
No historical evidence is overwritten. Exact final counts and CI results are in
the final evidence entry below and the pull request.

The first runtime pass exposed a draft-state timeout transition defect. Its
regression now checks durable timeout and zero effects. Further checks distinguish
unknown invariants from demonstrated violations, reject evidence renewal without
reobservation, prevent late verification from completing success, exercise lost
acknowledgements and atomic audit rollback, detect drift/tampering, and serialize
concurrent duplicate requests to a single committed effect.

## Supported boundary and remaining production work

This completes the **local synthetic MVP**, not a production or domain-general
platform. Identity separation is logical within one trusted process. The OS,
adapter, fixture author, controller and database administrator remain trusted.
Public fixture keys are unsuitable for production. The attester can use its own
key through the Python constructor; the fixture CLI reuses the approval key.

Transaction rollback provides local compensation. No external payment, cloud,
filesystem, network or irreversible action adapter is implemented. Budget units
are explicit synthetic action units, not actual billing measurements. The compiler
supports one registered recipe, not free-form natural language. Runtime guards
observe transaction boundaries; the kernel retains V3 point-in-time semantics.
No general always/eventually/stability or arbitrary intermediate-history proof is
claimed. Dependency composition shares a single tenant/resource database.

The serving process samples certificates once a second and reports monitor faults;
it cannot detect every transient change between samples or operate while stopped.
Production deployment would require external identity/key custody, isolated
executor/collector authorities, adapter-specific idempotency and compensation,
service limits, distributed resource protocols and operational monitoring. These
are explicit boundaries, not silently passed tests or deployed services.

The audit chain detects alteration through the supported API. An administrator
can replace a database and its chain; external anchoring is not implemented.
The runtime auditor checks projections, bounds, transitions, receipts and exact
kernel replay. It does not re-execute historical effects against an external world.

## Final executed gate — 28 November 2026

- `python -m unittest discover -s tests -q`: **98 passed**, zero failures/errors.
- Combined `tools/run_acceptance.py`: **PASS**, all six recorded subprocess checks passed.
- Kernel outcomes/replay: **80/80** cases; false SUCCESS **0/75** negative cases.
- Runtime outcomes/trajectory audits: **21/21** cases across seven scenarios repeated three times.
- Safety mutations: **11/11 kernel + 8/8 runtime detected by assertions**.
- Shipping policy regression tests: **17 passed**; automation remains paused.
- Coverage: **1645/1751 executable lines (93.95%)**, CPython executable-line trace including spawned API threads;
  this is line coverage, not branch coverage. Subprocess server lines are exercised
  by the service test but are not attributed back into the parent trace.
- `compileall` completed successfully. Archived SQLite evidence extracted with every
  SHA-256 matching, and both kernel replay and runtime trajectory audit passed.

The evidence source hashes match the final Python package. Local git baseline is
recorded separately from the remote main parent `4edf789f7683dda12957208068443133c54b513e`.
The local and hosted commits differ in layout because the GitHub project nests the
package under `verification-control-plane/`; source hashes provide exact binding.

New SQLite evidence is losslessly compressed in `evidence/loop-mvp/sqlite-evidence.zip`
with `sqlite-evidence-manifest.json`; previous evidence directories remain unchanged.
Extract to a new directory to reproduce read-only replay:

```bash
unzip evidence/loop-mvp/sqlite-evidence.zip -d /tmp/contractloop-replay
python tools/replay_audit.py --database /tmp/contractloop-replay/benchmark.sqlite --fault-plan evidence/loop-mvp/fault_plan.json
python -m vcp.loop_cli audit --database /tmp/contractloop-replay/runtime/happy-0.sqlite
```

Dependency execution is sequential with conditional branches. Parallel workflow
scheduling is not implemented. Budgets apply per task; no aggregate monetary cost
budget across the DAG is claimed. Hosted CI and the exact pushed commit are
recorded in the pull request, independently of this local evidence.
