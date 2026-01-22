"""Settings dialog for Cookie Cleaner.

Allows user to configure application settings.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QGroupBox,
    QComboBox,
    QSpinBox,
    QCheckBox,
    QFormLayout,
)
from PyQt6.QtCore import Qt

from src.core.config import ConfigManager
from src.ui.styles.themes import THEMES


class SettingsDialog(QDialog):
    """
    Dialog for configuring application settings.

    Includes theme selection, backup retention, and confirmation options.
    """

    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """
        Initialize the settings dialog.

        Args:
            config_manager: ConfigManager for reading/writing settings
            parent: Parent widget
        """
        super().__init__(parent)
        self._config_manager = config_manager
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle("Settings")
        self.setMinimumWidth(400)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Appearance group
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QFormLayout(appearance_group)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems([t.capitalize() for t in THEMES])
        appearance_layout.addRow("Theme:", self._theme_combo)

        layout.addWidget(appearance_group)

        # Backup group
        backup_group = QGroupBox("Backups")
        backup_layout = QFormLayout(backup_group)

        self._retention_spin = QSpinBox()
        self._retention_spin.setMinimum(1)
        self._retention_spin.setMaximum(365)
        self._retention_spin.setSuffix(" days")
        backup_layout.addRow("Retention period:", self._retention_spin)

        layout.addWidget(backup_group)

        # Behavior group
        behavior_group = QGroupBox("Behavior")
        behavior_layout = QVBoxLayout(behavior_group)

        self._confirm_checkbox = QCheckBox("Confirm before cleaning")
        behavior_layout.addWidget(self._confirm_checkbox)

        layout.addWidget(behavior_group)

        # Add stretch
        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save_clicked)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

    def _load_settings(self) -> None:
        """Load current settings into the UI."""
        if not self._config_manager:
            return

        settings = self._config_manager.settings

        # Theme
        theme = settings.get("theme", "system")
        index = THEMES.index(theme) if theme in THEMES else 0
        self._theme_combo.setCurrentIndex(index)

        # Backup retention
        retention = settings.get("backup_retention_days", 7)
        self._retention_spin.setValue(retention)

        # Confirm before clean
        confirm = settings.get("confirm_before_clean", True)
        self._confirm_checkbox.setChecked(confirm)

    def _on_save_clicked(self) -> None:
        """Handle save button click."""
        if self._config_manager:
            self._config_manager.update_settings(
                theme=THEMES[self._theme_combo.currentIndex()],
                backup_retention_days=self._retention_spin.value(),
                confirm_before_clean=self._confirm_checkbox.isChecked(),
            )
            self._config_manager.save()
        self.accept()

    def get_theme(self) -> str:
        """Return the selected theme."""
        return THEMES[self._theme_combo.currentIndex()]

    def get_retention_days(self) -> int:
        """Return the selected retention period in days."""
        return self._retention_spin.value()

    def get_confirm_before_clean(self) -> bool:
        """Return whether to confirm before cleaning."""
        return self._confirm_checkbox.isChecked()
