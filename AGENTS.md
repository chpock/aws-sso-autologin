# AGENTS.md

## Fast start (use these, do not guess)
- `make prepare-dev` - create `.venv` (if missing), upgrade pip, install dependencies and dev dependencies (pytest, etc.). Use this for development.
- `make prepare` - create `.venv` (if missing), upgrade pip, install runtime dependencies only.
- `make test` - run lint check, then test suite via `.venv/bin/pytest`.
- `make test-verbose` - same with `-v`.

### For AI agents (automated/testing contexts)
- `make run-agent` - run app in agent-safe mode with preflight checks only (exits after checks complete).
  - Sets 60-second watchdog timeout (`AWS_SSO_AUTOLOGIN_TIMEOUT=60`).
  - Runs with `--check-only` flag (no daemon loop, no indefinite blocking).
  - Returns exit code: 0 (success), 1 (preflight failure), 124 (watchdog timeout).
  - **AI agents MUST use this target - never use `make run`.**

### For interactive/daemon use (DO NOT USE in automation)
- `make run` - run app as daemon with automatic mode detection (interactive use only).
  - **WARNING**: This starts a long-running daemon process that blocks indefinitely.
  - **AI agents and automation scripts MUST NOT use this target.**

## Focused verification
- Single test file: `.venv/bin/pytest tests/test_service.py -q`
- Single test: `.venv/bin/pytest tests/test_service.py::test_check_tray_host_available_true_for_hyprland -q`

## Runtime behavior that is easy to misread
- `make run` can exit with code 1 before UI startup if tray-host preflight fails.
- For that failure, trust structured stdout logs first:
  - `event=tray_host_unavailable_unknown` or `event=tray_host_unavailable_protocol_mismatch` (from `aws_sso_autologin/service.py`)
  - `event=tray_host_preflight_failed` (from `aws_sso_autologin/__main__.py`)
- On Hyprland, detection is mapped as `TrayHostType.GENERIC` and considered StatusNotifier-capable in current code.

## Real entrypoints and boundaries
- App entrypoint: `aws_sso_autologin.__main__:main` (also wired as script `aws-sso-autologin` in `pyproject.toml`).
- Tray-host detection/preflight logic: `aws_sso_autologin/service.py`.
- Main runtime orchestration (Qt init, preflight, operators, event loop): `aws_sso_autologin/__main__.py`.

## Test environment quirks
- Tray/UI tests instantiate real `QApplication` (`tests/test_tray.py`); if PySide6 is missing, collection fails. Run `make prepare` first.
- No CI/workflow config is present in repo; local `make test` is the authoritative verification path.

## Current tooling reality
- `make lint` is a placeholder message only (no linter configured).
- `.gitignore` still contains legacy Go-oriented patterns; do not infer Go tooling from it.

## Git workflow convention
- Use Conventional Commits for all commit subjects: `<type>(<scope>): <summary>`.
- Prefer adding a scope that names the primary area changed (for example: `service`, `tray`, `tests`, `docs`, `deps`); omit scope only when no single area fits.
- Keep the first line as a concise summary in imperative mood, lowercase start, no trailing period, ideally <= 72 characters.
- Use valid types with intent: `feat` (new behavior), `fix` (bug fix), `refactor` (internal change without behavior change), `test`, `docs`, `chore`, `build`, `ci`, `perf`, `revert`.
- Separate subject and body with one blank line.
- In the body, describe changes as concrete bullet points, with the first bullets covering why and impact before low-level details.
- Prefer explicit bullets such as: what changed, why it changed, user/runtime risk, test or verification notes, and follow-up actions.
- Wrap body lines at about 72 characters and use short bullet points when helpful for readability.
- Reference issues or tickets in the footer (for example: `Refs: #123`, `Closes: #123`) and include breaking changes explicitly (`BREAKING CHANGE: ...`) when applicable.
- Example:
  ```
  fix(service): classify protocol mismatch preflight failures

  - detect protocol mismatch during tray-host preflight
  - explain early startup exit in structured logs on unsupported hosts
  - reduce ambiguous failure triage for operators

  Refs: #123
  ```

## Project state from session history
- Main branch already contains the full tray app feature merge (`621603a Merge aws-sso-autologin`).
- Branch-level review closure is recorded in `docs/leyline/plans/2026-05-09-aws-sso-autologin-review-log.md`:
  - `Code review complete - round 4 - 2026-05-09`
  - `Design review complete - round 3 - 2026-05-09`
- The current expected baseline is green locally (`make test`), including tray/UI tests.

## Spec artifacts (source of truth)
- Product spec: `docs/leyline/specs/2026-05-09-aws-sso-autologin-design.md`
- UX spec: `docs/leyline/design/2026-05-09-aws-sso-autologin-ux.md`
- Plan: `docs/leyline/plans/2026-05-09-aws-sso-autologin.md`
- Review log: `docs/leyline/plans/2026-05-09-aws-sso-autologin-review-log.md`

## When changing behavior, update specs in the same task
- If you change runtime behavior, user-visible copy/state semantics, thresholds, failure handling, or contracts, update the matching spec docs first (or in the same change), then code/tests.
- Keep product and UX specs aligned with implementation; do not leave intentional drift undocumented.
- After spec edits, append new approval markers with incremented rounds (same date format already used):
  - Product: `Product spec approved - round <N> - YYYY-MM-DD`
  - UX: `UX spec approved - round <N> - YYYY-MM-DD`
- If review expectations change, record them in the review log and ensure completion markers are re-emitted only after new findings are resolved.

## Minimum verification before claiming done
- Run targeted tests for changed modules plus `make test` before completion claims.
- For tray-host/startup issues, include `make run-agent` output with structured `event=` logs in your notes; those logs are part of the diagnostic contract.

## Logging requirements
- All application actions must be thoroughly logged using appropriate log levels based on message importance (from `trace` to `error`).
- All external interactions (command execution, HTTP requests, IPC calls, etc.) must be logged.
- Full details of external interactions (request/response bodies, headers, command output, exit codes, etc.) must be available at `trace` log level.
- Use structured logging with key-value pairs (e.g., `event=auth_flow_started`, `duration_ms=150`) to enable filtering and aggregation.
- Prefer explicit log levels:
  - `trace` - detailed external interaction payloads, function entry/exit with arguments
  - `debug` - internal state changes, configuration values, flow decisions
  - `info` - major lifecycle events, user-visible operations
  - `warn` - recoverable issues, deprecated usage, retries
  - `error` - failures that prevent operation completion
