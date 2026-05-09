"""System tray UI components."""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Callable
from datetime import datetime, timedelta

from PySide6.QtWidgets import (
    QSystemTrayIcon, QMenu, QWidget, QVBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QApplication
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon, QAction

from aws_sso_autologin.constants import STATUS_WINDOW_REFRESH_MS, TOOLTIP_THROTTLE_MS, PROFILE_MENU_LIMIT
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
        if self._window is not None:
            self._update_display()
    
    def remove_profile(self, profile_name: str) -> None:
        """Remove a profile from display."""
        if profile_name in self._profiles:
            del self._profiles[profile_name]
            if self._window is not None:
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


class StatusTray:
    """System tray icon with menu and status management.
    
    Implements the tray surface per UX spec with:
    - Single-item cache: "Logged In: N" (static)
    - Menu: Status Window, 25-item profile limit, overflow submenus
    - Tooltip: 5-second throttle, dynamic session minutes
    - Icon: static (same for all states in V1)
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        self._parent = parent
        self._profiles: Dict[str, ProfileStatus] = {}
        self._logged_in_count: int = 0
        self._status_window: Optional[StatusWindowProxy] = None
        
        # Create tray icon
        self.tray_icon = QSystemTrayIcon(parent)
        self._update_tooltip()
        self.tray_icon.setVisible(True)
        
        # Create context menu
        self._menu = QMenu(parent)
        self.tray_icon.setContextMenu(self._menu)
        
        # Tooltip throttle timer
        self._tooltip_timer = QTimer()
        self._tooltip_timer.setSingleShot(True)
        self._tooltip_timer.timeout.connect(self._update_tooltip)
        
        # Build initial menu
        self._rebuild_menu()
        
        logger.debug("StatusTray: Initialized")
    
    def _update_tooltip(self) -> None:
        """Update tray icon tooltip with logged-in count."""
        tooltip = f"AWS SSO Autologin\nLogged In: {self._logged_in_count}"
        self.tray_icon.setToolTip(tooltip)
    
    def _throttled_tooltip_update(self) -> None:
        """Schedule a tooltip update with 5-second throttle."""
        if not self._tooltip_timer.isActive():
            self._tooltip_timer.start(TOOLTIP_THROTTLE_MS)
    
    def _show_status_window(self) -> None:
        """Show the status window."""
        if self._status_window is None:
            self._status_window = StatusWindowProxy()
            # Sync existing profiles
            for status in self._profiles.values():
                self._status_window.update_profile(status)
        self._status_window.show()
    
    def _rebuild_menu(self) -> None:
        """Rebuild the context menu with current profiles."""
        self._menu.clear()
        
        # Status Window action
        status_action = QAction("Status Window", self._menu)
        status_action.triggered.connect(self._show_status_window)
        self._menu.addAction(status_action)
        
        self._menu.addSeparator()
        
        # Profile entries
        profile_names = sorted(self._profiles.keys(), key=str.lower)
        
        if len(profile_names) <= PROFILE_MENU_LIMIT:
            # All profiles fit in root menu
            for name in profile_names:
                status = self._profiles[name]
                action = QAction(self._format_profile_label(status), self._menu)
                self._menu.addAction(action)
        else:
            # Need overflow submenus
            self._build_overflow_menu(profile_names)
        
        self._menu.addSeparator()
        
        # Quit action
        quit_action = QAction("Quit", self._menu)
        self._menu.addAction(quit_action)
    
    def _build_overflow_menu(self, profile_names: List[str]) -> None:
        """Build menu with overflow submenus for high cardinality."""
        # Group profiles into chunks of PROFILE_MENU_LIMIT
        for i in range(0, len(profile_names), PROFILE_MENU_LIMIT):
            chunk = profile_names[i:i + PROFILE_MENU_LIMIT]
            start_idx = i + 1
            end_idx = min(i + PROFILE_MENU_LIMIT, len(profile_names))
            
            submenu = QMenu(f"Profiles {start_idx}-{end_idx}", self._menu)
            
            for name in chunk:
                status = self._profiles[name]
                action = QAction(self._format_profile_label(status), submenu)
                submenu.addAction(action)
            
            self._menu.addMenu(submenu)
    
    def _format_profile_label(self, status: ProfileStatus) -> str:
        """Format profile label for menu display."""
        if status.error_message:
            return f"Profile: {status.profile_name} - Error"
        elif status.is_logged_in:
            return f"Profile: {status.profile_name} - OK"
        else:
            return f"Profile: {status.profile_name} - Not Logged In"
    
    def update_profile(self, status: ProfileStatus) -> None:
        """Update status for a profile and rebuild menu if needed."""
        old_status = self._profiles.get(status.profile_name)
        self._profiles[status.profile_name] = status
        
        # Update logged-in count
        if old_status and old_status.is_logged_in:
            self._logged_in_count -= 1
        if status.is_logged_in:
            self._logged_in_count += 1
        
        # Throttled tooltip update
        self._throttled_tooltip_update()
        
        # Rebuild menu if profile count changes
        menu_needs_rebuild = (
            old_status is None or  # New profile
            (len(self._profiles) <= PROFILE_MENU_LIMIT) != (len(self._profiles) - (0 if old_status else 1) <= PROFILE_MENU_LIMIT)  # Overflow boundary crossed
        )
        
        if menu_needs_rebuild:
            self._rebuild_menu()
        else:
            # Just update status window
            if self._status_window:
                self._status_window.update_profile(status)
    
    def remove_profile(self, profile_name: str) -> None:
        """Remove a profile from the tray."""
        if profile_name in self._profiles:
            old_status = self._profiles[profile_name]
            if old_status.is_logged_in:
                self._logged_in_count -= 1
            del self._profiles[profile_name]
            self._throttled_tooltip_update()
            self._rebuild_menu()
    
    def close(self) -> None:
        """Clean up tray resources."""
        if self._tooltip_timer:
            self._tooltip_timer.stop()
        
        if self._status_window:
            self._status_window.close()
            self._status_window = None
        
        if self.tray_icon:
            self.tray_icon.setVisible(False)
            self.tray_icon = None
        
        logger.debug("StatusTray: Closed")
