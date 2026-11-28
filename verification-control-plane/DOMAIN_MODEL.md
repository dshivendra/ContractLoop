# Domain model and serialization

## Current controlled-loop extension

Current runtime additions are immutable typed models in `runtime_models.py`:
Intent, Context, Principal, ExecutionContract, ExecutionApproval, Task, Action,
Receipt, LoopResult, Attestation, Dependency, Composition, DependencyState and
RevisionProposal. Kernel models below are retained. Execution contracts pin a
kernel contract and approval; tasks pin an execution hash. Actions additionally
bind actor, resource, execution, expected state/snapshot and idempotency key.
Attestations bind kernel verdict, snapshot, child states and validity interval.
Event/state snapshots form the append-only trajectory; Task is its mutable
projection, checked by the read-only runtime auditor. Actual committed schemas
are EXECUTION_SCHEMA.json, ATTESTATION_SCHEMA.json and COMPOSITION_SCHEMA.json.

## Verification kernel reference

Implemented public data models are immutable Pydantic models, reject unknown fields
and serialize through JSON. Scalar facts are strict bool/int/str. IDs are nonempty
strings of at most 200 characters; integer versions and epoch-second times are strict.

| Concept | Phase 1 representation / relationship | Status |
|---|---|---|
| Intent | Contract objective, rationale, alignment reference, owner approval | Structured fields; NL alignment deferred |
| Context | Contract environment/resource/baseline/assumptions; Run state version | Point snapshot only |
| Task / execution | Run task_id/execution_id/tenant/executor/contract_hash | Typed; no scheduler |
| Contract | Contract, Approval; versioned tenant/id tuple in repository | Implemented |
| State | SQLite snapshot, cryptographic source baseline, Run state version | Fixture adapter only |
| Predicate | Compare, All, AnyOf, Not | Restricted executable AST |
| Preconditions / postconditions | Condition role and stage; success is postcondition | Historical preconditions UNKNOWN |
| Invariant / constraint | Mandatory Condition roles | Point checks only; history deferred |
| Policy | TrustPolicy / CollectorTrust; hash pinned in Contract and Verdict | Synthetic trust policy |
| Evidence | Evidence with exact scope, provenance, value/time, artifact/content hashes and HMAC | Implemented |
| Claim | Claim execution_status/message, ImportedClaim lineage | Never authoritative outcome evidence |
| Verifier / verdict | VerificationEngine, Assessment, Verdict | Implemented |
| Event / trajectory | Ordered ledger records and replay bundles | Audit events only; action trajectory deferred |
| Action / dependency | No runtime representation in Phase 1 | Phase 2 / 3 deferred |
| Attestation | Verdict attestation_status='not-issued' | Engine and validity lifecycle Phase 3 deferred |
| Recovery | No recovery object or executable controller | Phase 2 deferred |

Ownership: fixture approver owns contract semantics; trusted collector owns signed
observations; verifier owns verdict construction; ledger owns immutable history.
Executor reports have no contract/evidence/verdict mutation capability through the
supported interface. Same-process malicious code can bypass logical boundaries.
Approval or scope failure raises PermissionError. Malformed/contradictory models
raise ValidationError. Unsuitable evidence is a rejected record plus U. Evaluator
and resolver exceptions become separate faults and cannot establish success. Audit
failure raises and returns no issued verdict. No unsupported concept has a stub
that claims successful behavior.
