"""System tray UI components."""

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHeaderView,
    QLabel,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStyle,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from aws_sso_autologin.constants import (
    MAX_PROFILES_IN_ROOT_MENU,
    MAX_SUBMENU_PROFILES,
    STATUS_WINDOW_REFRESH_MS,
    TOOLTIP_THROTTLE_MS,
)
from aws_sso_autologin.logger import get_logger

logger = get_logger(__name__)


class ProfileState(Enum):
    """Profile row states from the UX state matrix."""

    OK = "ok"
    SYNCING = "syncing"
    WARNING = "warning"
    ERROR = "error"
    PAUSED_OK = "paused_ok"


@dataclass
class ProfileStatus:
    """Status information for a single profile row."""

    profile_name: str
    state: ProfileState = ProfileState.SYNCING
    last_login_time: datetime | None = None
    next_refresh_time: datetime | None = None
    queue_position: int | None = None
    short_reason: str | None = None
    diagnostics_summary: str | None = None
    diagnostics_details: str | None = None

    # Backward-compatible fields used by early scaffolding tests/code.
    is_logged_in: bool | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if self.error_message and not self.short_reason:
            self.short_reason = self.error_message

        if self.is_logged_in is None:
            return

        if self.state != ProfileState.SYNCING:
            return

        if self.short_reason:
            self.state = ProfileState.ERROR
        elif self.is_logged_in:
            self.state = ProfileState.OK
        else:
            self.state = ProfileState.WARNING


class StatusWindowProxy:
    """Lazy-initialized status window showing session details."""

    def __init__(self) -> None:
        self._window: QWidget | None = None
        self._table: QTableWidget | None = None
        self._profiles: dict[str, ProfileStatus] = {}
        self._refresh_timer: QTimer | None = None

    def ensure_window(self) -> QWidget:
        """Ensure the status window exists and return it."""
        if self._window is None:
            self._window = QWidget()
            self._window.setWindowTitle("AWS SSO Session Status")
            self._window.setMinimumSize(600, 400)

            layout = QVBoxLayout()
            self._window.setLayout(layout)

            header = QLabel("Active AWS SSO Sessions")
            header.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px;")
            layout.addWidget(header)

            self._table = QTableWidget(0, 5)
            self._table.setHorizontalHeaderLabels(
                ["Profile", "Status", "Last Login", "Next Refresh", "Queue"]
            )
            self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self._table.setSelectionBehavior(QTableWidget.SelectRows)
            self._table.setEditTriggers(QTableWidget.NoEditTriggers)
            layout.addWidget(self._table)

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

    def hide(self) -> None:
        """Hide the status window."""
        if self._window is not None:
            self._window.hide()

    def update_profile(self, status: ProfileStatus) -> None:
        """Update status for a profile."""
        self._profiles[status.profile_name] = status
        if self._window is not None:
            self._update_display()

    def remove_profile(self, profile_name: str) -> None:
        """Remove a profile from display."""
        self._profiles.pop(profile_name, None)
        if self._window is not None:
            self._update_display()

    def _update_display(self) -> None:
        if self._table is None:
            return

        self._table.setRowCount(len(self._profiles))

        for row, (name, status) in enumerate(sorted(self._profiles.items())):
            self._table.setItem(row, 0, QTableWidgetItem(name))
            self._table.setItem(row, 1, self._status_item(status))

            last_login = ""
            if status.last_login_time:
                last_login = status.last_login_time.strftime("%Y-%m-%d %H:%M:%S")
            self._table.setItem(row, 2, QTableWidgetItem(last_login))

            next_refresh = ""
            if status.next_refresh_time:
                next_refresh = status.next_refresh_time.strftime("%Y-%m-%d %H:%M:%S")
            elif status.state == ProfileState.SYNCING:
                next_refresh = "Calculating..."
            self._table.setItem(row, 3, QTableWidgetItem(next_refresh))

            queue = ""
            if status.queue_position is not None:
                queue = str(status.queue_position)
            self._table.setItem(row, 4, QTableWidgetItem(queue))

    def _status_item(self, status: ProfileStatus) -> QTableWidgetItem:
        if status.state == ProfileState.ERROR:
            reason = status.short_reason or "Unknown"
            item = QTableWidgetItem(f"Error: {reason}")
            item.setForeground(Qt.red)
            return item

        if status.state == ProfileState.WARNING:
            reason = status.short_reason or "Connectivity issue"
            item = QTableWidgetItem(f"Warning: {reason}")
            item.setForeground(Qt.darkYellow)
            return item

        if status.state == ProfileState.SYNCING:
            return QTableWidgetItem("Syncing...")

        if status.state == ProfileState.PAUSED_OK:
            return QTableWidgetItem("OK (paused)")

        item = QTableWidgetItem("OK")
        item.setForeground(Qt.darkGreen)
        return item

    def close(self) -> None:
        """Close and cleanup the window."""
        if self._refresh_timer is not None:
            self._refresh_timer.stop()
            self._refresh_timer = None

        if self._window is not None:
            self._window.close()
            self._window = None
            self._table = None


class ErrorDetailsDialog(QDialog):
    """Floating diagnostics dialog for warning/error profile states."""

    SECTION_ORDER = [
        "Summary",
        "Incident evidence",
        "Command",
        "Exit code",
        "stderr",
        "stdout",
        "Timestamp",
    ]

    def __init__(
        self,
        sections: dict[str, str],
        parent: QWidget | None = None,
        command_executed: bool | None = None,
        is_config_error: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("AWS SSO Autologin Diagnostics")
        self.setFixedSize(760, 480)
        self.section_order = list(self.SECTION_ORDER)
        self.sections = dict(sections)
        self._command_executed = command_executed
        self._is_config_error = is_config_error

        # Set window flags for floating behavior across all compositors
        # WindowStaysOnTopHint makes it float above other windows
        # Dialog flag ensures it's treated as a dialog window
        self.setWindowFlags(
            Qt.Dialog
            | Qt.WindowStaysOnTopHint
            | Qt.WindowCloseButtonHint
            | Qt.WindowTitleHint
        )

        layout = QVBoxLayout(self)

        # Three-region layout per UX spec
        # Region 1: Status header
        self._status_header = self._build_status_header()
        layout.addWidget(self._status_header)

        # Region 2: Smart fields region
        self._smart_fields_region = self._build_smart_fields_region()
        layout.addWidget(self._smart_fields_region)

        # Region 3: Details textarea
        self._text_edit = QPlainTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setPlainText(self._format_sections(sections))
        self._text_edit.setStyleSheet("""
            QPlainTextEdit {
                border: 1px solid #aaaaaa;
                border-radius: 3px;
                background-color: #f5f5f5;
                padding: 4px;
            }
        """)
        layout.addWidget(self._text_edit, 1)

        # Copy helper label (between textarea and buttons)
        self._copy_helper_label = QLabel("")
        self._copy_helper_label.setObjectName("copy-helper-label")
        # Accessibility: live region for screen reader announcements
        self._copy_helper_label.setAccessibleName("Copy status announcement")
        self._copy_helper_label.setProperty("accessible-live-region", "polite")
        layout.addWidget(self._copy_helper_label)

        # Action row: Copy and Close buttons
        buttons = QDialogButtonBox()
        self._copy_button = QPushButton("Copy all details")
        self._copy_button.setObjectName("copy-all-details-button")
        buttons.addButton(self._copy_button, QDialogButtonBox.ActionRole)
        buttons.addButton(QDialogButtonBox.Close)
        self._copy_button.clicked.connect(self._on_copy_all_details)
        buttons.rejected.connect(self._on_close)
        layout.addWidget(buttons)

        # Set initial focus to details textarea per UX spec accessibility contract
        self._text_edit.setFocus()

        # Copy helper state machine attributes
        self._copy_failure_streak = 0
        self._copy_helper_state = "none"
        self._clipboard = QApplication.clipboard()

    def _build_status_header(self) -> QFrame:
        """Build status header region based on execution state."""
        frame = QFrame(self)
        frame.setObjectName("diagnostics-status-header")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)

        if self._is_config_error:
            # Configuration errors show simple header with summary as title
            status_title = QLabel(self.sections.get("Summary", "Configuration Issue"))
            status_title.setStyleSheet(
                "font-weight: bold; font-size: 14px; padding: 4px 0;"
            )
            layout.addWidget(status_title)
        elif self._command_executed is None:
            # Unknown execution state copy contract per UX spec lines 132-134
            status_title = QLabel("Unknown execution state")
            status_title.setStyleSheet(
                "font-weight: bold; font-size: 14px; padding: 4px 0;"
            )
            layout.addWidget(status_title)

            status_subtitle = QLabel(
                "Diagnostics are available, but command execution state"
                " could not be determined."
            )
            status_subtitle.setStyleSheet("font-size: 12px; padding-bottom: 8px;")
            status_subtitle.setWordWrap(True)
            layout.addWidget(status_subtitle)
        else:
            # Default status header for known execution states
            status_title = QLabel("Diagnostics")
            status_title.setStyleSheet(
                "font-weight: bold; font-size: 14px; padding: 4px 0;"
            )
            layout.addWidget(status_title)

        return frame

    def _build_smart_fields_region(self) -> QScrollArea:
        """Build smart fields region as scrollable area."""
        area = QScrollArea(self)
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        area.setWidget(container)

        return area

    def _format_sections(self, sections: dict[str, str]) -> str:
        """Format sections into a single text block for display and copying."""
        lines = []
        processed = set()
        # First, process sections in defined order
        for section in self.section_order:
            if section not in sections:
                continue
            value = sections[section]
            lines.append(f"{section}: {value}")
            processed.add(section)
        # Then add any remaining sections not in the standard order
        for section, value in sections.items():
            if section not in processed:
                lines.append(f"{section}: {value}")
        return "\n\n".join(lines)

    def _on_copy_all_details(self) -> None:
        """Copy all details to clipboard with helper state machine."""
        payload = self._text_edit.toPlainText()
        # Determine incident type from summary for telemetry
        incident_type = (
            self.sections.get("Summary", "unknown").split()[0].lower()
            if self.sections.get("Summary")
            else "unknown"
        )
        command_executed = (
            self._command_executed if self._command_executed is not None else False
        )

        try:
            self._clipboard.setText(payload)
        except Exception as e:
            self._copy_failure_streak += 1
            fallback_used = self._copy_failure_streak >= 3
            if fallback_used:
                self._set_copy_helper_state("escalated")
            else:
                self._set_copy_helper_state("fail")
            logger.warning(
                "event=diagnostics_copy_failed",
                extra={
                    "incident_type": incident_type,
                    "command_executed": command_executed,
                    "fallback_used": fallback_used,
                    "error_class": type(e).__name__,
                    "copy_result": "failed",
                },
            )
            return

        self._copy_failure_streak = 0
        # UX spec line 63: clear helper immediately on success (no success display)
        self._set_copy_helper_state("none")
        logger.info(
            "event=diagnostics_copy_succeeded",
            extra={
                "incident_type": incident_type,
                "command_executed": command_executed,
                "fallback_used": False,
                "error_class": None,
                "copy_result": "succeeded",
            },
        )

    def _set_copy_helper_state(self, state: str) -> None:
        """Set the copy helper state and update the label text."""
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

    def _on_close(self) -> None:
        """Handle close button - only close the dialog, not the application."""
        self.close()

    @classmethod
    def from_text(
        cls,
        summary: str,
        details: str,
        parent: QWidget | None = None,
        is_config_error: bool = False,
    ) -> "ErrorDetailsDialog":
        # Configuration errors show simple, clear messaging without"
        # command-related fields
        if is_config_error:
            sections: dict[str, str] = {"Summary": summary}
            # Include details as helpful context if provided and different from summary
            if details and details.strip() != summary.strip():
                sections["Context"] = details.strip()
            return cls(sections=sections, parent=parent, is_config_error=True)

        raw_sections = {
            "Summary": summary,
            "Incident evidence": (
                "Incident evidence unavailable: retention window exceeded."
            ),
            "Command": "",
            "Exit code": "",
            "stderr": "",
            "stdout": "",
            "Timestamp": "",
        }

        mapping = {
            "incident evidence": "Incident evidence",
            "command": "Command",
            "exit code": "Exit code",
            "stderr": "stderr",
            "stdout": "stdout",
            "timestamp": "Timestamp",
            "summary": "Summary",
        }
        command_executed: bool | None = None

        for line in details.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            normalized = key.strip().lower()
            if normalized == "command executed":
                bool_value = value.strip().lower()
                if bool_value in {"true", "yes", "1"}:
                    command_executed = True
                elif bool_value in {"false", "no", "0"}:
                    command_executed = False
                continue
            section = mapping.get(normalized)
            if section is None:
                continue
            raw_sections[section] = value.strip()

        sections = {"Summary": raw_sections["Summary"]}

        if raw_sections["Incident evidence"]:
            sections["Incident evidence"] = raw_sections["Incident evidence"]

        # Track raw outputs for details textarea preservation when execution state"
        # unknown
        raw_stdout = raw_sections["stdout"]
        raw_stderr = raw_sections["stderr"]

        if command_executed is True:
            sections["Command"] = raw_sections["Command"] or "unknown"
            sections["Exit code"] = raw_sections["Exit code"] or "unknown"

            stderr = raw_sections["stderr"]
            stdout = raw_sections["stdout"]
            if stderr and stdout:
                sections["stderr"] = stderr
                sections["stdout"] = stdout
            elif stderr:
                sections["stderr"] = stderr
            elif stdout:
                sections["stdout"] = stdout
            else:
                sections["stdout"] = ""
        elif command_executed is None:
            # Unknown execution state: use unknown-state copy contract per UX"
            # spec
            # Smart fields avoid command-failure phrasing
            sections["Command"] = "unknown"
            sections["Exit code"] = "unknown"
            # Preserve raw outputs in details textarea even when hidden from"
            # smart fields
            if raw_stdout:
                sections["stdout"] = raw_stdout
            if raw_stderr:
                sections["stderr"] = raw_stderr

        if raw_sections["Timestamp"]:
            sections["Timestamp"] = raw_sections["Timestamp"]

        return cls(sections=sections, parent=parent, command_executed=command_executed)


class StatusTray:
    """System tray icon with control row, profile rows, and overflow menus."""

    def __init__(
        self,
        parent: QWidget | None = None,
        on_toggle_monitoring: Callable[[bool], None] | None = None,
        on_quit: Callable[[], None] | None = None,
        on_show_diagnostics: Callable[[str, str], None] | None = None,
    ) -> None:
        self._parent = parent
        self._profiles: dict[str, ProfileStatus] = {}
        self._monitoring_enabled = True
        self._is_syncing = False
        self._global_error_summary: str | None = None
        self._global_error_details: str = ""
        self._global_error_is_config: bool = False
        self._ok_count = 0
        self._status_window: StatusWindowProxy | None = None
        self._details_dialog: ErrorDetailsDialog | None = None
        self.current_icon_state = "enabled-ok"

        self._on_toggle_monitoring = on_toggle_monitoring
        self._on_quit = on_quit
        self._on_show_diagnostics = on_show_diagnostics
        self._state_icons = self._build_state_icons()

        self.tray_icon = QSystemTrayIcon(parent)
        self.tray_icon.setIcon(self._state_icons[self.current_icon_state])
        self.tray_icon.setVisible(True)

        self._menu = QMenu(parent)
        self.tray_icon.setContextMenu(self._menu)

        self._tooltip_timer = QTimer()
        self._tooltip_timer.setSingleShot(True)
        self._tooltip_timer.timeout.connect(self._update_tooltip)

        self._rebuild_menu()
        self._update_icon_state()
        self._update_tooltip()

    def set_monitoring_enabled(self, enabled: bool) -> None:
        """Set monitoring state and refresh control row/icon state."""
        self._monitoring_enabled = enabled
        if self._on_toggle_monitoring is not None:
            self._on_toggle_monitoring(enabled)
        self._rebuild_menu()
        self._update_icon_state()
        self._throttled_tooltip_update()

    def set_syncing(self, syncing: bool) -> None:
        """Set global syncing flag used by first-row/icon semantics."""
        self._is_syncing = syncing
        self._rebuild_menu()
        self._update_icon_state()
        self._throttled_tooltip_update()

    def set_global_error(
        self, summary: str | None, details: str = "", is_config_error: bool = False
    ) -> None:
        """Set or clear first-row global error action state."""
        self._global_error_summary = summary
        self._global_error_details = details
        self._global_error_is_config = is_config_error
        self._rebuild_menu()
        self._update_icon_state()
        self._throttled_tooltip_update()

    def update_profile(self, status: ProfileStatus) -> None:
        """Update status for one profile and refresh visible tray state."""
        self._profiles[status.profile_name] = status

        if self._status_window is not None:
            self._status_window.update_profile(status)

        self._recount_ok_profiles()
        self._rebuild_menu()
        self._update_icon_state()
        self._throttled_tooltip_update()

    def remove_profile(self, profile_name: str) -> None:
        """Remove a profile and refresh visible tray state."""
        self._profiles.pop(profile_name, None)

        if self._status_window is not None:
            self._status_window.remove_profile(profile_name)

        self._recount_ok_profiles()
        self._rebuild_menu()
        self._update_icon_state()
        self._throttled_tooltip_update()

    def _recount_ok_profiles(self) -> None:
        ok_states = {ProfileState.OK, ProfileState.PAUSED_OK}
        self._ok_count = sum(
            1
            for status in self._profiles.values()
            if self._effective_state(status) in ok_states
        )

    def _update_icon_state(self) -> None:
        icon_state = self._compute_icon_state()
        self.current_icon_state = icon_state
        self.tray_icon.setIcon(self._state_icons[icon_state])

    def _build_state_icons(self) -> dict[str, QIcon]:
        """Build state icons from PNG files with multiple sizes for HiDPI support."""
        state_to_file = {
            "enabled-ok": "icon_normal.png",
            "enabled-syncing": "icon_working.png",
            "enabled-warning": "icon_warning.png",
            "enabled-error": "icon_error.png",
            "disabled-paused": "icon_paused.png",
        }

        icons_dir = self._get_icons_dir()
        state_icons = {}

        for state, filename in state_to_file.items():
            icon = self._load_multi_resolution_icon(icons_dir, filename)
            state_icons[state] = icon

        return state_icons

    def _get_icons_dir(self) -> str:
        """Get the directory containing icon files."""
        # Icons are stored in aws_sso_autologin/icons/ relative to this file
        module_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(module_dir, "icons")

    def _load_multi_resolution_icon(self, icons_dir: str, filename: str) -> QIcon:
        """Load an icon with multiple resolutions for HiDPI support.

        Loads icon files from size-specific subdirectories (32x32, 64x64, etc.)
        and combines them into a single QIcon for automatic resolution selection.
        """
        icon = QIcon()
        sizes = ["32x32", "64x64", "128x128", "256x256"]

        for size in sizes:
            icon_path = os.path.join(icons_dir, size, filename)
            if os.path.exists(icon_path):
                pixmap = QPixmap(icon_path)
                if not pixmap.isNull():
                    icon.addPixmap(pixmap)
                    logger.log(
                        5,
                        "Loaded icon",
                        extra={
                            "icon_file": filename,
                            "icon_size": size,
                            "icon_path": icon_path,
                        },
                    )
                else:
                    logger.warning(
                        "Failed to load icon pixmap",
                        extra={
                            "icon_file": filename,
                            "icon_size": size,
                            "icon_path": icon_path,
                        },
                    )
            else:
                logger.debug(
                    "Icon file not found",
                    extra={
                        "icon_file": filename,
                        "icon_size": size,
                        "icon_path": icon_path,
                    },
                )

        # Fallback: if no icons loaded, create a simple colored circle
        if icon.isNull():
            logger.warning(
                "No icon files loaded, using fallback",
                extra={"icon_file": filename},
            )
            icon = self._make_fallback_icon()

        return icon

    def _make_fallback_icon(self) -> QIcon:
        """Create a fallback icon when PNG files are not available."""
        size = 16
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#1f1f1f"), 1))
        painter.setBrush(QColor("#616161"))
        painter.drawEllipse(1, 1, size - 2, size - 2)
        painter.end()

        return QIcon(pixmap)

    def _compute_icon_state(self) -> str:
        if not self._monitoring_enabled:
            return "disabled-paused"

        if self._global_error_summary:
            return "enabled-error"

        states = {self._effective_state(status) for status in self._profiles.values()}
        if ProfileState.ERROR in states:
            return "enabled-error"
        if ProfileState.WARNING in states:
            return "enabled-warning"
        if self._is_syncing or ProfileState.SYNCING in states:
            return "enabled-syncing"
        return "enabled-ok"

    def _first_row_label(self) -> str:
        if self._global_error_summary:
            return "Show startup/sync error"
        if self._is_syncing:
            return "Synchronizing..."
        if self._monitoring_enabled:
            return "Disable auto-login"
        return "Enable auto-login"

    def _on_first_row_triggered(self) -> None:
        if self._global_error_summary:
            self._emit_diagnostics(
                self._global_error_summary,
                self._global_error_details or "No diagnostics available.",
                is_config_error=self._global_error_is_config,
            )
            return

        if self._is_syncing:
            return

        self.set_monitoring_enabled(not self._monitoring_enabled)

    def _rebuild_menu(self) -> None:
        self._menu.clear()

        first_action = QAction(self._first_row_label(), self._menu)
        if self._global_error_summary:
            first_action.setIcon(
                QApplication.style().standardIcon(QStyle.SP_MessageBoxCritical)
            )
        first_action.triggered.connect(self._on_first_row_triggered)
        if self._is_syncing and not self._global_error_summary:
            first_action.setEnabled(False)
        self._menu.addAction(first_action)
        self._menu.addSeparator()

        profile_names = sorted(self._profiles.keys(), key=str.lower)
        if profile_names:
            if len(profile_names) > MAX_PROFILES_IN_ROOT_MENU:
                self._add_overflow_submenus(profile_names)
            else:
                self._add_profile_rows(self._menu, profile_names)
            self._menu.addSeparator()

        quit_action = QAction("Quit", self._menu)
        quit_action.triggered.connect(self._on_quit_triggered)
        self._menu.addAction(quit_action)

    def _add_overflow_submenus(self, profile_names: list[str]) -> None:
        for index in range(0, len(profile_names), MAX_SUBMENU_PROFILES):
            chunk = profile_names[index : index + MAX_SUBMENU_PROFILES]
            start_idx = index + 1
            end_idx = index + len(chunk)
            submenu = QMenu(f"Profiles {start_idx}-{end_idx}", self._menu)
            self._add_profile_rows(submenu, chunk)
            self._menu.addMenu(submenu)

    def _add_profile_rows(self, menu: QMenu, profile_names: list[str]) -> None:
        for name in profile_names:
            status = self._profiles[name]
            action = QAction(self._format_profile_label(status), menu)
            action.triggered.connect(
                lambda checked=False, profile_name=name: self._on_profile_selected(
                    profile_name
                )
            )
            menu.addAction(action)

    def _on_profile_selected(self, profile_name: str) -> None:
        status = self._profiles[profile_name]
        state = self._effective_state(status)

        if state in (ProfileState.WARNING, ProfileState.ERROR):
            summary = status.diagnostics_summary or (
                f'Auto-login failed for profile "{profile_name}".'
                f" Click to view full diagnostics."
            )
            details = status.diagnostics_details or (
                "Summary: Auto-login failed for profile "
                f'"{profile_name}". Click to view full diagnostics.\n'
                "Incident evidence: Incident evidence unavailable:"
                " retention window exceeded.\n"
                "Command: sts_check\n"
                "Exit code: unknown\n"
                "stderr: unavailable\n"
                "stdout: unavailable\n"
                "Timestamp: unavailable"
            )
            self._emit_diagnostics(summary, details)
            return

        self._menu.hide()

    def _on_quit_triggered(self) -> None:
        if self._on_quit is not None:
            self._on_quit()

    def _emit_diagnostics(
        self, summary: str, details: str, is_config_error: bool = False
    ) -> None:
        if self._on_show_diagnostics is not None:
            self._on_show_diagnostics(summary, details, is_config_error)
            return

        self._details_dialog = ErrorDetailsDialog.from_text(
            summary=summary,
            details=details,
            parent=self._parent,
            is_config_error=is_config_error,
        )
        self._details_dialog.show()

    def _effective_state(self, status: ProfileStatus) -> ProfileState:
        if not self._monitoring_enabled and status.state == ProfileState.OK:
            return ProfileState.PAUSED_OK
        return status.state

    def _format_profile_label(self, status: ProfileStatus) -> str:
        state = self._effective_state(status)
        name = status.profile_name

        if state == ProfileState.SYNCING:
            return f"Profile: {name} - Syncing..."
        if state == ProfileState.WARNING:
            reason = status.short_reason or "Connectivity issue"
            return f"Profile: {name} - Warning: {reason}"
        if state == ProfileState.ERROR:
            reason = status.short_reason or "Command failed"
            return f"Profile: {name} - Error: {reason}"
        if state == ProfileState.PAUSED_OK:
            return f"Profile: {name} - OK (paused)"

        if status.last_login_time is None:
            return f"Profile: {name} - OK, last refresh: unknown"

        age = datetime.now() - status.last_login_time
        seconds = max(int(age.total_seconds()), 0)
        if seconds < 60:
            duration = f"{seconds}s ago"
        elif seconds < 3600:
            duration = f"{seconds // 60}m ago"
        else:
            duration = f"{seconds // 3600}h ago"

        return f"Profile: {name} - OK, last refresh: {duration}"

    def _update_tooltip(self) -> None:
        total = len(self._profiles)
        tooltip = (
            "AWS SSO Autologin\n"
            f"Profiles OK: {self._ok_count}/{total}\n"
            f"State: {self.current_icon_state}"
        )
        self.tray_icon.setToolTip(tooltip)

    def _throttled_tooltip_update(self) -> None:
        if not self._tooltip_timer.isActive():
            self._tooltip_timer.start(TOOLTIP_THROTTLE_MS)

    def close(self) -> None:
        """Clean up tray resources."""
        if self._tooltip_timer is not None:
            self._tooltip_timer.stop()

        if self._status_window is not None:
            self._status_window.close()
            self._status_window = None

        if self._details_dialog is not None:
            self._details_dialog.close()
            self._details_dialog = None

        if self.tray_icon is not None:
            self.tray_icon.setVisible(False)
            self.tray_icon = None
