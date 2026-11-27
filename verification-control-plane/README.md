# Verification Control Plane — Phase 1

Independent contract-based verification over synthetic authoritative fixture state.
Execution status, verification verdict and attestation status are separate fields.
The executor never supplies a verdict. This package has no execution gateway.

Python 3.11+; runtime dependency Pydantic 2.13.4. QA uses jsonschema 4.26.0.
The supplied environment already had both installed. No dependencies were fetched.

```bash
python -m pip install -e '.[qa]'
python -m unittest discover -v
python -m vcp
python integrations/contract_loop_reference/validate_graph_package.py
python tools/validate_schema.py
```

For the full offline gate, including 70 synthetic cases, persisted evidence, exact
replay under the recorded fault assumptions, and seven isolated source mutations:

```bash
python tools/run_acceptance.py --output /tmp/contractloop-acceptance
```

Choose a new, empty output directory for each run. Historical `evidence/` stays
unchanged. Omitting `--output` selects `evidence/` and refuses an existing directory
with files. Unit tests use temporary files. Schema validation also rejects drift
between the committed schema and the current Contract model.
The command records real subprocess commands, exit codes and logs in
`acceptance_results.json` under the output directory; `FINAL_EVIDENCE_REPORT.md`
explains the original baseline results. GitHub Actions runs the same acceptance
command on Python 3.11 and 3.12 and uploads separate evidence for each run.

`vcp/reconciliation.py` creates synthetic fixtures. `collect()` reads them in one
SQLite read transaction. `VerificationEngine.verify()` validates approved contracts,
authenticates observations, evaluates predicates and writes an immutable audit record
before returning the verdict. `VerificationEngine.compute()` is a diagnostic pure
calculation; it does not issue a durable result. `replay()` checks chain integrity and
recomputes stored inputs with pinned engine/policy versions.

Existing Loop Engine dataclasses and the Contract Loop graph catalog are included.
`vcp/integrations/legacy.py` imports their reports as untrusted claims. It never
converts old `passed` flags, names, evidence references or artifact hashes into
authoritative Phase 1 observations. See `INTEGRATION_REPORT.md`.

Fixture HMAC keys are deliberately public and only demonstrate local trust wiring.
No real finance data, production infrastructure, cloud credentials, APIs, or LLMs
are used. Temporal verification, attestations, preventive authorization and execution
control remain deferred. This is an executable reference kernel, not a security
boundary against code running with the same process or database privileges.
