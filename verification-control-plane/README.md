# ContractLoop — controlled execution and independent verification

ContractLoop turns an approved typed contract into a bounded local execution loop:
intent → discovered context → compiled draft → owner approval → authorized action →
independent observation → verdict → recovery or attestation → drift monitoring.
The package is version **0.2.0**. The independent verification kernel retains
`vcp-kernel/0.1.1`; the added runtime is `controlled-loop/0.2.0`.

The implemented MVP uses synthetic reconciliation rows in one local SQLite database.
It includes durable lifecycle transitions, a guarded action gateway, atomic
side effects/receipts/audit, restart recovery, budgets, dependency DAGs, an
append-only trajectory, read-only audit replay, expiring signed attestations,
sampled drift revocation, revision proposals, and a loopback JSON API.

## Run the complete loop

Python 3.11+; runtime dependency Pydantic 2.13.4; QA dependency jsonschema 4.26.0.

```bash
python -m pip install -e '.[qa]'
python -m vcp.loop_cli demo --directory /tmp/contractloop-demo
python -m vcp.loop_cli status --database /tmp/contractloop-demo/loop.sqlite
python -m vcp.loop_cli audit --database /tmp/contractloop-demo/loop.sqlite
python -m vcp.loop_cli monitor --database /tmp/contractloop-demo/loop.sqlite
```

Use a new, empty demo directory. The demo executes a real local reconciliation
write, collects independent signed observations, verifies them, issues a certificate,
and writes the approved contract, result, trajectory and durable database.
The CLI prints `SUCCESS`, `completed`, `VALID` and the audit head on a normal run.
Certificates last at most 60 seconds in the default demo; historical SUCCESS
remains recorded after expiry or revocation. Running `monitor` samples current
state; `serve` also checks certificates every second while it is running.

## Local API

```bash
python -m vcp.loop_cli credentials --output /tmp/contractloop-tokens.json
python -m vcp.loop_cli serve --database /tmp/contractloop-demo/loop.sqlite --tokens /tmp/contractloop-tokens.json --port 8765
```

The credentials command exclusively creates a mode-0600 file with separate random
owner/verifier/reader/executor bearer tokens. It refuses to overwrite existing
credentials. The server binds only `127.0.0.1`. Supply `Authorization: Bearer TOKEN`
and `Content-Type: application/json`. Request payloads cannot assign their own roles.
See [LOOP_API.md](LOOP_API.md) for the explicit draft/approve/create/run sequence.
This is a local development interface; fixture signing keys are public.

## Validate

```bash
python -m unittest discover -s tests -v
python tools/run_acceptance.py --output /tmp/contractloop-acceptance
```

The combined gate runs the unit/integration/API tests with measured executable-line
coverage, kernel and runtime schema drift checks, graph validation, the original
80-case kernel benchmark and 11 mutations, the 21-case runtime benchmark and eight
additional mutations, and read-only replay. It refuses to overwrite historical
evidence. CI runs this same gate on Python 3.11 and 3.12. The older
`python -m vcp` verification-only demo remains available.

## Boundaries

Roles are logical identities in a trusted local process. The action transaction
provides exactly-once committed effects **only within this SQLite adapter**, not
across external services. Runtime invariants check transaction boundaries and
forbidden input/resource edits; arbitrary intermediate or external history is not
observed. Dependencies share this tenant/resource database; distributed composition
is unsupported. Parent success always requires its own independent predicates.

No real financial data, cloud infrastructure, paid APIs, LLM compiler, production
identity provider, general temporal verifier, external compensating transaction,
ontology integration or autonomous shipping is included. Monitoring samples state;
it cannot prove no transient drift between samples. Public fixture HMAC keys and
SQLite triggers do not defend against a privileged process/database administrator.

[LOOP_MVP_REPORT.md](LOOP_MVP_REPORT.md) records the delivered scope and evidence.
[FINAL_EVIDENCE_REPORT.md](FINAL_EVIDENCE_REPORT.md) and older `evidence/` directories
remain historical Phase 1 reports, not claims about the new runtime.
