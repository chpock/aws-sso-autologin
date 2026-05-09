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
- `System tray icon`: always-visible status indicator for monitoring and sync health.
- `Tray context menu`: primary interaction surface for control and status visibility.
- `Global control row`: first menu row for enable/disable toggle, or global error action when AWS CLI/discovery/config is unavailable/invalid, including unsupported AWS CLI version and unsupported config version cases.
- `Profile status rows`: one row per tracked SSO profile, with concise status text, shown directly or inside deterministic overflow submenus at high cardinality.
- `Profile overflow submenus`: deterministic range-labeled submenu containers used when tracked profile count exceeds top-level row budget.
- `Error details dialog`: modal diagnostics window for Warning/Error conditions.
- `Quit row`: explicit app shutdown action.

## User flows
### Flow 1 - Startup and healthy monitoring
1. App launches with auto-login monitoring enabled by default, unless safe mode is active via startup env/config override.
2. App writes startup version event to structured stdout logs with `version` and `source` fields.
3. Tray icon appears in enabled state.
4. App discovers SSO profiles and starts 30-second checks.
5. Menu shows control row, profile rows with healthy text, and quit action.
6. Profile rows display `Profile: <name> - OK, last refresh: <duration>` when checks succeed.

Failure path: if tray-host preflight fails (no compatible StatusNotifier/system tray host), no tray icon/menu/dialog is shown, app exits non-zero, and one actionable stdout message explains tray host support is required. If startup succeeds but one or more profiles fail checks, those profile rows show Warning or Error status and become actionable for diagnostics.

### Flow 2 - Expired SSO session recovery
1. Periodic check detects explicit expired/invalid SSO session for profile.
2. Profile row moves to warning state indicating refresh in progress or needed.
3. Profile is queued for login; logins execute strictly one at a time.
4. Successful login returns profile to OK on subsequent validation.

Failure path: if login fails, profile row shows Error/Warning and opens detailed diagnostics on click. If classifier-governance validation fails, auto-login is not attempted and the global control row remains a persistent actionable error state.

### Flow 3 - Pause, safe mode, and resume
1. User selects `Disable auto-login` in first row, or app starts with safe mode active.
2. App stops (or keeps stopped) all background activity: checks, watchers, and refresh loops.
3. Icon switches to `disabled-paused` variant.
4. Profile rows display OK paused messaging.
5. First row shows `Enable auto-login` while paused, unless a global error action must replace it.
6. User selects `Enable auto-login` to resume monitoring.

Failure path: if resume cannot start due to global AWS CLI/discovery/config issue, first row becomes a global error action that opens details. If rollback artifact verification fails, app remains in safe mode/global error action state until a valid artifact set is restored.

### Flow 4 - Global AWS CLI/discovery/config failure
1. App cannot perform global discovery/check operation due to unavailable/broken AWS CLI, unsupported AWS CLI version, classifier-governance validation failure, rollback artifact verification failure, globally invalid app config (including unsupported `config_version`), or config trust-policy violation (owner/permission/symlink checks).
2. First row becomes explicit error action instead of toggle; this error action stays visible while 30-second retries continue and does not oscillate with toggle semantics until the blocking gate is resolved.
3. User selects error row to open full diagnostics dialog, including incident evidence details when available.
4. App remains running and retries discovery/config recovery checks every 30 seconds.
5. For config trust-policy violations, app keeps last known-valid config behavior active until trust checks pass; for rollback-verification failures, app remains safe-mode blocked until verified artifacts are restored.

Recovery path: after successful retry and governance/verification checks pass, first row returns to enable/disable toggle behavior.

### Flow 5 - Profile row interaction
1. User selects profile row.
2. If profile is OK (including paused OK), menu closes and no dialog opens.
3. If profile is Warning or Error, diagnostics dialog opens with complete details.

Retention path: if incident evidence for the row has aged out or been evicted, dialog shows `Incident evidence unavailable: retention window exceeded.` instead of silently omitting evidence context.

### Flow 6 - High-cardinality profile navigation
1. When tracked SSO profiles exceed 40, profile rows are grouped into deterministic submenus with range labels (`Profiles 1-20`, `Profiles 21-40`, ...).
2. Profile names are sorted case-insensitive alphabetically before grouping.
3. User opens a submenu and selects a profile row.
4. Row behavior remains unchanged: OK closes menu; Warning/Error opens diagnostics.
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
| System tray icon | N/A - icon appears after app init | `enabled-syncing` while startup discovery/check is running | `enabled-error` for global failure or profile-level blocking issue | `enabled-ok` when monitoring is active and healthy; `disabled-paused` when paused; `enabled-warning` for non-blocking warning states | N/A - permission outcomes shown as command errors | N/A - offline represented as command failures |
| Global control row | N/A - row always exists | `Synchronizing...` disabled row during transient startup/sync operations | `Show startup/sync error` action replacing toggle when global AWS operations fail, including unsupported AWS CLI version, unsupported/invalid global config guidance, config trust-policy violations, classifier-governance validation failures, and rollback artifact verification failures | `Disable auto-login` when monitoring enabled, `Enable auto-login` when monitoring disabled (including intentional safe-mode pause) | N/A - permission issues surfaced via error action | N/A - offline surfaced via error action |
| Profile status row | N/A - row exists only for discovered SSO profile | `Profile: <name> - Syncing...` while check or login result is pending | `Profile: <name> - Error: <short reason>` and row is clickable; timeout uses explicit `Command timed out` reason | `Profile: <name> - OK, last refresh: <duration>` or `Profile: <name> - OK (paused)` | `Profile: <name> - Error: Access denied` with clickable details | `Profile: <name> - Warning: Connectivity issue` with clickable details; unknown-classifier failures do not imply auto-login |
| Profile overflow submenu | N/A - not shown when tracked profiles <= 40 | N/A - container does not represent command state | N/A - error states remain on individual profile rows | Visible and selectable only when tracked profiles > 40; labels are deterministic range buckets | N/A - permission outcomes stay on profile rows | N/A - offline outcomes stay on profile rows |
| Error details dialog | Not shown | Optional brief `Loading diagnostics...` only if data assembly is asynchronous | Shows structured details in order: Summary, Incident evidence, Command, Exit code, stderr, stdout, Timestamp; Summary class is explicit (`AWS CLI unavailable`, `AWS CLI v2 required`, `Configuration version unsupported`, `Configuration invalid`, `Configuration file trust policy failed`, `Classifier governance check failed`, `Rollback artifact verification failed`, `Browser wrapper execution failed`) and includes explicit stream truncation/omitted-byte notices when caps are hit. Summary may include concise governance status lines (for example: `Release gate blocked: classifier governance incomplete`). Incident evidence block includes retention bounds (latest 50 incidents, max 24h); if evidence is unavailable, show explicit `retention window exceeded` notice. | N/A - not opened for OK states | Shows permission-specific diagnostics details | Shows connectivity/offline diagnostics details |
| Quit row | N/A - row always exists | N/A | N/A | Executes graceful shutdown | N/A | N/A |

Signal-triggered shutdown follows the same success semantics as Quit row and adds explicit `system_signal_received` / `shutdown_action` logs for observability.

## Status precedence
- Global status precedence is fixed to: `global error > profile error/warning > syncing > ok`.
- When monitoring is disabled, `disabled-paused` always takes precedence for icon and control semantics.
- These precedence rules remain unchanged when paused state comes from safe mode.

## Interaction timing expectations
- Tray-host-preflight failure emits one actionable stdout message and exits immediately; no automatic retry occurs without relaunch in a supported session.
- Pause action reflects in tray icon and first-row label within 1 second after user click.
- Resume action reflects in tray icon and first-row label within 5 seconds after user click.
- After explicit expired/invalid detection, profile row reflects pending login-recovery state promptly (no silent waiting until login start).
- Global error action remains visible while 30-second retries continue, then auto-returns to toggle state after recovery.
- During classifier-governance or rollback-verification failures, first-row global error action stays persistent and does not oscillate with enable/disable toggle states.
- Refresh labels remain consistent with the 30-second monitoring cadence while monitoring is enabled.
- At 50 profiles, top-level menu open latency target is p95 <= 150 ms.
- At 100 profiles, top-level menu open latency target is p95 <= 300 ms.
- At 100 profiles, submenu open latency target is p95 <= 120 ms.
- File-event bursts are coalesced into stable UI transitions (no repetitive per-event flicker of row labels or global control text).
- Scheduler-overrun coalescing keeps a stable in-progress presentation (no stacked catch-up bursts or rapid first-row label churn).
- During scheduler-overrun coalescing at 50/100 profiles, deterministic ordering/grouping and diagnostics reachability remain intact.

## Voice and tone
Reference strings:
- Error: `Auto-login failed for profile "<name>". Click to view full diagnostics.`
- Success: `Profile: <name> - OK, last refresh: <duration>`
- Empty state: `No SSO profiles detected. Monitoring profile sources for changes.`
- Startup version event: `event=app_started version=<X.Y.Z> source=<embedded|default>`
- Global compatibility error: `AWS CLI v2 is required. Current version is unsupported.`
- Global trust error: `Configuration file is not trusted. Fix ownership, permissions, or symlink path and retry.`
- Governance gate error: `Release gate blocked: classifier governance incomplete. Complete governance checks and retry.`
- Rollback verification error: `Rollback artifact verification failed. Restore a valid artifact set and retry.`
- Wrapper execution error: `Browser wrapper failed to execute. Check browser configuration and permissions.`

Guidelines:
- Keep wording concise and operational.
- Use actionable language for non-OK states.
- Use consistent terms: `auto-login`, `profile`, `diagnostics`, `paused`.
- Safe-mode pause copy is explicit, for example: `Auto-login is paused by safe mode. Enable to resume monitoring.`
- Truncation copy is explicit, for example: `stderr truncated; 18240 bytes omitted.`
- Governance status copy is explicit and actionable; avoid internal shorthand without a direct next step.

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
