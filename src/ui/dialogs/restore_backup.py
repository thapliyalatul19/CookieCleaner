"""Restore backup dialog for Cookie Cleaner.

Allows user to select and restore a cookie database backup.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
)
from PyQt6.QtCore import Qt

from src.execution import BackupManager


class RestoreBackupDialog(QDialog):
    """
    Dialog for selecting and restoring cookie database backups.

    Shows a table of available backups with browser, profile, and timestamp.
    """

    def __init__(
        self,
        backup_manager: BackupManager | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """
        Initialize the restore backup dialog.

        Args:
            backup_manager: BackupManager instance for listing/restoring backups
            parent: Parent widget
        """
        super().__init__(parent)
        self._backup_manager = backup_manager or BackupManager()
        self._selected_backup: Path | None = None
        self._setup_ui()
        self._load_backups()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle("Restore Backup")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Instructions
        instructions = QLabel(
            "Select a backup to restore. This will overwrite the current cookie database."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Table of backups
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Browser", "Profile", "Date/Time", "Size"])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._table)

        # Buttons
        button_layout = QHBoxLayout()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._load_backups)
        button_layout.addWidget(refresh_btn)

        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        self._restore_btn = QPushButton("Restore")
        self._restore_btn.setEnabled(False)
        self._restore_btn.clicked.connect(self._on_restore_clicked)
        button_layout.addWidget(self._restore_btn)

        layout.addLayout(button_layout)

    def _load_backups(self) -> None:
        """Load available backups into the table."""
        self._table.setRowCount(0)
        backups = self._backup_manager.list_backups()

        # Parse backup paths to extract browser/profile/timestamp
        backup_info = []
        for backup_path in backups:
            # Path format: {root}/{browser}/{profile}/{filename}.{timestamp}.bak
            parts = backup_path.parts
            if len(parts) >= 3:
                profile = parts[-2]
                browser = parts[-3]

                # Parse timestamp from filename
                filename = backup_path.name
                # Format: Cookies.20260121_143052.bak
                try:
                    timestamp_str = filename.rsplit(".", 2)[-2]
                    timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                except (ValueError, IndexError):
                    timestamp = datetime.fromtimestamp(backup_path.stat().st_mtime)

                # Get file size
                try:
                    size = backup_path.stat().st_size
                    size_str = self._format_size(size)
                except OSError:
                    size_str = "Unknown"

                backup_info.append((browser, profile, timestamp, size_str, backup_path))

        # Sort by timestamp (newest first)
        backup_info.sort(key=lambda x: x[2], reverse=True)

        # Populate table
        for browser, profile, timestamp, size_str, path in backup_info:
            row = self._table.rowCount()
            self._table.insertRow(row)

            self._table.setItem(row, 0, QTableWidgetItem(browser))
            self._table.setItem(row, 1, QTableWidgetItem(profile))
            self._table.setItem(row, 2, QTableWidgetItem(timestamp.strftime("%Y-%m-%d %H:%M:%S")))
            self._table.setItem(row, 3, QTableWidgetItem(size_str))

            # Store path in first column's data
            self._table.item(row, 0).setData(Qt.ItemDataRole.UserRole, str(path))

    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def _on_selection_changed(self) -> None:
        """Handle table selection change."""
        selected = self._table.selectedItems()
        if selected:
            path_str = self._table.item(selected[0].row(), 0).data(Qt.ItemDataRole.UserRole)
            self._selected_backup = Path(path_str) if path_str else None
            self._restore_btn.setEnabled(self._selected_backup is not None)
        else:
            self._selected_backup = None
            self._restore_btn.setEnabled(False)

    def _on_restore_clicked(self) -> None:
        """Handle restore button click."""
        if not self._selected_backup:
            return

        # Confirm restoration
        reply = QMessageBox.warning(
            self,
            "Confirm Restore",
            f"Are you sure you want to restore from:\n{self._selected_backup.name}\n\n"
            "This will overwrite the current cookie database.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.accept()

    def get_selected_backup(self) -> Path | None:
        """Return the selected backup path."""
        return self._selected_backup
