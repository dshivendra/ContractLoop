# Phase 1 interfaces

These are concrete Python functions/classes, not a service scaffold. JSON models
and exact schemas define the portable boundary; no cloud/MCP dependency is required.

| Port / concrete API | Inputs → outputs | Trust / failure / concurrency / observability |
|---|---|---|
| ContractVerifier: Contract.model_validate | JSON dict → Contract | Pure, bounded; ValidationError; no NL alignment inference |
| Approval authority: approve | Contract, TrustPolicy, epoch time → Approval | Owner key in trusted harness; PermissionError |
| ContractRepository.put | Contract, Approval, policy, time → None | Valid approval; immutable identity; serialized SQLite append |
| StateProvider: read_snapshot | fixture Path → transactional snapshot | Read-only DB; SQLite errors propagate; no executor output |
| EvidenceCollector: collect | path, Contract, Run, policy, observed_at → tuple[Evidence] | Eight fixed facts; actual snapshot state/resource checked; exceptions propagate |
| EvidenceVerifier: validate_evidence | Evidence, Binding, Run, policy, now → reason or None | Authenticates only approved sources/methods and scope; deterministic |
| Evidence resolution: resolve | bounded records, contract, run, policy, now → facts/support/rejections | Conflicts U; duplicate ID equivocation rejected |
| PredicateEvaluator: evaluate | typed Expression, fact map → Truth | Strict comparisons, Kleene composition; missing/type errors U |
| VerificationEngine.verify | Contract, Approval, Run, iterable[Evidence], Claim, now → Verdict | Reads at most max_evidence+1; approval/scope rejects; durable audit required |
| VerificationEngine.compute | same → Verdict | Diagnostic only; no persistence; not an issuance capability |
| AuditLedger: Ledger.append/check/records | kind/identity/JSON → hash; check → head hash | Append-only API/triggers; transactional; database exceptions propagate |
| Replay: VerificationEngine.replay | stored bundle history → tuple[Verdict] | No rewrites; pinned policy/engine; errors reject |
| Legacy import adapters | old Observation or graph envelope → ImportedClaim | Provenance retained; authoritative_evidence_count=0 |

Core public models are in `vcp/models.py`; fixture and trust APIs are in
`vcp/reconciliation.py` and `vcp/security.py`. Complete diagnostics include evidence
IDs/rejection reasons, per-condition truth, faults, trust assumptions and assurance.
The supported identity policy isolates mismatched tenants in inputs; it is not a
multi-tenant authorization/API implementation.

Deferred ports: IntentProvider, ContextResolver, NL ContractCompiler,
DependencyResolver, runtime PolicyEngine, RiskEvaluator, Executor, ActionGateway,
action TrajectoryRecorder, persistent cross-service EvidenceRepository,
InvariantMonitor, CompositionalVerifier, RecoveryController, AttestationEngine.
Future implementations must supply authorization, concurrency, budget and failure
semantics at their actual boundaries before claiming those ports are supported.
