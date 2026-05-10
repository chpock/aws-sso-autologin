# AWS SSO Autologin - product spec
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
Product spec approved - round 7 - 2026-05-09
Product spec approved - round 8 - 2026-05-09
Product spec approved - round 9 - 2026-05-09
Product spec approved - round 10 - 2026-05-09
Product spec approved - round 11 - 2026-05-09
Product spec approved - round 12 - 2026-05-10

## Problem
Users with multiple AWS SSO profiles lose active sessions during normal work and must manually run `aws sso login` per profile. This tool should run as a tray-only Linux/Wayland desktop app, monitor SSO session validity, and perform controlled auto-login when an SSO session is explicitly expired or invalid.

## Goals
- Discover AWS profiles at startup and track only SSO profiles.
- Monitor all relevant AWS profile source files and refresh tracked profiles when those files change.
- Monitor application config and apply config changes without restart.
- Check each tracked SSO profile every 30 seconds using `aws sts get-caller-identity`.
- Trigger `aws sso login` only for explicit expired or invalid SSO session errors.
- Run logins strictly serially and enforce a per-profile login cooldown of 5 minutes.
- Provide tray-only status visibility and detailed error dialogs with full stdout and stderr from failed commands.

## Non-goals
- Supporting non-Linux desktop platforms.
- Providing a full settings window.
- Parallel login attempts for multiple profiles.
- Auto-remediation for non-SSO AWS errors.
- Localization (all strings are English only).

## V1 Known Limitations (to address in V2)
- **Non-English locale support:** The classifier assumes English AWS CLI error output. Systems with non-English locales (`LANG=de_DE`, `LANG=ja_JP`, etc.) may experience missed session expiration detection. Workaround: Set `LANG=C` in environment before launching the app. V2 will either force `LANG=C` on subprocess calls or expand classifier fixtures to cover major locales.
- **NFS/network filesystems:** File watchers and trust checks may behave unpredictably on NFS-mounted directories (spurious change events, permission quirks, non-atomic operations). V2 will add NFS-specific handling or document requirement for local filesystems.
- **X11/XEmbed support:** The app requires StatusNotifier-compatible tray hosts (modern Wayland/KDE/GNOME3+). X11-only environments or older XEmbed trays are not supported. V2 may add XEmbed fallback or explicit compatibility layer.
- **Queue position visibility:** At high profile counts (50+), users cannot see their position in the serial login queue or estimated wait time. V2 will add queue depth indicator to profile status rows.
- **Configurable slow-fail threshold:** The fixed 5 failures/24 hours threshold doesn't account for organizational session duration policies. High-churn environments may experience alert fatigue. V2 will make threshold configurable per-profile or derive from session duration.

## Constraints
- Runtime and UI stack: Python with Qt6 (`PySide6`).
- No main window; system tray icon and tray menu only.
- Tray-host preflight is mandatory at startup:
  - if a compatible StatusNotifier/system tray host is unavailable, do not start monitoring,
  - exit with non-zero code and emit actionable guidance to stdout that tray host support is required.
- Tray-host runtime health monitoring is mandatory:
  - heartbeat check every 30 seconds via D-Bus StatusNotifier ping,
  - on 3 consecutive heartbeat failures, escalate to structured stdout logging and signal-triggered diagnostic dump,
  - when tray-host is lost at runtime, pause monitoring after 30 seconds, emit structured log entry `tray_host_lost`, continue background checks only if explicitly configured via `tray_loss_behavior: continue` (default: `pause`).
- On startup, auto-login monitoring is enabled by default unless explicit safe-mode override is set for rollback.
- Right-click tray menu must include:
  - first item: status-dependent action — when a global error is active, an error action that opens a diagnostics dialog; otherwise a monitoring toggle (`Pause Monitoring` or `Resume Monitoring`). Clicking any first-item action closes the menu,
  - separator,
  - one entry per tracked SSO profile with `Profile: <name> - <status>`,
  - separator,
  - `Quit`.
- At high profile cardinality, tray-menu scalability rules apply:
  - first-row global control and `Quit` remain on the top-level menu,
  - when tracked SSO profiles exceed 40, profile rows are grouped into deterministic overflow submenus of at most 20 rows each,
  - each tracked SSO profile still maps to exactly one selectable row with unchanged row format.
- When AWS CLI is globally unavailable or profile discovery fails in a global way, replace the first toggle item with an explicit error item; clicking it closes the menu and opens a detailed error dialog.
- When monitoring is disabled by user:
  - stop all background activity,
  - do not run session checks,
  - do not watch files,
  - profile rows show OK with paused note.
- Monitoring enabled/disabled state is not persisted across restarts.
- Tray icon semantic set is fixed to: `enabled-ok`, `enabled-syncing`, `enabled-warning`, `enabled-error`, `disabled-paused`.
- Status precedence is fixed to: `global error > profile error/warning > syncing > ok`; when monitoring is disabled, `disabled-paused` always takes precedence.
- Command execution must capture stdout and stderr for diagnostics and enforce timeout/cancellation policy.
- Logging must use a modern, mature logging package and write to stdout.
- Use XDG variables wherever possible with conventional fallback paths.
- AWS CLI compatibility target is v2. Unsupported CLI version is treated as a global error with a clear first-row menu action.
- All security-sensitive file operations must be safe against symlink and race-condition attacks.
- First-row behavior is determined by two states:
  - global error present: the first row is an error action. Clicking it closes the menu and opens a diagnostics dialog,
  - no global error: the first row is a monitoring toggle (`Pause Monitoring` when monitoring is enabled, `Resume Monitoring` when disabled). Clicking it closes the menu and toggles monitoring.

## Approaches considered
### Approach A - Single-process Qt app (recommended)
Use one `PySide6` process with `QSystemTrayIcon`, `QMenu`, `QTimer`, and asynchronous command orchestration through Qt-safe workers. Keep a single in-memory state store and serialize login tasks in one queue.

Trade-offs: Lowest complexity for required behavior, easier state management, and straightforward testing with faked command execution. Requires careful queue and state transitions, but this is manageable within one process.

### Approach B - UI process plus worker process
Run tray UI in one process and AWS monitoring/login in another with IPC.

Trade-offs: Better isolation boundaries but significantly higher implementation and operational complexity for this scope. IPC protocol, lifecycle synchronization, and error propagation increase maintenance cost.

### Approach C - asyncio-first architecture with Qt bridge
Use asyncio as primary orchestrator and bridge it into Qt using `qasync`.

Trade-offs: Powerful and flexible, but introduces additional integration complexity and more moving parts than required for periodic checks and tray-state updates.

## Recommendation
Implement Approach A. It matches current requirements with the best complexity-to-value ratio, keeps behavior explicit and testable, and leaves clear extension points for future features.

## Runtime behavior
### Command-line interface contract
- CLI parser package: `typer` (Click-based) as the primary argument interface.
- Runtime settings are resolved through a dedicated, extensible settings resolver abstraction:
  - supports layered sources: defaults -> config file -> environment -> CLI flags,
  - produces one typed runtime settings object consumed by startup and logging setup,
  - adding a new runtime option requires registering it once in the resolver schema and mapping it to sources.
- `aws-sso-autologin --help` prints complete usage and exits with code `0`.
- `aws-sso-autologin --version` and `aws-sso-autologin -V` print resolved app version and exit with code `0`.
- Version string source follows existing runtime version policy (`embedded` first, fallback `0.0.0`).
- CLI flags must override equivalent environment controls when both are present:
  - `--log-level [error|warning|info|debug|trace]` overrides `AWS_SSO_AUTOLOGIN_DEBUG` and default logger level selection.
  - `--log-format [text|json]` overrides default stdout log renderer selection.
  - `--safe-mode` overrides `AWS_SSO_AUTOLOGIN_SAFE_MODE`.
  - `--tray-loss-behavior [pause|continue]` overrides `AWS_SSO_AUTOLOGIN_TRAY_LOSS_BEHAVIOR`.
- Log-level semantics:
  - default level remains current runtime default (`info` unless debug env/settings are active),
  - `debug` enables detailed operational diagnostics,
  - `trace` enables maximum verbosity including full event-level lifecycle logs,
  - invalid level values fail fast with actionable CLI parse error and non-zero exit.
- Log-format semantics:
  - default format is `text`,
  - `text` format uses colorized output when `stdout` is a TTY and plain text when not a TTY,
  - `json` format emits one structured JSON object per log event to stdout,
  - invalid format values fail fast with actionable CLI parse error and non-zero exit.
- Config-file parity for logging controls:
  - config supports `logging.level` with values `error|warning|info|debug|trace`,
  - config supports `logging.format` with values `text|json`,
  - CLI overrides config-file values when both are present.
- Add non-interactive preflight mode:
  - `--check-only` performs startup preflight checks (tray-host compatibility and profile discovery preconditions),
  - emits structured stdout events for pass/fail evidence,
  - does not create tray UI or enter Qt event loop,
  - exits `0` on successful preflight and non-zero on failure.
- Add profile scope filter:
  - `--profiles <name1,name2,...>` limits monitoring to explicit profile names after discovery,
  - unknown profile names are reported as actionable warning output and ignored,
  - if all requested names are unknown/non-SSO, app reports "No selected SSO profiles detected" and remains in idle-safe semantics.

### Application versioning and startup logging
- Runtime version source priority is fixed:
  1. embedded package version generated during CI/CD or Linux package build,
  2. fallback default version `0.0.0` when embedded metadata is unavailable.
- Release tags used for version derivation must match `vX.X.X`.
- Version derivation from git state uses nearest matching release tag:
  - exact tag commit resolves to `X.Y.Z`,
  - commits after tag resolve to `X.Y.Z.devN+g<sha>`.
- On every application start, structured stdout logs must include startup event,
  resolved version, and version source.

### Profile discovery and filtering
- Discover profiles at startup from AWS CLI/config sources.
- Keep only profiles that are SSO-capable.
- Ignore non-SSO profiles entirely in monitoring and tray profile rows.

### File monitoring
- Monitor all relevant files where AWS profile presence can change (including AWS config and credentials sources resolved from environment and standard fallbacks).
- Monitor app config file:
  - preferred path: `$XDG_CONFIG_HOME/aws-sso-autologin/config.yaml`,
  - fallback: `~/.config/aws-sso-autologin/config.yaml`.
- Reload affected state on file changes.
- File-watcher storm handling policy is mandatory:
  - use a fixed 750 ms settle window for debounce/coalescing,
  - deduplicate events by normalized absolute file path within the settle window,
  - allow only one in-flight reload/rediscovery pipeline,
  - if events arrive during an in-flight pipeline, queue exactly one follow-up rerun and collapse additional events into that rerun,
  - superseded intermediate events are skipped.
- Watcher-triggered reload activity must remain inside existing command concurrency, timeout, and spawn-rate budgets.
- Global profile-discovery retry interval when AWS CLI is unavailable is fixed to 30 seconds.

### Session checking and login
- Every 30 seconds run `aws sts get-caller-identity --profile <profile>` for each tracked SSO profile.
- `sts_check` subprocess concurrency is capped at 8 in-flight processes globally.
- Concurrency cap vs cadence validation: at 100 profiles, 30-second cycle, and 8-process cap, average per-check duration must not exceed 240 ms to maintain cadence,
- Per-check latency telemetry is mandatory: record `sts_check` duration per profile; if p95 per-check duration exceeds (30s × 8 ÷ profile_count), trigger observability alert `sts_check_capacity_exceeded` for capacity planning review.
- If and only if command output indicates explicit expired/invalid SSO session, enqueue `aws sso login --profile <profile>`.
- Expired/invalid classifier must be normative and versioned: it defines accepted patterns, precedence rules, and unknown-error fallback behavior.
- Classifier governance contract is mandatory:
  - canonical classifier fixture corpus path: `tests/fixtures/classifier/`,
  - fixture corpus must be versioned and include required AWS CLI/locale matrix coverage used by CI,
  - classifier change ownership is assigned to maintainer role,
  - any classifier pattern change is release-blocking until fixture corpus updates and validation pass,
  - release artifact manifest must include expected classifier corpus version and checksum,
  - startup enables monitoring only when local classifier corpus version/checksum matches release artifact manifest,
  - classifier corpus file watcher monitors corpus directory with same debounce/coalescing policy as config (750 ms settle window),
  - on corpus change at runtime, re-verify checksum against release manifest; on mismatch, force safe mode and global error action,
  - classifier corpus directory is subject to symlink/race protection same as other security-sensitive paths.
- Login operations must run strictly one at a time (global serialization).
- Serial login queue scalability limitation: at 100 profiles with realistic SSO delays (e.g., user interaction, MFA), worst-case cycle time is 100 × avg_login_duration; with 60-second average login time, full cycle takes ~100 minutes,
- Enforce minimum 5 minutes between login attempts per profile regardless of success or failure.
- Continue 30-second checks even when profile is in login cooldown.
- If a profile becomes valid again, show OK state immediately.
- Subprocess policy is mandatory for all AWS commands:
  - each command has a timeout,
  - timeout triggers graceful terminate first, then force kill on grace-period expiry,
  - pause/quit operations cancel in-flight commands and prevent new command starts.
- Scheduler overrun policy for the 30-second cadence is fixed:
  - if a cycle is still running when the next tick arrives, mark exactly one pending coalesced cycle,
  - do not queue additional backlog ticks while one coalesced cycle is already pending,
  - when active work completes, run one coalesced cycle immediately,
  - additional missed ticks are collapsed rather than replayed,
  - pause/disable clears pending coalesced work and blocks new starts.

### System signal handling
- The runtime installs explicit handlers for `SIGINT` and `SIGTERM` after Qt initialization.
- While the Qt event loop is running, the runtime must keep a lightweight periodic Python signal-pump timer active so terminal `Ctrl+C` (`SIGINT`) is observed promptly without repeated keypress bursts.
- On first termination signal, the app must log structured event `system_signal_received` with signal name and action `graceful_shutdown`, then execute the standard shutdown path.
- Shutdown path must log structured `shutdown_started` and per-step `shutdown_action` entries for operator stop, timer stop, tray close, and Qt event-loop quit request.
- If a second termination signal arrives while shutdown is already in progress, the app must log structured event `system_signal_force_exit` and perform immediate forced process exit with code `130`.

### Browser override per profile
- `config.yaml` defines browser override as an argument list per profile.
- For profile-specific login, create a temporary executable shell wrapper script that safely executes the configured command and passes `"$@"`.
- Set `BROWSER` environment variable to that wrapper path for the login process only.
- Remove wrapper file after command completion.
- Wrapper creation must be injection-safe and use an executable-capable directory (do not assume default temp is executable).
- Wrapper lifecycle requirements:
  - create using exclusive file creation semantics,
  - enforce restrictive permissions (owner read/write/execute only),
  - reject symlink targets and revalidate before exec,
  - always clean up wrapper file after login completion or cancellation,
  - wrapper execution failure handling:
    - if wrapper fails to execute (permission denied, missing interpreter, `execve` failure), capture error as `sso_login` failure with exit code 126/127,
    - include wrapper path, wrapper size, and permission bits in diagnostics for debugging,
    - classify wrapper execution failure as Error state for the profile with actionable dialog copy: "Browser wrapper failed to execute. Check browser configuration and permissions.",
- If no browser override exists for profile, do not set or mutate `BROWSER`.

### Error detail behavior
- Capture and store stdout/stderr and exit code for each failed relevant command using bounded diagnostics policy.
- Diagnostics capture and retention policy:
  - maximum capture per command stream is 48 KiB for `stdout` and 48 KiB for `stderr` (reduced from 64 KiB to fit 100 profiles within budget),
  - if a stream exceeds cap, preserve first 24 KiB and last 24 KiB with truncation marker `...[truncated <N> bytes]...`,
  - diagnostics are retained in-memory only (no diagnostics file persistence by this app),
  - retention uses split pool allocation:
    - per-profile pool: 8 MiB for latest failed command snapshot per profile (100 profiles × 96 KiB = 9.6 MiB max, fits within 8 MiB with compression/deduplication),
    - global pool: 4 MiB for latest 10 global failures,
    - pools are independent; global failures cannot evict per-profile data or vice versa,
  - total diagnostics memory budget is capped at 12 MiB with oldest-first eviction within each pool.
- Diagnostics security policy:
  - error dialog may show full captured details on explicit user action,
  - routine stdout logs must redact sensitive fields and avoid printing raw credential-like values,
  - logs must include enough structured metadata for debugging without exposing secrets,
  - secret pattern definition for redaction:
    - AWS Access Key ID patterns (e.g., `AKIA...`),
    - AWS Secret Access Key and session token values (high-entropy strings associated with credential contexts),
    - Pre-signed URL signatures (query parameters containing `X-Amz-Signature`, `Signature`),
    - Account IDs and role ARNs may be logged at `debug` level but redacted at `info` level and above,
  - shared redaction library is mandatory: same redaction logic must apply consistently across dialog export and log output paths,
  - redaction consistency is validated in integration tests: verify that secrets appearing in stderr are redacted identically in both dialog export and structured logs.
- Clicking profile menu item:
  - if profile status is OK, close menu only,
  - if status is Warning/Error, show detailed error dialog including diagnostics and explicit truncation notice when applied.
- Redacted incident export procedure:
  - dialog-triggered incident summary/export must include incident evidence schema fields and explicit redaction/truncation indicators,
  - export content must never include raw credential-like values.
- Config-migration diagnostics visibility:
  - when profiles are skipped due to invalid or incompatible config shapes, first-row global diagnostics must include skipped-profile summary (count, profile identifiers, reason class, remediation hint),
  - skipped-profile summary must remain reachable via first-row global error action and structured redacted logs.

## Command execution contract
- Command types: `profile_discovery`, `sts_check`, `sso_login`.
- Required per-command telemetry fields: `command_type`, `profile`, `exit_code`, `duration_ms`, `timed_out`, `stdout_bytes`, `stderr_bytes`, `stdout_truncated`, `stderr_truncated`, `stdout_omitted_bytes`, `stderr_omitted_bytes`.
- Timeout policy:
  - `sts_check`: 10 seconds timeout.
  - `profile_discovery`: 20 seconds timeout.
  - `sso_login`: 180 seconds timeout.
  - Timeout escalation is fixed: send terminate, wait 3 seconds grace, then force kill.
- Retry policy:
  - `sts_check`: no immediate retry within the same 30-second cycle; next attempt is next scheduled cycle.
  - `profile_discovery`: no additional retry beyond the fixed 30-second global discovery retry loop.
  - `sso_login`: no automatic retry after failure or timeout; next attempt requires a future explicit classifier hit and cooldown allowance.
- Hung-command handling must be deterministic and covered by integration tests with fake hanging subprocesses.

## Observability and operations
- Required counters:
  - total sts checks,
  - total login attempts,
  - login attempts suppressed by cooldown,
  - classifier outcomes (`expired`, `invalid`, `unknown`),
  - command timeouts,
  - global CLI-unavailable retry loops.
- Log rotation and retention policy:
  - if writing to file (not stdout): max file size 10 MiB, retain 5 rotated files,
  - recommended deployment: delegate to systemd journal or container log aggregator,
  - structured stdout logs are the primary observability surface for container/systemd environments.
- Periodic summary log every 5 minutes with profile-state totals (`ok`, `warning`, `error`, `paused`) and queue health indicators.
- Incident triggers and triage focus:
  - repeated global CLI-unavailable retries (10 consecutive loops = immediate triage),
  - repeated profile login failures (3 consecutive failures for one profile in 15 minutes = immediate triage),
  - slow-fail pattern detection: 5 failures for one profile within 24 hours (regardless of spacing) = warning triage,
  - timeout/hung-command recovery path activation (3 command timeouts in 10 minutes = immediate triage).
- Mandatory incident evidence schema for each trigger event:
  - `incident_id`, `trigger_type`, `first_seen_ts`, `last_seen_ts`,
  - `scope` (`global` or `profile`) and `profile` when applicable,
  - command telemetry snapshot (`command_type`, `exit_code`, `timed_out`, `duration_ms`, `stdout_bytes`, `stderr_bytes`, `stdout_truncated`, `stderr_truncated`, `stdout_omitted_bytes`, `stderr_omitted_bytes`),
  - runtime context (`safe_mode`, `scheduler_coalesced`, `queue_depth`),
  - environment context (`aws_cli_version`, `config_version`).
- Incident evidence retention boundaries:
  - raw stdout/stderr diagnostics remain bounded by in-memory diagnostics policy only,
  - incident evidence records are retained in-memory as a ring buffer of latest 50 incidents with max age 24 hours,
  - structured redacted incident summaries are always emitted to stdout logs for external retention.
- Restart-resilient trigger continuity is mandatory:
  - persist minimal redacted trigger checkpoints to `$XDG_STATE_HOME/aws-sso-autologin/incident-checkpoints.json` (fallback `~/.local/state/aws-sso-autologin/incident-checkpoints.json`),
  - rolling-window time basis uses monotonic elapsed-time checkpoints to avoid wall-clock skew artifacts,
  - trigger dedupe key is `trigger_type + scope + profile + command_type`,
  - on startup, retained checkpoints are loaded and aged-out entries are discarded before new trigger evaluation.

## Rollback and safe-mode operations
- Safe-mode entry paths:
  - User kill-switch: first menu row `Pause Monitoring` stops all background activity immediately.
  - Startup override: `AWS_SSO_AUTOLOGIN_SAFE_MODE=1` starts app with monitoring disabled for that run.
  - Config override: `safe_mode: true` in `config.yaml` starts monitoring disabled until explicitly re-enabled by user action or config edit.
- Release rollback checklist for maintainers:
  - enter safe mode on affected installs,
  - confirm command spawn suppression via telemetry (`sts_check`, `profile_discovery`, `sso_login` deltas stop),
  - capture global/profile diagnostics from dialog,
  - revert to last known-good release or classifier/config bundle,
  - resume monitoring only after one full 30-second cycle completes without new global errors.
- Rollback artifact integrity contract:
  - rollback artifact identity must include release ID, classifier corpus version, config schema version, and checksum manifest,
  - compatibility checks are required before restore (AWS CLI support, config schema support, artifact checksum validation),
  - rollback restore is atomic: stop monitoring, apply artifact set, validate checksums, restart in safe mode, run one verification cycle, then re-enable monitoring,
  - if startup classifier corpus parity check fails, force safe mode and global error action until a matching artifact set is restored.
- Rollback trigger thresholds:
  - classifier-regression signal: false-positive login trigger observed in validation corpus,
  - runtime-regression signal: timeout or CLI-unavailable incident threshold breaches as defined in Observability,
  - UX-regression signal: incorrect status-precedence rendering for global error versus profile states.
- Conflict-resolution transition matrix:
  - allowed: safe mode paused + no blocking global errors -> user can enable monitoring,
  - blocked: any blocking global error class active -> enable transition is rejected with actionable reason copy,
  - blocked: rollback verification failure or classifier artifact parity mismatch -> monitoring remains disabled and first row remains global error action,
  - allowed: blocking error cleared and verification passes -> first row returns to toggle semantics.

## Compatibility policy
- AWS CLI: v2 is required and supported.
- Unsupported AWS CLI versions are handled as explicit global errors with guided action text in menu/dialog.
- Dependency version floors are defined in project packaging metadata and validated in CI.
- Release artifact manifest must declare expected classifier corpus version/checksum and startup parity verification is mandatory before monitoring can enable.

## Ownership and escalation
- Maintainer role owns runtime incident triage and release decisions.
- Ownership continuity requirements:
  - maintain one secondary owner with backup triage authority,
  - document escalation path when primary owner is unavailable,
  - define tertiary escalation path for dual-unavailability (e.g., project mailing list, issue tracker auto-assignment, or documented incident commander protocol),
  - incident-acknowledgment SLO for configured trigger-class incidents is <= 4 business hours,
  - if acknowledgment SLO is breached, escalate automatically to secondary owner and record mandatory milestone re-baseline note before additional scope changes,
  - if secondary owner does not acknowledge within 4 additional business hours, escalate to tertiary path,
  - unresolved acknowledgment-SLO breaches block M5 release gate until closure evidence is recorded.
- Ownership responsibilities include:
  - global AWS CLI failure incidents,
  - repeated per-profile login failures,
  - timeout/hung-process behavior regressions,
  - dependency and compatibility breakage triage.

## Milestones and sequencing
- M1 (target: 2026-05-12) Core runtime shell: tray bootstrap, tray-host preflight/fallback, structured logging, config path resolution.
- M2 (target: 2026-05-14) Session control path: profile discovery/filtering, 30-second scheduler, classifier, serial login queue, cooldown. Depends on M1 close.
- M3 (target: 2026-05-16) Reliability and security hardening: timeout/kill policy, watcher storm controls, config trust checks, diagnostics caps/truncation. Depends on M2 close.
- M4 (target: 2026-05-20) Scale and UX operability: high-cardinality tray overflow behavior, latency/reachability validation at 50/100 profiles. Depends on M3 close.
- M5 (target: 2026-05-22) Release gate: soak/failure-budget validation, rollback/safe-mode verification, ownership/escalation docs complete. Depends on M4 close.
- Milestones close only when mapped measurable success criteria and required automated validations pass.
- Slip and re-baseline policy:
  - if a milestone gate is more than 2 business days late, maintainers must record an explicit re-baseline note in this spec before any additional scope expansion,
  - re-baseline notes must include cause, adjusted date, and impact on downstream milestone dates,
  - incident-acknowledgment SLO breaches automatically require a re-baseline note with escalation trace.
- Classifier-governance deadline:
  - classifier corpus versioning, ownership, and release-gate policy must be finalized by M3 close.

## Configuration format
`config.yaml` stores schema-versioned runtime controls and per-profile browser command arrays.

Top-level keys:
- `config_version` (integer, current value `1`).
- `safe_mode` (boolean, optional, default `false`).
- `profiles` map.

Compatibility and migration policy:
- Missing `config_version` is treated as legacy version `0` and migrated in-memory to version `1`.
- Unsupported future `config_version` is a global configuration error; app keeps last known-valid config.
- Legacy `browser` scalar string is migrated to a single-argument list without shell parsing.
- Invalid `browser` values (non-string, empty list, list with empty args) make that profile config invalid and skipped with diagnostics.
- Unknown keys are ignored with warning-level diagnostics.
- Skipped/invalid profile visibility is mandatory:
  - global diagnostics must show skipped-profile count, profile identifiers, and reason class per skipped profile,
  - diagnostics must include a concise remediation hint per reason class,
  - the same skipped-profile summary must be emitted in structured redacted logs.

Config trust policy before parse/apply:
- config path must resolve to a regular file and not a symlink.
- file owner UID must match current user UID.
- file must not be group-writable or world-writable.
- container/edge environment compatibility: if trust checks fail and environment suggests containerized execution (e.g., `/.dockerenv` exists, or `container` env var is set), emit specific diagnostic hint: "Config trust check failed in suspected container environment. Review UID mapping and volume permissions.",
- on trust-policy violation:
  - do not apply new config content,
  - keep last known-valid config active,
  - set global config error state with actionable diagnostics in first-row error action.

Example:

```yaml
config_version: 1
safe_mode: false
profiles:
  my-sso-profile:
    browser:
      - google-chrome
      - --profile-directory=Work
      - --new-window
```

## Proposed module layout
- `src/aws_sso_autologin/main.py` - package entrypoint.
- `src/aws_sso_autologin/app.py` - Qt app bootstrap and lifecycle.
- `src/aws_sso_autologin/domain/models.py` - typed domain models and status enums.
- `src/aws_sso_autologin/domain/state_store.py` - central state and update API.
- `src/aws_sso_autologin/tray/controller.py` - tray icon, menu, actions, dialogs routing.
- `src/aws_sso_autologin/aws/profile_discovery.py` - profile discovery and SSO filtering.
- `src/aws_sso_autologin/aws/session_checker.py` - sts check execution and error classification.
- `src/aws_sso_autologin/aws/login_runner.py` - serial login queue and cooldown logic.
- `src/aws_sso_autologin/aws/browser_wrapper.py` - safe wrapper creation/removal.
- `src/aws_sso_autologin/infra/command_runner.py` - subprocess wrapper with stdout/stderr capture.
- `src/aws_sso_autologin/config/loader.py` - config path resolution, parse, validation, hot reload.
- `src/aws_sso_autologin/watchers/file_watchers.py` - watched files orchestration and debouncing.
- `src/aws_sso_autologin/scheduler/loop.py` - periodic execution management.
- `src/aws_sso_autologin/logging/setup.py` - structured stdout logging.
- `src/aws_sso_autologin/errors/dialogs.py` - error dialog formatting helpers.

## Testing strategy
### Unit tests
- Config parsing and validation.
- SSO profile detection and filtering logic.
- Expired-session classifier for sts errors.
- Per-profile cooldown behavior.
- Browser wrapper command safety and cleanup.
- Menu label/status rendering logic.

### Integration tests
- Deterministic event-loop driven tests with mocked command execution.
- File-change simulation for AWS profile sources and config reload.
- End-to-end state transitions: OK -> expired -> login -> OK or Error.
- Global AWS CLI unavailable mode with first-menu error action.
- Pause/resume behavior with complete background stop when paused.
- Tray-host-unavailable startup path with deterministic non-zero exit and actionable guidance.
- Scheduler-overrun coalescing path with no unbounded tick backlog.
- Config trust-policy violations (symlink path, owner mismatch, insecure permissions) keep last known-valid config active.
- Classifier artifact parity mismatch at startup forces safe mode and persistent global error action.
- Restart trigger-continuity behavior preserves rolling-window incident thresholds across process restart.
- Skipped/invalid profile summary is visible in first-row global diagnostics and structured redacted logs.
- Benchmark protocol harness validates declared sampling/aggregation/pass-fail method reproducibly.

- Integration test: tray-host runtime loss simulation and pause/escalation behavior.
- Integration test: classifier corpus runtime modification detection and safe mode trigger.
- Integration test: wrapper execution failure (missing interpreter, permission denied) and error classification.
- Integration test: redaction consistency validation across dialog and log surfaces.
- Integration test: container environment trust-check failure and diagnostic hint.

Integration tests must not depend on user AWS environment, real credentials, or real network.

## Dependencies
- `PySide6`
- `pydantic`
- `PyYAML`
- `structlog`
- `watchdog`
- `pytest`
- `pytest-qt`
- `pytest-mock`
- `freezegun` (optional)

## Scale and unit economics
- Tested profile-count tiers: 10, 50, and 100 tracked SSO profiles.
- Steady-state resource budgets (10-minute local soak on reference Linux workstation):
  - 10 profiles: CPU average <= 3%, RSS <= 120 MiB.
  - 50 profiles: CPU average <= 8%, RSS <= 180 MiB.
  - 100 profiles: CPU average <= 15%, RSS <= 240 MiB.
- Tray-menu high-cardinality behavior:
  - profile rows are sorted case-insensitive alphabetically before submenu chunking,
  - overflow submenus use deterministic labels by row range (`Profiles 1-20`, `Profiles 21-40`, ...),
  - maximum 20 profile rows per submenu.
- Tray-menu responsiveness targets:
  - menu open latency at 50 profiles: p95 <= 150 ms,
  - menu open latency at 100 profiles: p95 <= 300 ms,
  - submenu open latency at 100 profiles: p95 <= 120 ms.
- Reachability requirement at 100 profiles:
  - warning/error profile diagnostics remain reachable via keyboard and pointer with no hidden or disabled profile rows.
- Spawn-rate budget:
  - `sts_check`: exactly one spawn per tracked profile per 30-second cycle (scheduler drift allowances excluded).
  - `profile_discovery`: at most one spawn per 30 seconds in CLI-unavailable mode.
  - `sso_login`: at most one concurrent process globally.
- Cost envelope expectation:
  - baseline operational cost scales linearly with profile count via `sts_check` cadence,
  - no unbounded retry loops are permitted for any command type.
- Normative benchmark protocol:
  - reference host class: Linux Wayland workstation, 8 vCPU, 16 GiB RAM (or CI-equivalent documented class),
  - warmup duration: 120 seconds before metric collection,
  - measurement window: 10 minutes steady-state for CPU/RSS; latency sampled across at least 100 menu/submenu opens per tier,
  - sampling cadence: CPU/RSS every 1 second;
  - aggregation method: nearest-rank p95/p99 from collected samples,
  - background-load envelope: no concurrent stress tools beyond baseline desktop session,
  - variance tolerance: p95/p99 measurements within 10% across 3 consecutive benchmark runs indicate reproducible results,
  - environmental exclusions: measurements corrupted by system load (>80% CPU, memory pressure, desktop compositor freeze) are excluded and re-run,
  - pass/fail rule: all declared tier targets must pass in the same benchmark run for milestone gate acceptance.

## Open questions
- Tray-host compatibility matrix across supported Linux/Wayland environments.
  - Owner: maintainer.
  - Closure condition: compatibility matrix documented and tray-host-unavailable fallback validated per supported environment class.
  - Must close by: M4 close.
  - Release-gate impact: unresolved at M4 is ship-block.
- Final `sts_check` concurrency-cap tuning from soak evidence.
  - Owner: maintainer.
  - Closure condition: 50/100-profile soak evidence confirms cap choice without violating CPU/RSS/latency targets.
  - Must close by: M4 close.
  - Release-gate impact: unresolved at M4 is ship-block.
- Config trust-policy edge cases on nonstandard filesystem/permission environments.
  - Owner: maintainer.
  - Closure condition: trust-policy integration tests cover edge cases and violation handling remains deterministic.
  - Must close by: M5 close.
  - Release-gate impact: unresolved at M5 is ship-block.
- Browser SSO flow duration distribution in target user population.
  - Owner: maintainer.
  - Closure condition: empirical data from early adopters or staging environment shows 95th percentile login duration;
    if 95th percentile exceeds 180 seconds, timeout policy must adjust or user guidance must address long flows.
  - Must close by: M4 close.
  - Release-gate impact: unresolved at M4 is advisory, at M5 is ship-block.
- Container/flatpak/snap distribution compatibility assessment.
  - Owner: maintainer.
  - Closure condition: documented compatibility or incompatibility with common container runtimes; if incompatible, installation docs must specify native Linux requirement.
  - Must close by: M5 close.
  - Release-gate impact: unresolved at M5 is ship-block.

## Success criteria
- App runs tray-only and logs to stdout.
- Only SSO profiles are listed and monitored.
- Profile and config file changes are reflected without restart.
- Session checks execute every 30 seconds while monitoring is enabled, with scheduler drift p95 <= 2 seconds and p99 <= 5 seconds in integration and soak validation.
- Auto-login runs serially and respects 5-minute per-profile cooldown.
- Browser override works via secure wrapper and wrapper is removed after login.
- Detailed error dialogs include complete stdout/stderr context.
- Disabling auto-login pauses all background activity.
- Recovery latency after explicit expired-session detection: login is enqueued within 5 seconds and starts within 30 seconds when queue is idle.
- False-positive auto-login trigger rate is 0 across mandatory non-expired fixtures in classifier corpus.
- Pause/resume transitions: pause blocks new command starts within 1 second and resume restarts scheduler activity within 5 seconds.
- Failure-budget criteria:
  - in healthy mocked runs at 100 profiles for 60 minutes, `command timeouts` counter remains 0,
  - in injected-hang runs, each forced timeout path recovers without deadlock and queue progress resumes within one scheduler cycle after kill.
- No deadlock in queue/loop progression under hanging-command integration scenarios.
- Burst file-event tests (100 rapid change events) coalesce deterministically and do not exceed defined spawn-rate budgets.
- At 50 and 100 profiles, tray overflow layout remains deterministic and row reachability is preserved for all profile diagnostics actions.
- At 50 and 100 profiles, tray menu latency targets from `Scale and unit economics` are met in automated validation.
- Tray-host-unavailable startup exits deterministically with actionable guidance and does not start monitoring.
- Scheduler-overrun validation confirms coalesced-cycle behavior with no unbounded backlog growth.
- Config trust checks block unsafe config files deterministically while preserving last known-valid runtime behavior.
- Ownership continuity and escalation metadata is documented and verifiable in project docs.
- Milestone completion evidence is traceable to measurable success checks and associated automated validations.
- Milestone re-baseline decisions and open-question closure decisions are traceable in spec revision history.
- Classifier governance policy (corpus versioning, ownership, release-blocking checks) is finalized by M3 close.
- Incident evidence records are emitted and retained per schema/retention policy for every configured incident trigger class.
- Startup blocks monitoring when classifier artifact parity check fails, forces safe mode/global error action, and emits actionable diagnostics.
- First-row control behavior remains deterministic under safe-mode/global-error/toggle conflicts per precedence matrix.
- Restarted app preserves trigger continuity and still escalates repeated failures according to configured rolling-window thresholds.
- Skipped/invalid profile summary is visible in global diagnostics with count, profile identifiers, reason class, and remediation hint.
- Benchmark-gate pass/fail results are produced using the normative benchmark protocol and are reproducible under declared harness constraints.
- Incident acknowledgment SLO compliance and any breach-triggered escalation/re-baseline actions are recorded before M5 release close.
- Unit and integration tests run successfully without user-specific AWS environment.

## Deep-discovery notes

Deep-discovery round 1 applied - 2026-05-09
Deep-discovery round 2 applied - 2026-05-09
Deep-discovery round 3 applied - 2026-05-09
Deep-discovery round 4 applied - 2026-05-09
Deep-discovery round 5 applied - 2026-05-09
Deep-discovery round 6 applied - 2026-05-09
Deep-discovery round 7 applied - 2026-05-09
Deep-discovery round 8 applied - 2026-05-09
Deep-discovery pass complete - round 8 - 2026-05-09

### Round 8 report - 2026-05-09
Questions asked: 100
Dimensions probed: assumptions, failure modes, missing requirements, dependencies, constraints, alternatives rejected, edge cases, scale boundaries, rollback paths, testing strategy, observability, security, operational concerns, team ownership, timelines, cost and unit economics, migration/backfill, success criteria, known-unknowns
Chain anchors:
  Q25: The chain traced from tray-host health monitoring through classifier runtime integrity to serial queue scalability—discovering that observability gaps in queue position and classifier coverage of edge cases create user confusion and false-positive error states.
  Q50: The chain challenged the assumption that 5 failures in 24 hours is a meaningful slow-fail pattern—discovering that fixed thresholds without normalization for session duration policy create alert fatigue in high-churn environments.
  Q75: The chain pivoted through security, operations, and rollback to discover that command validation, locale handling, and queue starvation lack defensive design—revealing that round 8's fixes for round 7 issues introduce new operational complexity without extending timeline or addressing environmental diversity (NFS, X11, non-English locales).

### Round 8 classification
- (S) Non-English locale handling is undefined and breaks classifier function: runtime behavior section - spec assumes English AWS CLI output but doesn't force `LANG=C` or handle localized errors.
- (O) Fixed slow-fail threshold creates alert fatigue without normalization: observability section - 5 failures/24h doesn't account for organizational session policies.
- (O) Queue starvation and position visibility gaps undermine UX: runtime behavior - profiles at end of 100-profile queue wait ~100 minutes with no visibility.
- (O) Tertiary escalation lacks SLO and further escalation path: ownership section - primary/secondary have 4-hour SLOs, but tertiary has no SLO.
- (R) Benchmark environmental detection is underspecified: scale section - "memory pressure" and "compositor freeze" lack definition.
- (R) Wrapper template and command validation are undefined: browser override section - "injection-safe" lacks template specification.
- (R) Tray recovery behavior after transient loss is undefined: constraints section - when tray host returns, auto-resume vs manual intervention not specified.
- (R) Classifier corpus verification lacks atomicity guarantees: runtime behavior - multi-file checksum can complete against hybrid states.
- (R) NFS/network filesystem behavior for corpus and config is undefined: multiple sections - file watchers may behave unpredictably on NFS.
- (E) X11/XEmbed support is implicitly excluded but not explicit: constraints section - StatusNotifier requirement limits to modern desktops without explicit X11 statement.

### Human partner decision
Material (S) and (O) findings were surfaced. Per human partner decision: **document limitations as V1 constraints and proceed**. Added "V1 Known Limitations" section to spec acknowledging non-English locale, NFS, X11, queue visibility, and configurable threshold as V2 features. Deep-discovery deemed converged for V1 scope.

### Round 1 report - 2026-05-09
Questions asked: 100
Dimensions probed: assumptions, failure modes, missing requirements, dependencies, constraints, alternatives rejected, edge cases, scale boundaries, rollback paths, testing strategy, observability, security, operational concerns, team ownership, timelines, cost and unit economics, migration/backfill, success criteria, known-unknowns
Chain anchors:
  Q25: The chain moved from session-check correctness into classifier ambiguity and showed that ambiguous error parsing can trigger either login storms or silent stale auth.
  Q50: The chain challenged the assumption that `aws sts get-caller-identity` is a stable binary signal, exposing CLI/version/error-shape drift as a core design risk.
  Q75: The chain pivoted through rollback/ops/security and found that command hangs, diagnostic data exposure, and undefined incident ownership can turn local failures into persistent operational debt.

### Round 1 classification
- (O) Unbounded command execution can deadlock monitoring and login progression.
- (S) Expired/invalid-session detection is underspecified and brittle across AWS CLI versions/locales.
- (O) Security/privacy boundary for diagnostics is missing.
- (O) Browser wrapper hardening requirements are incomplete for hostile local environments.
- (O) Observability and operability are not defined beyond stdout logging.
- (O) Ownership and support model is absent.
- (O) Dependency and compatibility constraints are incomplete.
- (S) Success criteria are mostly binary and not measurable against failure budgets.
- (S) Critical UI-operational semantics remain deferred in open questions for a `single-screen-ui` surface.

### Critical Issues
- Unbounded command execution can deadlock monitoring and login progression: lines 83, 85, 99 - no timeout, cancellation, or hung-process policy can block queue progress.
- Expired/invalid-session detection is underspecified and brittle: lines 84, 139 - no normative classifier contract risks false positives or missed refreshes.
- Security/privacy boundary for diagnostics is missing: lines 19, 47, 99 - full stdout/stderr handling needs explicit redaction and exposure policy.
- Browser wrapper hardening requirements are incomplete: lines 92, 95 - file-permission and anti-race constraints are not specified.
- Observability and operability are not defined beyond stdout logging: lines 47, 166, 168 - no counters or incident thresholds for global failure loops.
- Ownership and support model is absent: line 118 - no explicit maintainer/escalation ownership.
- Dependency and compatibility constraints are incomplete: line 153 - no version policy or AWS CLI compatibility matrix.
- Success criteria are mostly binary, not measurable: line 168 - missing false-positive, latency, and bound-style criteria.
- UX-operational risk is deferred too late for declared `single-screen-ui`: lines 4, 165 - icon/status semantics can affect user recovery behavior.

### Strengths
- Clear non-goals reduce architecture sprawl and keep scope focused.
- Single-process Qt recommendation matches current complexity.
- Serial login with cooldown reduces auth thrashing.
- Test strategy explicitly avoids dependence on real AWS environment.
- Global failure behavior is visible in the primary tray control surface.

### Revised Proposal
- Add subprocess execution contract: timeout, kill escalation, cancellation, and pause/quit behavior.
- Define explicit SSO expired/invalid classifier contract with tested pattern corpus and unknown-error policy.
- Add diagnostics data policy with redaction rules and explicit exposure boundaries for UI/logging.
- Harden browser wrapper spec with concrete file safety requirements (permissions, anti-symlink/TOCTOU checks, executable-dir fallback strategy).
- Add required telemetry counters and incident thresholds for repeated profile/global failures and command hangs.
- Add dependency version policy and AWS CLI compatibility matrix.
- Upgrade success criteria to measurable bounds (recovery latency, false-positive login rate, pause/resume latency).
- Add explicit ownership/escalation responsibilities for runtime incidents and release triage.

### Relevant paths audited
- `/w/projects/aws-sso-autologin/docs/leyline/specs/2026-05-09-aws-sso-autologin-design.md`

### Round 2 report - 2026-05-09
Questions asked: 100
Dimensions probed: assumptions, failure modes, missing requirements, dependencies, constraints, alternatives rejected, edge cases, scale boundaries, rollback paths, testing strategy, observability, security, operational concerns, team ownership, timelines, cost and unit economics, migration/backfill, success criteria, known-unknowns

### Round 2 classification
- (R) Quantitative timeout policy is still non-operational due qualitative timeout classes without concrete defaults/bounds.
- (O) Rollback path is undefined for classifier or login regressions.
- (S) Success criteria retain unresolved placeholder-style bound language and remain partly non-testable.
- (O) Cost and scale guardrails are not specified beyond counters.
- (O) Config evolution and migration policy is missing.

### Round 2 critical issues
- Quantitative timeout policy is still non-operational: line 126 - `short/medium/longer` lacks concrete thresholds and grace durations.
- Rollback path is undefined for bad classifier or login behavior regressions: runtime/ops/success sections - no explicit rollback or kill-switch procedure.
- Success criteria retain unresolved placeholders and missing hard bounds: line 231 - `within an agreed upper bound` is not testable.
- Cost and scale guardrails are not specified beyond counters: observability/success sections - no CPU, memory, or spawn-rate budget at profile-count tiers.
- Config evolution and migration policy is missing: configuration format section - no `config_version` compatibility/migration contract.

### Round 2 strengths
- Wrapper lifecycle hardening and symlink/TOCTOU constraints are explicit and actionable.
- Subprocess timeout/cancel/terminate/kill semantics and pause/quit cancellation behavior are now clearly mandated.
- Required counters, periodic summaries, and incident trigger categories provide actionable triage signal.
- Maintainer responsibilities for incidents, compatibility breakage, and releases are explicit.
- Integration test scenarios cover hangs, CLI-unavailable behavior, reload flows, and deterministic non-network execution.

### Round 2 revised proposal
- In `Command execution contract`, replace qualitative timeout classes with concrete defaults/bounds and explicit retry/backoff policy.
- Add `Rollback and safe-mode operations` section with kill-switch, rollback checklist, and trigger thresholds tied to counters.
- In `Success criteria`, replace placeholder bounds with fixed acceptance numbers and include failure-budget criteria.
- Add `Scale and unit economics` section with profile-count tiers and resource budgets.
- In `Configuration format`, add `config_version` and migration/backfill behavior for legacy/invalid shapes.

### Round 3 report - 2026-05-09
Questions asked: 100
Dimensions probed: assumptions, failure modes, missing requirements, dependencies, constraints, alternatives rejected, edge cases, scale boundaries, rollback paths, testing strategy, observability, security, operational concerns, team ownership, timelines, cost and unit economics, migration/backfill, success criteria, known-unknowns

### Round 3 classification
- (O) Diagnostics payload and retention policy is unbounded for full stdout/stderr capture and dialog exposure.
- (O) File-watcher event-storm handling is underspecified (debounce/coalescing/dedup/in-flight reload policy).
- (S) 100-profile tray menu scalability is not reconciled with required one-row-per-profile UX constraints.

### Round 3 critical issues
- Unbounded diagnostics payload and retention policy: lines 115-123 - no explicit capture-size, truncation, retention-age/count limits, or memory cap behavior.
- File-watcher event storm handling is underspecified: lines 80-87 - no debounce/coalescing contract, duplicate suppression, or superseded-event cancellation semantics.
- 100-profile tray-menu scalability is not operationally reconciled with UX constraints: lines 34-39, 256-264 and UX rows lines 13-17, 55-67 - no overflow/grouping strategy or responsiveness criteria at high profile counts.

### Round 3 strengths
- Timeout quantification, kill escalation, and deterministic hung-command recovery are explicit and test-oriented.
- Rollback/safe-mode pathways are concrete and tied to telemetry checks.
- Success criteria are measurable (drift, recovery latency, failure budget, false-positive target).
- Wrapper security hardening is explicit (exclusive create, restrictive permissions, anti-symlink/TOCTOU revalidation, guaranteed cleanup).
- Config migration policy is clear (`config_version`, legacy handling, unsupported-future behavior, invalid-profile skip semantics).

### Round 3 revised proposal
- In `Error detail behavior` and `Command execution contract`, add diagnostics budget policy: maximum captured bytes per stream, truncation markers, retention count/age caps, and redaction-before-log ordering.
- In `File monitoring`, define watcher debounce/coalescing window, duplicate-event suppression keys, and single in-flight reload/rediscovery rule with superseded-event cancel-or-skip semantics.
- In `Constraints`, `Scale and unit economics`, and `Success criteria`, define tray overflow strategy for large profile sets and add measurable high-cardinality UX criteria (menu-open latency, keyboard navigation responsiveness, diagnostics action reachability).

### Round 4 report - 2026-05-09
Questions asked: 100
Dimensions probed: assumptions, failure modes, missing requirements, dependencies, constraints, alternatives rejected, edge cases, scale boundaries, rollback paths, testing strategy, observability, security, operational concerns, team ownership, timelines, cost and unit economics, migration/backfill, success criteria, known-unknowns

### Round 4 classification
- (S) Tray-host availability is unspecified for a tray-only app.
- (O) STS-check concurrency limits are missing at high profile counts.
- (O) Scheduler overrun policy is not defined when a 30-second cycle cannot finish in time.
- (O) Config trust boundary and file-permission policy are underspecified.
- (O) Operational ownership model is single-point and lacks continuity requirements.
- (R) Timeline and delivery sequencing are absent from acceptance criteria.
- (R) `Open questions: None` remains inconsistent with unresolved known-unknown classes.

### Round 4 critical issues
- Tray-host availability is unspecified for a tray-only app: constraints/success criteria sections - no behavior contract when no StatusNotifier/system tray is available.
- STS-check concurrency limits are missing at high profile counts: session checking + scale sections - no hard cap on simultaneous `sts_check` processes at 50-100 profiles.
- Scheduler overrun policy is not defined when a 30-second cycle cannot finish: session checking + success criteria sections - no explicit skip/coalesce/backlog behavior.
- Config trust boundary and file-permission policy are underspecified: browser override + configuration sections - no required ownership/permission checks before config apply.
- Operational ownership continuity is underspecified: ownership section - no secondary owner/escalation continuity expectations.
- Timeline and delivery sequencing are absent: goals/success sections - no phase ordering or milestone gating.
- `Open questions: None` is not credible with unresolved known unknowns: open questions section does not track remaining design risks.

### Round 4 strengths
- Timeout, termination, and hang-recovery contracts remain concrete and testable.
- Watcher storm controls (debounce, dedup, single in-flight pipeline, queued rerun collapse) are explicit.
- Diagnostics budgeting and truncation behavior are bounded and operational.
- Safe-mode rollback pathways and incident trigger thresholds are clear.
- High-cardinality tray behavior now has explicit latency and reachability targets.
- Success criteria remain measurable across drift, recovery, and failure-budget checks.

### Round 4 revised proposal
- In `Runtime behavior -> Session checking and login`, add explicit `sts_check` concurrency cap and overrun policy (`skip` vs `coalesce`, carry-over limits, pause/reset behavior).
- In `Constraints` and `Success criteria`, add tray-host-unavailable fallback contract with actionable user guidance and acceptance checks.
- In `Configuration format` and security constraints, add owner/permission/symlink trust checks for config before parse/apply, with violation handling.
- In `Ownership and escalation`, add continuity requirements (secondary owner, escalation path, incident response expectations).
- Add lightweight milestone sequence tied to existing measurable success criteria.
- Replace `Open questions: None` with explicitly tracked remaining known unknowns until closure.

### Round 5 report - 2026-05-09
Questions asked: 100
Dimensions probed: assumptions, failure modes, missing requirements, dependencies, constraints, alternatives rejected, edge cases, scale boundaries, rollback paths, testing strategy, observability, security, operational concerns, team ownership, timelines, cost and unit economics, migration/backfill, success criteria, known-unknowns

### Round 5 classification
- (O) Classifier governance is underspecified beyond "normative and versioned".
- (R) Timeline risk is unmanaged at the milestone layer.
- (O) Rollback artifact strategy is incomplete.
- (O) Observability does not define structured incident evidence retention boundaries.
- (R) Known-unknown closure lacks deadline discipline.

### Round 5 critical issues
- Classifier governance is underspecified beyond "normative and versioned": runtime/testing/compatibility sections - no required fixture corpus versioning, update ownership, or release-gate policy for classifier changes.
- Timeline risk is unmanaged at the milestone layer: milestones section - no dates, dependency gates, or slip/rebaseline policy.
- Rollback artifact strategy is incomplete: rollback section - no rollback artifact identity/checksum model, compatibility checks, or atomic restore procedure.
- Observability does not define structured incident evidence retention boundaries: observability and diagnostics sections - no minimum evidence schema or retention window for intermittent incidents.
- Known-unknown closure lacks deadline discipline: open questions and milestones sections - no mandatory deadline binding to release gates.

### Round 5 strengths
- Command timeout, termination, cancellation, and coalesced-overrun semantics are concrete and testable.
- Security posture for local threat models is strong: config trust checks, wrapper hardening, anti-symlink/race controls, and bounded diagnostics.
- Scale behavior is measurable with profile-count tiers, resource budgets, deterministic overflow behavior, and latency/reachability targets.
- Safe-mode and rollback controls are explicit and tied to observability thresholds.
- Ownership model includes explicit primary and secondary continuity roles.

### Round 5 revised proposal
- In `Runtime behavior -> Session checking and login`, `Testing strategy`, and `Compatibility policy`, add classifier-governance contract: fixture corpus location, required CLI-version/locale matrix, change owner, and release-blocking validation on classifier pattern changes.
- In `Milestones and sequencing`, add target dates, dependency edges, slip thresholds, and explicit re-baseline procedure when a gate misses target.
- In `Rollback and safe-mode operations`, define rollback artifact model (versioned release ID plus classifier/config bundle checksum), compatibility verification steps, and atomic rollback/verification checklist.
- In `Observability and operations` and `Error detail behavior`, define mandatory incident evidence schema (minimum fields, correlation IDs, retention window, redacted export procedure) for each incident trigger.
- In `Open questions` and `Milestones and sequencing`, bind each open question to a milestone deadline and release-gate impact rule (`must close before M4/M5` or ship-block).

### Round 6 report - 2026-05-09
Questions asked: 100
Dimensions probed: assumptions, failure modes, missing requirements, dependencies, constraints, alternatives rejected, edge cases, scale boundaries, rollback paths, testing strategy, observability, security, operational concerns, team ownership, timelines, cost and unit economics, migration/backfill, success criteria, known-unknowns

### Round 6 classification
- (O) Incident counters/trigger windows reset on restart and can mask repeated failures.
- (S) Safe-mode, global-error, and user-toggle precedence is underdefined in conflict states.
- (O) Classifier governance lacks runtime rollout/rollback compatibility coupling at boot.
- (R) Resource-budget measurement protocol is not sufficiently normative for reproducible pass/fail evaluation.
- (O) Legacy/invalid config migration path can leave long-lived silent partial-profile behavior.
- (R) Ownership escalation expectations are not yet bound to concrete response SLO and breach behavior.

### Round 6 critical issues
- Incident counters and trigger windows reset on restart can create blind spots for repeated failures: observability + success criteria sections do not require restart-resilient trigger continuity.
- Startup safe-mode precedence is underdefined when hard global errors coexist with user enable actions: constraints/rollback/UX flows do not provide one deterministic conflict-resolution table.
- Classifier governance lacks explicit rollout/rollback coupling to runtime binary compatibility: classifier governance + rollback integrity sections do not require boot-time corpus/version parity verification.
- Resource budgets are defined without normative measurement protocol: scale/success sections lack required benchmark harness conditions and aggregation rules.
- Migration path for legacy/invalid profile config remains lossy for operators: configuration section allows profile skip with diagnostics but lacks explicit surfaced skipped-profile summary requirement.
- Ownership/escalation is structurally defined but not operationally enforceable: ownership/milestone sections do not set concrete acknowledgment SLO and breach actions.

### Round 6 strengths
- Subprocess control remains robust and test-oriented (timeouts, terminate/kill escalation, cancellation, cooldown, overrun coalescing).
- Local security posture remains strong (wrapper hardening, trust-policy checks, bounded diagnostics/redaction).
- High-cardinality tray behavior remains deterministic and measurable with explicit latency/reachability targets.
- Safe-mode/rollback pathways are explicit, integrity-aware, and operationally actionable.
- Classifier governance now has fixture ownership and release-blocking policy foundations.
- Product and UX specs remain aligned on precedence and diagnostics interaction surfaces.

### Round 6 revised proposal
- In `Observability and operations` and `Success criteria`, add restart-resilient incident continuity semantics (rolling-window checkpoint source, dedupe key, and trigger evaluation basis across restarts).
- In `Constraints`, `Rollback and safe-mode operations`, and UX state/flow sections, add a deterministic conflict-resolution matrix for first-row control precedence across safe mode, global error classes, and user toggle intent.
- In `Session checking and login`, `Rollback artifact integrity contract`, and `Compatibility policy`, require boot-time classifier corpus/version/checksum parity verification against release artifact manifest, with forced global error + safe mode on mismatch.
- In `Scale and unit economics` and `Testing strategy`, define a normative benchmark protocol (reference host class, background-load constraints, warmup duration, sample interval, and p95/p99 aggregation method).
- In `Configuration format`, `Error detail behavior`, and UX diagnostics sections, require explicit surfaced reporting of skipped/invalid profile configs (count, profile identifiers, reason class).
- In `Ownership and escalation` and `Milestones and sequencing`, replace expectation-only wording with concrete incident-acknowledgment SLO and breach-triggered re-baseline/escalation actions.
