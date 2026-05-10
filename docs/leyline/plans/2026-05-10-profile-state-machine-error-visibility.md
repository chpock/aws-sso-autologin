# Profile State Machine Error Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `leyline:subagent-driven-development` (recommended) or `leyline:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement explicit per-profile state-machine transitions with sticky error visibility and deterministic app/tray behavior.

**Architecture:** Add a single transition layer for profile state and confirmation substate, route runtime updates through it, and update tray rendering/aggregation to reflect deterministic rules. Back changes with focused unit tests, then full-suite verification.

**Tech Stack:** Python 3, PySide6, pytest, ruff

**Spec references:**
- Product spec: `docs/leyline/specs/2026-05-10-profile-state-machine-error-visibility-design.md` (Product spec round 10)
- UX spec: `docs/leyline/design/2026-05-10-profile-state-machine-error-visibility-ux.md` (UX spec round 10)
- Baseline: `/w/projects/aws-sso-autologin/docs/leyline/plans/2026-05-10-profile-state-machine-error-visibility-baseline.md`

**Surfaces:** multi-screen-ui

**Files:**
- Modify: `aws_sso_autologin/tray.py` (profile state model + app-state aggregation/view mapping)
- Modify: `aws_sso_autologin/__main__.py` (event mapping, transition application, paused precedence)
- Modify: `tests/test_tray.py` (surface/state presentation assertions)
- Modify: `tests/test_main.py` (runtime transition and aggregation assertions)
- Modify: `tests/test_service.py` (session classification contract coverage)

---

### Task 1: Add transition helper in tray model

**Files:**
- Modify: `aws_sso_autologin/tray.py`
- Test: `tests/test_tray.py`

- [ ] **Step 1: Write the failing test**

```python
def test_apply_event_ok_sync_succeeded_is_noop():
    status = ProfileStatus(profile_name="dev", state=ProfileState.OK)
    updated = status.apply_event("sync_succeeded")
    assert updated.state is ProfileState.OK
    assert updated.confirmation_pending is False
```

- [ ] **Step 2: Run the test, confirm failure**

```bash
.venv/bin/pytest tests/test_tray.py::test_apply_event_ok_sync_succeeded_is_noop -q
# Expected: failing test because apply_event is missing/incomplete.
```

- [ ] **Step 3: Implement minimal code**

```python
def apply_event(self, event: str) -> "ProfileStatus":
    if self.state is ProfileState.ERROR:
        if event == "session_check_success_active":
            return self._replace(state=ProfileState.OK, confirmation_pending=False)
        return self

    if event == "sync_succeeded":
        if self.state in (ProfileState.SYNCING, ProfileState.WARNING):
            return self._replace(confirmation_pending=True)
        return self

    # keep existing event mapping rules
    return self._apply_existing_event(event)
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
.venv/bin/pytest tests/test_tray.py::test_apply_event_ok_sync_succeeded_is_noop -q
# Expected: 1 passed.
```

- [ ] **Step 5: Commit**

```bash
git add aws_sso_autologin/tray.py tests/test_tray.py && git commit -m "fix(tray): enforce sync_succeeded noop for ok state"
```

### Task 1: Tray/menu state UX - UX Task

**Surface:** Profile menu row
**Artifact reference:** `docs/leyline/design/2026-05-10-profile-state-machine-error-visibility-ux.md#state-copy-contract`

- [ ] **Step 1:** Confirm artifact section is current.
- [ ] **Step 2:** Implement copy contract and modifier precedence in row rendering.
- [ ] **Step 3:** Trigger each state from the state matrix and observe.
  - Empty: N/A - tray always renders control and profile rows.
  - Loading: show `Profile: <name> - Syncing...`.
  - Error: show `Profile: <name> - Error: <reason>`.
  - Success: show `Profile: <name> - OK ...`.
  - Permission-denied: deterministic error row semantics.
  - Offline: warning text unless sticky-error already active.
- [ ] **Step 4:** Run accessibility verification (keyboard row activation and SR label readout).
- [ ] **Step 5:** Reconcile against UX artifact; update code or artifact explicitly if divergence appears.
- [ ] **Step 6:** Commit.

### Task 2: Route runtime status updates through deterministic events

**Files:**
- Modify: `aws_sso_autologin/__main__.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing test**

```python
def test_paused_status_overrides_error_icon():
    app = AutologinApp(...)
    app._monitoring_enabled = False
    app._profile_status["dev"] = ProfileStatus("dev", state=ProfileState.ERROR)
    app._on_status_change()
    assert app._tray.last_app_state == "paused"
```

- [ ] **Step 2: Run the test, confirm failure**

```bash
.venv/bin/pytest tests/test_main.py::test_paused_status_overrides_error_icon -q
# Expected: failure before paused precedence fix is applied.
```

- [ ] **Step 3: Implement minimal code**

```python
def _aggregate_app_state(self) -> str:
    if not self._monitoring_enabled:
        return "paused"
    if any(p.state is ProfileState.ERROR for p in self._profile_status.values()):
        return "error"
    return "working"
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
.venv/bin/pytest tests/test_main.py::test_paused_status_overrides_error_icon -q
# Expected: 1 passed.
```

- [ ] **Step 5: Commit**

```bash
git add aws_sso_autologin/__main__.py tests/test_main.py && git commit -m "fix(main): enforce paused precedence in aggregation"
```

### Task 2: Tray icon and dialog UX - UX Task

**Surface:** System tray icon + Error details dialog
**Artifact reference:** `docs/leyline/design/2026-05-10-profile-state-machine-error-visibility-ux.md#flow-4---paused-precedence`

- [ ] **Step 1:** Confirm paused-precedence + diagnostics-open failure path is current.
- [ ] **Step 2:** Ensure paused icon rendering and dialog-open recovery copy are wired.
- [ ] **Step 3:** Trigger each state from the state matrix and observe.
  - Empty: `Profiles OK: 0/0` tooltip.
  - Loading: `working/syncing` icon.
  - Error: `error` icon when monitoring active.
  - Success: `working/ok` icon.
  - Permission-denied: error icon semantics when active.
  - Offline: warning/error based on decision table mapping.
- [ ] **Step 4:** Run accessibility verification for dialog focus return after failure path.
- [ ] **Step 5:** Reconcile against artifact; no silent drift.
- [ ] **Step 6:** Commit.

### Task 3: Align failure classification and sticky-error transitions

**Files:**
- Modify: `aws_sso_autologin/__main__.py`
- Modify: `tests/test_service.py`
- Modify: `tests/test_main.py`

- [ ] **Step 1: Write the failing test**

```python
def test_indeterminate_failure_does_not_clear_error_state():
    status = ProfileStatus("dev", state=ProfileState.ERROR)
    updated = status.apply_event("session_check_failed_indeterminate")
    assert updated.state is ProfileState.ERROR
```

- [ ] **Step 2: Run the test, confirm failure**

```bash
.venv/bin/pytest tests/test_main.py::test_indeterminate_failure_does_not_clear_error_state -q
# Expected: failing assertion before sticky rule enforcement.
```

- [ ] **Step 3: Implement minimal code**

```python
if current.state is ProfileState.ERROR and event == "session_check_failed_indeterminate":
    self._log_ignored_event(profile, event, reason="sticky_error")
    return current
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
.venv/bin/pytest tests/test_main.py::test_indeterminate_failure_does_not_clear_error_state -q
# Expected: 1 passed.
```

- [ ] **Step 5: Commit**

```bash
git add aws_sso_autologin/__main__.py tests/test_main.py tests/test_service.py && git commit -m "fix(service): preserve sticky error on indeterminate checks"
```

### Task 4: Full verification and integration handoff

**Files:**
- Modify: `docs/leyline/plans/2026-05-10-profile-state-machine-error-visibility-baseline.md`

Exception: formatting task - no failing test. Verification: run full suite and record output.

- [ ] **Step 1:** Run full verification.

```bash
make test
```

- [ ] **Step 2:** Run agent-safe runtime preflight for tray-host contract evidence.

```bash
make run-agent
```

- [ ] **Step 3:** Record verification notes (including `event=` diagnostics) in baseline note.

- [ ] **Step 4:** Commit plan-execution prep updates.

```bash
git add docs/leyline/plans/2026-05-10-profile-state-machine-error-visibility-baseline.md && git commit -m "docs(plans): record verification evidence for profile-state rollout"
```
