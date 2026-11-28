# Formal semantics

## Current controlled-loop extension

This document specifies the unchanged `vcp-kernel/0.1.1` point verifier.
Package 0.2.0 additionally implements `controlled-loop/0.2.0`. Statements below
about deferred runtime execution/attestations describe the kernel alone.
Runtime preconditions authorize an action only on TRUE; UNKNOWN prevents execution.
Runtime invariant FALSE rolls back the effect and records a sticky historical
violation; UNKNOWN rolls back and remains UNKNOWN. Completed SUCCESS requires
independent kernel success and applicable dependency/global checks. A lifecycle
state named completed can also carry FAILURE; execution completion is not success.
A certificate additionally requires a completed SUCCESS, no sticky violation,
valid approval, current matching evidence and freshness/deadline bounds. VALID is
a separate sampled present-tense property; expiry/revocation never rewrites history.
No general temporal logic or unobserved intermediate-history proof is introduced.

## Verification kernel reference

Truth values are T (established), F (demonstrated false), U (insufficient).

| AND | F | U | T |
|---|---|---|---|
| F | F | F | F |
| U | F | U | U |
| T | F | U | T |

| OR | F | U | T |
|---|---|---|---|
| F | F | U | T |
| U | U | U | T |
| T | T | T | T |

NOT(F)=T; NOT(U)=U; NOT(T)=F. Empty compositions are rejected and empty
internal reductions produce U. bool and int are different scalar types. Missing
facts and mismatched scalar types produce U. No general Python execution is allowed.

Each condition is mandatory. Success, authorization, constraint, invariant and
precondition expressions have positive polarity; a failure expression is inverted
when contributing to the mandatory conjunction. Assessments preserve its original
truth so a TRUE failure criterion remains visible. Any established mandatory F
means FAILURE. Otherwise SUCCESS requires every mandatory T, every bound fact
supported by suitable evidence, supported assurance and no verifier faults.
Otherwise UNKNOWN. Missing data, rejected observations and faults alone are not
demonstrated task violations. A violation remains FAILURE despite other missing data.

All evidence mappings are required even when OR finds a true branch. This is a
deliberately conservative coverage guard. Conflicting authenticated values for
one fact at the same state version produce U, with all supporting IDs recorded.
The conflict rule does not pick a convenient value or prefer the newest reading.
Invalid/untrusted observations are rejected and cannot override a valid fact.
Equivocating evidence IDs quarantine every payload with that ID; identical repeats
are idempotent. IDs are scoped and signatures bind task, execution, tenant, resource,
contract hash, state version, source, method, observation time, coverage and value.

Freshness is closed interval 0 ≤ evaluated_at − observed_at ≤ max_age_seconds.
Future observations are rejected. A new snapshot may recollect stale facts. The
requested state version and evaluation time are trusted harness inputs. They are
not discovered from a live external environment by this kernel.

Only V3 point-in-time evaluation is supported. V0/V1/V2/V4, historical preconditions,
always/eventual/stability/deadline conditions return U. The fixture's `authorized`
fact proves a snapshot value under fixture assumptions, not preventive authorization.
No past invariant is inferred from current state. Attestations are not issued.

Approval is a separate HMAC envelope. The contract hash covers every Contract
field in sorted-key compact ASCII JSON with no NaN/floats, using SHA-256; the
approval envelope is outside that content. Model tuples serialize as JSON arrays.
This local canonicalization is not an RFC 8785 interoperability claim.
The approval HMAC covers contract hash, actor and approval time. New semantic
versions require fresh approval. Approval reissuance cannot replace a stored version.

Satisfiability enumerates scalar comparison cells: booleans, named strings plus
one other string, and integer thresholds plus adjacent integers. Fact types must
agree. A satisfiable mandatory conjunction with a non-tautological combined success
criterion is required. More than 100,000 assignments requires owner revision; the
kernel does not silently weaken requirements. Natural-language intent alignment
is approved by the fixture owner and not inferred by this checker.

Historical verdicts are immutable audit entries. Replay fixes evaluation time,
contract, approval, run, raw evidence, claim, engine/policy version and assumptions.
Ordinary deterministic cases replay directly. Injected infrastructure faults require
the same fault condition for exact recomputation, explicitly reinstated in the
benchmark; replay without that fault is expected to reject a mismatch.

Engine 0.1.1 completion corrections: authenticated observations from one
source/resource/state version must identify one immutable snapshot artifact.
Different hashes quarantine that source's facts as UNKNOWN before composition;
passing facts from separate failing snapshots cannot create SUCCESS. Distinct
independent sources may have distinct hashes. Invalid signatures cannot poison
an otherwise coherent authenticated group. UNKNOWN mandatory conditions and
incompatible fact types also force assurance=insufficient.

The synthetic collector accounts for bank-only input rows and rejects blank
currency observations instead of silently producing acceptable evidence. These
implement the existing completeness/classification/typed-money conditions.
`tools/replay_audit.py` opens the ledger read-only; a separate trusted fault-plan
file explicitly reinstates synthetic fault cases. Earlier engine versions are
rejected, not silently reinterpreted. Approved phase1/1 contract format is unchanged.
