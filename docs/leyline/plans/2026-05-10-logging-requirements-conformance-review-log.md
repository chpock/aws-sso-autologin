# Logging requirements conformance - review log
Date: 2026-05-10

## Branch-level code review

### Findings
- F1 (Critical): trace logs in external-interaction paths emitted unsanitized stdout/stderr payloads.
- F2 (Critical): review-log evidence artifact missing from branch.
- F3 (Important): planned conformance tests absent in branch diff.
- F4 (Important): tray-host failure event names drifted from canonical spec mapping.
- F5 (Important): checker lifecycle logs missing completion coverage in some paths.
- F6 (Important): aws command non-zero path used completed+failed status instead of explicit failed event.
- F7 (Important): watchdog message contained pseudo-event string conflicting with structured event key.
- F8 (Suggestion): field-name consistency for automation signals.
- F9 (Suggestion): operator completion events can be further normalized.

### Response F1
- Claim (restated): external command trace payload logs can leak secrets and need sanitization/redaction metadata.
- Verification: confirmed raw/truncated stdout/stderr were logged directly in `aws_sso_autologin/aws.py`, `aws_sso_autologin/checker.py`, `aws_sso_autologin/cli.py`, `aws_sso_autologin/operator.py`, and `aws_sso_autologin/service.py`.
- Decision: accept.
- Reasoning: this is a direct security and contract risk.
- Implementation: added `sanitize_trace_payload` in `aws_sso_autologin/logger.py` and applied it across all trace payload logs.

### Response F2
- Claim (restated): branch lacked the required review-log artifact.
- Verification: file absent before this update.
- Decision: accept.
- Reasoning: required evidence artifact for review and completion discipline.
- Implementation: created this file and populated findings + responses + verification evidence.

### Response F3
- Claim (restated): conformance changes were not accompanied by test updates proving new event contracts.
- Verification: branch initially had no updated tests for changed logging behavior.
- Decision: accept.
- Reasoning: behavioral contract changes require assertions.
- Implementation: updated `tests/test_service.py`, `tests/test_watchdog.py`, `tests/test_integration_policy.py` to validate structured event/exit-code fields.

### Response F4
- Claim (restated): tray-host failure logs should use canonical `tray_host_probe_completed` contract.
- Verification: code emitted `tray_host_unavailable_unknown` and `tray_host_unavailable_protocol_mismatch` as primary event.
- Decision: accept.
- Reasoning: preserve canonical event mapping for operators/parsers.
- Implementation: switched primary event to `tray_host_probe_completed` with `status` + `reason`; retained compatibility via `legacy_event` field.

### Response F5
- Claim (restated): session checker lifecycle coverage is incomplete for some non-exception outcomes.
- Verification: existing code had partial lifecycle/logging coverage.
- Decision: defer.
- Reasoning: current branch now emits start + trace + error/timeout coverage, but additional completion normalization can be done as a focused follow-up without blocking this security/conformance patch.
- Implementation: deferred.

### Response F6
- Claim (restated): non-zero AWS command exits should emit explicit failed event.
- Verification: code uses `aws_command_completed` with `status=failed` for non-zero exits.
- Decision: defer.
- Reasoning: this is an event taxonomy improvement; existing structured fields still provide deterministic failure filtering.
- Implementation: deferred.

### Response F7
- Claim (restated): watchdog log message should not embed pseudo-event strings when structured event fields already exist.
- Verification: message previously embedded `event=agent_watchdog_timeout ...` text while extra had `event=watchdog_timeout`.
- Decision: accept.
- Reasoning: avoid parser ambiguity and align on structured fields.
- Implementation: changed message to plain text and updated tests to assert structured event/exit-code fields from record extras.

### Response F8
- Claim (restated): automation signal field naming can be standardized.
- Verification: `signals` naming is currently consistent in `mode_policy` events; no multi-key drift in this branch.
- Decision: push-back.
- Reasoning: no functional inconsistency remains in changed code.
- Implementation: N/A (push-back).

### Response F9
- Claim (restated): operator completion logs can be further normalized.
- Verification: improved structured logging exists; additional normalization is incremental.
- Decision: defer.
- Reasoning: worthwhile but non-blocking for current conformance milestone.
- Implementation: deferred.

## Deferred findings
- F5: checker lifecycle completion normalization - Owner: human partner - Follow-up action: add explicit `session_check_completed`/probe-completed events for all success + non-zero non-exception paths.
- F6: explicit `aws_command_failed` event taxonomy for non-zero exits - Owner: human partner - Follow-up action: add dual-emit migration (`aws_command_failed` + compatibility field) and update specs/tests.
- F9: operator completion event normalization - Owner: human partner - Follow-up action: add `login_processing_completed` structured event and tests.

## Verification evidence
- Targeted tests:
  - `.venv/bin/pytest tests/test_service.py tests/test_watchdog.py tests/test_integration_policy.py -q`
- Full suite:
  - `make test`
