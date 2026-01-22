"""Transfer controls widget for Cookie Cleaner.

Provides > and < buttons for moving items between lists.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSizePolicy
from PyQt6.QtCore import pyqtSignal


class TransferControls(QWidget):
    """
    Widget with > and < buttons for transferring items between lists.

    Emits signals when buttons are clicked.
    """

    move_right = pyqtSignal()  # > button clicked
    move_left = pyqtSignal()  # < button clicked

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the TransferControls widget."""
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(8)

        # Add stretch to center buttons vertically
        layout.addStretch()

        # Move right button (>)
        self._move_right_btn = QPushButton(">")
        self._move_right_btn.setFixedSize(32, 32)
        self._move_right_btn.setToolTip("Add selected to whitelist")
        self._move_right_btn.clicked.connect(self.move_right.emit)
        layout.addWidget(self._move_right_btn)

        # Move left button (<)
        self._move_left_btn = QPushButton("<")
        self._move_left_btn.setFixedSize(32, 32)
        self._move_left_btn.setToolTip("Remove selected from whitelist")
        self._move_left_btn.clicked.connect(self.move_left.emit)
        layout.addWidget(self._move_left_btn)

        # Add stretch to center buttons vertically
        layout.addStretch()

        # Set size policy
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def set_move_right_enabled(self, enabled: bool) -> None:
        """Enable or disable the move right button."""
        self._move_right_btn.setEnabled(enabled)

    def set_move_left_enabled(self, enabled: bool) -> None:
        """Enable or disable the move left button."""
        self._move_left_btn.setEnabled(enabled)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable both buttons."""
        self._move_right_btn.setEnabled(enabled)
        self._move_left_btn.setEnabled(enabled)
