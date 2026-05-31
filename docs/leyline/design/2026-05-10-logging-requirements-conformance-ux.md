# Logging requirements conformance - UX spec
Date: 2026-05-10
Product spec: docs/leyline/specs/2026-05-10-logging-requirements-conformance-design.md
Surfaces: developer-facing

## Public API surface enumeration
- CLI invocation and mode selection logs from `aws_sso_autologin.__main__`.
- Runtime lifecycle logs for app startup, tray host preflight, operator wiring,
  monitoring start/stop, and fatal exits.
- Diagnostic output contract where users/operators inspect logs for `event=`
  records.

## Error shapes and failure-mode contracts
- Blocking failures use `error` level and include explicit failure event keys.
- Recoverable issues use `warn` with impact/recovery context.
- Startup gate failures emit deterministic event names for triage.
- Unexpected exceptions include stack traces (`exc_info`) and structured context.

## Log / output schema
- Required keys for major events:
  - `event`: machine-parseable event name.
  - `status`: `started|completed|failed|skipped` where applicable.
  - subsystem context keys (for example `mode`, `profile`, `host_type`,
    `duration_ms`, `status`).
- Required vs optional cardinality:
  - required: `event`
  - required when available by context: `status`, `duration_ms`, `reason`,
    `exit_code`, `error`
  - optional: subsystem-specific context fields
- Levels map:
  - `trace`: external request/response details, command output, deep payloads.
  - `debug`: internal decisions, branch selection, state transitions.
  - `info`: lifecycle milestones and user-visible operations.
  - `warn`: recoverable anomalies and degraded modes.
  - `error`: operation-fatal failures.
- AWS CLI subprocess trace logs use process-scoped logger names in the shape
  `aws_sso_autologin.aws.<id>` so operators can visually group start,
  progress, output, completion, and timeout records for one subprocess launch.
- AWS CLI subprocess progress logs emit once per second while the subprocess is
  running. The progress message is `subprocess output received` when new
  sanitized stdout/stderr is available and `<...still running...>` when no new
  output is available for that interval.
- When the subprocess exits, any final output that was not seen by the last
  progress check is emitted once as `subprocess output received`; output already
  emitted during progress checks is not repeated at completion.

## Exit-code semantics
- `0`: successful completion for bounded modes/checks.
- `1`: preflight/runtime failure preventing completion.
- Existing project-defined special codes remain unchanged; logs must include
  contextual fields that explain why that code occurred.
- Canonical event bindings:
  - `exit_code=0` -> `*_completed status=passed|succeeded`
  - `exit_code=1` -> `*_failed` with `reason` and `error`
  - special policy/timeouts -> dedicated canonical events with `exit_code`

## Telemetry-label conventions
- Event names are snake_case and action-oriented.
- Prefix subsystem where ambiguity risk exists.
- Include both intent and outcome when meaningful:
  - start events (`*_started`),
  - complete events (`*_completed` with `status`),
  - fail events (`*_failed` with `error` fields).
- Prefixing rules:
  - use subsystem prefix for shared verbs (`startup_*`, `tray_*`, `aws_*`)
  - allow unprefixed names only when globally unique within runtime namespace

## Documented failure modes
- Tray-host unavailable or protocol mismatch.
- Profile/config loading failure.
- External command execution failure.
- Health monitoring start failure.
- Unhandled exception in startup or runtime orchestration.

Canonical mappings:
- tray-host unavailable/protocol mismatch -> `tray_host_probe_completed`
  `status=failed`, `reason=<classification>`
- profile/config loading failure -> `profiles_load_failed` with `error`
- external command execution failure -> `aws_command_failed` with `command`,
  `exit_code`, `error`
- external command progress with output -> `subprocess_running_output` with
  `command`, `aws_process_id`, sanitized stdout/stderr fields
- external command progress without output -> `subprocess_still_running` with
  `command`, `aws_process_id`
- health monitoring start failure -> `health_monitor_start_failed` with `error`
- unhandled runtime exception -> `runtime_unhandled_exception` with `error`,
  `exc_info=true`

## Voice and tone in error messages
- Error: "Auto-login failed for profile \"{profile}\"; inspect diagnostics and event logs for details."
- Success: "Startup preflight passed; entering selected runtime mode."
- Empty state: "No SSO profiles found; app continues in empty-state mode until profiles are configured."

## Non-goals
- Localization/internationalization of log strings.
- Building a dashboard/viewer for logs.
- Redefining user-facing tray copy beyond logging clarity needs.

## Deep-discovery round 1 classification
- (O) Missing ownership matrix for external interaction classes.
- (O) Missing redaction/truncation policy for trace payloads.
- (S) "when available" loophole weakens trace-detail requirement.
- (O) No measurable denominator for "all runtime action paths" coverage.
- (O) Event-name/field migration compatibility policy missing.
- (O) Failure-mode catalog lacks required event/field bindings.
- (O) Exit-code semantics not bound to canonical event keys.
- (O) Rollback controls for noisy/expensive logging underdefined.

## Approvals
UX spec approved - round 1 - 2026-05-10
UX spec approved - round 2 - 2026-05-31

design-interrogation skipped - scope: developer-facing surface with no multi-screen UI and no interaction-flow expansion beyond structured logging contract
