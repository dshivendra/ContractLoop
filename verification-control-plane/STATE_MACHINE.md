# Durable controlled-loop lifecycle

The kernel's verdict and the runtime's lifecycle are separate. Lifecycle
`completed` can carry SUCCESS or FAILURE. UNKNOWN evidence exhausts into escalated;
preventive authorization/budget/recovery guards block execution. Cancellation and
timeout retain UNKNOWN, and demonstrated runtime invariant violations retain FAILURE.

The exact allowed graph is `runtime.TRANSITIONS`; undefined transitions reject.

| State | Authorized next states |
|---|---|
| draft | validation, cancelled, timed_out |
| validation | approval_pending, rejected, cancelled, timed_out |
| approval_pending | authorized, rejected, cancelled, timed_out |
| authorized | pre_verification, cancelled, timed_out |
| pre_verification | executing, blocked, suspended, timed_out, cancelled |
| executing | observing, recovering, blocked, suspended, timed_out, cancelled |
| observing | post_verification, collecting_evidence, suspended, timed_out, cancelled |
| post_verification | completed, recovering, collecting_evidence, blocked, timed_out, cancelled |
| collecting_evidence | observing, escalated, timed_out, cancelled |
| recovering | executing, escalated, blocked, timed_out, cancelled |
| suspended | pre_verification, observing, escalated, cancelled, timed_out |
| completed / rejected / blocked / escalated / timed_out / cancelled | None |

An approved dependency failure can atomically block its parent before any action;
this is a separately recorded dependency-blocked guard rather than an ordinary
executor transition. Controller transitions are authorized independently from the
executor. A recovery decision increments its durable allowance before retrying.
Each attempt receives a deterministic key and commits counters, receipt, effect
and audit together. After lost acknowledgement, restart reuses the committed receipt.
No terminal task is automatically reopened or assigned a new contract.

Attestation state is separately VALID, EXPIRED or REVOKED. Validity checks sample
the current resource. A demonstrated change revokes persistently, even if the
resource is subsequently restored. Historical task/verifier results stay unchanged.
