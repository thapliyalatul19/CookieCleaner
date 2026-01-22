"""Main toolbar widget for Cookie Cleaner.

Provides Scan, Clean, Settings, Restore actions and Dry Run checkbox.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QToolBar, QWidget, QCheckBox, QSizePolicy
from PyQt6.QtGui import QAction
from PyQt6.QtCore import pyqtSignal


class MainToolbar(QToolBar):
    """
    Main toolbar with scan, clean, settings, and restore actions.

    Includes a dry run checkbox that affects clean behavior.
    """

    scan_triggered = pyqtSignal()
    clean_triggered = pyqtSignal()
    settings_triggered = pyqtSignal()
    restore_triggered = pyqtSignal()
    dry_run_changed = pyqtSignal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the MainToolbar."""
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the toolbar UI."""
        self.setMovable(False)
        self.setFloatable(False)

        # Scan action
        self._scan_action = QAction("Scan", self)
        self._scan_action.setToolTip("Scan all browsers for cookies")
        self._scan_action.triggered.connect(self.scan_triggered.emit)
        self.addAction(self._scan_action)

        # Clean action
        self._clean_action = QAction("Clean", self)
        self._clean_action.setToolTip("Delete non-whitelisted cookies")
        self._clean_action.setEnabled(False)  # Disabled until scan completes
        self._clean_action.triggered.connect(self.clean_triggered.emit)
        self.addAction(self._clean_action)

        self.addSeparator()

        # Settings action
        self._settings_action = QAction("Settings", self)
        self._settings_action.setToolTip("Open settings dialog")
        self._settings_action.triggered.connect(self.settings_triggered.emit)
        self.addAction(self._settings_action)

        # Restore action
        self._restore_action = QAction("Restore", self)
        self._restore_action.setToolTip("Restore cookies from backup")
        self._restore_action.triggered.connect(self.restore_triggered.emit)
        self.addAction(self._restore_action)

        # Add spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)

        # Dry run checkbox
        self._dry_run_checkbox = QCheckBox("Dry Run")
        self._dry_run_checkbox.setToolTip(
            "Simulate deletion without making changes (generates report only)"
        )
        self._dry_run_checkbox.stateChanged.connect(self._on_dry_run_changed)
        self.addWidget(self._dry_run_checkbox)

    def _on_dry_run_changed(self, state: int) -> None:
        """Handle dry run checkbox state change."""
        self.dry_run_changed.emit(state != 0)

    @property
    def scan_action(self) -> QAction:
        """Return the scan action."""
        return self._scan_action

    @property
    def clean_action(self) -> QAction:
        """Return the clean action."""
        return self._clean_action

    @property
    def settings_action(self) -> QAction:
        """Return the settings action."""
        return self._settings_action

    @property
    def restore_action(self) -> QAction:
        """Return the restore action."""
        return self._restore_action

    def is_dry_run(self) -> bool:
        """Return True if dry run mode is enabled."""
        return self._dry_run_checkbox.isChecked()

    def set_dry_run(self, enabled: bool) -> None:
        """Set the dry run checkbox state."""
        self._dry_run_checkbox.setChecked(enabled)

    def set_scan_enabled(self, enabled: bool) -> None:
        """Enable or disable the scan action."""
        self._scan_action.setEnabled(enabled)

    def set_clean_enabled(self, enabled: bool) -> None:
        """Enable or disable the clean action."""
        self._clean_action.setEnabled(enabled)

    def set_all_enabled(self, enabled: bool) -> None:
        """Enable or disable all actions."""
        self._scan_action.setEnabled(enabled)
        self._clean_action.setEnabled(enabled)
        self._settings_action.setEnabled(enabled)
        self._restore_action.setEnabled(enabled)
        self._dry_run_checkbox.setEnabled(enabled)
