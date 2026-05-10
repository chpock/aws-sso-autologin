# Profile State Machine and Error Visibility - product spec
Date: 2026-05-10
Author: human partner
Surfaces: multi-screen-ui

## Problem
Current profile-status transitions are spread across multiple runtime branches and are partially implicit. This can hide actionable failures from users because an `error` state may be overwritten by intermediate checks before a clear recovery signal exists. The app must provide explicit, durable failure signaling so users know when manual action is required.

## Goals
- Introduce an explicit per-profile state machine with deterministic transitions.
- Keep `error` sticky until a profile has an explicit successful `ok` outcome.
- Define session liveness only by `aws sts get-caller-identity` outcomes, not by `seconds_remaining`.
- Keep `warning` only for indeterminate/ambiguous session-check outcomes.
- Ensure profile-level error menu entries always remain available and open a diagnostics dialog with reason and details, including during retries and ongoing checks.
- Define app-level aggregation rules:
  - Monitoring paused => app status `paused`, paused icon regardless of profile states.
  - Monitoring active + at least one profile `error` => app status `error`, error icon.
  - Monitoring active + profiles only in `ok|synchronizing|warning` => app status `working`.

## Non-goals
- Replacing AWS CLI integration or changing underlying auth command contracts.
- Redesigning the diagnostics dialog visual layout beyond behavior guarantees.
- Introducing external incident persistence or remote telemetry in this iteration.

## Constraints
- Must integrate with existing Qt tray architecture (`StatusTray`, `ErrorDetailsDialog`) and operators (`HealthOperator`, `SessionOperator`, `LoginOperator`).
- Must emit structured logs for every state transition with `profile`, `from_state`, `to_state`, `trigger`, and relevant diagnostics keys.
- Must be robust under asynchronous status updates from background checks.
- Must define a deterministic conflict-resolution policy for near-simultaneous events coming from session checks and sync retries.
- Must be covered by transition-focused tests and full regression verification via `make test`.

## Approaches considered
### Approach A - Patch existing branching
Apply targeted updates in existing conditional mapping logic without introducing a formal state-machine boundary.

Trade-offs: low immediate implementation cost; high long-term ambiguity and regression risk.

### Approach B - Explicit profile state machine
Introduce a dedicated transition layer that owns state updates and enforces transition contracts.

Trade-offs: higher initial implementation scope; strongest clarity, testability, and future maintainability.

### Approach C - Hybrid transition extraction
Move only high-risk transitions (sticky error and recovery) into a machine and leave remaining paths in current logic.

Trade-offs: moderate short-term cost; still leaves split mental models and ownership ambiguity.

## Recommendation
Use **Approach B** and route all profile-state updates through an explicit state machine.

### Proposed state model
- Primary states: `ok`, `synchronizing`, `warning`, `error`.
- Initial state on profile initialization: `synchronizing`.
- Orthogonal sync substate: `confirmation_pending` (`true|false`) for non-error states only.
- `confirmation_pending=true` means sync command succeeded and the profile is waiting for explicit `session_check_success_active` confirmation.

### Proposed transition events
- `session_check_success_active`: session check success, session active and not expired.
- `session_check_expired`: session check indicates expired or invalid session requiring auth.
- `session_check_failed_determinate`: deterministic failure class (decision table below).
- `session_check_failed_indeterminate`: ambiguous or unexpected failure class (decision table below).
- `sync_started`: login/sync workflow started.
- `sync_failed`: login/sync workflow failed.
- `sync_succeeded`: login/sync command succeeded and profile enters confirmation window pending a successful session check.
- `confirmation_timeout`: synthetic timer event emitted when `confirmation_pending=true` exceeds allowed window without `session_check_success_active`.

Decision table for failure classification:

| Failure class | Event type | Notes |
|---|---|---|
| Explicit auth denial (`AccessDenied`, auth policy refusal) | `session_check_failed_determinate` | Deterministic; user action required. |
| Explicit token/session expiry from provider response | `session_check_expired` | Requires synchronization/login path. |
| Command process timeout with no parsable identity result | `session_check_failed_indeterminate` | Treated as transport/host ambiguity, not proof of invalid credentials. |
| Network unreachable / DNS / transient transport failure | `session_check_failed_indeterminate` | Ambiguous environment fault. |
| Malformed/partial command output without definitive auth result | `session_check_failed_indeterminate` | Parsing ambiguity must not force sticky error entry. |
| Unknown non-zero exit with definitive auth-failure classification from parser | `session_check_failed_determinate` | Parser must log classifier reason. |

### Transition matrix (normative)
`current_state x event -> next_state`

| Current state | `session_check_success_active` | `session_check_expired` | `session_check_failed_determinate` | `session_check_failed_indeterminate` | `sync_started` | `sync_failed` | `sync_succeeded` |
|---|---|---|---|---|---|---|---|
| `ok` | `ok` | `synchronizing` | `error` | `warning` | `synchronizing` | `error` | `ok` |
| `synchronizing` | `ok` | `synchronizing` | `error` | `warning` | `synchronizing` | `error` | `synchronizing` + `confirmation_pending=true` |
| `warning` | `ok` | `synchronizing` | `error` | `warning` | `synchronizing` | `error` | `warning` + `confirmation_pending=true` |
| `error` | `ok` | `error` | `error` | `error` | `error` | `error` | `error` |

`confirmation_pending=true` synthetic event handling:

| Current state (with `confirmation_pending=true`) | `confirmation_timeout` |
|---|---|
| `ok` | `synchronizing` + `confirmation_pending=false` |
| `synchronizing` | `synchronizing` + `confirmation_pending=false` |
| `warning` | `synchronizing` + `confirmation_pending=false` |
| `error` | `error` |

Notes:
- `sync_succeeded` is not a direct recovery from `error`; it only sets `confirmation_pending=true` for non-error states.
- Unlisted events are treated as `no-op` and must be logged as ignored.

### Mandatory transition rules
- `error` is sticky until explicit `session_check_success_active`.
- `error -> warning` is forbidden.
- Indeterminate failures may map to `warning` only when current state is not `error`.
- `session_check_success_active` determines liveness by command outcome; `seconds_remaining` cannot demote status to `warning`.
- `sync_succeeded` sets `confirmation_pending=true` only when current primary state is `synchronizing` or `warning`; when current state is `ok`, `sync_succeeded` is a no-op.
- `session_check_success_active` may clear `error` only when recovery eligibility is met: `event_monotonic_ns >= last_failure_monotonic_ns` and `auth_attempt_id` matches the current sync/check epoch.
- Recovery events failing eligibility are ignored as stale success and must emit `event=profile_state_event_ignored` with `reason=stale_success`.
- `auth_attempt_id` lifecycle contract:
  - Generated by `LoginOperator` when sync begins and rotated on each new sync attempt.
  - Propagated on all related session-check and sync events for that profile.
  - Invalidated immediately when a newer sync attempt starts for the same profile.
  - Missing or mismatched `auth_attempt_id` on `session_check_success_active` makes recovery ineligible and must be logged as ignored with `reason=auth_attempt_mismatch`.
- Confirmation window duration is 30 seconds by default, evaluated on monotonic process clock; optional override is allowed only via bounded config range `[10s, 120s]` and must be logged at startup.
- `confirmation_timeout` is a first-class event and must participate in deterministic ordering rules.
- If no successful check arrives before confirmation timeout, emit `confirmation_timeout`, set `confirmation_pending=false`, set primary state to `synchronizing`, and emit warning-level transition log.

### Async conflict resolution policy
- Events are processed in arrival order on a single serialized queue per profile.
- Canonical event-time basis is monotonic process clock (`event_monotonic_ns`) for ordering, bucketing, and replay determinism.
- Optional audit time field is wall clock (`event_wall_epoch_ms`) and must never influence ordering or precedence.
- Timestamp bucket is fixed at 100 ms and derived only from monotonic process clock.
- If events share the same timestamp bucket, precedence is: `session_check_failed_determinate` > `session_check_success_active` > `session_check_expired` > `sync_failed` > `confirmation_timeout` > `sync_succeeded` > `session_check_failed_indeterminate` > `sync_started`.
- Every processed event must log `event_id`, `event_source`, `profile`, `event_monotonic_ns`, `event_wall_epoch_ms`, `prev_state`, `next_state`, `prev_confirmation_pending`, `next_confirmation_pending`, and `resolution_rule` (`ordered` or `precedence_tiebreak`).
- `correlation_id` is mandatory for all events; generation format is `<profile>:<source>:<event_monotonic_ns>:<nonce>`. Event sources unable to provide it must use local generator before enqueue.
- Duplicate events with identical `(profile, event_type, correlation_id)` are idempotent no-ops and must be logged as deduplicated.
- Terminal event taxonomy for overflow policy:

| Event type | Terminal class | Rationale |
|---|---|---|
| `session_check_success_active` | terminal | Concludes current auth epoch as healthy. |
| `session_check_failed_determinate` | terminal | Concludes current auth epoch with actionable failure. |
| `session_check_expired` | terminal | Concludes check and requires sync path. |
| `sync_failed` | terminal | Concludes sync attempt with failure. |
| `confirmation_timeout` | terminal | Concludes confirmation window without successful check. |
| `sync_succeeded` | non-terminal | Starts confirmation window; requires follow-up check. |
| `session_check_failed_indeterminate` | non-terminal | Ambiguous signal; does not conclude epoch. |
| `sync_started` | non-terminal | Start marker only. |
- Per-profile queue length is capped at 256 events.
- On overflow, drop oldest non-terminal event first; if only terminal events remain, drop newest and emit backpressure warning.
- Overflow handling must emit `event=profile_state_queue_overflow` with keys `profile`, `queue_len`, `dropped_event_type`, and `drop_policy`.
- If dropped events create a detected causality gap, emit `event=profile_state_causality_gap` and force bounded recovery behavior: `primary_state=synchronizing`, `confirmation_pending=false`.
- While causality-gap recovery is active, set profile UI degraded-mode reason suffix `state may be delayed` until the next successful `session_check_success_active` for the same profile.
- Causality-gap/operator signaling must be rate-limited to one warning emission per profile per 60 seconds via `event=profile_state_causality_gap_warn`.

### App-level aggregation
- Monitoring paused: app status `paused`, tray icon paused, tooltip/reporting status `paused`.
- Monitoring active and any profile `error`: app status `error`, tray icon error.
- Monitoring active and no profile `error`: app status `working` (icon can still reflect syncing vs steady OK based on current profile mix).

### Error visibility behavior
- A profile in `error` must always render as an error row/menu item.
- Clicking that profile must always open diagnostics dialog with reason plus details.
- This interaction remains available during retries, concurrent checks, and paused mode.

### Diagnostics retention policy
- Profile diagnostics payload (`summary`, `details`, `timestamp`, `failure_type`) is retained in memory until explicit `session_check_success_active` transitions the profile to `ok`.
- While retained data is older than 24h, UI keeps it visible but marks details as `stale`.
- On transition to `ok`, retained diagnostics for that profile are cleared.

## Observability
- Required transition log event: `event=profile_state_transition` with keys `profile`, `from_state`, `to_state`, `trigger`, `failure_type`, `correlation_id`, `queue_latency_ms`.
- Required ignored-event log event: `event=profile_state_event_ignored` with keys `profile`, `state`, `trigger`, `reason`.
- Required diagnostics interaction log events:
  - `event=profile_diagnostics_open_requested`
  - `event=profile_diagnostics_open_succeeded`
  - `event=profile_diagnostics_open_failed`
- Required aggregation log event: `event=app_state_aggregated` with keys `monitoring_enabled`, `profile_error_count`, `profile_sync_count`, `app_state`, `icon_state`.
- Required classifier quality log event: `event=session_failure_classified` with keys `profile`, `raw_failure_class`, `classified_event_type`, `classifier_confidence`, `classifier_version`.
- Required classifier anomaly log event: `event=session_failure_classifier_unknown` with keys `profile`, `raw_failure_class`, `reason`.

## Security and data handling
- Diagnostics details shown in UI must be redacted for known secret patterns (AWS access keys, session tokens, bearer tokens).
- Raw diagnostics payload persisted in profile state is capped to 16 KiB per profile; overflow must be truncated with explicit marker.
- Trace-level logs may include richer diagnostics but must pass the same redaction routine.
- Clipboard export (if added later) must export already-redacted content only.
- Redaction miss policy: if sanitizer confidence is below threshold, block raw payload display and replace with safe fallback text plus `event=diagnostics_redaction_blocked`.
- Sanitizer confidence threshold is controlled by `AWS_SSO_AUTOLOGIN_REDACTION_CONFIDENCE_THRESHOLD` with default `0.90` and bounded range `[0.70, 0.99]`; value must be logged at startup and on config reload via `event=diagnostics_redaction_threshold_configured`.
- Threshold owner is runtime on-call; recalibration is required when `diagnostics_redaction_blocked` exceeds 0.5% of diagnostics-open attempts over 15 minutes.
- Sanitizer confidence contract:
  - Confidence output must include `sanitizer_version` and `confidence_source` (`rules_only` or `rules_plus_model`).
  - Startup logs must emit active sanitizer contract as `event=diagnostics_redaction_contract_loaded`.
  - Recalibration changes must emit `event=diagnostics_redaction_contract_changed` with previous/new threshold and version.
  - Confidence algorithm changes require replay validation against adversarial redaction corpus before canary expansion.

## Rollout and rollback
- Introduce feature flag `AWS_SSO_AUTOLOGIN_PROFILE_SM_V2` (default: enabled in development, disabled for first production canary).
- Canary rollout: feature flag accepts target selectors (`all`, `workstation:<hostname>`, `profile:<name>`). Initial canary uses `workstation:<hostname>` on a fixed allowlist.
- Selector source of truth: `AWS_SSO_AUTOLOGIN_PROFILE_SM_V2_TARGETS` (comma-separated selectors) evaluated at process start; invalid selectors fail closed (feature remains disabled) and emit `event=profile_sm_selector_invalid`.
- Selector audit logs: emit `event=profile_sm_selector_loaded` with keys `selector_count`, `selectors_hash`, `source`, `enabled_profiles`.
- Selector expansion control-plane enforcement:
  - Enforcement actuator is runtime selector loader in `AutologinApp` startup path; expansion is blocked before profile state machine initialization when gates fail.
  - Gate failure or missing metric input is fail-closed for expansion attempts and must emit `event=profile_sm_selector_expansion_blocked` with `block_reason`.
  - Deployment pipeline may suggest selectors but cannot bypass runtime gate; runtime decision is source of truth.
- Rollback trigger:
  - ignored-event anomaly ratio = `profile_state_event_ignored` / `profile_state_transition` > 0.5% sustained for 15 minutes,
  - OR diagnostics-open failure rate >1% over 15 minutes.
- Trigger metric source of truth is process-local rolling windows emitted by runtime aggregator every 60 seconds.
- On process restart, windows are warm-started as empty; rollback automation is disabled until each trigger denominator reaches 200 events.
- Low-traffic fail-safe: while denominator warm-up blocks automation, runtime on-call must manually rollback if either trigger condition is exceeded for 30 consecutive minutes and at least one impacted profile is user-visible.
- Rollback action: disable `AWS_SSO_AUTOLOGIN_PROFILE_SM_V2`, clear in-memory `confirmation_pending` flags, keep diagnostics payload as read-only legacy-compatible snapshot, and revert to legacy mapping path without modifying persisted user config.
- Rollback sequencing is mandatory: stop V2 enqueue -> drain queue (or drop with explicit reason) -> switch to legacy mapper -> resume legacy-only event processing.
- Auto-reenable hysteresis: after any automatic or manual rollback, suppress automated re-enable for a cooldown of 60 minutes and require a minimum stable interval of 30 minutes below rollback thresholds before re-enable is permitted.
- Oscillation guard: if two rollback events occur within 6 hours on the same host, require explicit manual override to re-enable V2 (`event=profile_sm_reenable_manual_override_required`).
- Required rollback lifecycle logs:
  - `event=profile_sm_rollback_started`
  - `event=profile_sm_rollback_queue_drained` or `event=profile_sm_rollback_queue_dropped`
  - `event=profile_sm_rollback_legacy_mapper_active`

## Ownership and operations
- Primary owner: `service/runtime` maintainers of `AutologinApp` + operators stack.
- On-call responsibility: investigate `profile_state_transition` anomalies and diagnostics-open failures with runbook updates in same release.
- Required runbook additions: stuck `error` triage, confirmation-timeout behavior, and paused-mode visibility checks.
- Alert denominator for diagnostics-open failure is total `profile_diagnostics_open_requested` per 15-minute window.
- Paging threshold owner is runtime on-call; baseline and suppression policy must be documented in runbook before enabling canary.

## Open questions
- None.

Resolved constraints recorded in this round:
- Timestamp bucket remains fixed at 100 ms in v2 and is not configurable.

## Success criteria
- All profile transitions pass through one state-machine module and are unit tested.
- No `error -> warning` transition path exists.
- `session_check_success_active` with missing `seconds_remaining` still yields/keeps `ok`.
- Paused mode always reports app status `paused` and uses paused icon.
- Error-profile menu action consistently opens diagnostics with reason and detailed payload.
- Concurrency tests prove deterministic outcome for conflicting event orders.
- Property/fuzz tests cover random event sequences and preserve invariants (`error` sticky, no illegal transitions).
- Integration tests verify error-row clickability during retries and in paused mode.
- Deterministic replay tests verify same output states for identical event streams.
- Redaction tests cover known-token patterns plus adversarial near-miss payloads.
- Canary gate blocks selector expansion beyond initial allowlist when `session_failure_classifier_unknown` rate exceeds 0.2% over 15 minutes.
- Distribution-drift check alerts when determinate/indeterminate ratio deviates by more than 30% from canary baseline over a 60-minute window.
- Canary baseline contract: baseline window is first continuous 60 minutes after canary enablement with at least 500 classified events; baseline resets on rollback or process restart and must be re-established before drift alerts are actionable.
- Full verification passes via `make test`.

## Round 3 classification
- (S) Formalized confirmation behavior as orthogonal `confirmation_pending` substate to remove state-model ambiguity.
- (S) Removed `sync_succeeded` contradiction by making it set substate only, not transition primary state.
- (S) Defined timestamp-bucket width and mandatory correlation-id contract for deterministic dedup/tiebreak behavior.
- (O) Added explicit canary target-selector mechanism for controlled rollout.
- (O) Added rollback compatibility behavior for partially transitioned runtime state.
- (O) Added redaction-miss fallback behavior and blocking event emission.
- (O) Added denominator/ownership requirements for paging thresholds.

## Round 4 classification
- (S) Added explicit `confirmation_timeout` event with normative transition handling and precedence participation.
- (S) Added deterministic confirmation-window timing contract (default, bounds, clock source).
- (S) Replaced example-based failure typing with a decision table for determinate vs indeterminate classification.
- (O) Added selector control-plane contract (`AWS_SSO_AUTOLOGIN_PROFILE_SM_V2_TARGETS`) including fail-closed behavior and audit logs.
- (O) Added measurable ignored-event rollback threshold formula and sustained-window trigger semantics.

## Round 5 classification
- (S) Unified deterministic ordering and correlation contracts around monotonic time with wall-clock retained as audit-only.
- (O) Added explicit rollback queue sequencing and lifecycle logs to prevent mixed-mode transitions after rollback.
- (O) Added classifier quality/unknown telemetry and rollout guardrails for failure-classification drift.

## Round 6 classification
- (S) Added recovery-eligibility guard to prevent stale success replay from clearing sticky `error`.
- (O) Added bounded queue and overflow/backpressure policy with required overflow telemetry.
- (O) Added normative metric computation/warm-up contract for rollback triggers.

## Round 7 classification
- (S) Added normative `auth_attempt_id` lifecycle contract to make stale-success rejection deterministic across operators.
- (S) Added explicit causality-gap handling under queue overflow to preserve transition safety.
- (O) Added low-traffic manual rollback fail-safe for canary windows blocked by denominator warm-up.
- (O) Added baseline capture/reset contract for drift alert reliability.
- (R) Aligned product-level stale marker expectations with UX dual-surface requirement.

## Round 9 classification
- (S) Added normative terminal/non-terminal event taxonomy to make overflow drop behavior deterministic.
- (O) Added sanitizer-confidence contract telemetry/versioning and recalibration traceability.
- (O) Added explicit runtime selector-expansion enforcement path with fail-closed behavior and auditable block events.
- (R) Resolved bucket-configurability ambiguity by locking v2 to fixed 100 ms and documenting as non-configurable.

## Round 10 classification
- (R) Resolved confirmation visibility policy: `confirmation_pending` remains internal-only for primary labels; optional tooltip hint is allowed for support context.

## Round 8 classification
- (S) Resolved `sync_succeeded` applicability ambiguity by constraining confirmation entry to `synchronizing|warning` and making `ok + sync_succeeded` a no-op.
- (S) Updated same-bucket precedence to favor determinate failure over success to preserve sticky-error intent under contention.
- (O) Added sanitizer confidence threshold governance (bounded config, startup/reload logging, and recalibration trigger ownership).
- (O) Added explicit degraded-mode affordance and rate-limited causality-gap operator warnings for overflow recovery periods.
- (O) Added rollback hysteresis/cooldown and oscillation guard requiring manual override after repeated rollback events.

## Round 2 classification
- (S) Added explicit transition matrix and no-op rules to eliminate ambiguous transition pairs.
- (S) Added async conflict-resolution and tie-break policy for concurrent events.
- (S) Defined confirmation-window semantics for `sync_succeeded` and timeout fallback behavior.
- (S) Resolved diagnostics retention into a normative policy.
- (O) Added observability contract for transitions, diagnostics open flow, and app aggregation.
- (O) Added diagnostics redaction and payload-capping policy.
- (O) Added feature-flag rollout and rollback trigger/action contract.
- (O) Added ownership/on-call and runbook requirements.
- (O) Expanded test obligations with concurrency/fuzz/integration coverage.

## Approvals
Product spec approved - round 1 - 2026-05-10
Product spec approved - round 2 - 2026-05-10
Product spec approved - round 3 - 2026-05-10
Product spec approved - round 4 - 2026-05-10
Product spec approved - round 5 - 2026-05-10
Product spec approved - round 6 - 2026-05-10
Product spec approved - round 7 - 2026-05-10
Product spec approved - round 8 - 2026-05-10
Product spec approved - round 9 - 2026-05-10
Product spec approved - round 10 - 2026-05-10
Deep-discovery pass complete - round 9 - 2026-05-10
