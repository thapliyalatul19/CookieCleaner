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

        # Warning message
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
        for report in self._lock_reports:
            for process in report.blocking_processes:
                if process not in blocking_processes:
                    blocking_processes[process] = []
                blocking_processes[process].append(str(report.db_path))

        # Populate list
        for process, paths in blocking_processes.items():
            item = QListWidgetItem(f"{process} (blocking {len(paths)} database(s))")
            item.setToolTip("\n".join(paths))
            self._list_widget.addItem(item)

        layout.addWidget(self._list_widget)

        # Instructions
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
        close_retry_btn.setDefault(True)
        close_retry_btn.setStyleSheet("font-weight: bold;")
        close_retry_btn.clicked.connect(self._on_close_and_retry)
        button_layout.addWidget(close_retry_btn)

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
