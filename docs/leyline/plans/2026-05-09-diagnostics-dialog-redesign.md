# Diagnostics Dialog Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `leyline:subagent-driven-development` (recommended) or `leyline:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the diagnostics dialog into a fixed-size floating surface with status header, deterministic smart fields, copy workflow feedback, and non-terminating close behavior.

**Architecture:** Keep `ErrorDetailsDialog` as the single UI entry point from tray actions, but split rendering into deterministic normalization + presentation helpers so malformed payload behavior is testable. Use a stateful copy-helper flow in the dialog (none/fail/escalated/success->clear) and keep app-level quit policy in `AutologinApp` so closing the dialog never exits the process.

**Tech Stack:** Python 3.14 (current repo runtime), PySide6/Qt6 widgets, pytest + pytest-qt.

**Spec references:**
- Product spec: `docs/leyline/specs/2026-05-09-diagnostics-dialog-redesign-design.md` (Product spec round 6 + deep-discovery round 7 marker)
- UX spec: `docs/leyline/design/2026-05-09-diagnostics-dialog-redesign-ux.md` (UX spec round 11 + design-interrogation round 1 marker)
- Baseline: `docs/leyline/plans/2026-05-09-diagnostics-dialog-redesign-baseline.md`

**Surfaces:** single-screen-ui

**Files:**
- Modify: `aws_sso_autologin/tray.py` (diagnostics dialog model, rendering, copy state machine, keyboard/accessibility hooks)
- Modify: `aws_sso_autologin/__main__.py` (Qt app quit policy guard)
- Test: `tests/test_tray.py` (dialog policy matrix, rendering, copy helper, accessibility contract)
- Test: `tests/test_main.py` (quit-on-last-window-closed guard)

---

### Task 1: Implement deterministic diagnostics field policy normalization

**Files:**
- Modify: `aws_sso_autologin/tray.py` (near `class ErrorDetailsDialog`)
- Test: `tests/test_tray.py`

- [ ] **Step 1: Write the failing test**

```python
def test_error_details_dialog_normalizes_command_executed_true_missing_values(qapp):
    dialog = ErrorDetailsDialog.from_text(
        summary="AWS CLI command failed",
        details="Command: \nExit code: \nstderr: boom\nstdout: ",
    )

    assert dialog.sections["Command"] == "unknown"
    assert dialog.sections["Exit code"] == "unknown"
    assert dialog.sections["stderr"] == "boom"
    assert dialog.sections["stdout"] == ""
    dialog.close()


def test_error_details_dialog_hides_command_fields_when_not_executed(qapp):
    dialog = ErrorDetailsDialog(
        {
            "Summary": "No profiles found",
            "Incident evidence": "inventory-empty",
            "Command": "sts_check",
            "Exit code": "1",
            "stderr": "ignored",
            "stdout": "ignored",
            "Timestamp": "2026-05-09T12:00:00Z",
            "command_executed": "false",
        }
    )

    visible = dialog._visible_sections
    assert "Command" not in visible
    assert "Exit code" not in visible
    assert "stderr" not in visible
    assert "stdout" not in visible
    dialog.close()
```

- [ ] **Step 2: Run the test, confirm failure**

```bash
.venv/bin/pytest tests/test_tray.py::test_error_details_dialog_normalizes_command_executed_true_missing_values tests/test_tray.py::test_error_details_dialog_hides_command_fields_when_not_executed -q
# Expected: failing assertions because normalization/visibility policy is not implemented yet
```

- [ ] **Step 3: Implement minimal code**

```python
class ErrorDetailsDialog(QDialog):
    SECTION_ORDER = [
        "Summary",
        "Incident evidence",
        "Command",
        "Exit code",
        "stderr",
        "stdout",
        "Timestamp",
    ]

    def _normalize_sections(self, sections: dict[str, str]) -> dict[str, str]:
        normalized = {key: str(sections.get(key, "")).strip() for key in self.SECTION_ORDER}
        command_state = str(sections.get("command_executed", "unknown")).strip().lower()
        if command_state in {"true", "1", "yes"}:
            if not normalized["Command"]:
                normalized["Command"] = "unknown"
            if not normalized["Exit code"]:
                normalized["Exit code"] = "unknown"
        return normalized

    def _resolve_visible_sections(
        self, normalized: dict[str, str], command_state: str
    ) -> list[str]:
        visible = ["Summary"]
        if normalized.get("Incident evidence"):
            visible.append("Incident evidence")

        if command_state in {"true", "1", "yes"}:
            visible.extend(["Command", "Exit code"])
            stderr_value = normalized.get("stderr", "")
            stdout_value = normalized.get("stdout", "")
            if stderr_value:
                visible.append("stderr")
            if stdout_value or (not stderr_value and stdout_value == ""):
                visible.append("stdout")

        if normalized.get("Timestamp"):
            visible.append("Timestamp")
        return visible
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
.venv/bin/pytest tests/test_tray.py::test_error_details_dialog_normalizes_command_executed_true_missing_values tests/test_tray.py::test_error_details_dialog_hides_command_fields_when_not_executed -q
# Expected: 2 passed
```

- [ ] **Step 5: Commit**

```bash
git add aws_sso_autologin/tray.py tests/test_tray.py && git commit -m "fix(tray): normalize diagnostics field visibility policy"
```

### Task 2: Build three-region dialog layout with status header and smart fields

**Files:**
- Modify: `aws_sso_autologin/tray.py` (near `ErrorDetailsDialog.__init__`)
- Test: `tests/test_tray.py`

- [ ] **Step 1: Write the failing test**

```python
def test_error_details_dialog_has_three_regions(qapp):
    dialog = ErrorDetailsDialog.from_text(
        summary="AWS CLI unavailable",
        details="Command: sts_check\nExit code: 1\nstderr: fail",
    )

    assert dialog._status_header is not None
    assert dialog._smart_fields_region is not None
    assert dialog._text_edit is not None
    assert dialog._text_edit.isReadOnly() is True
    dialog.close()
```

- [ ] **Step 2: Run the test, confirm failure**

```bash
.venv/bin/pytest tests/test_tray.py::test_error_details_dialog_has_three_regions -q
# Expected: failing due to missing region widgets/attributes
```

- [ ] **Step 3: Implement minimal code**

```python
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

class ErrorDetailsDialog(QDialog):
    def __init__(self, sections: dict[str, str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AWS SSO Autologin Diagnostics")
        self.setFixedSize(760, 480)
        self.setWindowFlags(
            Qt.Dialog
            | Qt.WindowStaysOnTopHint
            | Qt.WindowCloseButtonHint
            | Qt.WindowTitleHint
        )

        root = QVBoxLayout(self)
        self._status_header = self._build_status_header()
        self._smart_fields_region = self._build_smart_fields_region()
        self._text_edit = QPlainTextEdit()
        self._text_edit.setReadOnly(True)

        root.addWidget(self._status_header)
        root.addWidget(self._smart_fields_region)
        root.addWidget(self._text_edit, 1)
        root.addLayout(self._build_action_row())

    def _build_status_header(self) -> QFrame:
        frame = QFrame(self)
        frame.setObjectName("diagnostics-status-header")
        layout = QVBoxLayout(frame)
        layout.addWidget(QLabel("Unknown execution state"))
        layout.addWidget(QLabel("Diagnostics are available."))
        return frame

    def _build_smart_fields_region(self) -> QScrollArea:
        area = QScrollArea(self)
        area.setWidgetResizable(True)
        container = QWidget()
        area.setWidget(container)
        return area
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
.venv/bin/pytest tests/test_tray.py::test_error_details_dialog_has_three_regions -q
# Expected: 1 passed
```

- [ ] **Step 5: Commit**

```bash
git add aws_sso_autologin/tray.py tests/test_tray.py && git commit -m "feat(tray): add diagnostics header smart-fields and details regions"
```

### Task 3: Implement copy-all behavior and helper lifecycle state machine

**Files:**
- Modify: `aws_sso_autologin/tray.py`
- Test: `tests/test_tray.py`

- [ ] **Step 1: Write the failing test**

```python
def test_error_details_dialog_copy_failure_shows_helper(qapp, monkeypatch):
    dialog = ErrorDetailsDialog.from_text("summary", "Command: sts_check")

    class RaisingClipboard:
        def setText(self, _text: str) -> None:
            raise RuntimeError("clipboard unavailable")

    monkeypatch.setattr(dialog, "_clipboard", RaisingClipboard())
    dialog._on_copy_all_details()

    assert dialog._copy_helper_label.text() == "Copy failed. Select details text and copy manually."
    assert dialog._copy_helper_state in {"fail", "escalated"}
    dialog.close()


def test_error_details_dialog_copy_success_clears_helper(qapp):
    dialog = ErrorDetailsDialog.from_text("summary", "Command: sts_check")
    dialog._set_copy_helper_state("fail")
    dialog._on_copy_all_details()

    assert dialog._copy_helper_state == "none"
    assert dialog._copy_helper_label.text() == ""
    dialog.close()
```

- [ ] **Step 2: Run the test, confirm failure**

```bash
.venv/bin/pytest tests/test_tray.py::test_error_details_dialog_copy_failure_shows_helper tests/test_tray.py::test_error_details_dialog_copy_success_clears_helper -q
# Expected: failing because copy callback/helper-state machine is not implemented
```

- [ ] **Step 3: Implement minimal code**

```python
class ErrorDetailsDialog(QDialog):
    def __init__(self, sections: dict[str, str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._copy_failure_streak = 0
        self._copy_helper_state = "none"
        self._copy_helper_label = QLabel("")
        self._clipboard = QApplication.clipboard()

    def _on_copy_all_details(self) -> None:
        payload = self._text_edit.toPlainText()
        try:
            self._clipboard.setText(payload)
        except Exception:
            self._copy_failure_streak += 1
            if self._copy_failure_streak >= 3:
                self._set_copy_helper_state("escalated")
            else:
                self._set_copy_helper_state("fail")
            logger.warning("event=diagnostics_copy_failed")
            return

        self._copy_failure_streak = 0
        self._set_copy_helper_state("success")
        self._set_copy_helper_state("none")
        logger.info("event=diagnostics_copy_succeeded")

    def _set_copy_helper_state(self, state: str) -> None:
        self._copy_helper_state = state
        if state == "fail":
            self._copy_helper_label.setText(
                "Copy failed. Select details text and copy manually."
            )
        elif state == "escalated":
            self._copy_helper_label.setText(
                "Copy is still failing. Select details text and copy manually."
            )
        elif state == "success":
            self._copy_helper_label.setText("Copy succeeded.")
        else:
            self._copy_helper_label.setText("")
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
.venv/bin/pytest tests/test_tray.py::test_error_details_dialog_copy_failure_shows_helper tests/test_tray.py::test_error_details_dialog_copy_success_clears_helper -q
# Expected: 2 passed
```

- [ ] **Step 5: Commit**

```bash
git add aws_sso_autologin/tray.py tests/test_tray.py && git commit -m "feat(tray): add copy helper lifecycle and telemetry events"
```

### Task 4: Enforce close semantics and app-survival contract

**Files:**
- Modify: `aws_sso_autologin/__main__.py`
- Modify: `aws_sso_autologin/tray.py`
- Test: `tests/test_main.py`
- Test: `tests/test_tray.py`

- [ ] **Step 1: Write the failing test**

```python
def test_initialize_qt_disables_quit_on_last_window_closed():
    app = AutologinApp([])
    mock_qapp = MagicMock()

    with patch("aws_sso_autologin.__main__.QApplication", return_value=mock_qapp):
        assert app._initialize_qt() is True

    mock_qapp.setQuitOnLastWindowClosed.assert_called_once_with(False)


def test_error_details_dialog_close_only_hides_dialog(qapp):
    dialog = ErrorDetailsDialog.from_text("summary", "Command: sts_check")
    dialog.show()
    dialog._on_close()
    assert dialog.isVisible() is False
```

- [ ] **Step 2: Run the test, confirm failure**

```bash
.venv/bin/pytest tests/test_main.py::test_initialize_qt_disables_quit_on_last_window_closed tests/test_tray.py::test_error_details_dialog_close_only_hides_dialog -q
# Expected: failure if quit policy or close behavior is not wired exactly
```

- [ ] **Step 3: Implement minimal code**

```python
class AutologinApp:
    def _initialize_qt(self) -> bool:
        try:
            self._app = QApplication(self._args)
            self._app.setApplicationName("AWS SSO Autologin")
            self._app.setOrganizationName("aws-sso-autologin")
            self._app.setQuitOnLastWindowClosed(False)
            return True
        except Exception:
            return False
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
.venv/bin/pytest tests/test_main.py::test_initialize_qt_disables_quit_on_last_window_closed tests/test_tray.py::test_error_details_dialog_close_only_hides_dialog -q
# Expected: 2 passed
```

- [ ] **Step 5: Commit**

```bash
git add aws_sso_autologin/__main__.py aws_sso_autologin/tray.py tests/test_main.py tests/test_tray.py && git commit -m "fix(__main__,tray): keep app alive when diagnostics closes"
```

### Task 5: Diagnostics dialog surface UX verification and reconciliation

**Surface:** Diagnostics dialog
**Artifact reference:** `docs/leyline/design/2026-05-09-diagnostics-dialog-redesign-ux.md#state-matrix`

- [ ] **Step 1:** Confirm the artifact section is current (matches current intent; DRAW step of DRAW-BUILD-RECONCILE)
- [ ] **Step 2:** Implement the surface per the artifact (BUILD step)
- [ ] **Step 3:** Trigger each state from the state matrix and observe. Copy each state-matrix cell verbatim from the UX spec.
  - Empty: `N/A - opens only when incident exists`
  - Loading: `N/A - data prepared before open`
  - Error: `Fallback content + textarea with available details`
  - Success: `Layout renders and controls are interactive`
  - Permission-denied: `N/A - no separate permission model`
  - Offline: `N/A - offline is represented as incident context`
- [ ] **Step 4:** Run the accessibility verification procedure (keyboard walk, screen-reader narration, contrast check, motion preference) and paste the output
- [ ] **Step 5:** Side-by-side reconciliation against the artifact (RECONCILE step). If divergence exists, choose one: (a) fix the code to match the artifact; OR (b) update the UX artifact AND loop back to `design-brainstorming` for the human partner's re-approval before continuing. Silent drift is forbidden.
- [ ] **Step 6:** Commit

### Task 6: Final verification and evidence capture

**Files:**
- Modify: `docs/leyline/plans/2026-05-09-diagnostics-dialog-redesign-review-log.md` (if required by review stage)

- [ ] **Step 1: Run targeted tests for changed modules**

```bash
.venv/bin/pytest tests/test_tray.py tests/test_main.py -q
# Expected: all pass
```

- [ ] **Step 2: Run full suite**

```bash
make test
# Expected: full suite green
```

- [ ] **Step 3: Capture runtime startup evidence for diagnostics contract context**

```bash
make run
# Expected: app starts or exits with structured event=... logs per AGENTS.md contract
```

- [ ] **Step 4: Commit verification artifacts (if files changed)**

```bash
git add -A && git commit -m "test(tray): verify diagnostics redesign evidence"
```
