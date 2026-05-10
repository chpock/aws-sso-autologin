# Profile State Machine and Error Visibility - UX spec
Date: 2026-05-10
Product spec: docs/leyline/specs/2026-05-10-profile-state-machine-error-visibility-design.md
Surfaces: multi-screen-ui

## Surfaces enumerated
- System tray icon: global app-state indicator (`paused`, `error`, `working/syncing`, `working/ok`).
- Tray context menu: primary control row plus per-profile status rows.
- Profile menu row: per-profile state and short reason text.
- Error details dialog: reason and diagnostics payload for problematic profiles.
- Tooltip: compact aggregate status summary.

## User flows
### Flow 1 - startup and initial profile evaluation
1. App starts and each profile initializes as `synchronizing`.
2. App checks session with `aws sts get-caller-identity`.
3. If check is successful and session is not expired, profile transitions to `ok`.
4. If session is expired, profile remains/transitions to `synchronizing` and sync starts.
5. If sync succeeds and session re-check is successful, profile becomes `ok`.
6. If sync fails, profile becomes `error`.
Failure path: deterministic check/sync failures surface `error`; indeterminate failures surface `warning` only when profile is not currently `error`.

### Flow 2 - indeterminate runtime check
1. Periodic check returns indeterminate/ambiguous result.
2. If profile is not `error`, profile transitions to `warning`.
3. If profile is `error`, it stays `error` (sticky-error rule).
Failure path: repeated indeterminate results do not clear `error`.

### Flow 5 - sync succeeded confirmation window
1. Sync command reports success for a profile currently in `synchronizing` or `warning`.
2. Profile enters `confirmation_pending=true` substate while retaining its current non-error primary state and synchronizing-style progress presentation.
3. App waits for explicit `session_check_success_active` event.
4. If confirmation arrives in time, profile transitions to `ok`.
5. If confirmation times out, profile returns to `synchronizing` and keeps user-visible progress semantics.
Failure path: confirmation timeout never clears an existing `error`; it only affects non-error states. If current state is already `ok`, `sync_succeeded` is ignored and does not start a confirmation window.

### Flow 3 - inspect profile error details
1. Human partner opens tray menu.
2. Human partner selects profile row in `error`.
3. Diagnostics dialog opens with summary and details.
4. Human partner closes dialog and returns to tray menu usage.
Failure path: if retries/checks are running concurrently, profile row remains selectable and still opens diagnostics.
Dialog-open failure path:
1. If diagnostics dialog fails to render, app shows inline recoverable message: `Could not open details. Try again.`
2. Primary action: `Retry opening details`.
3. Secondary action: `Dismiss`.
4. Keyboard focus returns to the originating profile row after dismiss or failed retry.
5. Screen reader announces failure message, then announces available actions.

### Flow 4 - paused precedence
1. Human partner pauses monitoring.
2. App status becomes `paused`; tray icon becomes paused regardless of profile states.
3. Error profile rows remain visible/selectable.
4. Selecting an error profile still opens diagnostics dialog.
Failure path: none; paused state overrides app-level status presentation only.

## State matrix
| Surface | Empty | Loading | Error | Success | Permission-denied | Offline |
|---------|-------|---------|-------|---------|-------------------|---------|
| System tray icon | N/A - profiles are initialized during startup | `working/syncing` icon while any profile synchronizing and monitoring active | `error` icon when monitoring active and any profile is `error` | `working/ok` icon when monitoring active and no profile is `error` or `synchronizing` | Treated as deterministic failure -> profile `error` -> error icon (when monitoring active) | Classified by decision table: transport/offline ambiguity -> `warning`; definitive auth denial -> `error` |
| Tray context menu | Control row + no profiles placeholder semantics | Control row may show synchronizing state; profile rows can show syncing | Error rows show `Error: <reason>` and remain selectable | Profile rows show OK state text | Row shown as error with permission-denied reason | Row shown as warning text unless profile currently sticky-error |
| Profile menu row | N/A | `Profile: <name> - Syncing...` | `Profile: <name> - Error: <reason>` | `Profile: <name> - OK ...` | Same as error row semantics | Same as warning row semantics unless sticky-error |
| Error details dialog | Not shown | Can still be opened for existing error rows during retries/checks | Shows error summary + diagnostics details | Not shown for OK profiles | Shows access-denied diagnostics detail text | Shows indeterminate/offline diagnostic text when surfaced |
| Tooltip | `Profiles OK: 0/0` + state text | Shows syncing/working state while monitoring active | Shows error state while monitoring active | Shows working/ok or paused (if paused) | Same as error behavior when monitoring active | Mirrors decision-table outcome: warning for ambiguous transport failures, error for definitive auth failures |

## State copy contract
- `synchronizing`: `Profile: <name> - Syncing...`
- `warning`: `Profile: <name> - Check uncertain`
- `error`: `Profile: <name> - Error: <reason>`
- `degraded suffix`: append ` (state may be delayed)` after primary reason text when causality-gap recovery is active.
- `stale marker`: append ` [stale]` to row reason and dialog header when retained diagnostics age exceeds 24h.
- `redaction-blocked`: when sanitizer confidence is below threshold, replace details body and row reason tail with `Sensitive details hidden for safety. Re-run with trace logs or contact support.`
- Copy precedence when multiple modifiers coexist: `error reason` -> `degraded suffix` -> `stale marker` -> `redaction-blocked fallback`.

## Information architecture
- Entry surface: tray icon.
- Primary navigation: tray icon -> context menu.
- Menu hierarchy:
  - Row 1: monitoring/global action row.
  - Separator.
  - Profile rows (or overflow submenus when profile count is high).
  - Separator.
  - Quit action.
- Error inspection branch: profile error row -> diagnostics dialog -> close dialog -> return to tray background state.

## Cross-screen state handling
- Monitoring mode (`working`/`paused`) is global.
- Profile state is per-profile and persistent between checks.
- `confirmation_pending` is an internal profile substate for non-error states and is not rendered as a standalone primary label by default.
- `error` is sticky per profile until explicit successful `ok` event.
- Diagnostics summary/details for an error profile persist until explicit `ok` transition.
- Background retries/checks must not hide or disable profile error diagnostics entry.
- If event conflicts happen in same processing window, UI uses deterministic precedence outcome from profile event queue and avoids transient contradictory labels.
- Profile state updates are idempotent for duplicate event correlation IDs; UI must not flicker for deduplicated events.
- When causality-gap recovery is active after queue overflow, profile row appends degraded suffix text `state may be delayed` until next successful active session check.
- Causality-gap degraded warning visibility is rate-limited per profile to avoid repeated noise while preserving operator awareness.
- Stale-marker lifecycle:
  - threshold trigger: retained diagnostics age crossing 24h.
  - refresh cadence: on each menu open and each periodic check tick.
  - synchronization rule: row and dialog stale indicator must update atomically from the same profile-state snapshot.
- Confirmation visibility policy: `confirmation_pending` remains internal-only for primary labels; tooltip may append `awaiting session confirmation` when pending=true.

## Route / URL conventions
- Native tray application; no URL routes.
- Transition conventions:
  - tray menu action -> modal diagnostics dialog
  - modal close -> return to passive tray interaction

## Voice and tone
Three reference strings used as copy baseline:
- Error: "Profile \"<name>\" requires attention. Authentication failed; open details for remediation steps."
- Success: "Profile \"<name>\" is authenticated and ready."
- Empty state: "No actionable profiles right now. Monitoring is active."

## Accessibility targets
- WCAG level: AA
- Keyboard flow: tray menu rows keyboard reachable; Enter activates profile row; dialog close reachable via keyboard.
- Screen reader: announce profile name, state, and short reason; dialog announces title then summary.
- Motion: no critical information conveyed only through animation.
- Color independence: all state meaning represented in text labels, not only icon color.
- Error diagnostics trigger remains keyboard reachable in both active and paused monitoring modes.

## Accessibility feasibility constraints
- Minimum acceptance for Linux tray hosts: keyboard can focus profile rows, activate row action with Enter/Space, and return focus after dialog close/failure.
- Minimum screen reader acceptance: announces profile name + state text on focus, and announces dialog title + summary on open.
- If tray host cannot expose reliable row semantics, app must expose alternate diagnostics access via a dedicated menu action `Open latest error details` and announce this fallback in the tooltip.
- Accessibility verification is host-specific; unsupported host capability must be logged and surfaced as non-blocking limitation with fallback path available.

## Platform / harness constraints
- Linux desktop environment with compatible StatusNotifier tray host.
- PySide6/Qt constraints for modal dialog focus and tray context-menu behavior.
- Threaded check results must enter UI via Qt signal bridge to avoid cross-thread UI mutation.
- Tray menu and diagnostics interactions must remain responsive while background queue processes retries and conflict resolution.

## Security and privacy UX constraints
- Diagnostics dialog must show already-redacted details only (never raw unredacted secrets).
- If details are truncated by payload cap, dialog must explicitly show truncation marker.
- If retained diagnostics age exceeds 24h, both row and dialog copy must surface `stale` context text.
- If redaction confidence is below threshold, row reason and dialog body must use this fallback copy: `Sensitive details hidden for safety. Re-run with trace logs or contact support.`

## Observability UX hooks
- UI emits diagnostics interaction events for open request, success, and failure.
- UI-visible aggregation decisions map 1:1 to structured `app_state_aggregated` logs for support correlation.
- Dialog-open failures must show a recoverable user-facing message while also logging failure context.

## Non-goals
- Re-skinning icon set or introducing a new visual language.
- Building a separate full-window profile management surface.
- Persisting full historical diagnostics beyond current in-memory state lifecycle.

## Round 2 alignment notes
- Added confirmation-window flow after `sync_succeeded` to match product-spec transition semantics.
- Added deterministic conflict-resolution UX expectations (no contradictory transient states).
- Added stale/truncated/redacted diagnostics presentation requirements.
- Added UX-level observability hook expectations for diagnostics and aggregation.

## Round 3 alignment notes
- Clarified confirmation behavior as orthogonal `confirmation_pending` substate for non-error profiles.
- Kept confirmation UX rendered as synchronizing-style progress state instead of adding a separate primary label.
- Preserved deterministic conflict-resolution expectations while aligning with mandatory correlation/dedup semantics.
- Continued to require explicit stale/truncation/redaction signaling in diagnostics surfaces.
- Retained observability hooks that map diagnostics interactions and app-level aggregation to structured logs.

## Round 4 alignment notes
- Aligned offline/timeout-visible behavior with product-level failure decision table to avoid ambiguous `warning` vs `error` flips.
- Confirmed confirmation-timeout is treated as deterministic internal event while preserving synchronizing-style UX fallback.
- Kept paused precedence and sticky-error diagnostics access unchanged during classification/timeout refinements.

## Round 5 alignment notes
- Added normative redaction-blocked fallback copy for both row reason and diagnostics dialog body.
- Kept error rows actionable even when sensitive details are withheld by sanitizer policy.

## Round 6 alignment notes
- Clarified stale diagnostics marker placement as mandatory on both row and dialog surfaces for consistent triage screenshots.

## Round 8 alignment notes
- Aligned confirmation-window entry with product transition rules: only `synchronizing|warning` profiles enter `confirmation_pending`; `ok + sync_succeeded` is explicitly a no-op.
- Added degraded-mode UX requirement for causality-gap recovery (`state may be delayed`) with rate-limited operator warning behavior.
- Kept redaction-blocked fallback copy unchanged while deferring threshold governance to product/ops contracts.

## Round 9 alignment notes
- Clarified that degraded-mode and redaction-blocked UX states correlate with product-side `sanitizer_version`, `confidence_source`, and selector-expansion block events for support triage.
- Kept visual copy unchanged while requiring screenshot/log correlation to use the new product observability keys.

## Round 10 alignment notes
- Added canonical state copy contract and modifier-precedence rules for `warning`, `degraded`, `stale`, and redaction-blocked states.
- Added explicit dialog-open failure recovery path with retry/dismiss actions, focus return, and screen-reader announcement order.
- Added Linux tray accessibility feasibility constraints and alternate diagnostics fallback path when row semantics are unavailable.
- Added stale-marker trigger/refresh/atomic-sync rules and resolved confirmation visibility policy (`confirmation_pending` internal-only primary label; optional tooltip hint).

## Approvals
UX spec approved - round 1 - 2026-05-10
UX spec approved - round 2 - 2026-05-10
UX spec approved - round 3 - 2026-05-10
UX spec approved - round 4 - 2026-05-10
UX spec approved - round 5 - 2026-05-10
UX spec approved - round 6 - 2026-05-10
UX spec approved - round 7 - 2026-05-10
UX spec approved - round 8 - 2026-05-10
UX spec approved - round 9 - 2026-05-10
UX spec approved - round 10 - 2026-05-10
Design-interrogation pass complete - round 1 - 2026-05-10
