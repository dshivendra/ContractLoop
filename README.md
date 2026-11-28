# ContractLoop

ContractLoop executes approved contracts and independently verifies the resulting
state before declaring success. The **0.2.0 local synthetic MVP** is runnable now.

```bash
cd verification-control-plane
python -m pip install -e '.[qa]'
python -m vcp.loop_cli demo --directory /tmp/contractloop-demo
python -m vcp.loop_cli audit --database /tmp/contractloop-demo/loop.sqlite
```

The demo approves a typed reconciliation contract, executes a guarded SQLite
mutation, collects signed independent evidence, verifies the result and issues an
expiring attestation. It saves the contract, trajectory, database and result.

Delivered capabilities include durable lifecycle, authorization, CAS and
idempotency receipts, atomic effects/audit, bounded recovery and budgets,
approved dependency DAGs, independent parent verification, signed attestations,
sampled drift revocation, read-only replay, revision proposals and a local
role-authenticated JSON API.

See the [implementation README](verification-control-plane/README.md),
[local API guide](verification-control-plane/LOOP_API.md), and
[MVP evidence and boundaries](verification-control-plane/LOOP_MVP_REPORT.md).

The combined acceptance gate is:

```bash
python tools/run_acceptance.py --output /tmp/contractloop-acceptance
```

Run it from `verification-control-plane/`. CI executes the same gate on Python
3.11 and 3.12. Phase 1 evidence remains historical and unchanged.

This release uses synthetic local data and public fixture signing keys. It does
not deploy a production service, call cloud APIs, compile arbitrary natural
language, guarantee external exactly-once effects or prove unobserved temporal
invariants. Optional ontology work and autonomous shipping remain paused.
