# AI-safe run/test - UX spec
Date: 2026-05-09
Product spec: docs/leyline/specs/2026-05-09-ai-safe-run-test-design.md
Surfaces: developer-facing

## Public API surface enumeration
- CLI flag `--check-only` as canonical safe automation mode.
- Default application run path without `--check-only`.
- Explicit daemon opt-in path for long-lived operation.
- Test harness policy surface (`pytest` marker and fixtures).
- Make command surfaces (`make run`, `make run-daemon`, optional
  `make run-agent`).

## Error shapes and failure-mode contracts
- Automation context requesting daemon without explicit opt-in:
  - fail fast
  - non-zero exit code
  - actionable message describing allowed paths
- Test attempts daemon without required marker:
  - immediate test failure
  - guidance to add marker and rationale
- `--check-only` failures:
  - deterministic non-zero exit
  - structured `event=` log output for diagnosis

## Log / output schema
- Check-only path emits bounded lifecycle events and exits.
- Policy violation events are explicit and stable:
  - `event=automation_daemon_blocked`
  - `event=test_daemon_requires_marker`
  - `event=check_only_completed`
  - `event=agent_watchdog_timeout`
- Required structured fields for every policy event:
  - `event`
  - `mode`
  - `reason`
  - `exit_code`
- Output remains short, machine-greppable, and operator-readable.

## Exit-code semantics
- `0`: check/policy pass.
- `1`: preflight/check failure.
- `2`: policy violation (disallowed daemon behavior).
- `124`: watchdog timeout in automation run.

## Telemetry-label conventions
- Prefix policy events by domain:
  - `automation_*`
  - `test_*`
  - `check_only_*`
- Event names should be stable enough for assertions in tests.

## Documented failure modes
- Implicit daemon loop during automation run.
- Implicit daemon startup in tests.
- Unbounded run duration in AI-agent workflows.
- Ambiguous `--check-only` semantics leading to accidental regressions.

## Voice and tone
Reference strings:
- Error: "Daemon mode is blocked in automation context. Use --check-only or explicit daemon opt-in."
- Success: "Check-only completed successfully; no daemon loop started."
- Guidance: "This test requires daemon mode. Add @pytest.mark.requires_daemon and document why."

Canonical policy-failure templates:
- Automation daemon block: "Daemon mode is blocked in automation context. Use --check-only or set explicit daemon opt-in with AWS_SSO_AUTOLOGIN_ALLOW_DAEMON=1."
- Test daemon marker block: "This test requires daemon mode. Add @pytest.mark.requires_daemon and document why daemon behavior is required."
- Watchdog timeout: "Automation run exceeded timeout and was terminated safely."

## Deep-discovery round 1 outcome
- Product-spec revisions are material and required before implementation.
- UX copy and event schema are aligned to the revised contractual event and
  exit-code model.

## Non-goals
- Business logic changes unrelated to startup/run lifecycle.
- Removal of daemon capability.
- Broad CLI redesign beyond policy clarity and safety semantics.

## Approvals
UX spec approved - round 1 - 2026-05-09
UX spec approved - round 2 - 2026-05-09

## Design-interrogation
design-interrogation skipped - scope: developer-facing CLI/tool policy with straightforward error paths; deep-discovery coverage sufficient
