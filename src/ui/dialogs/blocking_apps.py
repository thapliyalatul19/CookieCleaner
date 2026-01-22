"""Blocking apps dialog for Cookie Cleaner.

Shows which browsers are locking cookie databases.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QListWidget,
    QListWidgetItem,
)
from PyQt6.QtCore import Qt, pyqtSignal

from src.execution import LockReport


# Dialog result code for "Close & Retry" action
CLOSE_AND_RETRY = 2


class BlockingAppsDialog(QDialog):
    """
    Dialog showing browser processes blocking cookie databases.

    Allows user to close browsers and retry, or manually close and retry.
    """

    # Signal emitted when user clicks "Close & Retry" with list of browser names
    close_browsers_requested = pyqtSignal(list)

    def __init__(
        self,
        lock_reports: list[LockReport],
        parent: QWidget | None = None,
    ) -> None:
        """
        Initialize the blocking apps dialog.

        Args:
            lock_reports: List of LockReport instances for locked databases
            parent: Parent widget
        """
        super().__init__(parent)
        self._lock_reports = lock_reports
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle("Browsers Running")
        self.setMinimumWidth(450)
        self.setMinimumHeight(300)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Check if any blockers are unknown
        has_unknown_blocker = any(r.blocker_unknown for r in self._lock_reports)

        # Warning message
        if has_unknown_blocker:
            warning_label = QLabel(
                "Some cookie databases are locked but the blocking application "
                "could not be identified.\n\n"
                "Please close all browsers and check for other applications that may "
                "be accessing the database files, such as:\n"
                "• Antivirus or security software\n"
                "• File indexing services (Windows Search, Everything)\n"
                "• Cloud sync tools (OneDrive, Dropbox, Google Drive)\n"
                "• Backup software"
            )
        else:
            warning_label = QLabel(
                "The following browsers are running and locking their cookie databases.\n"
                "Please close them before cleaning."
            )
        warning_label.setStyleSheet("color: #d32f2f; font-weight: bold;")
        warning_label.setWordWrap(True)
        layout.addWidget(warning_label)

        # List of blocking processes
        self._list_widget = QListWidget()

        # Collect unique blocking processes
        blocking_processes: dict[str, list[str]] = {}
        unknown_locks: list[str] = []

        for report in self._lock_reports:
            if report.blocker_unknown or not report.blocking_processes:
                unknown_locks.append(str(report.db_path))
            else:
                for process in report.blocking_processes:
                    if process not in blocking_processes:
                        blocking_processes[process] = []
                    blocking_processes[process].append(str(report.db_path))

        # Populate list with known blockers
        for process, paths in blocking_processes.items():
            item = QListWidgetItem(f"{process} (blocking {len(paths)} database(s))")
            item.setToolTip("\n".join(paths))
            self._list_widget.addItem(item)

        # Add unknown locks
        if unknown_locks:
            item = QListWidgetItem(f"Unknown process (blocking {len(unknown_locks)} database(s))")
            item.setToolTip("\n".join(unknown_locks))
            self._list_widget.addItem(item)

        layout.addWidget(self._list_widget)

        # Instructions
        if has_unknown_blocker:
            instructions = QLabel(
                "Options:\n"
                "• 'Retry' - Try again after closing the blocking application(s)\n"
                "• 'Cancel' - Abort the operation\n\n"
                "Note: 'Close Browsers & Retry' is disabled because the blocking "
                "application could not be identified. Try closing browsers and the "
                "applications listed above, then click Retry."
            )
        else:
            instructions = QLabel(
                "Options:\n"
                "• 'Close Browsers & Retry' - Automatically close blocking browsers and retry\n"
                "• 'Retry' - Try again after manually closing browsers\n"
                "• 'Cancel' - Abort the operation"
            )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        retry_btn = QPushButton("Retry")
        retry_btn.clicked.connect(self.accept)
        button_layout.addWidget(retry_btn)

        close_retry_btn = QPushButton("Close Browsers && Retry")
        close_retry_btn.clicked.connect(self._on_close_and_retry)
        button_layout.addWidget(close_retry_btn)

        # Disable auto-close when blocker is unknown (safety)
        if has_unknown_blocker or not blocking_processes:
            close_retry_btn.setEnabled(False)
            retry_btn.setDefault(True)
            retry_btn.setStyleSheet("font-weight: bold;")
        else:
            close_retry_btn.setDefault(True)
            close_retry_btn.setStyleSheet("font-weight: bold;")

        layout.addLayout(button_layout)

    def _on_close_and_retry(self) -> None:
        """Handle Close & Retry button click."""
        browsers = self.get_blocking_processes()
        self.close_browsers_requested.emit(browsers)
        self.done(CLOSE_AND_RETRY)

    def get_blocking_processes(self) -> list[str]:
        """Return list of blocking process names."""
        processes = set()
        for report in self._lock_reports:
            processes.update(report.blocking_processes)
        return list(processes)
