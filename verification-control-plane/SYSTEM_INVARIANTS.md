# System invariant traceability

Implemented means demonstrated inside the declared local synthetic TCB. Partial
means the named slice is tested, not that the complete architectural requirement passes.

| ID | Component / enforcement / evidence | Acceptance test | Status |
|---|---|---|---|
| INV-001 | Approval/hash + immutable version ledger | approved_version_immutable; unapproved_or_tampered_contract_rejected | Implemented |
| INV-002 | Kernel constructs verdict; legacy input only Claim | claim_cannot_change_outcome; legacy_false_success_requires_fresh_evidence | Implemented logically |
| INV-003 | Missing fact + mandatory coverage guard | missing_evidence_is_unknown; missing_guard_with_or_true_still_unknown | Implemented |
| INV-004 | False mandatory dominates success | false_completion_and_partial_demonstrated; violation_overrides_missing_other_evidence | Implemented |
| INV-005 | No action gateway | No action boundary in Phase 1 | Deferred |
| INV-006 | Run/hash/version + audit bundle | correct_execution_success; cross_scope_and_replay_rejected | Implemented |
| INV-007 | Per-condition evidence IDs, raw audit bundle | correct_execution_success; replay_restart_canonical_and_order_independence | Implemented |
| INV-008 | Evidence count/AST/semantic budget | evidence_budget_enforced; unbounded_input_iterator_is_bounded; ast_depth_budget | Partial; execution/recovery deferred |
| INV-009 | Signed observation time, age policy | stale_future_and_recollection | Implemented for requested point state |
| INV-010 | No composition or child success inputs | No parent inference API | Deferred |
| INV-011 | No recovery can alter requirements | No recovery API | Deferred |
| INV-012 | No learning writes contracts | Approved version immutability test | Partial; learning deferred |
| INV-013 | SQLite observation transaction and audit BEGIN IMMEDIATE | snapshot code; replay tests | Partial; concurrent controlled effects deferred |
| INV-014 | Verdict says not-issued | correct_execution_success | Deferred; no attestation issued |
| INV-015 | Restart replay and idempotent audit writes | replay_restart_canonical_and_order_independence | Partial; external effects/idempotency deferred |
| INV-016 | Exact signed tenant/task/run isolation | cross_scope_and_replay_rejected | Partial; production tenant isolation deferred |
| INV-017 | Unsupported temporal/stage facts U | temporal_and_assurance_unsupported_unknown; historical_preconditions_and_unsupported_stages_unknown | Implemented fail-closed slice |
| INV-018 | Verdict assurance + assumptions + policy hash | correct_execution_success; temporal_and_assurance_unsupported_unknown | Implemented |

Test method names above are prefixed `test_` in `tests/test_kernel.py`. All statuses
are scoped to Phase 1; deferred controls are not counted as passed invariants.
