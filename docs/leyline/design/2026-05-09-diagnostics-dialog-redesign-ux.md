# Diagnostics Dialog Redesign - UX spec
Date: 2026-05-09
Product spec: docs/leyline/specs/2026-05-09-diagnostics-dialog-redesign-design.md
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

## Surfaces enumerated
- Diagnostics dialog: single modal surface showing incident status, curated field details, and full copyable diagnostics payload.
- Status header region: semantic icon + short status title + supporting one-line context.
- Smart fields region: conditionally rendered key/value fields based on incident type and command-execution evidence.
- Details textarea region: readonly multi-line full diagnostics payload for manual select/copy.
- Action row: `Copy all details` and `Close` controls.

## User flows
### Flow 1 - Open diagnostics from tray for global/runtime issue
1. User selects diagnostics action from tray (global first-row error action or profile row with warning/error).
2. Fixed-size floating dialog opens.
3. User reads status header (icon + title).
4. User reviews only relevant structured fields in smart fields region.
5. User copies full payload via `Copy all details` or manual textarea selection.
6. User closes dialog with `Close`; app continues running.

Failure path: if clipboard copy fails, show inline helper text (`Copy failed. Select details text and copy manually.`) and keep textarea accessible.

Assistive-announcement contract:
- On copy failure, announce helper text via a polite live status update so screen-reader users receive failure feedback without moving focus.
- On next successful copy in the same dialog session, announce helper-clear state (`Copy succeeded`) and clear helper text.

Open narration algorithm (normative):
- On dialog open, announcement order is deterministic: title -> status -> subtitle/context -> focused control.
- Open-sequence announcements are non-interruptible by copy-helper updates.
- Initial focus remains details textarea, but focus events must not preempt the open narration sequence.
- If a copy action is triggered during open narration, helper announcements are queued and emitted only after open narration completes.
- If normal rendering fails and minimal safe fallback is shown, open narration still announces title -> status -> subtitle/context before focused control, and uses the same unknown-state phrasing rules when `command_executed=unknown`.
- Narration/focus arbitration guardrails:
  - Open narration is queued before focused-control speech and uses a bounded arbitration window of 500 ms.
  - If assistive technology interrupts the queued order, fallback behavior replays status + subtitle/context once after focused-control speech completes.
  - If interruption recurs during replay, perform one final concise replay (`Status unchanged. <status>. <subtitle/context>.`) and suppress further replays for the current open event.
  - Interaction preemption rule: if user triggers copy before open narration completes, finish the current narration phrase, then emit one queued helper-state announcement; suppress additional replay unless interruption recurs twice in the same open event.
  - After replay is exhausted for the current open event, queued helper announcements are prefixed once with `Status unchanged.` and no further status/subtitle re-reads are allowed for that open event.
  - Acceptance requires both a normal-mode proof (no interruption) and an interrupted-mode proof (fallback replay) in release evidence.

Recovery path: after a subsequent successful copy in the same dialog session, clear the copy-failure helper text.

Retry lifecycle contract:
- Helper semantic states: `none`, `fail`, `escalated`, `success`.
- `none -> fail`: first failed copy in a session, show base helper and announce once.
- `fail -> escalated`: after 3 consecutive failures in uninterrupted retry streak, show escalated helper and announce transition.
- `fail|escalated -> success`: on any successful copy, announce success transition and clear failure streak immediately.
- `success -> none`: clear helper immediately after successful copy in the same session (no persistent visual success helper state).
- Any state -> `none`: dialog close or reopen resets helper state and streak counters.
- Announcement throttling: identical state announcements are rate-limited to at most once per 1 second; state transitions are always announced.
- Retry feedback cadence: during repeated failures inside throttle windows, helper region still updates visible retry feedback (`Retry failed. Copy is still unavailable.`) so non-screen-reader users receive immediate progress feedback without speech spam.
- Throttle synchronization: if helper text changes during a throttle window, announce the latest helper semantic state once immediately after throttle expiry.
- If helper state changes multiple times during one throttle window, only the latest semantic state is announced after throttle expiry.
- Disclosure/helper precedence stack:
  - At 100% and 200% scaling, visible line 1 is the persistent sensitive-data warning.
  - Visible line 2 is the current copy-helper state when helper is shown.
  - If line 2 truncates, full helper text remains available through accessible description.

### Flow 2 - Incident without command execution
1. User opens diagnostics for a non-command incident (example: no profiles found without command failure).
2. Header shows non-command status with type-specific icon/accent.
3. Smart fields show summary + relevant metadata only.
4. `Command`, `Exit code`, `stdout`, and `stderr` are hidden.
5. Full details remain available in textarea.

Failure path: when metadata is partially missing, UI shows required minimum (status + summary + details) without rendering placeholder noise cards.

Offline/open tie-breaker:
- If an incident exists but payload context is incomplete (for example connectivity-related acquisition issues), dialog still opens in minimal safe mode and preserves copy/close actions.

### Flow 3 - Command execution failure
1. User opens diagnostics after command execution error.
2. Header shows error status with error icon/accent.
3. Smart fields show `Command`, `Exit code`, and output fields per visibility policy.
4. User copies payload with one click or manual selection.

Failure path: when command execution is known but exit code is unavailable, show `Exit code: unknown`.

Header subtitle contract:
- If profile is known, subtitle includes profile name.
- If profile is unknown or incident is global, subtitle uses incident-scope wording.
- If both profile and incident-scope context are unavailable, subtitle shows `Context unavailable`.
- At 200% scaling, at least one scope token (`profile`, `global`, or `context unavailable`) remains fully visible; truncate trailing explanatory text first.

Combined-degradation precedence:
- When payload is malformed/partial and execution state is unknown at the same time, preserve unknown-state header/supporting copy first, then apply minimal safe rendering for fields.
- In this combined case, command-failure phrasing is forbidden.

## State matrix
| Surface | Empty | Loading | Error | Success | Permission-denied | Offline |
|---------|-------|---------|-------|---------|-------------------|---------|
| Diagnostics dialog container | N/A - opens only when incident exists | N/A - data prepared before open | Fallback content + textarea with available details | Layout renders and controls are interactive | N/A - no separate permission model | N/A - offline is represented as incident context |
| Status header | N/A - status always exists | N/A | Error icon/accent/title | Info/warning/success icon by incident type | N/A | Offline incident uses warning/error icon + connectivity text |
| Smart fields region | Summary-only when no additional relevant fields | N/A | Shows relevant error fields only | Shows relevant informational fields | N/A | Shows connectivity-relevant fields; hides command fields when command was not executed |
| Unknown execution-state variant | Summary + unknown-state supporting copy; no command-failure phrasing | N/A | Unknown-state wording remains visible; command-failure phrasing suppressed | Unknown-state wording remains visible; copy/close actions still available | N/A | Same as online behavior; unknown-state wording unchanged |
| Combined fallback + unknown execution-state | Minimal safe view remains available; unknown-state header/supporting copy preserved | N/A | Unknown-state wording has precedence; degraded fields may collapse to summary/details | Unknown-state wording remains; copy/close preserved | N/A | Same precedence and visibility rules as online |
| Details textarea | Never truly empty; minimum payload includes summary/meta | N/A | Always readable/selectable even under partial degradation | Readonly + selectable + contrast background | N/A | Always available; includes offline context |
| Copy all details button | Never disabled in normal operation; guard case falls back to minimal payload copy | N/A | On copy failure shows inline helper message | Copies full payload to clipboard | N/A | Works offline (local clipboard operation) |
| Copy helper text | N/A - hidden until failure occurs | N/A | Visible after copy failure | Clears after next successful copy | N/A | Same behavior as online mode |
| Copy helper semantic state | `none` | N/A | `fail` or `escalated` per streak rules | `success` then auto-clear to `none` in-session | N/A | Same state machine and announcement policy as online |
| Close button | Always available | N/A | Closes dialog only | Closes dialog only | N/A | Closes dialog only |

## Voice and tone
Reference strings:
- Error: "AWS CLI command failed. Review command output and copy details if you need support."
- Informational: "Diagnostics are available. This incident did not include a command execution failure."
- Empty output: "Command completed with no output."
- Copy failure helper: "Copy failed. Select details text and copy manually."
- Copy recovery helper: "Copy succeeded."
- Copy escalated helper: "Copy is still failing. Select details text and copy manually."
- Unknown execution-state header: "Unknown execution state"
- Unknown execution-state supporting copy: "Diagnostics are available, but command execution state could not be determined."

Canonical empty-output rendering contract:
- When command execution is confirmed and both outputs are empty, smart fields render an explicit empty `stdout` value and show the helper sentence "Command completed with no output." as supporting copy.

Unknown execution-state copy contract:
- Header status text: `Unknown execution state`.
- Supporting copy: "Diagnostics are available, but command execution state could not be determined."
- Smart fields must avoid command-failure phrasing when this contract is active.
- Incident icon remains tied to incident type, while subtitle/supporting copy remains neutral (no command-failure phrasing).
- Combined fallback icon semantics: incident-type icon remains primary. When combined fallback + unknown execution-state is active, subtitle/supporting copy must explicitly qualify uncertainty and must not imply confirmed command failure.
- Unknown-state source qualifier (presentation-only): UI may show one neutral qualifier label (`payload incomplete` or `telemetry unavailable`) to aid triage; this label is non-operational and must not change product-spec mapping semantics.

Tone principles:
- Direct, calm, and action-oriented.
- No blame language.
- Header stays concise; technical depth lives in fields and textarea.

## Accessibility targets
- WCAG level: AA.
- Keyboard flow:
  - Focus sequence (normative): details textarea -> smart-fields entry (when present and scrollable) -> `Copy all details` -> `Close`.
  - If smart-fields has no focusable/scrollable content, focus skips directly from details textarea to `Copy all details`.
  - `Ctrl/Cmd+A` and `Ctrl/Cmd+C` supported in textarea.
  - Enter/Space activate action buttons.
- Screen reader:
  - Announce dialog title and status text on open.
  - Announcement order on open: title -> status -> subtitle/context -> focused control.
  - Buttons have explicit accessible names.
  - Textarea announced as readonly multi-line diagnostics details.
- Copy-helper failure and recovery messages are announced as status updates without forced focus change.
- Smart-fields internal scroll area supports keyboard and screen-reader traversal (enter region, read wrapped values, exit to action row).
- Live-region interruption policy: open-announcement sequence has priority; copy-helper announcements queue politely and must not cancel status/subtitle announcements.
  - AT mode expectations:
    - Focus mode: keyboard contract governs entry/traversal/exit for smart-fields region.
    - Browse/virtual-cursor mode: reading order follows visible region order and preserves persistent-context-first contract.
- Smart-fields region accessibility semantics are explicit: named region, tabbable entry point, no focus trap, and deterministic keyboard exit to action row.
- Smart-fields key behavior is deterministic:
  - `PageDown` / `PageUp` scroll viewport by one page.
  - `Home` moves to start of smart-fields content.
  - `End` moves to end of smart-fields content.
  - Re-entering the region restores the last read/scroll position for the current dialog session.
  - `Esc` exits smart-fields region directly to action row without intermediate tabbing.
  - Key precedence: `Esc` exit has highest precedence; `Tab` exits region only when no active scroll traversal is in progress.
  - Active scroll traversal definition: smart-fields region has focus and last key is in `{Up, Down, PageUp, PageDown, Home, End}` within 1.5 seconds.
  - `Tab` exit behavior is identical for SR focus mode and browse/virtual-cursor mode when active traversal is not in progress.
- Motion:
  - No required animations.
  - Optional micro-motion must not carry meaning and must be skippable by reduced-motion settings.
- Color independence:
  - Incident type encoded by icon + text + color.
  - Textarea differentiation uses background and boundary, not color alone.
- Product-spec gate alignment:
  - Release acceptance must include keyboard-flow and screen-reader checks in product success criteria, not contrast-only checks.

## Release evidence alignment
- Canonical release evidence checklist lives in `docs/leyline/specs/2026-05-09-diagnostics-dialog-redesign-design.md` under `## Release evidence checklist`.
- UX acceptance evidence contributes the following required artifacts to that checklist:
  - keyboard-flow proof (focus order and keyboard activation),
  - screen-reader proof (open announcements and textarea semantics),
  - contrast proof for header/details separation.
- Guard-case alignment: if payload normalization yields minimal fallback data only, copy action remains enabled and copies minimal fallback payload (not disabled).
- Unknown execution-state alignment: when execution state is unavailable, header/body copy uses `unknown execution state` wording and avoids command-failure phrasing.
- Unknown execution-state telemetry alignment: UI-copy assertions for `unknown execution state` map to telemetry fixtures where `command_executed=unknown`.
- Unknown execution-state event mapping:
  - `event=diagnostics_dialog_opened` + `command_executed=unknown` -> UI asserts header `Unknown execution state` and supporting unknown-state copy.
  - `event=diagnostics_dialog_open_failed` + `command_executed=unknown` -> UI asserts fallback view keeps unknown-state wording (no command-failure phrasing).
  - `event=diagnostics_copy_succeeded` + `command_executed=unknown` -> UI asserts copy success state while preserving unknown-state header/supporting copy.
  - `event=diagnostics_copy_failed` + `command_executed=unknown` -> UI asserts helper text is shown and announced; unknown-state header/supporting copy remains unchanged.
- Subtitle variant mapping:
  - profile context available -> subtitle includes profile name and telemetry fixture includes profile-context variant.
  - profile unknown or global incident -> subtitle uses incident-scope wording and telemetry fixture includes incident-scope variant.
  - both unavailable -> subtitle `Context unavailable` and telemetry fixture includes context-unavailable variant.

## Platform / harness constraints
- Implement in PySide6/Qt6 with current tray-first architecture.
- Dialog remains fixed-size and non-resizable.
- Dialog remains floating (`WindowStaysOnTopHint`).
- Closing dialog must never terminate app (`setQuitOnLastWindowClosed(False)` at app level).
- Use dialog-local palette/stylesheet with sufficient contrast in light/dark environments.
- Field-visibility policy must be deterministic and unit-testable.
- UI tests verify field presence/absence, copy action, and close semantics.
- Structured-rendering fallback must keep minimal safe view (status + summary + details textarea) when payload is malformed.
- Smart-fields overflow behavior must be deterministic: long values wrap and the smart-fields region scrolls internally; action row remains visible without resizing dialog.
- Smart-fields keyboard contract: region has a named tabbable entry point; arrow/page keys traverse wrapped content; Tab exits deterministically to action row; if region has no focusable descendants, focus skips directly to action row.
- Assistive-technology precedence: in focus mode, keyboard contract is authoritative; in browse/virtual-cursor mode, reading order remains deterministic and must not trap focus.
- Open-failure accessibility contract: when normal render fails and fallback view is used, narration order remains title -> status -> subtitle/context -> focused control, and the event-to-copy assertion follows `MAP-OPEN-FAIL-UNK-02` when `command_executed=unknown`.
- Narration evidence operationalization:
  - Maximum replay count per open event: 2 (one standard replay + one final concise replay).
  - Timing tolerance for queued/replay narration checks: +/- 200 ms in automated/manual evidence.
  - Release evidence must include proof for at least two SR modes (focus mode and browse/virtual-cursor mode).
- Fallback presentation preserves status icon/accent and subtitle contract whenever incident type/context is available from normalized payload.
- Initial focus rationale: default focus starts in details textarea to preserve immediate manual-copy path; open announcement must still present status/title before user navigation.
- Sensitive-data disclosure placement: disclosure text remains visible next to copy action in normal and fallback modes, including copy failure/recovery states.
- Sensitive-data disclosure interaction: disclosure is persistent (no acknowledge click required) and never blocks copy action; it remains visible across success/failure/unknown/fallback states.
- Sensitive-data disclosure layout guardrails: disclosure occupies at most two lines at 100% scaling; wraps at higher scaling; must never overlap action buttons.
- Sensitive-data disclosure minimum text: at all scales, visible disclosure includes `Copied data may contain sensitive information`.
- High-scaling resilience: at 200% scaling, action row and disclosure must remain visible without overlap; smart-fields region is the sole elastic scroller; disclosure keeps one persistent visible warning line and an always-visible adjacent info affordance.
- Disclosure accessibility parity: at 200% scaling, persistent visible warning line remains readable without semantic truncation of the lead warning clause; full warning sentence is exposed through an always-visible adjacent info affordance and accessible description.
- Disclosure feasibility contract at 200% scaling:
  - Persistent visible warning line is always shown and never overlaps action buttons.
  - Full warning sentence is always reachable through the adjacent always-visible info affordance and accessible description.
  - Smart-fields remains the only elastic/scrolling region; action row and warning affordance remain fully visible.
  - When helper text and disclosure compete for space, helper uses short variant first; full helper text remains reachable via accessible description.
  - Constraint-collision precedence at 200% scaling (normative): action row visibility > disclosure warning line visibility > details textarea minimum height > smart-fields proportional target.
- Contrast evidence targets:
  - Header title/supporting text versus header background meets WCAG AA.
  - Smart-field card text versus card background meets WCAG AA.
  - Copy-helper text versus surface background meets WCAG AA in both failure and cleared states.

Message-priority contract:
- Persistent context content (status + subtitle + unknown-state supporting copy when applicable) remains visible at all times.
- Transient copy helper messages (failure/recovery) appear in helper region and must not replace persistent context content.
- Escalated-risk reinforcement: when copy helper enters `escalated` state after repeated failures, helper copy adds a non-blocking reminder to share diagnostics only with trusted support channels.

Telemetry mapping source-of-truth:
- UI status/subtitle/helper variants and corresponding telemetry fixture assertions are maintained as one mapping table in `docs/leyline/specs/2026-05-09-diagnostics-dialog-redesign-design.md` (operational contract) and referenced here for UX assertions.
- Conflict-precedence rule: product spec mapping table is authoritative for event-to-state mapping; UX spec may add presentation assertions but must not redefine operational mapping.

UX mapping appendix rule:
- UX assertions must reference product-spec mapping IDs and may define only presentation-layer expectations (copy, icon/text pairing, announcement behavior), never operational event semantics.

UX mapping appendix (compact reference):
| Mapping ID | Event fixture | Required presentation assertion |
|------------|---------------|---------------------------------|
| `MAP-OPEN-UNK-01` | `diagnostics_dialog_opened` + `command_executed=unknown` | Header/supporting copy uses unknown-state wording; no command-failure phrasing |
| `MAP-OPEN-FAIL-UNK-02` | `diagnostics_dialog_open_failed` + `command_executed=unknown` | Fallback view preserves unknown-state wording and persistent context |
| `MAP-COPY-SUCCESS-UNK-03` | `diagnostics_copy_succeeded` + `command_executed=unknown` | Success transition announced; unknown-state header/supporting copy unchanged |
| `MAP-COPY-FAIL-UNK-04` | `diagnostics_copy_failed` + `command_executed=unknown` | Failure helper shown/announced; unknown-state header/supporting copy unchanged |

Sparse-content scaffolding:
- Summary-only states keep visible section scaffolding (status header + smart-fields container frame + details textarea label) so minimal presentations read as intentional rather than broken.
- Sparse-state layout guardrails:
  - Header region uses 2-4 lines total (title + status + subtitle/context) before wrapping to smart-fields region.
  - Subtitle/context is limited to 2 lines; overflow truncates with deterministic ellipsis.
  - Smart-fields region keeps minimum 25% and maximum 55% of dialog height before internal scrolling.
  - Details textarea keeps minimum 25% of dialog height in all states.

## Non-goals
- New multi-window UX model.
- In-dialog search/filter controls.
- Editing diagnostics values.
- Export-to-file workflow.
- Tray menu redesign outside diagnostics interaction.
