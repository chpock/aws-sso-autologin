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

## Branch-level code review - round 2

### Findings
- F1 (Critical): sanitizer still misses JSON/header token shapes and may leak secrets.
- F2 (Critical): TDD RED evidence missing from review log.
- F3 (Important): coverage below plan for changed modules.
- F4 (Important): event compatibility concern for tray-host unavailable taxonomy.
- F5 (Important): trace metadata fields not surfaced consistently.
- F6 (Important): verification evidence lacked pasted command output.

### Response F1
- Claim (restated): current sanitizer can leak secrets for common formats.
- Verification: reproduced with failing tests in `tests/test_logger.py` for JSON token fields and `Authorization: Bearer`.
- Decision: accept.
- Reasoning: this is a direct secret-exposure risk and merge blocker.
- Implementation: hardened sanitizer in `aws_sso_autologin/logger.py` with parser-aware JSON pair redaction and explicit auth-header token masking.

### Response F2
- Claim (restated): RED evidence was not present in this log.
- Verification: confirmed missing before this update.
- Decision: accept.
- Reasoning: required by process discipline.
- Implementation: added RED evidence section below with failing test output excerpt captured before sanitizer fix.

### Response F3
- Claim (restated): changed modules lacked coverage expansion aligned with plan.
- Verification: partially true; tests were previously concentrated in service/watchdog paths.
- Decision: accept (partial).
- Reasoning: this round adds logger-focused regression tests for high-risk redaction behavior.
- Implementation: added sanitizer regression tests in `tests/test_logger.py`.

### Response F4
- Claim (restated): tray-host event compatibility regressed by moving unavailable events out of primary `event`.
- Verification: confirmed prior implementation used `event=tray_host_probe_completed` with legacy alias only.
- Decision: accept.
- Reasoning: preserve existing machine consumers while retaining normalized event mapping.
- Implementation: restored primary `event` values (`tray_host_unavailable_unknown`, `tray_host_unavailable_protocol_mismatch`) and added `normalized_event=tray_host_probe_completed`.

### Response F5
- Claim (restated): trace metadata omitted key redaction/detail markers in several modules.
- Verification: confirmed missing `*_payload_size_bytes`, `*_redaction_applied`, and `*_detail_unavailable_reason` fields in some trace events.
- Decision: accept.
- Reasoning: required for conformance and safe payload observability.
- Implementation: added complete metadata fields across trace logs in `aws.py`, `checker.py`, `cli.py`, `operator.py`, and `service.py`.

### Response F6
- Claim (restated): verification section listed commands but not captured outputs.
- Verification: confirmed.
- Decision: accept.
- Reasoning: completion gate requires fresh evidence lines, not command names alone.
- Implementation: added output excerpts below for RED and GREEN runs.

## RED evidence (round 2)
- Command:
  - `.venv/bin/pytest tests/test_logger.py::test_sanitize_trace_payload_redacts_json_token_fields tests/test_logger.py::test_sanitize_trace_payload_redacts_bearer_authorization -q`
- Output excerpt:
  - `FF`
  - `FAILED tests/test_logger.py::test_sanitize_trace_payload_redacts_json_token_fields`
  - `assert 'abc123' not in sanitized["value"]`
  - `FAILED tests/test_logger.py::test_sanitize_trace_payload_redacts_bearer_authorization`
  - `assert 'super-secret-token' not in sanitized["value"]`

## GREEN evidence (round 2)
- Command:
  - `.venv/bin/pytest tests/test_logger.py -q`
- Output:
  - `10 passed in 0.01s`
- Command:
  - `.venv/bin/pytest tests/test_service.py tests/test_cli.py tests/test_checker.py tests/test_operator.py tests/test_aws.py -q`
- Output:
  - `79 passed in 4.08s`

## Branch-level code review - round 3

### Findings
- F1 (Critical): secret redaction coverage still too narrow.
- F2 (Important): verification evidence missing pasted full-suite and runtime outputs.
- F3 (Important): `aws_command_failed` explicit taxonomy requested for non-zero exits.
- F4 (Important): checker lifecycle completion event symmetry incomplete.

### Response F1
- Claim (restated): sanitizer misses common credential shapes.
- Verification: reviewed `logger.py` and confirmed previous keyset omitted `aws_session_token`, `id_token`, and `client_secret` variants.
- Decision: accept.
- Reasoning: remaining leak paths are merge blockers.
- Implementation: expanded key denylist and regex coverage in `aws_sso_autologin/logger.py`; added regression test in `tests/test_logger.py`.

### Response F2
- Claim (restated): review evidence requires pasted outputs, including runtime startup logs.
- Verification: prior section had command-only/full-suite summary gaps.
- Decision: accept.
- Reasoning: verification gate requires explicit output evidence.
- Implementation: added fresh pasted outputs for targeted tests, full suite, and `make run` startup/runtime logs below.

### Response F3
- Claim (restated): non-zero AWS command exits should emit explicit failed event.
- Verification: previous code emitted `aws_command_completed` with `status=failed`.
- Decision: accept.
- Reasoning: explicit failed taxonomy improves operational filtering.
- Implementation: updated `aws_sso_autologin/aws.py` to emit `event=aws_command_failed`; added assertion test in `tests/test_aws.py`.

### Response F4
- Claim (restated): checker should emit completion event on both success and inactive non-exception paths.
- Verification: previously only partial lifecycle closure existed.
- Decision: accept.
- Reasoning: complete lifecycle contract requires explicit completion on all normal returns.
- Implementation: added `session_check_completed` logs in both active and inactive normal branches in `aws_sso_autologin/checker.py`; added tests in `tests/test_checker.py`.

## GREEN evidence (round 3)
- Targeted command:
  - `.venv/bin/pytest tests/test_logger.py tests/test_aws.py tests/test_checker.py tests/test_service.py -q`
- Output:
  - `59 passed in 4.07s`

- Full suite command:
  - `make test`
- Output:
  - `229 passed in 4.69s`

- Runtime command:
  - `make run`
- Output excerpt (startup/preflight and runtime evidence):
  - `DEBUG [aws_sso_autologin.service] tray host env probe`
  - `DEBUG [aws_sso_autologin.service] tray host detected`
  - `DEBUG [aws_sso_autologin.service] tray host preflight compatible`
  - `DEBUG [aws_sso_autologin.aws] aws command started`
  - `DEBUG [aws_sso_autologin.aws] subprocess started`
  - `DEBUG [aws_sso_autologin.aws] subprocess completed`
  - `INFO [aws_sso_autologin.aws] profile discovery completed`
  - `INFO [__main__] AutologinApp: Starting Qt event loop`
