# AWS SSO Autologin - UX spec
Date: 2026-05-09
Product spec: docs/leyline/specs/2026-05-09-aws-sso-autologin-design.md
Surfaces: single-screen-ui

## Approvals
UX spec approved - round 1 - 2026-05-09
UX spec approved - round 2 - 2026-05-09
UX spec approved - round 3 - 2026-05-09
UX spec approved - round 4 - 2026-05-09
UX spec approved - round 5 - 2026-05-09
UX spec approved - round 6 - 2026-05-09
UX spec approved - round 7 - 2026-05-09
UX spec approved - round 8 - 2026-05-09
UX spec approved - round 9 - 2026-05-09
UX spec approved - round 10 - 2026-05-09
UX spec approved - round 11 - 2026-05-09
UX spec approved - round 12 - 2026-05-10
UX spec approved - round 13 - 2026-05-10
UX spec approved - round 14 - 2026-05-11
UX spec approved - round 15 - 2026-06-05
UX spec approved - round 16 - 2026-06-06
UX spec approved - round 17 - 2026-06-06
UX spec approved - round 18 - 2026-06-06
Design-interrogation pass complete - round 1 - 2026-05-09

## Design-interrogation notes

### Round 1 report - 2026-05-09
Questions asked: 100
Dimensions probed: State completeness, Flow failure paths, Voice consistency, Platform conventions, Accessibility target realism, Accessibility tree correctness, Cross-surface state leakage, Perceived latency, Copy density, Information architecture
Chain anchors:
  Q25: The chain traced state matrix inconsistencies—specifically that Empty/Loading states are underspecified for startup halt paths, that Warning conflates transient progress with actual problems, that overflow submenus lack status aggregation, and that Error state labels in the matrix don't align with voice reference strings, revealing a documentation coherence problem where multiple UX surfaces describe the same states with different vocabularies.
  Q50: The chain pressured voice consistency and platform accessibility—finding that reference strings and matrix labels diverge in format and casing, that safe-mode states have orphaned copy not mapped to matrix cells, that queue position visibility is acknowledged as a V2 limitation but still referenced in V1 flow text, and that StatusNotifier accessibility implementation details remain unresolved against the "no icon only" requirement.
  Q75: The chain pressured failure paths and state precedence—discovering that compound states (safe mode + global error, user toggle + global error) aren't explicitly documented in the matrix, that classifier governance terminology may violate voice guidelines about internal shorthand, that quit/cancel operations lack defined UX feedback states, and that immediate OK transitions after login could create visual flashing without grace periods.

### Critical UX Issues
- State matrix uses inconsistent labeling conventions between matrix cells and voice reference strings
- Warning state conflates transient progress with actual problems
- Overflow submenus lack status aggregation forcing exhaustive search
- Queue position acknowledged as V2 limitation but referenced in V1 flow text
- Classifier governance terminology uses internal shorthand
- Compound states (safe mode + global error) not documented in matrix
- Quit operation lacks defined UX feedback for in-flight cancellation
- Immediate OK transition after login could create visual flashing
- Empty column doesn't document startup halt path
- Accessibility implementation details unresolved for StatusNotifier

### Human partner decision
Per human partner decision: **document UX limitations as V1 constraints and proceed**. Added "V1 UX Limitations" section to spec. Design-interrogation deemed complete for V1 scope.

## Surfaces enumerated
- `CLI command surface`: startup invocation feedback for `--help`, `--version`/`-V`, and operational flags.
- `System tray icon`: always-visible status indicator for monitoring and sync health.
- `Tray context menu`: primary interaction surface for control and status visibility.
- `Global control row`: first menu row for enable/disable toggle, or global error action when AWS CLI/discovery/config is unavailable/invalid, including unsupported AWS CLI version and unsupported config version cases.
- `Profile status rows`: one row per tracked SSO profile, with concise status text, shown directly or inside deterministic overflow submenus at high cardinality.
- `Profile overflow submenus`: deterministic range-labeled submenu containers used when tracked profile count exceeds top-level row budget.
- `Error details dialog`: modal diagnostics window for Warning/Error conditions.
- `Quit row`: explicit app shutdown action.

## User flows
### Flow 0 - CLI invocation and quick-exit modes
1. User runs `aws-sso-autologin --help`.
2. CLI prints usage, options, and short descriptions.
3. Process exits `0` without creating tray surfaces.

Failure path: invalid flag or malformed option value prints actionable parse error and exits non-zero.

### Flow 0d - Log verbosity selection
1. User runs `aws-sso-autologin --log-level debug` for detailed runtime diagnostics.
2. User may run `aws-sso-autologin --log-level trace` for maximal lifecycle-level logging.
3. Runtime applies selected verbosity before startup logging and all subsequent events.

Failure path: unsupported log level prints valid choices and exits non-zero.

### Flow 0e - Log format selection
1. User runs `aws-sso-autologin --log-format text` for human-readable logs.
2. Default behavior uses `text` logs when no format is provided.
3. In `text` mode, runtime enables colorized output when stdout is a TTY and falls back to plain text otherwise.
4. User runs `aws-sso-autologin --log-format json` to emit structured machine-readable logs.

Failure path: unsupported log format prints valid choices and exits non-zero.

### Flow 0f - Settings source precedence
1. User sets logging options in config file (`logging.level`, `logging.format`).
2. User optionally provides CLI overrides (`--log-level`, `--log-format`) for current run.
3. Runtime resolves effective settings via deterministic precedence and logs effective values at startup.

Failure path: invalid config value produces actionable validation error; if valid CLI override is present for the same field, runtime uses CLI value and reports config issue as warning diagnostics.

### Flow 0b - Version check
1. User runs `aws-sso-autologin --version` or `aws-sso-autologin -V`.
2. CLI prints resolved app version.
3. Process exits `0` without creating tray surfaces.

Failure path: if version metadata is unavailable, CLI prints fallback `0.0.0` per runtime contract and exits `0`.

### Flow 0c - Preflight-only operational check
1. User runs `aws-sso-autologin --check-only`.
2. Runtime executes tray-host and startup readiness preflight.
3. Runtime emits structured stdout pass/fail evidence.
4. Process exits without entering Qt event loop.

Failure path: on failed preflight, runtime emits actionable reason and exits non-zero.

### Flow 1 - Startup and healthy monitoring
1. App launches with auto-login monitoring enabled by default, unless safe mode is active via startup env/config override.
2. App writes startup version event to structured stdout logs with `version` and `source` fields.
3. Tray icon appears in enabled state.
4. App discovers SSO profiles and starts 30-second checks.
5. Menu shows control row, profile rows with healthy text, and quit action.
6. Profile rows display current state and next action together when actionable, for example `<name> - OK -> Pause monitoring` or `<name> - OK (paused) -> Resume monitoring`.

Failure path: if tray-host preflight fails (no compatible StatusNotifier/system tray host), no tray icon/menu/dialog is shown, app exits non-zero, and one actionable stdout message explains tray host support is required. If startup succeeds but one or more profiles fail checks, those profile rows show Warning or Error status and become actionable for diagnostics.

### Flow 2 - Expired SSO session recovery
1. Periodic check detects explicit expired/invalid SSO session for profile.
2. Profile row moves to warning state indicating refresh in progress or needed.
3. Profile is queued for login; logins execute strictly one at a time.
4. Successful login returns profile to OK on subsequent validation.

Failure path: if login fails, profile row shows Error/Warning and opens detailed diagnostics on click. If classifier-governance validation fails, auto-login is not attempted and the global control row remains a persistent actionable error state.

### Flow 3 - Pause, safe mode, and resume
1. User selects `Pause Monitoring` in first row, or app starts with safe mode active.
2. App stops (or keeps stopped) all background activity: checks, watchers, and refresh loops.
3. Icon switches to `paused` variant.
4. Profile rows display explicit paused messaging; when global pause removes any per-profile action, affected rows are visibly disabled.
5. First row shows `Resume Monitoring` while paused, unless a global error is active.
6. User selects `Resume Monitoring` to resume monitoring.
7. Menu closes on any first-row click.

Persistence path: user-selected global pause state is persisted across restarts and takes precedence over per-profile state until resumed; safe mode remains a runtime-only override for that launch.

### Flow 4 - Global error (AWS CLI/discovery/config failure)
1. App encounters a global blocking condition: unavailable/broken AWS CLI, unsupported AWS CLI version, globally invalid app config, or config trust-policy violation (owner/permission/symlink checks).
2. First row becomes an explicit error action instead of a toggle; this error action stays visible while 30-second retries continue.
3. User selects the error row — the menu closes and a diagnostics dialog opens.
4. App remains running and retries discovery/config recovery checks every 30 seconds.

Recovery path: after the blocking condition is resolved, first row returns to the monitoring toggle.

### Flow 5 - Profile row interaction
1. User selects profile row.
2. If profile is OK and running, the row label advertises `Pause monitoring`; selecting it closes the menu, pauses the profile, and future checks for that profile are skipped across restarts.
3. If profile is OK (paused) because that profile was individually paused and global monitoring is enabled, the row label advertises `Resume monitoring`; selecting it closes the menu, resumes the profile, and future checks for that profile run again.
4. If profile is Warning or Error, the row label advertises `Show details`; selecting it opens diagnostics and does not toggle monitoring.

Global-pause path: when the first-row global control has paused monitoring, profile rows show explicit global-pause copy such as `OK (global pause)` and are disabled when no per-profile action is available. Persisted per-profile state is retained underneath, but the persisted global paused state takes visual and behavioral precedence until global monitoring is enabled again.

Retention path: if incident evidence for the row has aged out or been evicted, dialog shows `Incident evidence unavailable: retention window exceeded.` instead of silently omitting evidence context.

### Flow 6 - High-cardinality profile navigation
1. When tracked SSO profiles exceed 40, profile rows are grouped into deterministic submenus with range labels (`Profiles 1-20`, `Profiles 21-40`, ...).
2. Profile names are sorted case-insensitive alphabetically before grouping.
3. User opens a submenu and selects a profile row.
4. Row behavior remains unchanged: actionable OK rows toggle per-profile monitoring, Warning/Error rows open diagnostics, and rows with no current action are visibly disabled.
5. During scheduler-overrun coalescing, grouping/order remains stable and diagnostics actions remain reachable.

Failure path: if performance target is missed at high cardinality, this is treated as UX regression against acceptance criteria.

### Flow 7 - Termination signal handling (`Ctrl+C` / `SIGTERM`)
1. App is running in a console session and receives `SIGINT` (`Ctrl+C`) or `SIGTERM`.
2. Runtime keeps a lightweight signal-pump heartbeat active during Qt loop so a single `Ctrl+C` is handled promptly in normal conditions.
3. Runtime logs explicit structured event `system_signal_received` including signal name and planned action `graceful_shutdown`.
4. App executes the same graceful shutdown sequence as tray `Quit`.
5. Runtime logs each shutdown action stage and requests Qt event-loop exit.

Failure path: if another termination signal is received while graceful shutdown is in progress, runtime logs structured event `system_signal_force_exit` and exits immediately with code `130`.

## State matrix
Preflight tray-host failure is a startup halt path; in that path tray surfaces are not created, so matrix rows are N/A and app exits with actionable stdout guidance.

| Surface | Empty | Loading | Error | Success | Permission-denied | Offline |
|---------|-------|---------|-------|---------|-------------------|---------|
| CLI command surface | Help/version/check-only/log-level/log-format not requested | N/A - command parsing is immediate | Invalid argument/value (including unsupported `--log-level` or `--log-format`) prints actionable parse error and non-zero exit | `--help`, `--version`/`-V`, successful `--check-only`, valid `--log-level`/`--log-format`, and deterministic config+CLI precedence produce expected behavior and `0` semantics | N/A - represented via command failure text | N/A - represented via preflight/command failure text |
| System tray icon | N/A - icon appears after app init | `normal` while startup discovery/check is running | `error` for global failure or profile-level blocking issue | `working` when monitoring is active and healthy; `paused` when paused; `warning` for non-blocking warning states | N/A - permission outcomes shown as command errors | N/A - offline represented as command failures |
| Global control row | N/A - row always exists | Toggle row disabled during transient startup/sync operations (label reflects monitoring state) | Error action replacing toggle when a global blocking condition is active (unavailable/broken AWS CLI, unsupported AWS CLI version, invalid config, config trust-policy violation). Clicking it closes the menu and opens a diagnostics dialog | `Pause Monitoring` when monitoring enabled, `Resume Monitoring` when monitoring disabled (including intentional safe-mode pause). Clicking it closes the menu and toggles monitoring | N/A - permission issues surfaced via error action | N/A - offline surfaced via error action |
| Profile status row | N/A - row exists only for discovered SSO profile | `<name> - Syncing...` and row is disabled while no direct action is available | `<name> - Error -> Show details` and row is clickable; timeout uses explicit `Command timed out` reason in diagnostics | `<name> - OK -> Pause monitoring`, `<name> - OK (paused) -> Resume monitoring`, or `<name> - OK (global pause)` when global pause blocks per-profile actions | `<name> - Error -> Show details` with access-denied diagnostics | `<name> - Warning -> Show details` with connectivity diagnostics; unknown-classifier failures do not imply auto-login |
| Profile overflow submenu | N/A - not shown when tracked profiles <= 40 | N/A - container does not represent command state | N/A - error states remain on individual profile rows | Visible and selectable only when tracked profiles > 40; labels are deterministic range buckets | N/A - permission outcomes stay on profile rows | N/A - offline outcomes stay on profile rows |
| Error details dialog | Not shown | Optional brief `Loading diagnostics...` only if data assembly is asynchronous | Shows structured details in order: Summary, Incident evidence, Command, Exit code, stderr, stdout, Timestamp; Summary class is explicit (`AWS CLI unavailable`, `AWS CLI v2 required`, `Configuration version unsupported`, `Configuration invalid`, `Configuration file trust policy failed`, `Browser wrapper execution failed`) and includes explicit stream truncation/omitted-byte notices when caps are hit. Incident evidence block includes retention bounds (latest 50 incidents, max 24h); if evidence is unavailable, show explicit `retention window exceeded` notice. **Configuration errors** (e.g., `No SSO profiles detected`) show simplified view with Summary and Context only, without command-related fields or incident evidence. | N/A - not opened for OK states | Shows permission-specific diagnostics details | Shows connectivity/offline diagnostics details |
| Quit row | N/A - row always exists | N/A | N/A | Executes graceful shutdown | N/A | N/A |

Signal-triggered shutdown follows the same success semantics as Quit row and adds explicit `system_signal_received` / `shutdown_action` logs for observability.

## Status precedence
- Global status precedence is fixed to: `global error > profile error > warning > paused > working`.
- The `normal` icon is shown only at startup before the first status cycle completes.
- These precedence rules remain unchanged when paused state comes from safe mode.

## Interaction timing expectations
- Tray-host-preflight failure emits one actionable stdout message and exits immediately; no automatic retry occurs without relaunch in a supported session.
- Pause action reflects in tray icon and first-row label within 1 second after user click.
- Resume action reflects in tray icon and first-row label within 5 seconds after user click.
- After explicit expired/invalid detection, profile row reflects pending login-recovery state promptly (no silent waiting until login start).
- Global error action remains visible while 30-second retries continue, then auto-returns to toggle state after recovery.
- Refresh labels remain consistent with the 30-second monitoring cadence while monitoring is enabled.
- At 50 profiles, top-level menu open latency target is p95 <= 150 ms.
- At 100 profiles, top-level menu open latency target is p95 <= 300 ms.
- At 100 profiles, submenu open latency target is p95 <= 120 ms.
- File-event bursts are coalesced into stable UI transitions (no repetitive per-event flicker of row labels or global control text).
- Scheduler-overrun coalescing keeps a stable in-progress presentation (no stacked catch-up bursts or rapid first-row label churn).
- During scheduler-overrun coalescing at 50/100 profiles, deterministic ordering/grouping and diagnostics reachability remain intact.

## Voice and tone
Reference strings:
- CLI parse error: `Invalid option value. Run --help to see valid usage.`
- CLI log-level error: `Invalid log level. Use one of: error, warning, info, debug, trace.`
- CLI log-format error: `Invalid log format. Use one of: text, json.`
- CLI check-only success: `Startup preflight passed. Tray host and AWS prerequisites are available.`
- CLI check-only failure: `Startup preflight failed. See structured event logs for tray host or AWS readiness details.`
- Settings precedence note: `Effective logging settings: level=<...>, format=<...>, source=<config|cli|default>.`
- Error: `Auto-login failed for profile "<name>". Click to view full diagnostics.`
- Success: `Profile: <name> - OK, last refresh: <duration>`
- Empty state: `No SSO profiles detected. Monitoring profile sources for changes.`
- Startup version event: `event=app_started version=<X.Y.Z> source=<embedded|default>`
- Global compatibility error: `AWS CLI v2 is required. Current version is unsupported.`
- Global trust error: `Configuration file is not trusted. Fix ownership, permissions, or symlink path and retry.`
- Wrapper execution error: `Browser wrapper failed to execute. Check browser configuration and permissions.`

Guidelines:
- Keep wording concise and operational.
- Use actionable language for non-OK states.
- Use consistent terms: `auto-login`, `profile`, `diagnostics`, `paused`.
- Safe-mode pause copy is explicit, for example: `Auto-login is paused by safe mode. Enable to resume monitoring.`
- Truncation copy is explicit, for example: `stderr truncated; 18240 bytes omitted.`

## Accessibility targets
- WCAG intent: align with AA principles where applicable to tray/menu/dialog desktop surfaces.
- Keyboard flow:
  - menu must be fully keyboard navigable,
  - focus order follows row order,
  - overflow submenu entry and navigation are fully keyboard accessible at high cardinality,
  - dialog supports keyboard dismissal (Esc/Enter) and visible default focus on the close action,
  - diagnostics content navigation order is predictable: Summary -> Incident evidence -> Command -> Exit code -> stderr -> stdout -> Timestamp.
- Screen reader:
  - every status is expressed in text labels, not icon only,
  - diagnostics dialog content is structured in readable order,
  - governance status lines and incident-evidence fields are announced as part of dialog content order,
  - large stderr/stdout blocks remain readable for assistive technologies.
- Motion:
  - no essential animation required to understand state,
  - syncing animation is optional and non-critical.
- Color independence:
  - state information is never color-only; text always carries meaning.

## Platform / harness constraints
- Target platform: Linux with Wayland support.
- Runtime stack: Python + Qt6 (`PySide6`).
- CLI parsing stack: `typer` with deterministic terminal help/error behavior.
- Logging output modes: `text` (default, colorized on TTY) and `json` (structured events).
- Runtime settings precedence: defaults -> config file -> environment -> CLI.
- AWS CLI v2 is the supported CLI baseline for UX guarantees.
- Tray availability depends on desktop environment support for system tray/status notifier.
- No primary window; tray and modal dialogs only.
- All user-facing strings are English only.

## Non-goals
- Building a full interactive preferences window.
- Providing localization or multilingual copy.
- Presenting advanced analytics/history UI.
- Supporting non-Linux desktop environments in this phase.

## V1 UX Limitations (to address in V2)
- **Warning/Syncing state conflation:** The Warning state is used for both "refresh in progress" (normal operation) and "connectivity issues" (actual problems). Users cannot visually distinguish between transient activity and errors requiring attention. V2 will split these into separate Syncing and Warning states with distinct visual treatments.
- **Queue position visibility:** Flow text references "refresh in progress or needed" but queue depth is not visible. Users at high profile counts (50+) cannot see their position in the serial login queue or estimated wait time. V2 will add queue depth indicator to profile status.
- **Overflow submenu status aggregation:** At 100 profiles across 5 submenus, users must open each submenu to find profiles with errors. No badge or highlight indicates which submenus contain Warning/Error profiles. V2 will add status badges to submenu labels.
- **Classifier governance terminology:** The error message "Release gate blocked: classifier governance incomplete" uses internal terminology. V2 will replace with user-facing language like "Session detection rules need update. Contact administrator."
- **Compound states undocumented:** Safe mode + global error combinations are not explicitly documented in the state matrix. Implementation relies on precedence rules. V2 will add explicit compound state cells to the matrix.
- **Quit operation feedback:** Graceful shutdown shows no visual feedback while commands are cancelling. Users may think the app froze. V2 will add "Shutting down..." transient state.
- **StatusNotifier accessibility:** Qt6 StatusNotifierItem doesn't expose accessible names directly. The "no icon only" requirement may not be fully implementable for the tray icon itself. V2 will investigate D-Bus accessible interfaces or tooltip-based workarounds.
