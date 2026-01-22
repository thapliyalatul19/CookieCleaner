"""Error dialog for Cookie Cleaner.

Displays error messages and allows user acknowledgment.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QTextEdit,
)
from PyQt6.QtCore import Qt


class ErrorDialog(QDialog):
    """
    Dialog for displaying error messages.

    Shows error type, message, and optional details.
    """

    def __init__(
        self,
        error_type: str,
        error_message: str,
        details: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """
        Initialize the error dialog.

        Args:
            error_type: Type/name of the error
            error_message: Main error message
            details: Optional detailed error information
            parent: Parent widget
        """
        super().__init__(parent)
        self._error_type = error_type
        self._error_message = error_message
        self._details = details
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle("Error")
        self.setMinimumWidth(450)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Error icon and type
        header_layout = QHBoxLayout()

        error_icon = QLabel("\u26A0")  # Warning sign
        error_icon.setStyleSheet("font-size: 24px; color: #d32f2f;")
        header_layout.addWidget(error_icon)

        type_label = QLabel(self._error_type)
        type_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #d32f2f;")
        header_layout.addWidget(type_label)

        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Error message
        message_label = QLabel(self._error_message)
        message_label.setWordWrap(True)
        layout.addWidget(message_label)

        # Details (if provided)
        if self._details:
            details_label = QLabel("Details:")
            details_label.setStyleSheet("font-weight: bold;")
            layout.addWidget(details_label)

            details_text = QTextEdit()
            details_text.setPlainText(self._details)
            details_text.setReadOnly(True)
            details_text.setMaximumHeight(150)
            layout.addWidget(details_text)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)

    @staticmethod
    def show_error(
        error_type: str,
        error_message: str,
        details: str | None = None,
        parent: QWidget | None = None,
    ) -> int:
        """
        Convenience method to show an error dialog.

        Args:
            error_type: Type/name of the error
            error_message: Main error message
            details: Optional detailed error information
            parent: Parent widget

        Returns:
            Dialog result (QDialog.DialogCode)
        """
        dialog = ErrorDialog(error_type, error_message, details, parent)
        return dialog.exec()
