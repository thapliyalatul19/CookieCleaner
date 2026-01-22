"""Status bar widget for Cookie Cleaner.

Displays application state, domain count, and cookie count.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QStatusBar, QLabel, QWidget, QProgressBar
from PyQt6.QtCore import Qt

from src.ui.state_machine import AppState


class CookieStatusBar(QStatusBar):
    """
    Custom status bar showing state, domain count, and cookie count.

    Layout: [State] | [Domain Count] | [Cookie Count] | [Progress]
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the CookieStatusBar."""
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the status bar UI."""
        # State label
        self._state_label = QLabel("IDLE")
        self._state_label.setMinimumWidth(80)
        self.addWidget(self._state_label)

        # Separator
        self.addWidget(self._create_separator())

        # Domain count label
        self._domain_label = QLabel("0 domains")
        self._domain_label.setMinimumWidth(100)
        self.addWidget(self._domain_label)

        # Separator
        self.addWidget(self._create_separator())

        # Cookie count label
        self._cookie_label = QLabel("0 cookies")
        self._cookie_label.setMinimumWidth(100)
        self.addWidget(self._cookie_label)

        # Progress bar (hidden by default)
        self._progress_bar = QProgressBar()
        self._progress_bar.setMaximumWidth(150)
        self._progress_bar.setMaximumHeight(16)
        self._progress_bar.hide()
        self.addPermanentWidget(self._progress_bar)

    def _create_separator(self) -> QLabel:
        """Create a separator label."""
        sep = QLabel("|")
        sep.setStyleSheet("color: gray;")
        return sep

    def set_state(self, state: AppState) -> None:
        """
        Update the displayed state.

        Args:
            state: The current application state
        """
        state_text = state.value.upper()
        self._state_label.setText(state_text)

        # Update styling based on state
        if state == AppState.ERROR:
            self._state_label.setStyleSheet("color: red; font-weight: bold;")
        elif state == AppState.SCANNING or state == AppState.CLEANING:
            self._state_label.setStyleSheet("color: blue;")
        elif state == AppState.READY:
            self._state_label.setStyleSheet("color: green;")
        else:
            self._state_label.setStyleSheet("")

        # Show/hide progress bar
        if state in (AppState.SCANNING, AppState.CLEANING):
            self._progress_bar.setRange(0, 0)  # Indeterminate
            self._progress_bar.show()
        else:
            self._progress_bar.hide()

    def set_counts(self, domain_count: int, cookie_count: int) -> None:
        """
        Update the displayed counts.

        Args:
            domain_count: Number of domains
            cookie_count: Number of cookies
        """
        self._domain_label.setText(f"{domain_count:,} domains")
        self._cookie_label.setText(f"{cookie_count:,} cookies")

    def set_progress(self, current: int, total: int) -> None:
        """
        Update the progress bar.

        Args:
            current: Current progress value
            total: Maximum progress value (0 for indeterminate)
        """
        if total <= 0:
            self._progress_bar.setRange(0, 0)  # Indeterminate
        else:
            self._progress_bar.setRange(0, total)
            self._progress_bar.setValue(current)
        self._progress_bar.show()

    def show_message(self, message: str, timeout: int = 3000) -> None:
        """
        Show a temporary message in the status bar.

        Args:
            message: Message to display
            timeout: Display time in milliseconds
        """
        self.showMessage(message, timeout)

    def clear_counts(self) -> None:
        """Reset counts to zero."""
        self.set_counts(0, 0)
