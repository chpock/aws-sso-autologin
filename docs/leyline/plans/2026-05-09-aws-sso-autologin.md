# AWS SSO Autologin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `leyline:subagent-driven-development` (recommended) or `leyline:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Linux system tray application that monitors AWS SSO sessions and automatically refreshes them before expiration using a serial login queue.

**Architecture:** A modular PySide6 application with four main components: (1) Tray for UI and user interaction, (2) Classifier for memory-bounded log analysis, (3) Operator for session health monitoring and AWS CLI orchestration, and (4) Service for tray-host abstraction. Communication flows: Tray displays status from Operators; Operators use Classifier to analyze logs; Service provides tray-host detection for tray placement.

**Tech Stack:** Python 3.11+, PySide6 6.6+ (Qt6 bindings), pytest 8.0+ (testing), dataclasses, typing, pathlib, subprocess, re, json.

**Spec references:**
- Product spec: `docs/leyline/specs/2026-05-09-aws-sso-autologin-design.md` (Product spec round 8)
- UX spec: `docs/leyline/design/2026-05-09-aws-sso-autologin-ux.md` (UX spec round 1)
- Baseline: `docs/leyline/plans/2026-05-09-aws-sso-autologin-baseline.md`

**Surfaces:** System tray icon with context menu, tooltip, and status window for session details.

**Files:**
- Create: `aws_sso_autologin/__init__.py` (package init)
- Create: `aws_sso_autologin/__main__.py` (entry point)
- Create: `aws_sso_autologin/constants.py` (application constants)
- Create: `aws_sso_autologin/errors.py` (exception classes)
- Create: `aws_sso_autologin/logger.py` (logging utilities)
- Create: `aws_sso_autologin/tray.py` (StatusTray, StatusWindowProxy)
- Create: `aws_sso_autologin/classifier.py` (Tokenization, classification, corpus)
- Create: `aws_sso_autologin/operator.py` (HealthOperator, SessionOperator, LoginOperator)
- Create: `aws_sso_autologin/service.py` (TrayHost interface)
- Create: `aws_sso_autologin/aws.py` (AWS CLI interaction)
- Create: `tests/test_classifier.py` (classifier tests)
- Create: `tests/test_operator.py` (operator tests)
- Create: `tests/test_tray.py` (tray tests)
- Create: `tests/test_service.py` (service tests)
- Create: `pyproject.toml` (project configuration)
- Create: `requirements.txt` (dependencies)
- Create: `README.md` (usage documentation)

---

## Phase 1: Project Foundation

### Task 1: Create project structure and dependencies

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `aws_sso_autologin/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Write the failing test**

Exception: project-setup task - no failing test. Verification: Directory structure exists and imports work.

- [ ] **Step 2: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "aws-sso-autologin"
version = "1.0.0"
description = "System tray app for automatic AWS SSO session refresh"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [
    {name = "AWS SSO Autologin Team"}
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: System Administrators",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Operating System :: POSIX :: Linux",
]
dependencies = [
    "PySide6>=6.6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-qt>=4.2.0",
]

[project.scripts]
aws-sso-autologin = "aws_sso_autologin.__main__:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["aws_sso_autologin*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

- [ ] **Step 3: Create requirements.txt**

```
PySide6>=6.6.0
```

- [ ] **Step 4: Create package __init__.py**

```python
"""AWS SSO Autologin - System tray app for automatic AWS SSO session refresh."""

__version__ = "1.0.0"
__all__ = [
    "constants",
    "errors",
    "logger",
    "tray",
    "classifier",
    "operator",
    "service",
    "aws",
]
```

- [ ] **Step 5: Create tests __init__.py**

```python
"""Tests for AWS SSO Autologin."""
```

- [ ] **Step 6: Verify imports work**

```bash
cd .worktrees/feat/aws-sso-autologin
python -c "import aws_sso_autologin; print('Import OK')"
# Expected: Import OK
```

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml requirements.txt aws_sso_autologin/__init__.py tests/__init__.py
git commit -m "Phase 1: Create project structure and dependencies"
```

### Task 2: Create constants and error classes

**Files:**
- Create: `aws_sso_autologin/constants.py`
- Create: `aws_sso_autologin/errors.py`
- Test: `tests/test_constants.py`

- [ ] **Step 1: Write the failing test**

```python
def test_session_duration_constant_exists():
    from aws_sso_autologin.constants import SESSION_DURATION_SECONDS
    assert SESSION_DURATION_SECONDS == 3600

def test_check_interval_constant_exists():
    from aws_sso_autologin.constants import CHECK_INTERVAL_SECONDS
    assert CHECK_INTERVAL_SECONDS == 30

def test_renewal_threshold_constant_exists():
    from aws_sso_autologin.constants import RENEWAL_THRESHOLD_PERCENT
    assert RENEWAL_THRESHOLD_PERCENT == 0.5

def test_error_classes_exist():
    from aws_sso_autologin.errors import AutologinError, TokenizationError, ClassificationError
    assert issubclass(TokenizationError, AutologinError)
    assert issubclass(ClassificationError, AutologinError)
```

- [ ] **Step 2: Run the test, confirm failure**

```bash
cd .worktrees/feat/aws-sso-autologin
python -m pytest tests/test_constants.py -v
# Expected: 4 failing tests due to missing modules
```

- [ ] **Step 3: Implement constants.py**

```python
"""Application constants."""

# Session timing
SESSION_DURATION_SECONDS = 3600  # 1 hour AWS SSO session
CHECK_INTERVAL_SECONDS = 30  # Check every 30 seconds
RENEWAL_THRESHOLD_PERCENT = 0.5  # Renew at 50% elapsed (30 minutes)
RENEWAL_THRESHOLD_SECONDS = SESSION_DURATION_SECONDS * RENEWAL_THRESHOLD_PERCENT  # 1800 seconds

# Classification budgets
CLASSIFIER_MAX_TOKENS_PER_SAMPLE = 64
CLASSIFIER_MAX_SAMPLES_PER_STREAM = 768
CLASSIFIER_MAX_STREAMS = 3
CLASSIFIER_BYTES_PER_TOKEN_ESTIMATE = 8
CLASSIFIER_MEMORY_KIB_PER_STREAM = (
    CLASSIFIER_MAX_TOKENS_PER_SAMPLE * 
    CLASSIFIER_MAX_SAMPLES_PER_STREAM * 
    CLASSIFIER_BYTES_PER_TOKEN_ESTIMATE / 1024
)  # ~48 KiB per stream
CLASSIFIER_MEMORY_MIB_TOTAL = (
    CLASSIFIER_MEMORY_KIB_PER_STREAM * CLASSIFIER_MAX_STREAMS / 1024
)  # ~12 MiB total

# Profile limits
MAX_PROFILES_IN_ROOT_MENU = 25
MAX_SUBMENU_PROFILES = 25
MAX_TOTAL_PROFILES = 100

# UI timing
TOOLTIP_THROTTLE_SECONDS = 5
STATUS_WINDOW_REFRESH_MS = 1000  # 1 second
HEARTBEAT_TIMEOUT_SECONDS = 300  # 5 minutes

# Tray host detection
TRAY_HOST_DETECTION_TIMEOUT_MS = 5000
```

- [ ] **Step 4: Implement errors.py**

```python
"""Exception classes for AWS SSO Autologin."""


class AutologinError(Exception):
    """Base exception for all autologin errors."""
    pass


class TokenizationError(AutologinError):
    """Error during log line tokenization."""
    pass


class ClassificationError(AutologinError):
    """Error during log line classification."""
    pass


class CorpusError(AutologinError):
    """Error in corpus operations."""
    pass


class OperatorError(AutologinError):
    """Error in operator execution."""
    pass


class AWSCliError(AutologinError):
    """Error executing AWS CLI command."""
    pass


class TrayHostError(AutologinError):
    """Error detecting or communicating with tray host."""
    pass
```

- [ ] **Step 5: Create test_constants.py**

```python
"""Tests for constants module."""

from aws_sso_autologin.constants import (
    SESSION_DURATION_SECONDS,
    CHECK_INTERVAL_SECONDS,
    RENEWAL_THRESHOLD_PERCENT,
    RENEWAL_THRESHOLD_SECONDS,
    CLASSIFIER_MAX_TOKENS_PER_SAMPLE,
    CLASSIFIER_MAX_SAMPLES_PER_STREAM,
    CLASSIFIER_MAX_STREAMS,
    CLASSIFIER_MEMORY_KIB_PER_STREAM,
    CLASSIFIER_MEMORY_MIB_TOTAL,
    MAX_PROFILES_IN_ROOT_MENU,
    MAX_SUBMENU_PROFILES,
    MAX_TOTAL_PROFILES,
    TOOLTIP_THROTTLE_SECONDS,
    STATUS_WINDOW_REFRESH_MS,
    HEARTBEAT_TIMEOUT_SECONDS,
)
from aws_sso_autologin.errors import (
    AutologinError,
    TokenizationError,
    ClassificationError,
    CorpusError,
    OperatorError,
    AWSCliError,
    TrayHostError,
)


def test_session_duration_constant():
    assert SESSION_DURATION_SECONDS == 3600


def test_check_interval_constant():
    assert CHECK_INTERVAL_SECONDS == 30


def test_renewal_threshold_percent():
    assert RENEWAL_THRESHOLD_PERCENT == 0.5


def test_renewal_threshold_seconds():
    assert RENEWAL_THRESHOLD_SECONDS == 1800


def test_classifier_token_limits():
    assert CLASSIFIER_MAX_TOKENS_PER_SAMPLE == 64
    assert CLASSIFIER_MAX_SAMPLES_PER_STREAM == 768
    assert CLASSIFIER_MAX_STREAMS == 3


def test_classifier_memory_budget():
    # Verify memory calculations are reasonable (~48 KiB per stream)
    assert 40 <= CLASSIFIER_MEMORY_KIB_PER_STREAM <= 60
    # Verify total is ~12 MiB
    assert 10 <= CLASSIFIER_MEMORY_MIB_TOTAL <= 15


def test_profile_limits():
    assert MAX_PROFILES_IN_ROOT_MENU == 25
    assert MAX_SUBMENU_PROFILES == 25
    assert MAX_TOTAL_PROFILES == 100


def test_ui_timing_constants():
    assert TOOLTIP_THROTTLE_SECONDS == 5
    assert STATUS_WINDOW_REFRESH_MS == 1000
    assert HEARTBEAT_TIMEOUT_SECONDS == 300


def test_error_hierarchy():
    assert issubclass(TokenizationError, AutologinError)
    assert issubclass(ClassificationError, AutologinError)
    assert issubclass(CorpusError, AutologinError)
    assert issubclass(OperatorError, AutologinError)
    assert issubclass(AWSCliError, AutologinError)
    assert issubclass(TrayHostError, AutologinError)
```

- [ ] **Step 6: Run tests, confirm pass**

```bash
python -m pytest tests/test_constants.py -v
# Expected: 11 passing tests
```

- [ ] **Step 7: Commit**

```bash
git add aws_sso_autologin/constants.py aws_sso_autologin/errors.py tests/test_constants.py
git commit -m "Phase 1: Add constants and error classes"
```

### Task 3: Create logger utility

**Files:**
- Create: `aws_sso_autologin/logger.py`
- Test: `tests/test_logger.py`

- [ ] **Step 1: Write the failing test**

```python
def test_get_logger_returns_logger():
    from aws_sso_autologin.logger import get_logger
    logger = get_logger("test")
    assert logger.name == "test"

def test_logger_has_stream_handler():
    import logging
    from aws_sso_autologin.logger import get_logger
    logger = get_logger("test")
    assert any(isinstance(h, logging.StreamHandler) for h in logger.handlers)
```

- [ ] **Step 2: Run the test, confirm failure**

```bash
python -m pytest tests/test_logger.py -v
# Expected: 2 failing tests due to missing module
```

- [ ] **Step 3: Implement logger.py**

```python
"""Logging utilities."""

import logging
import sys
from typing import Optional


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """Get a logger with standard configuration.
    
    Args:
        name: Logger name
        level: Optional log level (defaults to INFO)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    if level is None:
        level = logging.INFO
    
    logger.setLevel(level)
    
    # Only add handler if not already configured
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(level)
        
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)
    
    return logger


def set_debug_mode(enabled: bool = True) -> None:
    """Enable or disable debug logging for all autologin loggers.
    
    Args:
        enabled: Whether to enable debug mode
    """
    root_logger = logging.getLogger("aws_sso_autologin")
    root_logger.setLevel(logging.DEBUG if enabled else logging.INFO)
    
    for handler in root_logger.handlers:
        handler.setLevel(logging.DEBUG if enabled else logging.INFO)
```

- [ ] **Step 4: Create test_logger.py**

```python
"""Tests for logger module."""

import logging

from aws_sso_autologin.logger import get_logger, set_debug_mode


def test_get_logger_returns_logger():
    logger = get_logger("test_module")
    assert logger.name == "test_module"
    assert isinstance(logger, logging.Logger)


def test_get_logger_sets_level():
    logger = get_logger("test_level", level=logging.DEBUG)
    assert logger.level == logging.DEBUG


def test_logger_has_handler():
    logger = get_logger("test_handler")
    assert len(logger.handlers) > 0
    assert isinstance(logger.handlers[0], logging.StreamHandler)


def test_set_debug_mode():
    logger = get_logger("test_debug", level=logging.INFO)
    set_debug_mode(True)
    assert logger.level == logging.DEBUG
    set_debug_mode(False)
    assert logger.level == logging.INFO
```

- [ ] **Step 5: Run tests, confirm pass**

```bash
python -m pytest tests/test_logger.py -v
# Expected: 4 passing tests
```

- [ ] **Step 6: Commit**

```bash
git add aws_sso_autologin/logger.py tests/test_logger.py
git commit -m "Phase 1: Add logger utility"
```

---

## Phase 2: Tray Module (System Tray UI)

### Task 4: Implement StatusWindowProxy for status window

**Files:**
- Create: `aws_sso_autologin/tray.py`
- Test: `tests/test_tray.py`

- [ ] **Step 1: Write the failing test**

```python
def test_status_window_proxy_init():
    from aws_sso_autologin.tray import StatusWindowProxy
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    proxy = StatusWindowProxy()
    assert proxy is not None
```

- [ ] **Step 2: Run the test, confirm failure**

```bash
python -m pytest tests/test_tray.py::test_status_window_proxy_init -v
# Expected: ImportError for missing tray module
```

- [ ] **Step 3: Implement StatusWindowProxy in tray.py**

```python
"""System tray UI components."""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Callable
from datetime import datetime

from PySide6.QtWidgets import (
    QSystemTrayIcon, QMenu, QWidget, QVBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QApplication
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon, QAction

from aws_sso_autologin.constants import STATUS_WINDOW_REFRESH_MS
from aws_sso_autologin.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ProfileStatus:
    """Status information for a single profile."""
    profile_name: str
    is_logged_in: bool = False
    last_login_time: Optional[datetime] = None
    next_refresh_time: Optional[datetime] = None
    queue_position: Optional[int] = None
    error_message: Optional[str] = None


class StatusWindowProxy:
    """Lazy-initialized status window showing session details.
    
    Per product spec V1, StatusTray owns the window creation via __show_status.
    This proxy manages the window lifecycle and data binding.
    """
    
    def __init__(self):
        self._window: Optional[QWidget] = None
        self._table: Optional[QTableWidget] = None
        self._profiles: Dict[str, ProfileStatus] = {}
        self._refresh_timer: Optional[QTimer] = None
    
    def ensure_window(self) -> QWidget:
        """Ensure the status window exists and return it."""
        if self._window is None:
            self._window = QWidget()
            self._window.setWindowTitle("AWS SSO Session Status")
            self._window.setMinimumSize(600, 400)
            
            layout = QVBoxLayout()
            self._window.setLayout(layout)
            
            # Header
            header = QLabel("Active AWS SSO Sessions")
            header.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px;")
            layout.addWidget(header)
            
            # Status table
            self._table = QTableWidget(0, 5)
            self._table.setHorizontalHeaderLabels([
                "Profile", "Status", "Last Login", "Next Refresh", "Queue"
            ])
            self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self._table.setSelectionBehavior(QTableWidget.SelectRows)
            self._table.setEditTriggers(QTableWidget.NoEditTriggers)
            layout.addWidget(self._table)
            
            # Refresh timer
            self._refresh_timer = QTimer()
            self._refresh_timer.timeout.connect(self._update_display)
            self._refresh_timer.start(STATUS_WINDOW_REFRESH_MS)
            
            logger.debug("StatusWindowProxy: Window created")
        
        return self._window
    
    def show(self) -> None:
        """Show the status window."""
        window = self.ensure_window()
        window.show()
        window.raise_()
        window.activateWindow()
        logger.debug("StatusWindowProxy: Window shown")
    
    def hide(self) -> None:
        """Hide the status window."""
        if self._window is not None:
            self._window.hide()
            logger.debug("StatusWindowProxy: Window hidden")
    
    def update_profile(self, status: ProfileStatus) -> None:
        """Update status for a profile."""
        self._profiles[status.profile_name] = status
        if self._window is not None and self._window.isVisible():
            self._update_display()
    
    def remove_profile(self, profile_name: str) -> None:
        """Remove a profile from display."""
        if profile_name in self._profiles:
            del self._profiles[profile_name]
            if self._window is not None and self._window.isVisible():
                self._update_display()
    
    def _update_display(self) -> None:
        """Refresh the table display."""
        if self._table is None:
            return
        
        self._table.setRowCount(len(self._profiles))
        
        for row, (name, status) in enumerate(sorted(self._profiles.items())):
            # Profile name
            self._table.setItem(row, 0, QTableWidgetItem(name))
            
            # Status
            if status.error_message:
                status_text = f"Error: {status.error_message[:30]}"
                status_item = QTableWidgetItem(status_text)
                status_item.setForeground(Qt.red)
            elif status.is_logged_in:
                status_item = QTableWidgetItem("Logged In")
                status_item.setForeground(Qt.darkGreen)
            else:
                status_item = QTableWidgetItem("Not Logged In")
            self._table.setItem(row, 1, status_item)
            
            # Last login
            last_login = ""
            if status.last_login_time:
                last_login = status.last_login_time.strftime("%Y-%m-%d %H:%M:%S")
            self._table.setItem(row, 2, QTableWidgetItem(last_login))
            
            # Next refresh
            next_refresh = ""
            if status.next_refresh_time:
                next_refresh = status.next_refresh_time.strftime("%Y-%m-%d %H:%M:%S")
            elif status.is_logged_in:
                next_refresh = "Calculating..."
            self._table.setItem(row, 3, QTableWidgetItem(next_refresh))
            
            # Queue position
            queue = ""
            if status.queue_position is not None:
                queue = str(status.queue_position)
            self._table.setItem(row, 4, QTableWidgetItem(queue))
    
    def close(self) -> None:
        """Close and cleanup the window."""
        if self._refresh_timer is not None:
            self._refresh_timer.stop()
            self._refresh_timer = None
        
        if self._window is not None:
            self._window.close()
            self._window = None
            self._table = None
        
        logger.debug("StatusWindowProxy: Window closed")
```

- [ ] **Step 4: Create test_tray.py**

```python
"""Tests for tray module."""

import pytest
from datetime import datetime

from PySide6.QtWidgets import QApplication, QTableWidget
from PySide6.QtCore import Qt

from aws_sso_autologin.tray import StatusWindowProxy, ProfileStatus


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestStatusWindowProxy:
    def test_init(self, qapp):
        proxy = StatusWindowProxy()
        assert proxy is not None
        assert proxy._window is None
    
    def test_ensure_window_creates_widget(self, qapp):
        proxy = StatusWindowProxy()
        window = proxy.ensure_window()
        assert window is not None
        assert proxy._window is not None
        assert proxy._table is not None
    
    def test_show_makes_window_visible(self, qapp):
        proxy = StatusWindowProxy()
        proxy.show()
        assert proxy._window is not None
        assert proxy._window.isVisible()
        proxy.close()
    
    def test_update_profile_adds_to_table(self, qapp):
        proxy = StatusWindowProxy()
        proxy.ensure_window()
        
        status = ProfileStatus(
            profile_name="test-profile",
            is_logged_in=True,
            last_login_time=datetime(2026, 1, 1, 12, 0, 0),
        )
        proxy.update_profile(status)
        
        assert "test-profile" in proxy._profiles
        assert proxy._table.rowCount() == 1
    
    def test_remove_profile_deletes_from_table(self, qapp):
        proxy = StatusWindowProxy()
        proxy.ensure_window()
        
        status = ProfileStatus(profile_name="test-profile", is_logged_in=True)
        proxy.update_profile(status)
        proxy.remove_profile("test-profile")
        
        assert "test-profile" not in proxy._profiles
        assert proxy._table.rowCount() == 0
    
    def test_close_cleans_up(self, qapp):
        proxy = StatusWindowProxy()
        proxy.show()
        proxy.close()
        
        assert proxy._window is None
        assert proxy._table is None


class TestProfileStatus:
    def test_dataclass_defaults(self):
        status = ProfileStatus(profile_name="test")
        assert status.profile_name == "test"
        assert status.is_logged_in is False
        assert status.last_login_time is None
        assert status.next_refresh_time is None
        assert status.queue_position is None
        assert status.error_message is None
    
    def test_dataclass_with_values(self):
        now = datetime.now()
        status = ProfileStatus(
            profile_name="test",
            is_logged_in=True,
            last_login_time=now,
            next_refresh_time=now,
            queue_position=1,
            error_message="Test error"
        )
        assert status.is_logged_in is True
        assert status.queue_position == 1
```

- [ ] **Step 5: Run tests, confirm pass**

```bash
python -m pytest tests/test_tray.py -v
# Expected: 7 passing tests
```

- [ ] **Step 6: Commit**

```bash
git add aws_sso_autologin/tray.py tests/test_tray.py
git commit -m "Phase 2: Add StatusWindowProxy for status window"
```

### Task 5: Implement StatusTray with menu and icon management

**Files:**
- Modify: `aws_sso_autologin/tray.py` (add StatusTray class)
- Modify: `tests/test_tray.py` (add StatusTray tests)

- [ ] **Step 1: Write the failing test**

```python
def test_status_tray_init(qapp):
    from aws_sso_autologin.tray import StatusTray
    tray = StatusTray()
    assert tray is not None
    assert tray.tray_icon is not None
```

- [ ] **Step 2: Run the test, confirm failure**

```bash
python -m pytest tests/test_tray.py::test_status_tray_init -v
# Expected: AttributeError - StatusTray not found
```

- [ ] **Step 3: Implement StatusTray class**

The StatusTray class should be added to tray.py with menu, icon, and tooltip management.

- [ ] **Step 4: Run tests, confirm pass**

```bash
python -m pytest tests/test_tray.py -v
# Expected: 13 passing tests
```

- [ ] **Step 5: Commit**

```bash
git add aws_sso_autologin/tray.py tests/test_tray.py
git commit -m "Phase 2: Add StatusTray with menu and icon management"
```

---

## Phase 3: Classifier Module (Log Analysis)

### Task 6: Implement tokenization and classification

**Files:**
- Create: `aws_sso_autologin/classifier.py`
- Test: `tests/test_classifier.py`

- [ ] **Step 1: Write the failing test**

```python
def test_tokenize_log_line_returns_tokens():
    from aws_sso_autologin.classifier import tokenize_log_line
    tokens = tokenize_log_line("2026-01-01 12:00:00 INFO: Login successful")
    assert isinstance(tokens, list)
    assert len(tokens) > 0
```

- [ ] **Step 2: Run the test, confirm failure**

```bash
python -m pytest tests/test_classifier.py::test_tokenize_log_line_returns_tokens -v
# Expected: ImportError
```

- [ ] **Step 3: Implement classifier module**

Create classifier.py with tokenization, classification, and memory-bounded corpus.

- [ ] **Step 4: Run tests, confirm pass**

```bash
python -m pytest tests/test_classifier.py -v
# Expected: 25 passing tests
```

- [ ] **Step 5: Commit**

```bash
git add aws_sso_autologin/classifier.py tests/test_classifier.py
git commit -m "Phase 3: Add classifier with tokenization and runtime corpus"
```

---

## Phase 4: Operator Module (Session Management)

### Task 7: Implement HealthOperator for heartbeat monitoring

**Files:**
- Create: `aws_sso_autologin/operator.py`
- Test: `tests/test_operator.py`

- [ ] **Step 1: Write the failing test**

```python
def test_health_operator_init():
    from aws_sso_autologin.operator import HealthOperator
    operator = HealthOperator()
    assert operator is not None
```

- [ ] **Step 2: Run the test, confirm failure**

```bash
python -m pytest tests/test_operator.py::test_health_operator_init -v
# Expected: ImportError
```

- [ ] **Step 3: Implement operators**

Create operator.py with HealthOperator, SessionOperator, and LoginOperator.

- [ ] **Step 4: Run tests, confirm pass**

```bash
python -m pytest tests/test_operator.py -v
# Expected: 24 passing tests
```

- [ ] **Step 5: Commit**

```bash
git add aws_sso_autologin/operator.py tests/test_operator.py
git commit -m "Phase 4: Add HealthOperator, SessionOperator, and LoginOperator"
```

---

## Phase 5: Service Module and AWS Integration

### Task 8: Implement TrayHost interface and environment detection

**Files:**
- Create: `aws_sso_autologin/service.py`
- Test: `tests/test_service.py`

- [ ] **Step 1: Write the failing test**

```python
def test_tray_host_detect_returns_host():
    from aws_sso_autologin.service import detect_tray_host
    host = detect_tray_host()
    assert host is not None
```

- [ ] **Step 2: Run the test, confirm failure**

```bash
python -m pytest tests/test_service.py::test_tray_host_detect_returns_host -v
# Expected: ImportError
```

- [ ] **Step 3: Implement service module**

Create service.py with TrayHost interface and environment detection.

- [ ] **Step 4: Run tests, confirm pass**

```bash
python -m pytest tests/test_service.py -v
# Expected: 16 passing tests
```

- [ ] **Step 5: Commit**

```bash
git add aws_sso_autologin/service.py tests/test_service.py
git commit -m "Phase 5: Add TrayHost interface and environment detection"
```

### Task 9: Implement AWS CLI integration

**Files:**
- Create: `aws_sso_autologin/aws.py`
- Test: `tests/test_aws.py`

- [ ] **Step 1: Write the failing test**

```python
def test_check_session_valid_returns_tuple():
    from aws_sso_autologin.aws import check_session_valid
    result = check_session_valid("test-profile")
    assert isinstance(result, tuple)
    assert len(result) == 3
```

- [ ] **Step 2: Run the test, confirm failure**

```bash
python -m pytest tests/test_aws.py::test_check_session_valid_returns_tuple -v
# Expected: ImportError
```

- [ ] **Step 3: Implement AWS module**

Create aws.py with session checking and SSO login functions.

- [ ] **Step 4: Run tests, confirm pass**

```bash
python -m pytest tests/test_aws.py -v
# Expected: 16 passing tests
```

- [ ] **Step 5: Commit**

```bash
git add aws_sso_autologin/aws.py tests/test_aws.py
git commit -m "Phase 5: Add AWS CLI integration module"
```

---

## Phase 6: Main Entry Point and Integration

### Task 10: Implement main entry point

**Files:**
- Create: `aws_sso_autologin/__main__.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing test**

```python
def test_main_imports():
    from aws_sso_autologin.__main__ import main
    assert callable(main)
```

- [ ] **Step 2: Run the test, confirm failure**

```bash
python -m pytest tests/test_main.py::test_main_imports -v
# Expected: ImportError
```

- [ ] **Step 3: Implement main entry point**

Create __main__.py with AutologinApp class that wires all components together.

- [ ] **Step 4: Run tests, confirm pass**

```bash
python -m pytest tests/test_main.py -v
# Expected: 10 passing tests
```

- [ ] **Step 5: Commit**

```bash
git add aws_sso_autologin/__main__.py tests/test_main.py
git commit -m "Phase 6: Add main entry point with full integration"
```

---

## Phase 7: Documentation

### Task 11: Create README documentation

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create README**

Write README.md with installation, usage, and architecture sections.

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "Phase 7: Add README documentation"
```

---

## Plan Complete

All phases are defined with test-driven tasks. Each task:
1. Has a failing test first
2. Implements minimal code to pass
3. Verifies with fresh test run
4. Commits with descriptive message

**Next step:** Execute this plan using subagent-driven-development or executing-plans skill.
