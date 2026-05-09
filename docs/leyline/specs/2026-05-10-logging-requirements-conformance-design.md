# Logging requirements conformance - product spec
Date: 2026-05-10
Author: human partner
Surfaces: developer-facing

## Problem
Current application logging is inconsistent in coverage and structure. Some actions
and failure paths are logged, but not all runtime activity and external
interactions are guaranteed to emit structured logs aligned with AGENTS.md
Logging requirements.

## Goals
- Audit all runtime paths where the application performs actions.
- Ensure all key actions and decisions are logged with explicit levels.
- Ensure all external interactions are logged, with full interaction details
  available at `trace` level.
- Standardize structured event logs to support filtering and triage.

## Non-goals
- Redesign authentication/login business behavior.
- Introduce a new telemetry backend or log shipping pipeline.
- Replace existing logging framework primitives.

## Constraints
- Follow AGENTS.md Logging requirements as normative contract.
- Preserve current runtime behavior except logging-related observability changes.
- Keep existing tests green and extend tests where logging behavior is changed.
- Update spec artifacts when behavior contracts are changed.

## Approaches considered
### Approach A - Full audit plus event-schema normalization
Inventory all runtime actions and external interactions, map them to required log
events/levels/fields, then patch missing and non-conforming call sites.
Trade-offs: highest up-front effort, best completeness and consistency.

### Approach B - Gap-only patching
Patch only locations with no logging and leave partially conforming logs as-is.
Trade-offs: fastest path, but leaves inconsistent field naming and level usage.

### Approach C - Logging abstraction refactor first
Introduce helper wrappers/decorators for structured logging and migrate call sites.
Trade-offs: clean long-term architecture, but larger risk and scope for current
task.

## Recommendation
Adopt Approach A. It directly matches the requirement to thoroughly inspect all
application actions and ensure full conformance to Logging requirements.

## Scope and boundaries
- In scope:
  - Runtime modules under `aws_sso_autologin/`.
  - Application startup/shutdown, mode routing, preflight checks, operators,
    tray integration paths, watchdog/policy flows, config loading, and external
    process/IPC interactions.
  - Structured logging field consistency (`event`, contextual keys,
    `duration_ms`, outcomes).
  - Tests that validate logging behavior.
- Out of scope:
  - Test-only instrumentation unless needed to verify runtime logging contracts.
  - Non-runtime scripts unless they are part of application execution flow.

## Logging contract for this change
- Every significant application action emits structured logs.
- Every external interaction emits:
  - lifecycle event(s) at `debug`/`info` level, and
  - full request/response payload detail at `trace` level.
- If full payload detail is unavailable, emit
  `detail_unavailable_reason=<reason>` and include all available metadata.
- Sensitive data policy for trace details:
  - never log secrets/tokens/passwords/session cookies/raw credentials
  - redact secret-like fields using stable placeholders
  - truncate payload fields above configured limits and log
    `payload_truncated=true` with `payload_size_bytes`
- Failures that block completion are logged at `error` with machine-parseable
  fields.
- Recoverable anomalies are logged at `warn` with recovery/impact context.
- Event naming is explicit, stable, and scoped by subsystem where needed.

## Ownership and conformance matrix
| Subsystem | External interaction | Owner | Required event set | Required fields | Verification |
|-----------|----------------------|-------|--------------------|-----------------|--------------|
| startup/main | mode selection + process lifecycle | app runtime | `mode_selected`, `startup_preflight_started`, `startup_preflight_completed` | `event`, `mode`, `status`, `duration_ms` | unit/integration tests in `tests/test_main.py` |
| service/preflight | tray-host probing + env inspection | service | `tray_host_probe_started`, `tray_host_probe_completed`, `tray_host_unavailable_*` | `event`, `host_type`, `status`, `reason` | `tests/test_service.py` |
| checker/aws | subprocess command execution | checker/aws | `aws_command_started`, `aws_command_completed`, `aws_command_failed` | `event`, `command`, `exit_code`, `duration_ms` | `tests/test_checker.py`, `tests/test_aws.py` |
| tray/diagnostics | clipboard/UI diagnostic emission | tray | `diagnostics_copy_started`, `diagnostics_copy_succeeded`, `diagnostics_copy_failed` | `event`, `status`, `error` | `tests/test_tray.py` |
| watchdog/policy | timeout and policy guardrails | watchdog/policy | `watchdog_started`, `watchdog_timeout`, `policy_violation` | `event`, `mode`, `timeout_s`, `exit_code` | `tests/test_watchdog.py`, `tests/test_mode_policy.py` |

Conformance gate: every row above requires both success-path and failure-path
assertions.

## Acceptance criteria
- All runtime action paths have explicit logging coverage.
- All external interactions provide trace-detail logging.
- Existing non-structured or ambiguous logs are normalized to structured form.
- Updated and new logging-focused tests pass, and full `make test` is green.
- Measurable conformance gates:
  - 100% of ownership-matrix rows verified by tests.
  - each row has at least one success and one failure log assertion.
  - each externally interacting row verifies trace-level detail behavior,
    including redaction/truncation branches.

## Verification plan
- Build a module-level checklist of actions and external interactions.
- Run targeted tests for changed modules.
- Run full `make test`.
- For startup/tray-host behavior, capture `make run` structured `event=` logs in
  notes.
- Emit a committed conformance checklist artifact that maps each matrix row to
  concrete test cases and observed events.

## Risks and mitigations
- Risk: noisy logs from over-instrumentation.
  - Mitigation: place verbose payload detail at `trace`, keep higher levels
    concise.
- Risk: fragile tests tied to exact message strings.
  - Mitigation: assert stable `event` keys and critical fields rather than full
    human-readable text.

## Compatibility and rollback
- Event/field compatibility policy:
  - do not rename or remove existing production event keys without compatibility
    aliasing
  - maintain old+new event names/fields during transition window where feasible
  - document changed events in changelog/release notes
- Rollback controls:
  - allow temporary verbosity reduction via log level settings
  - keep structured minimal fields (`event`, `status`, `reason`) intact during
    rollback
  - revert conformance deltas in isolated commit if performance/storage impact is
    unacceptable

## Open questions
- Whether to centralize external-interaction logging helpers now or defer to a
  later refactor after conformance is complete.

## Approvals
Product spec approved - round 1 - 2026-05-10

## Deep-discovery
Deep-discovery pass complete - round 1 - 2026-05-10
