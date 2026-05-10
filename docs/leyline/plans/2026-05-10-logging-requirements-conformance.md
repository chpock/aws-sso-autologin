# Logging Requirements Conformance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `leyline:subagent-driven-development` (recommended) or `leyline:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring all runtime logging in `aws_sso_autologin` into conformance with AGENTS.md logging requirements, including complete structured coverage and trace-level external interaction details.

**Architecture:** Add a consistent structured-event contract across runtime modules, then close logging coverage gaps by subsystem. External interactions are instrumented with lifecycle events (`*_started`, `*_completed`, `*_failed`) and trace payload detail with redaction/truncation safety. Tests assert stable `event` and key context fields.

**Tech Stack:** Python, pytest, stdlib logging, PySide6

**Spec references:**
- Product spec: `docs/leyline/specs/2026-05-10-logging-requirements-conformance-design.md` (Product spec round 1)
- UX spec: `docs/leyline/design/2026-05-10-logging-requirements-conformance-ux.md` (UX spec round 1)
- Baseline: `docs/leyline/plans/2026-05-10-logging-requirements-conformance-baseline.md`

**Surfaces:** developer-facing

**Files:**
- Modify: `aws_sso_autologin/__main__.py` - normalize startup/mode/exit structured logs and failure contexts.
- Modify: `aws_sso_autologin/service.py` - ensure tray-host checks and preflight paths emit complete structured events.
- Modify: `aws_sso_autologin/checker.py` - instrument external command interactions with trace payloads and lifecycle events.
- Modify: `aws_sso_autologin/aws.py` - instrument AWS interaction paths and failure detail.
- Modify: `aws_sso_autologin/operator.py` - log operator lifecycle actions and recoverable vs fatal outcomes.
- Modify: `aws_sso_autologin/tray.py` - normalize diagnostics/interaction logging events and required fields.
- Modify: `aws_sso_autologin/watchdog.py` - ensure watchdog and timeout/policy events use required schema.
- Modify: `aws_sso_autologin/mode_policy.py` - emit policy decision logs with reason + exit semantics.
- Test: `tests/test_main.py`
- Test: `tests/test_service.py`
- Test: `tests/test_checker.py`
- Test: `tests/test_aws.py`
- Test: `tests/test_operator.py`
- Test: `tests/test_tray.py`
- Test: `tests/test_watchdog.py`
- Test: `tests/test_mode_policy.py`

---

### Task 1: Baseline Logging Contract Tests

**Files:**
- Modify: `tests/test_main.py`
- Modify: `tests/test_service.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_startup_events_are_structured(caplog):
    events = [r.__dict__.get("event") for r in caplog.records if r.__dict__.get("event")]
    assert "startup_preflight_started" in events
    assert "startup_preflight_completed" in events


def test_tray_host_failure_has_reason_field(caplog):
    failed = [r for r in caplog.records if r.__dict__.get("event") == "tray_host_probe_completed"]
    assert failed
    assert all("reason" in r.__dict__ for r in failed if r.__dict__.get("status") == "failed")
```

- [ ] **Step 2: Run the tests, confirm failure**

```bash
.venv/bin/pytest tests/test_main.py::test_startup_events_are_structured tests/test_service.py::test_tray_host_failure_has_reason_field -q
# Expected: failing assertions for missing/unnormalized event keys
```

- [ ] **Step 3: Implement minimal production code**

```python
# In startup/preflight call sites, use structured extra fields:
logger.info("startup preflight started", extra={"event": "startup_preflight_started", "mode": mode})
logger.info("startup preflight completed", extra={"event": "startup_preflight_completed", "status": status})
logger.warning("tray host probe failed", extra={"event": "tray_host_probe_completed", "status": "failed", "reason": reason})
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
.venv/bin/pytest tests/test_main.py::test_startup_events_are_structured tests/test_service.py::test_tray_host_failure_has_reason_field -q
# Expected: 2 passed
```

- [ ] **Step 5: Commit**

```bash
git add aws_sso_autologin/__main__.py aws_sso_autologin/service.py tests/test_main.py tests/test_service.py && git commit -m "test(logging): enforce structured startup and preflight events"
```

### Task 2: External Interaction Trace Coverage

**Files:**
- Modify: `tests/test_checker.py`
- Modify: `tests/test_aws.py`
- Modify: `aws_sso_autologin/checker.py`
- Modify: `aws_sso_autologin/aws.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_checker_logs_command_lifecycle_and_trace(caplog):
    lifecycle = [r.__dict__.get("event") for r in caplog.records]
    assert "aws_command_started" in lifecycle
    assert "aws_command_completed" in lifecycle or "aws_command_failed" in lifecycle
    traces = [r for r in caplog.records if r.levelname.lower() == "trace"]
    assert any("payload_truncated" in t.__dict__ or "detail_unavailable_reason" in t.__dict__ for t in traces)
```

- [ ] **Step 2: Run the tests, confirm failure**

```bash
.venv/bin/pytest tests/test_checker.py::test_checker_logs_command_lifecycle_and_trace tests/test_aws.py -q
# Expected: failing due to missing trace-detail fields and/or lifecycle events
```

- [ ] **Step 3: Implement minimal production code**

```python
logger.debug("aws command started", extra={"event": "aws_command_started", "command": cmd})
logger.log(5, "aws command trace detail", extra={"event": "aws_command_trace", "stdout": safe_stdout, "stderr": safe_stderr, "payload_truncated": truncated})
logger.info("aws command completed", extra={"event": "aws_command_completed", "status": "succeeded", "exit_code": code, "duration_ms": duration_ms})
logger.error("aws command failed", extra={"event": "aws_command_failed", "status": "failed", "exit_code": code, "reason": reason, "error": err})
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
.venv/bin/pytest tests/test_checker.py tests/test_aws.py -q
# Expected: all selected tests pass
```

- [ ] **Step 5: Commit**

```bash
git add aws_sso_autologin/checker.py aws_sso_autologin/aws.py tests/test_checker.py tests/test_aws.py && git commit -m "fix(logging): add lifecycle and trace logs for external commands"
```

### Task 3: Runtime Subsystem Coverage Normalization

**Files:**
- Modify: `aws_sso_autologin/operator.py`
- Modify: `aws_sso_autologin/tray.py`
- Modify: `aws_sso_autologin/watchdog.py`
- Modify: `aws_sso_autologin/mode_policy.py`
- Modify: `tests/test_operator.py`
- Modify: `tests/test_tray.py`
- Modify: `tests/test_watchdog.py`
- Modify: `tests/test_mode_policy.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_operator_events_include_status_and_reason(caplog):
    assert any(r.__dict__.get("event") == "operator_action_completed" for r in caplog.records)
    assert all("status" in r.__dict__ for r in caplog.records if r.__dict__.get("event") == "operator_action_completed")


def test_watchdog_timeout_event_has_exit_context(caplog):
    timeout = [r for r in caplog.records if r.__dict__.get("event") == "watchdog_timeout"]
    assert timeout and all("exit_code" in r.__dict__ for r in timeout)
```

- [ ] **Step 2: Run the tests, confirm failure**

```bash
.venv/bin/pytest tests/test_operator.py tests/test_tray.py tests/test_watchdog.py tests/test_mode_policy.py -q
# Expected: failures for missing required fields/event names
```

- [ ] **Step 3: Implement minimal production code**

```python
logger.info("operator action completed", extra={"event": "operator_action_completed", "status": status, "reason": reason})
logger.warning("policy violation", extra={"event": "policy_violation", "mode": mode, "reason": reason, "exit_code": exit_code})
logger.error("watchdog timeout", extra={"event": "watchdog_timeout", "status": "failed", "timeout_s": timeout_s, "exit_code": 124})
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
.venv/bin/pytest tests/test_operator.py tests/test_tray.py tests/test_watchdog.py tests/test_mode_policy.py -q
# Expected: selected tests pass
```

- [ ] **Step 5: Commit**

```bash
git add aws_sso_autologin/operator.py aws_sso_autologin/tray.py aws_sso_autologin/watchdog.py aws_sso_autologin/mode_policy.py tests/test_operator.py tests/test_tray.py tests/test_watchdog.py tests/test_mode_policy.py && git commit -m "fix(logging): normalize runtime subsystem event contracts"
```

### Task 4: Conformance Verification Sweep

**Files:**
- Modify: `docs/leyline/plans/2026-05-10-logging-requirements-conformance-review-log.md`

- [ ] **Step 1: Exception declaration**

```text
Exception: doc-only task - no failing test. Verification: run targeted logging tests plus full make test and capture make run event logs.
```

- [ ] **Step 2: Run verification commands**

```bash
.venv/bin/pytest tests/test_main.py tests/test_service.py tests/test_checker.py tests/test_aws.py tests/test_operator.py tests/test_tray.py tests/test_watchdog.py tests/test_mode_policy.py -q
make test
make run
```

- [ ] **Step 3: Record outcomes in review log**

```markdown
- logging conformance verification completed
- targeted tests: passed
- full test suite: passed
- make run: captured required `event=` startup/preflight contract logs
```

- [ ] **Step 4: Commit**

```bash
git add docs/leyline/plans/2026-05-10-logging-requirements-conformance-review-log.md && git commit -m "docs(logging): record conformance verification evidence"
```
