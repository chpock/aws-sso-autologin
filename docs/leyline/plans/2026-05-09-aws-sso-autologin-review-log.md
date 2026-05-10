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

## Branch-level code review (round 2)

- Reviewed range: `5fd6c44..63f9cd9`
- Re-review head before fixes: `63f9cd9`

### Findings
- F15 (Critical): Runtime login path bypasses secure-wrapper + 180s timeout contract (`aws_sso_autologin/operator.py`, `aws_sso_autologin/cli.py`, `aws_sso_autologin/aws.py`).
- F16 (Critical): Tray-host heartbeat/loss logic not integrated in runtime app lifecycle (`aws_sso_autologin/__main__.py`, `aws_sso_autologin/service.py`).
- F17 (Critical): Missing iron-law RED/debugging records in review log.
- F18 (Important): Empty-profile startup exits instead of continuing in empty-state mode (`aws_sso_autologin/__main__.py`).
- F19 (Important): Missing per-task post-implementation verification evidence in review log.

### Response F15
- Claim (restated): Actual operator login execution must use one canonical path that enforces wrapper lifecycle and `sso_login` timeout policy.
- Verification: `LoginOperator._process_login` called `CLIExecutor.execute_login`; `CLIExecutor` used direct `subprocess.run(... timeout=300)` and did not invoke `run_sso_login`.
- Decision: accept
- Reasoning: This bypassed both security and timeout requirements in the production login flow.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): N/A
- Implementation: Implemented in working tree (uncommitted): `aws_sso_autologin/cli.py`, `aws_sso_autologin/constants.py`, `tests/test_cli.py`.

### Response F16
- Claim (restated): Runtime tray-host heartbeat exists but must be wired into `AutologinApp` lifecycle with periodic checks and pause behavior.
- Verification: `ConcreteTrayHost.ping()` existed in `service.py`, but `__main__.py` did not instantiate tray host monitor or heartbeat timer.
- Decision: accept
- Reasoning: Required runtime safety path was not active.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): Required (design review)
- Implementation: Implemented in working tree (uncommitted): `aws_sso_autologin/__main__.py`, `aws_sso_autologin/constants.py`, `tests/test_main.py`.

### Response F17
- Claim (restated): Review log must include explicit RED/debugging records for branch-level remediation findings.
- Verification: No `Systematic-debugging record` sections were present for re-review findings before this update.
- Decision: accept
- Reasoning: Process artifact is mandatory for iron-law traceability.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): N/A
- Implementation: This section plus `Systematic-debugging record - round 2` entries below.

### Response F18
- Claim (restated): App should remain running in empty-profile mode and show actionable global state rather than exiting.
- Verification: `run()` returned `1` when `_load_profiles()` failed.
- Decision: accept
- Reasoning: UX flow requires continued monitoring state for profile-source updates.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): Required (design review)
- Implementation: Implemented in working tree (uncommitted): `aws_sso_autologin/__main__.py`, `tests/test_main.py`.

### Response F19
- Claim (restated): Review log should include concrete post-implementation verification outputs.
- Verification: Prior review-log section lacked explicit command-result evidence for round-2 fixes.
- Decision: accept
- Reasoning: Verification-before-completion requires explicit observable evidence.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): N/A
- Implementation: Added `Failing-test output (round 2)` and `Post-implementation verification output (round 2)` sections below.

## Branch-level design review (round 2)

### Findings
- D13 (Critical): Icon semantic states were tracked logically but rendered with a single blank icon (`aws_sso_autologin/tray.py`).
- D14 (Critical): Default diagnostics text was not structured `key: value`, leaving dialog fields empty (`aws_sso_autologin/tray.py`).
- D15 (Critical): Startup global-error summary used action-label wording rather than class-accurate summary (`aws_sso_autologin/__main__.py`).
- D16 (Critical): A11y evidence lacked keyboard-walk + narration proxy transcript detail (`docs/leyline/plans/2026-05-09-aws-sso-autologin-a11y-evidence.md`).
- D17 (Important): Dialog default focus on close action not explicitly enforced/tested (`aws_sso_autologin/tray.py`, `tests/test_tray.py`).
- D18 (Important): Error fallback copy used vague `Unknown error` text (`aws_sso_autologin/tray.py`).

### Response D13
- Claim (restated): Icon semantics must render distinct visual assets for each state, not just state strings.
- Verification: `_update_icon_state` set `QIcon()` regardless of `current_icon_state`.
- Decision: accept-impl
- Reasoning: Primary surface signal was visually non-functional.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): Required (code review)
- Implementation / spec update / tracking: Implemented in working tree (uncommitted): `aws_sso_autologin/tray.py`, `tests/test_tray.py`.

### Response D14
- Claim (restated): Default diagnostics payload must populate all required dialog fields.
- Verification: Default text used unlabeled lines (`Summary\nCommand\nExit code...`) that parser ignored.
- Decision: accept-impl
- Reasoning: Failure-path dialog could open with mostly empty fields.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): Required (code review)
- Implementation / spec update / tracking: Implemented in working tree (uncommitted): `aws_sso_autologin/tray.py`, `tests/test_tray.py`.

### Response D15
- Claim (restated): Global-error summary content must be semantic diagnosis, not first-row action label.
- Verification: `set_global_error(summary="Show startup/sync error", ...)` was used in startup failure paths.
- Decision: accept-impl
- Reasoning: Action label and diagnostics summary serve different UX purposes.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): Required (code review)
- Implementation / spec update / tracking: Implemented in working tree (uncommitted): `aws_sso_autologin/__main__.py`.

### Response D16
- Claim (restated): Accessibility evidence must include concrete keyboard/read-order transcript detail.
- Verification: Prior artifact listed test pass counts but lacked explicit transcript-like evidence.
- Decision: accept-impl
- Reasoning: Iron-law-5 requires concrete evidence, not just high-level claims.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): N/A
- Implementation / spec update / tracking: Updated `docs/leyline/plans/2026-05-09-aws-sso-autologin-a11y-evidence.md` with keyboard-walk and narration-proxy transcript commands/results.

### Response D17
- Claim (restated): Dialog should explicitly focus close action for predictable keyboard behavior.
- Verification: Close button existed but focus behavior was not explicitly set or tested.
- Decision: accept-impl
- Reasoning: Keyboard entry point should be deterministic.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): N/A
- Implementation / spec update / tracking: Implemented in working tree (uncommitted): `aws_sso_autologin/tray.py`, `tests/test_tray.py`.

### Response D18
- Claim (restated): Error fallback copy should use operationally meaningful wording.
- Verification: Fallback label used `Unknown error`.
- Decision: accept-impl
- Reasoning: Operational copy should stay actionable and consistent.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): N/A
- Implementation / spec update / tracking: Implemented in working tree (uncommitted): `aws_sso_autologin/tray.py`.

## Systematic-debugging record - round 2

### Record 1 - Login execution contract
- Root cause (one sentence, plain English): Login operator used a legacy CLI path with 300s timeout and no secure-wrapper lifecycle.
- Falsifying test: `python` contract script on pre-round2 worktree asserted timeout `180` and failed with `expected timeout 180, got 300`.
- Hypothesis: If `CLIExecutor.execute_login` delegates to `run_sso_login(... timeout=180)`, operator runtime path will inherit wrapper + timeout contract.
- Fix: Delegated `CLIExecutor.execute_login` to `run_sso_login` and introduced `SSO_LOGIN_TIMEOUT_SECONDS = 180`.
- Regression coverage: `pytest tests/test_cli.py -q`.

### Record 2 - Runtime tray-host heartbeat integration
- Root cause (one sentence, plain English): Tray-host ping logic existed only in `service.py` and was never invoked by the running app.
- Falsifying test: `python` contract script on pre-round2 worktree failed `missing runtime tray-host heartbeat hook`.
- Hypothesis: Adding tray-host monitor creation + 30s timer + loss handler in `AutologinApp` will enforce runtime heartbeat behavior.
- Fix: Added `_create_tray_host_monitor`, `_on_tray_host_heartbeat`, timer start/stop wiring, and pause/continue behavior gates.
- Regression coverage: `pytest tests/test_main.py -q`.

### Record 3 - Empty-profile startup behavior
- Root cause (one sentence, plain English): Startup path treated `no profiles` as fatal even though UX flow expects empty-state continuation.
- Falsifying test: `python` contract script on pre-round2 worktree failed `expected continue-in-empty-state (0), got 1`.
- Hypothesis: Converting no-profile path to global error + continued run loop will satisfy UX flow without startup exit.
- Fix: `run()` now keeps app alive in empty-state mode and sets summary `No SSO profiles detected`.
- Regression coverage: `pytest tests/test_main.py::test_run_continues_when_profiles_do_not_load -q`.

### Record 4 - Icon-state rendering and diagnostics population
- Root cause (one sentence, plain English): Tray state machine updated string state only; icon rendering and default diagnostics field population were incomplete.
- Falsifying test: pre-round2 icon contract script failed `expected distinct icon states, got enabled=0, paused=0`.
- Hypothesis: Rendering state-specific icon assets and using default `key: value` diagnostics payload will satisfy state-matrix/icon/dialog contracts.
- Fix: Added state-icon rendering map, close-focus behavior, and structured fallback diagnostics text.
- Regression coverage: `pytest tests/test_tray.py -q`.

## Failing-test output (round 2)

### Pre-fix contract failure snapshots (from temp worktree at `63f9cd9`)

1. Login timeout contract:

```
AssertionError: expected timeout 180, got 300
```

2. Empty-state startup contract:

```
AssertionError: expected continue-in-empty-state (0), got 1
```

3. Icon-state rendering contract:

```
AssertionError: expected distinct icon states, got enabled=0, paused=0
```

4. Runtime heartbeat hook contract:

```
AssertionError: missing runtime tray-host heartbeat hook
```

## Post-implementation verification output (round 2)

- Contract checks on current worktree:

```
login_timeout_contract: pass
empty_state_startup_contract: pass
icon_state_rendering_contract: pass
runtime_heartbeat_hook_contract: pass
```

- Accessibility-focused tray interaction checks:

```
9 passed, 13 deselected in 0.18s
```

- Full verification:

```
125 passed in 2.25s
```

## Task-granular remediation evidence (round 2 addendum)

### Failing-test output - task 9

```
AssertionError: expected timeout 180, got 300
```

### Systematic-debugging record - task 9
- Root cause (one sentence, plain English): Task 9 runtime path still executed login via legacy CLI wrapper without canonical timeout/wrapper contract.
- Falsifying test: pre-fix contract script asserted login timeout policy and failed (`expected timeout 180, got 300`).
- Hypothesis: Delegating `CLIExecutor.execute_login` to `run_sso_login(... timeout=180)` will align runtime login path with Task 9 security/timeout contract.
- Fix: Updated `aws_sso_autologin/cli.py` to call `run_sso_login`; introduced `SSO_LOGIN_TIMEOUT_SECONDS = 180` in constants.
- Regression coverage: `pytest tests/test_cli.py -q` (all pass).

### Post-implementation verification output - task 9

```
login_timeout_contract: pass
```

### Failing-test output - task 10

```
AssertionError: missing runtime tray-host heartbeat hook
AssertionError: expected continue-in-empty-state (0), got 1
```

### Systematic-debugging record - task 10
- Root cause (one sentence, plain English): Task 10 app lifecycle never instantiated tray-host heartbeat checks and still treated empty-profile startup as fatal.
- Falsifying test: pre-fix contract scripts failed for missing heartbeat hook and empty-state continuation behavior.
- Hypothesis: Wiring tray-host monitor/timer into `AutologinApp` and converting no-profile startup to global-error continuation will satisfy Task 10 runtime contracts.
- Fix: Added tray-host monitor methods, timer start/stop lifecycle, source-aware global-error handling, and empty-state continuation in `aws_sso_autologin/__main__.py`.
- Regression coverage: `pytest tests/test_main.py -q` (all pass).

### Post-implementation verification output - task 10

```
runtime_heartbeat_hook_contract: pass
empty_state_startup_contract: pass
```

### Failing-test output - task 5

```
AssertionError: expected distinct icon states, got enabled=0, paused=0
```

### Systematic-debugging record - task 5
- Root cause (one sentence, plain English): Task 5 state machine tracked icon semantics internally but always rendered a blank icon and could emit unstructured default diagnostics fields.
- Falsifying test: pre-fix contract script failed icon differentiation check (`enabled=0, paused=0`).
- Hypothesis: Rendering concrete per-state icons and structured fallback diagnostics payload will make Task 5 surfaces conform to icon/dialog contracts.
- Fix: Added state-icon rendering map, structured fallback diagnostics `key: value` lines, and explicit close-focus behavior in `aws_sso_autologin/tray.py`.
- Regression coverage: `pytest tests/test_tray.py -q` (all pass).

### Post-implementation verification output - task 5

```
icon_state_rendering_contract: pass
9 passed, 13 deselected in 0.18s
```

### Failing-test output - task 1

```
Exception: project-setup task - no failing test (per plan exception).
```

### Post-implementation verification output - task 1

```
Import OK
```

### Failing-test output - task 2

```
ModuleNotFoundError: No module named 'aws_sso_autologin.constants'
ModuleNotFoundError: No module named 'aws_sso_autologin.errors'
4 failed in 0.02s
```

### Post-implementation verification output - task 2

```
9 passed in 0.01s
```

### Failing-test output - task 3

```
ModuleNotFoundError: No module named 'aws_sso_autologin.logger'
1 error during collection
```

### Post-implementation verification output - task 3

```
4 passed in 0.01s
```

### Failing-test output - task 4

```
ModuleNotFoundError: No module named 'aws_sso_autologin.tray'
```

### Post-implementation verification output - task 4

```
8 passed in 0.16s
```

### Failing-test output - task 6

```
ModuleNotFoundError: No module named 'aws_sso_autologin.classifier'
```

### Post-implementation verification output - task 6

```
1 passed in 0.01s
```

### Failing-test output - task 7

```
ModuleNotFoundError: No module named 'aws_sso_autologin.operator'
```

### Post-implementation verification output - task 7

```
30 passed in 0.03s
```

### Failing-test output - task 8

```
ModuleNotFoundError: No module named 'aws_sso_autologin.service'
```

### Post-implementation verification output - task 8

```
16 passed in 0.03s
```

### Failing-test output - task 11

```
Exception: doc-only task - no failing test (per plan exception).
```

### Post-implementation verification output - task 11

```
README created and validated against plan sections.
```

## Branch-level code review (round 3)

### Findings
- F20 (Critical): `SessionChecker` used direct timeout handling without terminate->grace->kill escalation (`aws_sso_autologin/checker.py`).
- F21 (Important): Logger formatter was plain text instead of structured stdout logging (`aws_sso_autologin/logger.py`).

### Response F20
- Claim (restated): `sts_check` execution path in checker must use deterministic timeout escalation consistent with command contract.
- Verification: `checker.py` used `subprocess.run(... timeout=10)` directly, bypassing escalation helper used in `aws.py`.
- Decision: accept
- Reasoning: Timeout policy applies to all AWS command paths, including checker command execution.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): N/A
- Implementation: Implemented in working tree (uncommitted): `aws_sso_autologin/checker.py`, `tests/test_checker.py` (indirect coverage), `tests/test_aws.py` (escalation coverage).

### Systematic-debugging record - task 7
- Root cause (one sentence, plain English): Session checker kept an isolated subprocess timeout implementation that did not follow shared escalation policy.
- Falsifying test: branch-level code review finding F20 on range `5fd6c44..9d9859d` flagged direct `subprocess.run(... timeout=...)` path in checker.
- Hypothesis: Replacing checker command calls with shared `_run_subprocess_with_escalation` will align timeout behavior across `sts_check` paths.
- Fix: Updated checker command calls to use `_run_subprocess_with_escalation` and classify timeout/check errors from unified error surface.
- Regression coverage: `pytest tests/test_checker.py tests/test_aws.py -q`.

### Response F21
- Claim (restated): Logs should be structured stdout records for predictable operations telemetry ingestion.
- Verification: `logger.py` used plain formatter string `'%(asctime)s - %(name)s - %(levelname)s - %(message)s'`.
- Decision: accept
- Reasoning: Product spec identifies structured stdout logs as primary observability surface.
- Re-dispatch or escalation (push-back on Critical only): N/A
- Sibling review re-dispatch (if fix crossed concerns): N/A
- Implementation: Implemented in working tree (uncommitted): `aws_sso_autologin/logger.py`, `tests/test_logger.py`.

### Post-implementation verification output - task 7

```
pytest tests/test_checker.py tests/test_aws.py tests/test_logger.py -q
all tests passed
```

## Branch-level review resolution (round 4)

- Code review range: `5fd6c44..69a3578`
- Design review range: `5fd6c44..69a3578`
- Result: no unresolved Critical/Important findings remain in either review stream.

## Systematic-debugging record - CLI --help behavior

### Record - --help flag starts application
- Root cause (one sentence, plain English): When using `standalone_mode=False`, typer doesn't exit after showing `--help`, causing the application to start.
- Falsifying test: `pytest tests/test_main.py::test_main_help_exits_without_starting_app -v` failed with `AutologinApp` being instantiated after help display.
- Hypothesis: If we check for `--help` in raw_args before invoking application logic and return 0 after showing help, the application will not start.
- Fix: Added early check for `--help` in `main()` before application startup; typer shows help and returns 0 immediately.
- Regression coverage: `pytest tests/test_main.py -q` (all pass).

### Post-implementation verification output

```
$ timeout 2 .venv/bin/python -m aws_sso_autologin --help 2>&1; echo "Exit code: $?"

 Usage: python -m aws_sso_autologin [OPTIONS] COMMAND [ARGS]...

 AWS SSO tray autologin

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --version             -V            Show app version and exit                │
│ --log-level                   TEXT  Log level                                │
│ --log-format                  TEXT  Log format                               │
│ --safe-mode                         Start paused                             │
│ --tray-loss-behavior          TEXT  Tray-loss behavior                       │
│ --check-only                        Run preflight only                       │
│ --profiles                    TEXT  Comma-separated profiles                 │
│ --help                              Show this message and exit.              │
╰──────────────────────────────────────────────────────────────────────────────╯

Exit code: 0
```

- Full test suite: `pytest` - 197 passed

Code review complete - round 4 - 2026-05-09
Design review complete - round 3 - 2026-05-09

## Systematic-debugging record - diagnostics dialog not shown

### Record - Error dialog not displayed when clicking error menu item
- Root cause (one sentence, plain English): `AutologinApp._on_show_diagnostics` callback was registered with `StatusTray` but only logged errors without displaying the `ErrorDetailsDialog`.
- Falsifying test: `pytest tests/test_main.py::test_on_show_diagnostics_displays_error_dialog -v` failed because `ErrorDetailsDialog` was neither imported nor instantiated in `__main__.py`.
- Hypothesis: If `_on_show_diagnostics` imports and shows `ErrorDetailsDialog`, clicking the error menu item will display the diagnostic window as expected.
- Fix: Added `ErrorDetailsDialog` import and dialog instantiation/show in `_on_show_diagnostics` method.
- Regression coverage: `pytest tests/test_main.py::test_on_show_diagnostics_displays_error_dialog -v` (pass), `make test` (199 passed).

### Record 2 - Dialog destroyed by GC / not shown properly
- Root cause (one sentence, plain English): `ErrorDetailsDialog` was created as a local variable in `_on_show_diagnostics`, causing it to be garbage-collected immediately; also `show()` doesn't block for modal dialog.
- Falsifying test: User reported dialog still not appearing after first fix; no errors in logs.
- Hypothesis: If dialog reference is stored in `self._details_dialog` and `exec()` is used instead of `show()`, dialog will remain alive and display modally.
- Fix: Added `self._details_dialog` attribute to store dialog reference; changed `show()` to `exec()`; added cleanup in `shutdown()`; added exception handling and logging.
- Regression coverage: `pytest tests/test_main.py::test_on_show_diagnostics_displays_error_dialog -v` (pass), `make test` (199 passed).

### Post-implementation verification output

```
$ pytest tests/test_main.py::test_on_show_diagnostics_displays_error_dialog -v
============================= test session starts ==============================
platform linux -- Python 3.14.4, pytest-9.0.3, pluggy-1.6.0
collected 1 item

tests/test_main.py::test_on_show_diagnostics_displays_error_dialog PASSED [100%]

============================== 1 passed in 0.11s ===============================

$ make test
============================= test session starts ==============================
platform linux -- Python 3.14.4, pytest-9.0.3, pluggy-1.6.0
collected 199 items

tests/test_aws.py ...................                                   [  9%]
tests/test_checker.py ....                                               [ 11%]
tests/test_classifier.py .                                               [ 12%]
tests/test_cli.py ..                                                     [ 13%]
tests/test_cli_integration.py ......                                     [ 16%]
tests/test_constants.py .........                                        [ 20%]
tests/test_daemon_marker.py ....                                         [ 22%]
tests/test_integration_policy.py .......                                 [ 26%]
tests/test_logger.py ........                                            [ 30%]
tests/test_main.py ....................................                   [ 47%]
tests/test_mode_policy.py ........                                       [ 51%]
tests/test_operator.py ................................                  [ 67%]
tests/test_service.py ......................                             [ 78%]
tests/test_settings.py ...                                               [ 80%]
tests/test_tray.py .......................                               [ 91%]
tests/test_version.py ..                                                 [ 92%]
tests/test_versioning.py ....                                            [ 94%]
tests/test_watchdog.py ..........                                        [100%]

============================= 199 passed in 4.30s ===============================
```

## User-reported issue fix - 2026-05-10

### Issue
When no SSO profiles were detected, the error dialog showed confusing messages:
- "Unknown execution state"
- "Incident evidence unavailable: retention window exceeded"
- "Command: unknown"
- "Exit code: unknown"

These messages were inappropriate for a configuration state (no profiles configured) rather than a command execution failure.

### Root Cause
The `ErrorDetailsDialog.from_text()` method always defaulted to command-execution error display, showing "Unknown execution state" when `command_executed` was `None`, and always including "Incident evidence" field.

### Fix
1. Added `is_config_error` parameter to `ErrorDetailsDialog.from_text()` to distinguish configuration errors from command execution errors
2. For configuration errors:
   - Shows summary as the header title instead of "Unknown execution state"
   - Displays only Summary and Context sections (no Command, Exit code, Incident evidence)
   - Provides clear, actionable messaging
3. Updated `StatusTray.set_global_error()` and `_emit_diagnostics()` to support `is_config_error` flag
4. Updated `AutologinApp._set_tray_global_error()` in `__main__.py` to pass `is_config_error=True` for "No SSO profiles detected" error
5. Improved error message to: "No SSO profiles found in AWS config. Add a profile with sso_start_url to enable auto-login."

### Files Changed
- `aws_sso_autologin/tray.py`: Added `is_config_error` support to `ErrorDetailsDialog` and `StatusTray`
- `aws_sso_autologin/__main__.py`: Updated error handling for no profiles scenario
- `docs/leyline/design/2026-05-09-aws-sso-autologin-ux.md`: Updated state matrix to document configuration error display
- `tests/test_tray.py`: Added tests for configuration error dialog behavior

### Verification
- All 223 tests pass
- New tests verify: no "Unknown execution state" header, no incident evidence, no command/exit code fields for config errors
- UX spec updated and approved (round 12)

## Systematic-debugging record - subprocess timeout stdout/stderr logging

### Record - Timeout subprocess output not logged
- Root cause (one sentence, plain English): When `aws sso login` times out, the stdout/stderr captured from the terminating process is available but never logged, making it impossible to diagnose why the command failed.
- Falsifying test: `pytest tests/test_aws.py::test_timeout_logs_stdout_stderr_on_terminate tests/test_aws.py::test_timeout_force_kill_logs_stdout_stderr -v` failed with `AssertionError: assert 'stdout_preview' in {'command': [...], 'event': 'subprocess_failed', 'reason': 'timeout_terminated', 'status': 'failed'}` - stdout_preview/stderr_preview keys missing from log extra fields.
- Hypothesis: If we include captured stdout/stderr (with sanitization) in the error log messages during timeout handling, users will see what the AWS command produced before termination.
- Fix: Modified `_run_subprocess_with_escalation` in `aws_sso_autologin/aws.py` to:
  1. Capture stdout/stderr from `process.communicate()` in both terminate and force-kill branches
  2. Apply `sanitize_trace_payload()` for security (redaction of secrets, truncation)
  3. Include `stdout_preview`, `stderr_preview` (first 200 chars), and payload metadata fields in error log extra dict
- Regression coverage: `pytest tests/test_aws.py -q` (24 passed), `make test` (241 passed).

### Post-implementation verification output

```
$ pytest tests/test_aws.py::test_timeout_logs_stdout_stderr_on_terminate tests/test_aws.py::test_timeout_force_kill_logs_stdout_stderr -v
============================= test session starts ==============================
platform linux -- Python 3.14.4, pytest-9.0.3, pluggy-1.6.0 -- /w/projects/aws-sso-autologin/.venv/bin/python
PySide6 6.11.0 -- Qt runtime 6.11.0 -- Qt compiled 6.11.0
rootdir: /w/projects/aws-sso-autologin
collecting ... collected 2 items

tests/test_aws.py::test_timeout_logs_stdout_stderr_on_terminate PASSED   [ 50%]
tests/test_aws.py::test_timeout_force_kill_logs_stdout_stderr PASSED     [100%]

============================== 2 passed in 0.02s ===============================

$ make test
241 passed in 4.52s
```
