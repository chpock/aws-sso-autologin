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
