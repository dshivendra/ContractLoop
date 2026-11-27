# Trust model

TCB: CPython/Pydantic, local kernel and collector code, fixture setup and source
manifest/baseline, SQLite engine/file permissions, verifier host, HMAC policy/key
holders, harness-provided clock/resource/state version, independent test oracle.
Executor is logically separate and only reports completion. Tests mutate fixture
state adversarially to demonstrate outcome checks; these are not production effects.

| Threat | Implemented control | Residual limitation |
|---|---|---|
| Contract revision | Hash, owner HMAC, immutable tenant/id/version repository | Approver compromise and semantic gaming remain possible |
| Fabrication/tampering | Scoped envelope HMAC, content hash, approved collector bindings | Key holders can sign false facts; signature is provenance, not truth |
| Replay | Exact tenant/task/execution/contract/resource/state binding and freshness | Repeated identical observations in the same evaluation are intentionally idempotent |
| Staleness / races | Declared age bound, snapshot read transaction, state-version match | No live resource discovery or preventive action CAS |
| Conflicting evidence | Conservative UNKNOWN for differing authenticated values | One equivocating trusted collector can deny assurance |
| Correlated errors | Independent hardcoded golden and generated destination oracle, mutation checks | Shared runtime, humans, source data and crypto implementation remain correlated |
| Executor self-verification | Legacy reports only Claim; collector identity cannot equal executor | Logical APIs cannot stop arbitrary same-process code with keys/DB access |
| Audit rewrite | SQLite triggers, hash chain, no public update/delete method | DB admin can drop triggers/rewrite or truncate/rebuild whole chain; no external checkpoint |
| Tenant leakage | Tenant included in hash/HMAC/run/evidence checks | No tenant API, IAM, process or encrypted storage boundary |
| Exhaustion | Count/depth/node/assignment limits and bounded input iterator | No hard CPU deadline or memory isolation against malicious host process |
| Metric gaming | Baseline hash, per-currency conservation, ID/classification/destination checks | Synthetic batch only; production criteria need domain owner validation |
| Unauthorized effects / duplicates | No executor side effects in kernel | Action gateway, exactly-once claims, crash recovery deferred |
| Attestation forgery/drift | No attestations issued | Issuance, asymmetric signatures, expiry/revocation and monitoring deferred |

Keys are public fixture constants intentionally. HMAC is sufficient to exercise
separate key roles in tests; it does not provide nonrepudiation or protect against
the package recipient. Trust-policy fingerprint pins key digests and scoped source
configuration. A version label alone is not trusted evidence. No guarantees are
made about enterprise safety, availability, regulatory acceptance, real cash, or
preventing external actions.

Snapshot coherence is enforced after authenticity: one source/resource/state
version has one artifact hash. Different authenticated hashes make that stream
UNKNOWN; invalid observations cannot force a snapshot conflict. Different sources
remain independent. Content hashes establish consistency under the declared
collector trust assumptions, not factual truth. The replay fault plan is trusted
experiment configuration and is never inferred from a model's completion claim.
