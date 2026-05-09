# AI-safe run/test - product spec
Date: 2026-05-09
Author: human partner
Surfaces: developer-facing

## Problem
When an AI agent runs the application via `make run`, the process can enter a
long-lived daemon/UI event loop and block forever until manually terminated.
The same class of issue can appear in tests, especially when new tests are
added: daemon behavior can be started implicitly and cause hanging test runs.

## Goals
- Guarantee agent/automation runs do not block indefinitely.
- Enforce no-daemon-by-default behavior for tests.
- Allow daemon mode in tests only via explicit opt-in and documentation.
- Keep failure reasons deterministic and easy to triage via structured logs and
  exit codes.

## Non-goals
- Remove daemon mode as a feature.
- Perform a full runtime architecture rewrite.

## Constraints
- Preserve manual user workflows for long-lived interactive/daemon operation.
- Keep developer ergonomics simple (`make run`, `make test`).
- Make policy enforceable in code and tests, not convention-only.
- Reuse existing CLI behavior where possible, especially `--check-only`.

## Approaches considered
### Approach A - Policy + runtime guardrails around existing `--check-only`
Use `--check-only` as the canonical safe automation mode, enforce daemon
blocking by default in automation/tests, and add watchdog protections.
Trade-offs: moderate implementation effort, strongest protection against
regressions.

### Approach B - Wrapper-only timeouts
Keep runtime behavior unchanged and wrap calls with shell timeouts.
Trade-offs: fast to add but only treats symptoms, weak test-policy guarantees,
and brittle diagnostics.

### Approach C - Hard split of daemon and non-daemon entrypoints
Introduce fully separate command surfaces for short-lived and long-lived modes.
Trade-offs: very robust but higher refactor and migration cost.

## Recommendation
Adopt Approach A. Use existing `--check-only` as the official non-daemon path
for automation and tests, then enforce explicit daemon opt-in where needed.

## Proposed solution
- Treat `--check-only` as the canonical safe mode:
  - performs only bounded preflight/check behavior
  - must not initialize long-lived daemon/event-loop operators
  - exits deterministically with structured `event=` logs
- Add explicit daemon entry path for manual workflows (for example, dedicated
  make target or explicit CLI mode).
- In automation contexts, default to check-only semantics unless explicit daemon
  opt-in is present.
- Add an agent watchdog timeout for bounded automation runs.
- Enforce pytest policy:
  - daemon disabled by default
  - daemon allowed only with explicit marker (for example,
    `@pytest.mark.requires_daemon`)
  - daemon tests must document why daemon behavior is required
  - policy violation fails fast with actionable guidance

## Policy contract
- Automation-context mode decision order is deterministic:
  1. explicit CLI flag (`--check-only` or explicit daemon flag)
  2. make target contract (`make run` safe path, `make run-daemon` explicit)
  3. explicit env override (`AWS_SSO_AUTOLOGIN_MODE=check|daemon`)
  4. automation heuristics fallback (`CI`, `AI_AGENT`, `PYTEST_CURRENT_TEST`)
- Explicit daemon entrypoints for this change:
  - CLI daemon opt-in flag (existing or introduced in implementation)
  - `make run-daemon`
- `make run` must remain bounded and non-daemon in automation contexts.
- Daemon opt-in is rejected in automation contexts unless
  `AWS_SSO_AUTOLOGIN_ALLOW_DAEMON=1` is set explicitly.

## Exit code and watchdog contract
- `0`: check/policy pass.
- `1`: preflight/check failure.
- `2`: policy violation (disallowed daemon behavior or disallowed daemon test).
- `124`: watchdog timeout.
- Watchdog contract:
  - default timeout: 60 seconds (configurable via env)
  - start point: immediately before application startup orchestration
  - stop point: successful process exit or fatal failure
  - timeout behavior: emit timeout event, terminate process, return `124`

## Test enforcement design
- Daemon remains disabled by default in all tests.
- Daemon enablement requires both:
  - `@pytest.mark.requires_daemon`
  - test-level rationale string in docstring or inline comment
- Enforcement mechanism is mandatory:
  - collection-time marker validation for daemon test paths
  - runtime fixture guard that hard-fails on unmarked daemon startup attempts

## Observability and compatibility
- Policy/log events are contractual, not illustrative.
- Required fields for structured policy logs:
  - `event`
  - `mode`
  - `reason`
  - `exit_code`
- Contract events for this change:
  - `event=automation_daemon_blocked`
  - `event=test_daemon_requires_marker`
  - `event=check_only_completed`
  - `event=agent_watchdog_timeout`
- Event names and meanings are backward-compatible within the current major
  version of the project.

## Rollout and rollback
- Rollout:
  1. land policy enforcement and tests behind implementation branch
  2. run full `make test` and targeted startup checks
  3. validate `make run` in automation context and manual daemon workflow
- Rollback trigger examples:
  - false-positive daemon blocking in valid manual workflows
  - unstable timeout behavior across supported environments
- Rollback path:
  - disable new policy gate by env toggle
  - keep `--check-only` semantics intact

## Success criteria
- `make test` completes without hanging by default.
- Any implicit daemon startup in tests fails immediately and deterministically.
- Automation/agent `make run` path does not block indefinitely.
- Daemon behavior remains available only through explicit opt-in paths.

## Verification matrix
- CLI check-only path never enters daemon/event loop.
- Automation-context daemon request fails with exit code `2` and contract event.
- Watchdog timeout path emits timeout event and exits with `124`.
- Unmarked daemon test fails fast with actionable message.
- Marked daemon test with rationale is allowed to run daemon behavior.

## Open questions
- Whether to keep `make run-agent` as explicit helper target or document
  `make run` + env strategy only.

## Deep-discovery round 1 classification
- (S) Automation-context detection must be defined as a normative precedence
  model to avoid bypass and inconsistent behavior.
- (S) Safe default behavior and manual ergonomics require fixed command
  semantics for `make run` and `make run-daemon`.
- (O) Watchdog scope/start/cleanup semantics must be explicit for deterministic
  operations and testing.
- (S) Exit-code matrix must be normative in product spec, not only UX notes.
- (S) Daemon opt-in surface must be finalized for implementation and docs.
- (S) Pytest enforcement architecture must be explicit and mandatory.
- (O) Explicit anti-circumvention boundary is needed for daemon opt-in in
  automation contexts.
- (O) Structured log event fields and event set must be contractual.
- (O) Rollout and rollback requirements are needed to protect operators.
- (O) Minimum verification matrix must be explicit.

## Approvals
Product spec approved - round 1 - 2026-05-09
Product spec approved - round 2 - 2026-05-09

## Deep-discovery
Deep-discovery pass complete - round 1 - 2026-05-09
