"""Clean confirmation dialog for Cookie Cleaner.

Shows summary of what will be deleted and asks for user confirmation.
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
)
from PyQt6.QtCore import Qt

from src.core.models import DomainAggregate


class CleanConfirmationDialog(QDialog):
    """
    Dialog to confirm cookie deletion.

    Shows summary: "Delete X cookies from Y domains across Z profiles"
    """

    def __init__(
        self,
        domains: list[DomainAggregate],
        dry_run: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        """
        Initialize the confirmation dialog.

        Args:
            domains: List of DomainAggregate instances to delete
            dry_run: Whether this is a dry run
            parent: Parent widget
        """
        super().__init__(parent)
        self._domains = domains
        self._dry_run = dry_run
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle("Confirm Delete" if not self._dry_run else "Confirm Dry Run")
        self.setMinimumWidth(400)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Calculate summary stats
        total_cookies = sum(d.cookie_count for d in self._domains)
        total_domains = len(self._domains)
        browsers = set()
        profiles = set()
        for domain in self._domains:
            browsers.update(domain.browsers)
            for record in domain.records:
                profiles.add(f"{record.store.browser_name}/{record.store.profile_id}")

        # Warning message
        if self._dry_run:
            warning_text = "This will simulate deletion (no changes will be made):"
        else:
            warning_text = "This action will permanently delete the following cookies:"

        warning_label = QLabel(warning_text)
        warning_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(warning_label)

        # Summary group
        summary_group = QGroupBox("Summary")
        summary_layout = QVBoxLayout(summary_group)

        summary_layout.addWidget(QLabel(f"Cookies: {total_cookies:,}"))
        summary_layout.addWidget(QLabel(f"Domains: {total_domains:,}"))
        summary_layout.addWidget(QLabel(f"Browsers: {', '.join(sorted(browsers))}"))
        summary_layout.addWidget(QLabel(f"Profiles: {len(profiles)}"))

        layout.addWidget(summary_group)

        # Sample domains (show first 5)
        if self._domains:
            sample_group = QGroupBox("Sample Domains")
            sample_layout = QVBoxLayout(sample_group)

            for domain in self._domains[:5]:
                sample_layout.addWidget(
                    QLabel(f"  {domain.normalized_domain} ({domain.cookie_count})")
                )
            if len(self._domains) > 5:
                sample_layout.addWidget(
                    QLabel(f"  ... and {len(self._domains) - 5} more")
                )

            layout.addWidget(sample_group)

        # Dry run note
        if self._dry_run:
            note_label = QLabel("Dry run mode: A report will be generated but no cookies will be deleted.")
            note_label.setStyleSheet("color: blue; font-style: italic;")
            note_label.setWordWrap(True)
            layout.addWidget(note_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        confirm_text = "Delete" if not self._dry_run else "Run Simulation"
        confirm_btn = QPushButton(confirm_text)
        confirm_btn.setDefault(True)
        if not self._dry_run:
            confirm_btn.setStyleSheet("background-color: #d32f2f; color: white;")
        confirm_btn.clicked.connect(self.accept)
        button_layout.addWidget(confirm_btn)

        layout.addLayout(button_layout)
