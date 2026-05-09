# AWS SSO Autologin Review Log

- Feature: `aws-sso-autologin`
- Branch: `feat/aws-sso-autologin`
- Base SHA: `5fd6c44`
- Initial review SHA: `c608245`

## Branch-level code review

### Findings
- F1 (Critical): Session renewal triggers login for inactive/threshold states without explicit expired/invalid classifier gating (`aws_sso_autologin/operator.py`, `aws_sso_autologin/checker.py`).
- F2 (Critical): Per-profile cooldown is 480 seconds instead of required 300 (`aws_sso_autologin/operator.py`).
- F3 (Critical): Tray first-row global control contract is missing; first row is `Status Window` (`aws_sso_autologin/tray.py`).
- F4 (Critical): Tray-host preflight failure path does not emit required actionable stdout guidance (`aws_sso_autologin/__main__.py`, `aws_sso_autologin/logger.py`).
- F5 (Critical): Secure browser-wrapper lifecycle for `aws sso login` is missing (`aws_sso_autologin/aws.py`).
- F6 (Critical): Runtime tray-host heartbeat is placeholder (`aws_sso_autologin/service.py`).
- F7 (Critical): Test suite does not enforce required contracts (classifier governance, timeout policy, login-gating behavior).
- F8 (Important): Classifier memory constants/comments are inconsistent (`aws_sso_autologin/constants.py`).
- F9 (Important): Logged-in count can drift on repeated updates (`aws_sso_autologin/tray.py`).
- F10 (Important): Menu labels can be stale after profile status changes (`aws_sso_autologin/tray.py`).
- F11 (Important): Startup path continues despite no profiles and ignores monitoring-start failures (`aws_sso_autologin/__main__.py`).
- F12 (Important): `run_sso_login` comment says pass-through interaction but implementation captures output (`aws_sso_autologin/aws.py`).
- F13 (Suggestion): Remove unused imports/locals in `__main__.py`.
- F14 (Suggestion): Remove unused import in `service.py`.

### Response F1
- Claim (restated): Login should be queued only when command output is explicitly classified as expired/invalid SSO session, not merely inactive or below-threshold.
- Verification: Confirmed in `aws_sso_autologin/operator.py` that `check_and_renew` enqueues on `not info.is_active` and threshold. Product spec `docs/leyline/specs/2026-05-09-aws-sso-autologin-design.md:127` requires explicit expired/invalid classifier gating.
- Decision: accept
- Reasoning: Current trigger condition violates core correctness contract and can generate false-positive logins.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): Pending after remediation
- Implementation: Implemented in working tree (uncommitted): `aws_sso_autologin/models.py`, `aws_sso_autologin/checker.py`, `aws_sso_autologin/operator.py`, `tests/test_operator.py`, `tests/test_checker.py`.

### Response F2
- Claim (restated): Per-profile cooldown must be 5 minutes, not 8 minutes.
- Verification: Confirmed `LOGIN_LOCK_SECONDS = 480` in `aws_sso_autologin/operator.py`; product spec `docs/leyline/specs/2026-05-09-aws-sso-autologin-design.md:141` requires 5 minutes.
- Decision: accept
- Reasoning: Direct spec mismatch.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): N/A
- Implementation: Implemented in working tree (uncommitted): `aws_sso_autologin/constants.py`, `aws_sso_autologin/operator.py`, `tests/test_operator.py`.

### Response F3
- Claim (restated): First menu row must be global enable/disable control (or global error action), not `Status Window`.
- Verification: Confirmed first action currently `Status Window` in `aws_sso_autologin/tray.py`. Product spec `docs/leyline/specs/2026-05-09-aws-sso-autologin-design.md:53-64` and UX spec state matrix row `Global control row` require control semantics first.
- Decision: accept
- Reasoning: Core surface behavior is non-compliant.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): Required (design review)
- Implementation: Implemented in working tree (uncommitted): `aws_sso_autologin/tray.py`, `tests/test_tray.py`.

### Response F4
- Claim (restated): On startup tray-host preflight failure, app must print one actionable stdout message and exit non-zero.
- Verification: Confirmed `_detect_tray_host` only logs error and returns False in `aws_sso_autologin/__main__.py`; logger writes to stderr. Product spec `docs/leyline/specs/2026-05-09-aws-sso-autologin-design.md:45-48` requires actionable stdout guidance.
- Decision: accept
- Reasoning: Startup failure path currently misses required operator-facing guidance.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): Required (design review)
- Implementation: Implemented in working tree (uncommitted): `aws_sso_autologin/__main__.py`, `aws_sso_autologin/logger.py`, `tests/test_main.py`, `tests/test_logger.py`.

### Response F5
- Claim (restated): Browser override for SSO login must use a secure temporary executable wrapper with safe lifecycle checks.
- Verification: Confirmed `run_sso_login` sets `BROWSER` directly and does not create wrapper in `aws_sso_autologin/aws.py`. Product spec `docs/leyline/specs/2026-05-09-aws-sso-autologin-design.md:155-170` mandates wrapper lifecycle.
- Decision: accept
- Reasoning: Security-sensitive requirement is absent.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): N/A
- Implementation: Implemented in working tree (uncommitted): `aws_sso_autologin/aws.py`, `tests/test_aws.py`.

### Response F6
- Claim (restated): Runtime tray-host heartbeat must perform real checks and detect repeated failures instead of always returning True.
- Verification: Confirmed `ConcreteTrayHost.ping()` is placeholder always-true in `aws_sso_autologin/service.py`. Product spec `docs/leyline/specs/2026-05-09-aws-sso-autologin-design.md:48-51` mandates heartbeat checks and escalation.
- Decision: accept
- Reasoning: Runtime safety requirement is not implemented.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): N/A
- Implementation: Implemented in working tree (uncommitted): `aws_sso_autologin/service.py`, `tests/test_service.py`.

### Response F7
- Claim (restated): Branch tests currently do not enforce critical contracts for login gating, wrapper failures, heartbeat behavior, and key spec constraints.
- Verification: Confirmed tests are mostly scaffold-level (`tests/test_classifier.py` has one basic test; `tests/test_aws.py`, `tests/test_tray.py`, `tests/test_service.py`, `tests/test_main.py` do not assert required contracts).
- Decision: accept
- Reasoning: Without contract-level tests, critical regressions are likely.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): Required (design review for surface tests)
- Implementation: Implemented in working tree (uncommitted): expanded contract tests in `tests/test_operator.py`, `tests/test_checker.py`, `tests/test_main.py`, `tests/test_service.py`, `tests/test_aws.py`, `tests/test_tray.py`.

### Response F8
- Claim (restated): Classifier memory constants and comments should match stated budget intent.
- Verification: `CLASSIFIER_BYTES_PER_TOKEN_ESTIMATE = 1` with comments claiming `~48 KiB per stream` and `~12 MiB total` in `aws_sso_autologin/constants.py`; arithmetic is inconsistent with comments.
- Decision: accept
- Reasoning: Clarifying constants and deterministic checks prevents future drift.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): N/A
- Implementation: Implemented in working tree (uncommitted): `aws_sso_autologin/constants.py`, `tests/test_constants.py`.

### Response F9
- Claim (restated): Logged-in count should transition-aware update, not increment on repeated already-logged-in updates.
- Verification: In `aws_sso_autologin/tray.py`, `update_profile` decrements old logged-in and increments new logged-in, but with inconsistent status refresh logic and stale labels this can drift in behavior under repeated updates.
- Decision: accept
- Reasoning: Accurate aggregate status is user-visible and required for trust.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): Required (design review)
- Implementation: Implemented in working tree (uncommitted): `aws_sso_autologin/tray.py`, `tests/test_tray.py`.

### Response F10
- Claim (restated): Profile menu labels must refresh after status changes, not only when profile count boundary changes.
- Verification: Confirmed `update_profile` only rebuilds menu for new profile/overflow-boundary transitions in `aws_sso_autologin/tray.py`; existing profile text can remain stale.
- Decision: accept
- Reasoning: Stale labels violate state visibility requirements.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): Required (design review)
- Implementation: Implemented in working tree (uncommitted): `aws_sso_autologin/tray.py`, `tests/test_tray.py`.

### Response F11
- Claim (restated): Startup should not silently continue to ambiguous running state when profiles fail to load or monitoring cannot start.
- Verification: Confirmed `_load_profiles` failure only warns and `run` continues; `_start_monitoring` result is ignored in `aws_sso_autologin/__main__.py`.
- Decision: accept
- Reasoning: Needs deterministic startup/global-error semantics.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): Required (design review)
- Implementation: Implemented in working tree (uncommitted): `aws_sso_autologin/__main__.py`, `tests/test_main.py`.

### Response F12
- Claim (restated): Code/comment mismatch in `run_sso_login` should be corrected so behavior is explicit and intentional.
- Verification: Comment says pass-through for interaction while code uses `capture_output=True`.
- Decision: accept
- Reasoning: Mismatch creates maintenance confusion.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): N/A
- Implementation: Implemented in working tree (uncommitted): `aws_sso_autologin/aws.py`, `tests/test_aws.py`.

### Response F13
- Claim (restated): Remove unused imports/locals in `__main__.py`.
- Verification: `ProfileInfo` import and local variable `profile_config` are unused in current implementation.
- Decision: accept
- Reasoning: Cleanup was completed during startup/tray-integration remediation.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): N/A
- Implementation: Implemented in working tree (uncommitted): `aws_sso_autologin/__main__.py`.

### Response F14
- Claim (restated): Remove unused import(s) in `service.py`.
- Verification: `auto` from `enum` is imported but unused.
- Decision: accept
- Reasoning: Cleanup was completed while implementing tray-host heartbeat probing.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): N/A
- Implementation: Implemented in working tree (uncommitted): `aws_sso_autologin/service.py`.

## Branch-level design review

### Findings
- D1 (Critical): Global control row semantics are missing; first row is not control/action row.
- D2 (Critical): Required icon-state semantics and precedence are not implemented.
- D3 (Critical): Profile row state taxonomy/copy is incomplete vs UX spec.
- D4 (Critical): Required Error details dialog surface is missing.
- D5 (Critical): Startup preflight failure does not emit explicit actionable stdout copy.
- D6 (Critical): Accessibility evidence artifact is missing.
- D7 (Important): Overflow thresholds/chunk sizes differ from UX contract (`>40`, chunk `20`).
- D8 (Important): Voice/copy strings are inconsistent with UX reference strings.
- D9 (Important): Status-window surface introduced despite UX artifact constraints (`no primary window`).
- D10 (Important): Interaction wiring incomplete for profile row behavior and quit flow.
- D11 (Suggestion): Add state-matrix-driven UI tests.
- D12 (Suggestion): Reconcile README copy with approved UX behavior.

### Response D1
- Claim (restated): First row must always be global control toggle or global error action, never a non-control row.
- Verification: UX spec state matrix `Global control row` requires first-row control semantics; current tray menu starts with `Status Window`.
- Decision: accept-impl
- Reasoning: This is a primary flow contract and must be fixed in code.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): Required (code review)
- Implementation / spec update / tracking: Implemented in working tree (uncommitted): `aws_sso_autologin/tray.py`, `tests/test_tray.py`.

### Response D2
- Claim (restated): Tray icon must map to specified semantic states with documented precedence.
- Verification: UX spec row `System tray icon` and precedence section require `enabled-ok/syncing/warning/error/disabled-paused`; current code uses static icon semantics only.
- Decision: accept-impl
- Reasoning: Required status communication is missing.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): Required (code review)
- Implementation / spec update / tracking: Implemented in working tree (uncommitted): `aws_sso_autologin/tray.py`, `tests/test_tray.py`.

### Response D3
- Claim (restated): Profile rows need full state-specific copy and behavior (Syncing, Warning, Error reasons, paused OK variants).
- Verification: UX spec `Profile status row` matrix cell defines required copy; current labels are limited to `OK/Not Logged In/Error` variants.
- Decision: accept-impl
- Reasoning: Copy/state behavior is central to operability.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): Required (code review)
- Implementation / spec update / tracking: Implemented in working tree (uncommitted): `aws_sso_autologin/tray.py`, `tests/test_tray.py`.

### Response D4
- Claim (restated): Error details dialog must exist and be opened for warning/error interactions with ordered content.
- Verification: UX spec includes explicit `Error details dialog` surface and required field order; current code has no dialog implementation.
- Decision: accept-impl
- Reasoning: Missing required surface and failure-path visibility.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): Required (code review)
- Implementation / spec update / tracking: Implemented in working tree (uncommitted): `aws_sso_autologin/tray.py`, `tests/test_tray.py`.

### Response D5
- Claim (restated): Preflight tray-host failure must emit a deterministic actionable stdout message.
- Verification: UX flow 1 failure path and timing section require one actionable stdout line; current startup path only logs.
- Decision: accept-impl
- Reasoning: Required startup guidance is absent.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): Required (code review)
- Implementation / spec update / tracking: Implemented in working tree (uncommitted): `aws_sso_autologin/__main__.py`, `aws_sso_autologin/logger.py`, `tests/test_main.py`.

### Response D6
- Claim (restated): Branch must include concrete accessibility verification evidence for touched surfaces.
- Verification: No review-log artifact currently records keyboard/screen-reader/a11y checks for branch-level UX changes.
- Decision: accept-impl
- Reasoning: Evidence is required by process and acceptance discipline.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): N/A
- Implementation / spec update / tracking: Implemented in working tree (uncommitted): accessibility evidence at `docs/leyline/plans/2026-05-09-aws-sso-autologin-a11y-evidence.md` and interaction coverage in `tests/test_tray.py`.

### Response D7
- Claim (restated): Overflow behavior must use threshold >40 and submenu size 20.
- Verification: UX flow 6 and matrix row `Profile overflow submenu` define >40 and 20-sized buckets; current constants use 25.
- Decision: accept-impl
- Reasoning: Deterministic high-cardinality behavior is a defined acceptance criterion.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): Required (code review)
- Implementation / spec update / tracking: Implemented in working tree (uncommitted): `aws_sso_autologin/constants.py`, `aws_sso_autologin/tray.py`, `tests/test_constants.py`, `tests/test_tray.py`.

### Response D8
- Claim (restated): Visible copy should align with approved voice reference strings and terminology.
- Verification: Compared tray labels/tooltip text against UX `Voice and tone` section; current copy diverges.
- Decision: accept-impl
- Reasoning: Consistent copy is part of UX contract.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): Required (code review)
- Implementation / spec update / tracking: Implemented in working tree (uncommitted): `aws_sso_autologin/tray.py`, `tests/test_tray.py`.

### Response D9
- Claim (restated): Status-window promotion conflicts with UX constraint of tray + dialog surfaces only.
- Verification: UX `Platform / harness constraints` says no primary window; current tray includes `Status Window` as top-level interaction path.
- Decision: accept-impl
- Reasoning: Implementation should match approved surface set for V1.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): Required (code review)
- Implementation / spec update / tracking: Implemented in working tree (uncommitted): removed status-window menu promotion in `aws_sso_autologin/tray.py`; diagnostics dialog is primary failure surface.

### Response D10
- Claim (restated): Profile row and quit actions require complete behavior wiring.
- Verification: Current menu actions are mostly structural and do not enforce UX flow rules for OK vs Warning/Error interaction.
- Decision: accept-impl
- Reasoning: Interaction behavior is core usability contract.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): Required (code review)
- Implementation / spec update / tracking: Implemented in working tree (uncommitted): profile row callbacks and quit wiring in `aws_sso_autologin/tray.py`, verified by `tests/test_tray.py`.

### Response D11
- Claim (restated): Add tests that enforce state-matrix behavior and copy contracts.
- Verification: Existing tray tests assert existence/shape but not state-matrix semantics.
- Decision: accept-impl
- Reasoning: Added state-matrix and interaction-contract tests for first-row semantics, profile-row behavior, overflow grouping, and diagnostics ordering.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): N/A
- Implementation / spec update / tracking: Implemented in working tree (uncommitted): `tests/test_tray.py`.

### Response D12
- Claim (restated): README user-facing behavior descriptions must match implemented/approved UX semantics.
- Verification: Current README text predates review findings and may drift from updated behavior.
- Decision: accept-impl
- Reasoning: README now reflects first-row global control semantics, overflow thresholds, diagnostics dialog, and 5-minute cooldown behavior.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): N/A
- Implementation / spec update / tracking: Implemented in working tree (uncommitted): `README.md`.

## Deferred findings
- None currently.
