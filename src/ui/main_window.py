"""Main window for Cookie Cleaner.

Central UI orchestration component with dual-pane layout.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QMessageBox,
    QApplication,
)
from PyQt6.QtCore import Qt

from src.core.config import ConfigManager
from src.core.constants import APP_NAME, APP_VERSION
from src.core.models import DomainAggregate
from src.core.whitelist import WhitelistManager
from src.execution import BackupManager, LockReport, DeleteReport, LockResolver

from src.ui.state_machine import AppState, StateManager, InvalidTransitionError
from src.ui.app import apply_theme
from src.ui.widgets import (
    SearchableListWidget,
    TransferControls,
    MainToolbar,
    CookieStatusBar,
)
from src.ui.workers import ScanWorker, CleanWorker
from src.ui.dialogs import (
    CleanConfirmationDialog,
    BlockingAppsDialog,
    CLOSE_AND_RETRY,
    RestoreBackupDialog,
    SettingsDialog,
    ErrorDialog,
)

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """
    Main application window with dual-pane layout.

    Layout:
        +--------------------------------------------------+
        | [Scan] [Clean] [Settings] [Restore]  [ ] Dry Run |
        +--------------------------------------------------+
        |                    |    |                        |
        | Cookies to Delete  | >  | Cookies to Keep        |
        | [Search________]   | <  | [Search________]       |
        | - domain1.com (3)  |    | - domain:google.com    |
        | - domain2.com (5)  |    | - exact:auth.site.com  |
        |                    |    |                        |
        +--------------------------------------------------+
        | READY | 150 domains | 2,340 cookies              |
        +--------------------------------------------------+
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the MainWindow."""
        super().__init__(parent)

        # Initialize managers
        self._config_manager = ConfigManager()
        self._whitelist_manager = WhitelistManager(self._config_manager.whitelist)
        self._backup_manager = BackupManager()
        self._lock_resolver = LockResolver()
        self._state_manager = StateManager(self)

        # Scan results storage
        self._scan_results: list[DomainAggregate] = []
        self._domains_to_delete: list[DomainAggregate] = []

        # Workers
        self._scan_worker: ScanWorker | None = None
        self._clean_worker: CleanWorker | None = None

        # Setup UI
        self._setup_ui()
        self._connect_signals()
        self._apply_theme()

    def _setup_ui(self) -> None:
        """Set up the main window UI."""
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(800, 600)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # Toolbar
        self._toolbar = MainToolbar(self)
        self.addToolBar(self._toolbar)

        # Main content area with dual panes
        content_layout = QHBoxLayout()
        content_layout.setSpacing(8)

        # Left pane - Cookies to Delete
        self._left_pane = SearchableListWidget(
            title="Cookies to Delete",
            placeholder="Search domains...",
        )
        content_layout.addWidget(self._left_pane, stretch=1)

        # Transfer controls
        self._transfer_controls = TransferControls()
        content_layout.addWidget(self._transfer_controls)

        # Right pane - Whitelist (Cookies to Keep)
        self._right_pane = SearchableListWidget(
            title="Cookies to Keep (Whitelist)",
            placeholder="Search whitelist...",
        )
        content_layout.addWidget(self._right_pane, stretch=1)

        main_layout.addLayout(content_layout)

        # Status bar
        self._status_bar = CookieStatusBar(self)
        self.setStatusBar(self._status_bar)

        # Load whitelist into right pane
        self._refresh_whitelist_display()

    def _connect_signals(self) -> None:
        """Connect signals and slots."""
        # Toolbar signals
        self._toolbar.scan_triggered.connect(self._on_scan_clicked)
        self._toolbar.clean_triggered.connect(self._on_clean_clicked)
        self._toolbar.settings_triggered.connect(self._on_settings_clicked)
        self._toolbar.restore_triggered.connect(self._on_restore_clicked)

        # Transfer controls
        self._transfer_controls.move_right.connect(self._on_add_to_whitelist)
        self._transfer_controls.move_left.connect(self._on_remove_from_whitelist)

        # Double-click transfers
        self._left_pane.item_double_clicked.connect(self._on_left_item_double_clicked)
        self._right_pane.item_double_clicked.connect(self._on_right_item_double_clicked)

        # Selection changes for button enablement
        self._left_pane.selection_changed.connect(self._update_transfer_buttons)
        self._right_pane.selection_changed.connect(self._update_transfer_buttons)

        # State changes
        self._state_manager.state_changed.connect(self._on_state_changed)

    def _apply_theme(self) -> None:
        """Apply the configured theme."""
        theme = self._config_manager.settings.get("theme", "system")
        app = QApplication.instance()
        if app:
            apply_theme(app, theme)

    def _refresh_whitelist_display(self) -> None:
        """Refresh the whitelist pane display."""
        entries = self._whitelist_manager.get_entries()
        self._right_pane.set_whitelist_items(entries)

    def _update_transfer_buttons(self) -> None:
        """Update transfer button enabled states based on selection."""
        self._transfer_controls.set_move_right_enabled(self._left_pane.has_selection())
        self._transfer_controls.set_move_left_enabled(self._right_pane.has_selection())

    def _on_state_changed(self, state: AppState) -> None:
        """Handle state change events."""
        self._status_bar.set_state(state)

        # Update button states based on new state
        if state == AppState.IDLE:
            self._toolbar.set_scan_enabled(True)
            self._toolbar.set_clean_enabled(False)
            self._transfer_controls.set_enabled(False)
        elif state == AppState.SCANNING:
            self._toolbar.set_scan_enabled(False)
            self._toolbar.set_clean_enabled(False)
            self._transfer_controls.set_enabled(False)
        elif state == AppState.READY:
            self._toolbar.set_scan_enabled(True)
            self._toolbar.set_clean_enabled(len(self._domains_to_delete) > 0)
            self._transfer_controls.set_enabled(True)
            self._update_transfer_buttons()
        elif state == AppState.CLEANING:
            self._toolbar.set_scan_enabled(False)
            self._toolbar.set_clean_enabled(False)
            self._transfer_controls.set_enabled(False)
        elif state == AppState.ERROR:
            self._toolbar.set_scan_enabled(True)  # Allow scan to retry after error
            self._toolbar.set_clean_enabled(False)
            self._transfer_controls.set_enabled(False)

    # === Scan Operations ===

    def _on_scan_clicked(self) -> None:
        """Handle scan button click."""
        try:
            self._state_manager.start_scan()
        except InvalidTransitionError:
            return

        # Clear previous results
        self._left_pane.clear()
        self._scan_results = []
        self._domains_to_delete = []
        self._status_bar.clear_counts()

        # Create and start scan worker
        self._scan_worker = ScanWorker(self._whitelist_manager, self)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.start()

    def _on_scan_progress(self, message: str) -> None:
        """Handle scan progress updates."""
        self._status_bar.show_message(message)

    def _on_scan_finished(self, results: list[DomainAggregate]) -> None:
        """Handle scan completion."""
        self._scan_results = results
        self._domains_to_delete = results.copy()

        # Populate left pane
        items = [(d.normalized_domain, d.cookie_count) for d in self._domains_to_delete]
        self._left_pane.set_items(items)

        # Update counts
        total_cookies = sum(d.cookie_count for d in self._domains_to_delete)
        self._status_bar.set_counts(len(self._domains_to_delete), total_cookies)

        try:
            self._state_manager.scan_complete()
        except InvalidTransitionError as e:
            logger.error("Failed to complete scan state: %s", e)

    def _on_scan_error(self, error_type: str, error_message: str) -> None:
        """Handle scan error."""
        try:
            self._state_manager.scan_error(error_message)
        except InvalidTransitionError:
            pass

        ErrorDialog.show_error(error_type, error_message, parent=self)
        self._state_manager.acknowledge_error()

    # === Clean Operations ===

    def _on_clean_clicked(self) -> None:
        """Handle clean button click."""
        if not self._domains_to_delete:
            return

        dry_run = self._toolbar.is_dry_run()

        # Check if confirmation is required
        if self._config_manager.settings.get("confirm_before_clean", True):
            dialog = CleanConfirmationDialog(
                self._domains_to_delete, dry_run=dry_run, parent=self
            )
            if dialog.exec() != CleanConfirmationDialog.DialogCode.Accepted:
                return

        try:
            self._state_manager.start_clean()
        except InvalidTransitionError:
            return

        # Create and start clean worker
        self._clean_worker = CleanWorker(
            self._domains_to_delete,
            dry_run,
            whitelist_manager=self._whitelist_manager,
            parent=self,
        )
        self._clean_worker.progress.connect(self._on_clean_progress)
        self._clean_worker.finished.connect(self._on_clean_finished)
        self._clean_worker.lock_detected.connect(self._on_lock_detected)
        self._clean_worker.browsers_running.connect(self._on_browsers_running)
        self._clean_worker.error.connect(self._on_clean_error)
        self._clean_worker.start()

    def _on_clean_progress(self, message: str, current: int, total: int) -> None:
        """Handle clean progress updates."""
        self._status_bar.show_message(message)
        if total > 0:
            self._status_bar.set_progress(current, total)

    def _on_clean_finished(self, report: DeleteReport) -> None:
        """Handle clean completion."""
        try:
            self._state_manager.clean_complete()
        except InvalidTransitionError as e:
            logger.error("Failed to complete clean state: %s", e)

        # Show completion message
        if report.dry_run:
            msg = f"Dry run complete: {report.total_would_delete} cookies would be deleted."
        else:
            msg = f"Clean complete: {report.total_deleted} cookies deleted."

        if report.total_failed > 0:
            msg += f"\n{report.total_failed} operation(s) failed."

        QMessageBox.information(self, "Clean Complete", msg)

        # Refresh scan to show updated state
        if not report.dry_run and report.total_deleted > 0:
            self._on_scan_clicked()

    def _on_lock_detected(self, lock_reports: list[LockReport]) -> None:
        """Handle locked database detection."""
        # Return to READY state for retry
        try:
            self._state_manager.clean_complete()
        except InvalidTransitionError:
            pass

        dialog = BlockingAppsDialog(lock_reports, parent=self)
        result = dialog.exec()

        if result == CLOSE_AND_RETRY:
            # User wants to close browsers and retry
            browsers = dialog.get_blocking_processes()
            self._close_browsers_and_retry(browsers)
        elif result == BlockingAppsDialog.DialogCode.Accepted:
            # User wants to retry after manually closing browsers
            self._on_clean_clicked()
        # else: user cancelled

    def _on_browsers_running(self, browsers: list[str]) -> None:
        """Handle preflight detection of running browsers."""
        # Return to READY state
        try:
            self._state_manager.clean_complete()
        except InvalidTransitionError:
            pass

        # Show dialog with blocking browsers
        browser_names = ", ".join(browsers)
        result = QMessageBox.warning(
            self,
            "Browsers Running",
            f"The following browsers are running and have cookies to delete:\n\n"
            f"{browser_names}\n\n"
            "Please close these browsers to continue cleaning cookies.",
            QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Abort,
            QMessageBox.StandardButton.Abort,
        )

        if result == QMessageBox.StandardButton.Retry:
            # User closed browsers manually and wants to retry
            self._on_clean_clicked()
        # else: user chose to abort

    def _close_browsers_and_retry(self, browsers: list[str]) -> None:
        """
        Close blocking browsers and retry the clean operation.

        Args:
            browsers: List of browser executable names to terminate
        """
        if not browsers:
            self._on_clean_clicked()
            return

        # Show progress message
        self._status_bar.show_message("Closing browsers...")

        # Terminate each browser
        failed_browsers = []
        for browser in browsers:
            if not self._lock_resolver.terminate_browser(browser):
                failed_browsers.append(browser)

        if failed_browsers:
            QMessageBox.warning(
                self,
                "Could Not Close Browsers",
                f"Failed to close the following browsers:\n"
                f"{', '.join(failed_browsers)}\n\n"
                "Please close them manually and try again.",
            )
            return

        # Wait briefly for file handles to be released
        import time
        time.sleep(0.5)

        # Retry the clean operation
        self._status_bar.show_message("Retrying clean operation...")
        self._on_clean_clicked()

    def _on_clean_error(self, error_type: str, error_message: str) -> None:
        """Handle clean error."""
        try:
            self._state_manager.clean_error(error_message)
        except InvalidTransitionError:
            pass

        ErrorDialog.show_error(error_type, error_message, parent=self)
        self._state_manager.acknowledge_error()

    # === Whitelist Operations ===

    def _on_add_to_whitelist(self) -> None:
        """Add selected domains to whitelist."""
        selected = self._left_pane.get_selected_items()
        if not selected:
            return

        for domain in selected:
            # Add as domain: prefix for recursive matching
            entry = f"domain:{domain}"
            success, error = self._whitelist_manager.add_entry(entry)
            if not success:
                logger.warning("Failed to add whitelist entry '%s': %s", entry, error)

        # Save whitelist
        self._config_manager.set_whitelist(self._whitelist_manager.get_entries())
        self._config_manager.save()

        # Refresh displays
        self._refresh_whitelist_display()
        self._refresh_delete_list()

    def _on_remove_from_whitelist(self) -> None:
        """Remove selected entries from whitelist."""
        selected = self._right_pane.get_selected_items()
        if not selected:
            return

        for entry in selected:
            self._whitelist_manager.remove_entry(entry)

        # Save whitelist
        self._config_manager.set_whitelist(self._whitelist_manager.get_entries())
        self._config_manager.save()

        # Refresh displays
        self._refresh_whitelist_display()
        self._refresh_delete_list()

    def _on_left_item_double_clicked(self, domain: str) -> None:
        """Handle double-click on left pane item."""
        self._left_pane.clear_selection()
        # Find and select the item, then add to whitelist
        for i in range(self._left_pane._list_widget.count()):
            item = self._left_pane._list_widget.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == domain:
                item.setSelected(True)
                break
        self._on_add_to_whitelist()

    def _on_right_item_double_clicked(self, entry: str) -> None:
        """Handle double-click on right pane item."""
        self._right_pane.clear_selection()
        # Find and select the item, then remove from whitelist
        for i in range(self._right_pane._list_widget.count()):
            item = self._right_pane._list_widget.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == entry:
                item.setSelected(True)
                break
        self._on_remove_from_whitelist()

    def _refresh_delete_list(self) -> None:
        """Refresh the delete list after whitelist changes."""
        # Re-filter scan results with updated whitelist
        self._domains_to_delete = [
            d for d in self._scan_results
            if not self._whitelist_manager.is_whitelisted(d.normalized_domain)
        ]

        # Update left pane
        items = [(d.normalized_domain, d.cookie_count) for d in self._domains_to_delete]
        self._left_pane.set_items(items)

        # Update counts
        total_cookies = sum(d.cookie_count for d in self._domains_to_delete)
        self._status_bar.set_counts(len(self._domains_to_delete), total_cookies)

        # Update clean button state
        self._toolbar.set_clean_enabled(len(self._domains_to_delete) > 0)

    # === Settings and Restore ===

    def _on_settings_clicked(self) -> None:
        """Handle settings button click."""
        dialog = SettingsDialog(self._config_manager, parent=self)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted:
            # Apply new theme
            self._apply_theme()

    def _on_restore_clicked(self) -> None:
        """Handle restore button click."""
        dialog = RestoreBackupDialog(self._backup_manager, parent=self)
        if dialog.exec() == RestoreBackupDialog.DialogCode.Accepted:
            backup_path = dialog.get_selected_backup()
            if backup_path:
                self._restore_backup(backup_path)

    def _restore_backup(self, backup_path: Path) -> None:
        """
        Restore a cookie database from backup.

        Args:
            backup_path: Path to the backup file
        """
        # Try to get original path from metadata
        original_path = self._backup_manager.get_original_path(backup_path)

        # Fall back to path inference for old backups without metadata
        if original_path is None:
            original_path = self._infer_original_path(backup_path)

        if original_path is None:
            QMessageBox.warning(
                self,
                "Restore Failed",
                "Could not determine original database location from backup.\n\n"
                "This backup may have been created by an older version without metadata.",
            )
            return

        # Get metadata for display
        metadata = self._backup_manager.get_backup_metadata(backup_path)
        browser = metadata.get("browser", "Unknown") if metadata else "Unknown"
        profile = metadata.get("profile", "Unknown") if metadata else "Unknown"
        created_at = metadata.get("created_at", "Unknown") if metadata else "Unknown"

        # Confirm with user
        confirm = QMessageBox.question(
            self,
            "Confirm Restore",
            f"Restore backup to:\n{original_path}\n\n"
            f"Browser: {browser}\n"
            f"Profile: {profile}\n"
            f"Created: {created_at}\n\n"
            "This will replace the current cookie database. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        # Perform restoration
        success = self._backup_manager.restore_backup(backup_path, original_path)

        if success:
            QMessageBox.information(
                self,
                "Restore Complete",
                f"Successfully restored backup to:\n{original_path}",
            )
        else:
            QMessageBox.critical(
                self,
                "Restore Failed",
                f"Failed to restore backup.\n\n"
                f"Target path: {original_path}\n\n"
                "Check that the browser is not running and try again.",
            )

    def _infer_original_path(self, backup_path: Path) -> Path | None:
        """
        Infer original database path from backup path structure.

        Fallback for old backups without metadata.
        Path format: {backup_root}/{browser}/{profile}/{filename}.{timestamp}.bak

        Args:
            backup_path: Path to the backup file

        Returns:
            Inferred original path, or None if cannot be determined
        """
        import os

        # Get browser and profile from directory structure
        parts = backup_path.parts
        if len(parts) < 3:
            return None

        browser = parts[-3]
        profile = parts[-2]

        # Extract original filename from backup name
        # Format: Cookies.20260120_143052.bak -> Cookies
        filename = backup_path.name
        if ".bak" in filename:
            # Remove .bak and timestamp
            base_parts = filename.rsplit(".", 3)
            if len(base_parts) >= 3:
                original_filename = base_parts[0]
            else:
                return None
        else:
            return None

        # Map browser name to user data path
        appdata_local = Path(os.environ.get("LOCALAPPDATA", ""))
        appdata_roaming = Path(os.environ.get("APPDATA", ""))

        browser_paths = {
            "Chrome": appdata_local / "Google" / "Chrome" / "User Data",
            "Edge": appdata_local / "Microsoft" / "Edge" / "User Data",
            "Brave": appdata_local / "BraveSoftware" / "Brave-Browser" / "User Data",
            "Opera": appdata_local / "Opera Software" / "Opera Stable",  # Opera uses LOCALAPPDATA
            "Vivaldi": appdata_local / "Vivaldi" / "User Data",
            "Firefox": appdata_roaming / "Mozilla" / "Firefox" / "Profiles",
        }

        user_data = browser_paths.get(browser)
        if user_data is None or not user_data.exists():
            return None

        # Build full path
        if browser == "Firefox":
            # Firefox: {profiles}/{profile}/cookies.sqlite
            profile_dir = user_data / profile
        else:
            # Chromium: {user_data}/{profile}/Network/Cookies or {user_data}/{profile}/Cookies
            profile_dir = user_data / profile

        if not profile_dir.exists():
            return None

        # Try modern path first, then legacy
        modern_path = profile_dir / "Network" / original_filename
        legacy_path = profile_dir / original_filename

        if modern_path.parent.exists():
            return modern_path
        elif legacy_path.parent.exists():
            return legacy_path

        return None

    def closeEvent(self, event) -> None:
        """Handle window close event."""
        # Cancel any running workers
        if self._scan_worker and self._scan_worker.isRunning():
            self._scan_worker.cancel()
            self._scan_worker.wait()

        if self._clean_worker and self._clean_worker.isRunning():
            self._clean_worker.cancel()
            self._clean_worker.wait()

        event.accept()
