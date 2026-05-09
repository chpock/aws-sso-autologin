# Diagnostics Dialog Redesign - product spec
Date: 2026-05-09
Author: human partner
Surfaces: single-screen-ui

## Approvals
Product spec approved - round 1 - 2026-05-09
Product spec approved - round 2 - 2026-05-09
Product spec approved - round 3 - 2026-05-09
Product spec approved - round 4 - 2026-05-09
Product spec approved - round 5 - 2026-05-09
Product spec approved - round 6 - 2026-05-09
Deep-discovery pass complete - round 7 - 2026-05-09

## Problem
The current diagnostics dialog looks primitive and noisy. It renders a raw textarea-like experience, shows fields that are not relevant for the incident, and does not present error context with modern visual hierarchy. Users need a cleaner dialog that communicates status quickly while still preserving full copyable technical details.

## Goals
- Show a top status block with icon and short status text.
- Show status subtitle with profile name when known; otherwise show incident-scope subtitle.
- Use smart field visibility so only relevant fields are shown for the current incident.
- Keep a full readonly details textarea at the bottom for manual selection/copying.
- Add a `Copy all details` button for one-click full-copy behavior.
- Preserve fixed-size, floating behavior and ensure `Close` does not quit the app.
- Improve visual quality to modern desktop-app standards (clear sections, spacing, field backgrounds, and contrast).

## Non-goals
- Changing core runtime error-detection logic in operators/services.
- Adding historical incident timelines.
- Adding editable fields in the diagnostics dialog.
- Replacing structured logging contracts.

## Constraints
- Qt/PySide6 implementation in existing app architecture.
- Dialog remains fixed-size and stays floating above app surfaces.
- Closing dialog never terminates application process.
- Field visibility must be deterministic and testable.
- Full technical payload remains accessible in bottom textarea and copy action.
- Rendering policy must be deterministic for malformed and partial payloads, not only ideal payloads.

## Dependencies and ownership
- Primary implementation owner: tray/runtime maintainers of `aws_sso_autologin/tray.py`.
- Escalation owner for production regressions: app runtime maintainers in `aws_sso_autologin/__main__.py`.
- Runtime dependencies that affect behavior: PySide6 clipboard APIs, Qt palette/theme behavior, Linux compositor/window-manager handling of floating dialogs.
- Compatibility expectation: dialog behavior is validated on Linux tray environments supported by current app baseline; unsupported tray hosts remain out of scope.

## Approaches considered
### Approach A - Status header + smart field cards + details textarea
Use three clear regions: (1) status header with semantic icon and short summary, (2) card-style key/value fields rendered conditionally, (3) readonly details textarea with explicit copy action.

Trade-offs: Highest UX clarity and modern feel; moderate implementation and test complexity.

### Approach B - Two-column inspector + details textarea
Use technical inspector layout (labels left, values right), with conditional rows and bottom textarea.

Trade-offs: Simple to implement, but more tool-like and less approachable for non-technical users.

### Approach C - Collapsible groups + details textarea
Use expandable sections for command outputs and metadata.

Trade-offs: Flexible for dense output but increases interaction complexity and state management.

## Recommendation
Choose Approach A. It provides the best readability, visual hierarchy, and modern UX while preserving complete diagnostics exportability.

## Field visibility policy
- Input contract:
  - `command_executed` is derived from incident payload semantics, not guessed from `stdout/stderr` content alone.
  - Empty string and missing key are distinct states in normalization (`""` vs absent).
  - Unknown values are rendered explicitly (`unknown`) when execution is confirmed but value is unavailable.
- Precedence rules:
  1. `Summary` always renders.
  2. If `command_executed` is false, hide `Command`, `Exit code`, `stdout`, `stderr` regardless of stray output-like strings.
  3. If `command_executed` is true, render `Command` and `Exit code` (`unknown` when missing).
  4. Output fields are resolved after execution state is resolved.
- `Summary`: always show.
- `Incident evidence`: show when available.
- `Command`: show only when a command was executed.
- `Exit code`: show when a command was executed; if unavailable, show `unknown`.
- `stderr` / `stdout`:
  - If command was not executed: hide both.
  - If only `stderr` is non-empty: show `stderr` only.
  - If only `stdout` is non-empty: show `stdout` only.
  - If both are non-empty: show both.
  - If command executed and both are empty: show empty `stdout` explicitly to indicate no output.
- `Timestamp`: show when available.
- Conflict handling:
  - `command_executed=true` with missing command text: show `Command: unknown`.
  - `command_executed=true` with missing exit code: show `Exit code: unknown`.
  - Payload has output keys but execution state unavailable: default to non-command view and include raw values only in details textarea.
  - Payload execution state unavailable: status/header and field copy must use `unknown execution state` wording and avoid command-failure phrasing.

## Security and data-handling
- Diagnostics payload is treated as potentially sensitive (may include profile names, account identifiers, command output fragments).
- `Copy all details` copies full normalized diagnostics payload to clipboard without truncation.
- Telemetry and logs must not include raw diagnostics payload text, raw `stdout`, or raw `stderr` fragments.
- Allowed telemetry fields are limited to event metadata (`incident_type`, `command_executed`, `copy_result`, `fallback_used`, `error_class`, `policy_reason`) and must exclude account/profile identifiers when not required for triage.
- Telemetry retention window for diagnostics-dialog events is 30 days.
- Telemetry access control: only app runtime maintainers and on-call incident responders may query diagnostics-dialog telemetry.
- Telemetry access auditability: every telemetry query must be logged with requester identity, timestamp, and incident/reference reason.
- Telemetry governance verification: app runtime maintainers review access-audit logs weekly during active rollout windows.
- Copy action shows inline disclosure text: copied data may contain sensitive information and should be shared only with trusted support channels.
- No silent redaction in v1 of this redesign; masking/redaction is deferred and must be tracked as follow-up if security review requires it.
- Mandatory follow-up: create and assign a redaction-review ticket before broader rollout beyond current baseline environments; owner is tray/runtime maintainers.
- Redaction-review SLA: owner must deliver decision (retain full-copy behavior, add masking, or scope-based redaction) within 5 business days from implementation-ready state.
- Rollout gate linkage: broader rollout is blocked if redaction-review SLA is missed.
- Trigger for immediate escalation: first confirmed report that copied diagnostics exposed sensitive data in an unintended support channel.
- Escalation response contract: assign incident owner within 1 business day, add temporary support-channel warning hardening immediately, and record containment action in incident notes.
- Escalation response SLA: containment decision (rollout hold, copy-action disable, or warning hardening only) must be recorded within 1 business day.
- Manual-copy textarea path remains available even when copy button fails.

## Operational readiness and rollback
- Observability events required:
  - dialog open success/failure,
  - copy success/failure,
  - field-policy fallback activation for malformed payloads.
- Telemetry contract (minimum fields and emit points):
  - `event=diagnostics_dialog_opened` emitted when dialog opens; required fields: `incident_type`, `command_executed`, `fallback_used`.
  - `event=diagnostics_dialog_open_failed` emitted when dialog cannot render normally; required fields: `incident_type`, `error_class`, `fallback_used=true`.
  - `event=diagnostics_copy_succeeded` emitted after successful copy action; required fields: `incident_type`, `command_executed`, `copy_result=success`, `fallback_used`.
  - `event=diagnostics_copy_failed` emitted after failed copy action; required fields: `incident_type`, `command_executed`, `copy_result=failure`, `error_class`, `fallback_used`.
  - `event=diagnostics_field_policy_fallback` emitted when malformed/partial payload forces fallback policy; required fields: `incident_type`, `command_executed`, `fallback_used=true`, `policy_reason`.
- Unknown execution-state telemetry alignment:
  - when execution state is unavailable, event payload keeps `command_executed=unknown` and UI-copy assertions use `unknown execution state` wording.
- Mapping IDs (authoritative):
  - `MAP-OPEN-UNK-01`: `event=diagnostics_dialog_opened` + `command_executed=unknown`.
  - `MAP-OPEN-FAIL-UNK-02`: `event=diagnostics_dialog_open_failed` + `command_executed=unknown`.
  - `MAP-COPY-SUCCESS-UNK-03`: `event=diagnostics_copy_succeeded` + `command_executed=unknown`.
  - `MAP-COPY-FAIL-UNK-04`: `event=diagnostics_copy_failed` + `command_executed=unknown`.
- Rollback trigger conditions:
  - reproducible app termination on dialog close,
  - copy reliability gate (decision-stable):
    - early gate: rollback-candidate if >= 2 copy failures in first 100 manual-QA attempts,
    - sustained gate: rollback-candidate if copy failure rate remains > 1% after >= 300 attempts,
    - both gates must be reported with per-environment breakdown.
  - missing critical diagnostics fields in command-failure incidents.
- Rollback decision ownership and precedence:
  - Decision owner: app runtime maintainers.
  - Precedence: runtime telemetry trends take priority when available; manual QA threshold is authoritative pre-release when telemetry is not yet representative.
  - Evaluation cadence: owner reviews copy reliability telemetry daily during rollout and immediately after each release-blocking QA run.
  - Threshold-breach SLA: if any rollback-candidate gate is breached, owner must record rollback/hotfix decision within 4 business hours.
  - Environment normalization for copy gates:
    - include an environment in global copy-reliability aggregation only after >= 50 attempts in that environment,
    - aggregate global copy-failure rate as attempt-weighted across included environments,
    - treat environments below inclusion floor as informational and non-blocking unless they breach by >= 2x the sustained gate.
  - Tie-breaker rule: if manual QA and runtime telemetry disagree, use the stricter outcome until additional evidence resolves discrepancy.
- Rollback adjudication playbook:
  - required evidence packet: manual-QA results table, telemetry slice for copy events, and environment matrix,
  - decision record must include timestamp, owner, and chosen action.
- Rollback mechanism:
  - revert dialog redesign to prior stable dialog implementation while retaining non-termination close behavior.
- Runtime fallback behavior:
  - if structured rendering fails, render minimal safe view (status + summary + details textarea) and keep copy/close actions available.

## Open questions
- None.

## Success criteria
- Dialog has three visual regions: status header, smart fields, details textarea.
- Status icon and accent color vary by incident type and are verifiable by UI tests per incident class; when execution state is unknown in combined fallback scenarios, subtitle/supporting copy must explicitly qualify uncertainty without implying confirmed command failure.
- Field-visibility policy is fully covered by deterministic tests, including malformed/partial payload cases and conflict handling.
- `Copy all details` copies full payload and emits success/failure signal for verification.
- Copy failure path shows inline helper text and preserves manual-copy textarea behavior.
- Copy failure helper text clears immediately after the next successful copy action in the same dialog session (success transition may be announced without persistent success helper text).
- `Close` closes only the dialog and does not terminate application process.
- Accessibility verification captures WCAG AA contrast checks for status/header and textarea separation.
- Accessibility verification includes deterministic keyboard-flow checks (focus order and button activation via keyboard).
- Accessibility verification includes screen-reader checks (dialog/status announced on open, textarea announced readonly multiline).
- Regression suite includes matrix coverage for: command executed/non-executed, stdout-only, stderr-only, both-empty outputs, and unknown exit-code fallback.
- Outcome metric: median triage time from dialog open to identifying incident type is reduced by >= 20% versus pre-redesign baseline in manual support drills.
- Outcome metric: support handoff completeness reaches >= 95% (required diagnostics present in copied payload during support drill samples).
- Outcome metric: copy-action reliability is >= 99% in supported environments over >= 300 attempts.
- Baseline method for outcome metrics:
  - triage-time baseline comes from pre-redesign support drills using the same incident scenarios,
  - support-handoff baseline comes from pre-redesign drill packets scored with the same rubric,
  - copy-reliability baseline uses pre-redesign dialog behavior where applicable and environment-normalized manual runs.
- Sampling protocol for outcome metrics:
  - minimum 30 drill samples for triage-time and handoff metrics,
  - minimum 300 copy attempts with per-environment breakdown,
  - all metrics reported with supported-environment stratification.
- Confidence rule for release decision:
  - no single low-volume environment may veto global success unless it exceeds failure thresholds with >= 50 attempts,
  - if confidence is inconclusive, release remains blocked pending more samples.

## Release evidence checklist
- Deterministic field-policy test matrix evidence covering normal + malformed/partial/conflict payloads.
- Keyboard-flow evidence (focus order and keyboard activation for action buttons).
- Screen-reader evidence (dialog/status announced on open; textarea announced readonly multiline).
- Screen-reader interrupted-mode evidence (open-narration replay behavior validated in both focus mode and browse/virtual-cursor mode, within declared timing tolerance).
- WCAG AA contrast evidence for status/header and textarea separation.
- Copy action evidence (success/failure telemetry events with required fields and emit points).
- Close behavior evidence proving dialog close does not terminate app process.
- Conditional evidence rule: if any copy-threshold rollback-candidate gate is breached, attach rollback adjudication evidence packet to release decision artifacts.

## Terminology map
- `full details` = `normalized diagnostics payload` shown in the details textarea and copied by `Copy all details`.
- `details textarea` = readonly view of the same `normalized diagnostics payload` used by copy action.
