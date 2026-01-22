"""Background clean worker for Cookie Cleaner.

Runs cookie deletion in a separate thread to prevent UI blocking.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from src.core.constants import BACKUPS_DIR
from src.core.models import DomainAggregate, DeletePlan
from src.core.delete_planner import DeletePlanner
from src.core.delete_plan_validator import DeletePlanValidator
from src.core.whitelist import WhitelistManager
from src.core.logging_config import log_clean_operation
from src.execution import (
    LockResolver,
    LockReport,
    DeleteExecutor,
    DeleteReport,
    ProcessGateError,
)

logger = logging.getLogger(__name__)


class CleanWorker(QThread):
    """
    Background worker for deleting cookies.

    Checks locks, creates backups, and executes deletion plan.
    """

    progress = pyqtSignal(str, int, int)  # (message, current, total)
    finished = pyqtSignal(object)  # DeleteReport
    lock_detected = pyqtSignal(list)  # list[LockReport]
    browsers_running = pyqtSignal(list)  # list[str] of browser executables blocking operation
    error = pyqtSignal(str, str)  # (error_type, error_message)

    def __init__(
        self,
        domains_to_delete: list[DomainAggregate] | None = None,
        dry_run: bool = False,
        whitelist_manager: WhitelistManager | None = None,
        parent=None,
    ) -> None:
        """
        Initialize the CleanWorker.

        Args:
            domains_to_delete: List of DomainAggregate instances to delete
            dry_run: If True, simulate deletion without making changes
            whitelist_manager: Optional WhitelistManager for plan validation
            parent: Parent QObject
        """
        super().__init__(parent)
        self._domains = domains_to_delete or []
        self._dry_run = dry_run
        self._cancelled = False
        self._lock_resolver = LockResolver()
        self._delete_executor = DeleteExecutor()
        self._planner = DeletePlanner(backup_root=BACKUPS_DIR)
        self._validator = DeletePlanValidator(whitelist_manager, verify_counts=True)

    def set_domains(self, domains: list[DomainAggregate]) -> None:
        """Set the domains to delete."""
        self._domains = domains

    def set_dry_run(self, dry_run: bool) -> None:
        """Set the dry run mode."""
        self._dry_run = dry_run

    def cancel(self) -> None:
        """Request cancellation of the clean operation."""
        self._cancelled = True

    def run(self) -> None:
        """
        Execute the clean operation in a background thread.

        Emits:
            progress: Status messages during clean
            finished: DeleteReport with results
            lock_detected: List of LockReports if databases are locked
            browsers_running: List of browser executables if process gate fails
            error: Error details if clean fails
        """
        self._cancelled = False

        try:
            # NOTE: Browser process gate is now enforced by DeleteExecutor.execute()
            # which raises ProcessGateError if any target browser is running.
            # This ensures the gate cannot be bypassed by calling executor directly.

            if not self._domains:
                self.progress.emit("No domains to delete", 0, 0)
                report = DeleteReport(plan_id="empty", dry_run=self._dry_run)
                self.finished.emit(report)
                return

            # Step 1: Build delete plan
            self.progress.emit("Building delete plan...", 0, 0)
            plan = self._planner.build_plan(self._domains, dry_run=self._dry_run)

            if not plan.operations:
                self.progress.emit("No operations to execute", 0, 0)
                report = DeleteReport(plan_id=plan.plan_id, dry_run=self._dry_run)
                self.finished.emit(report)
                return

            # Step 1.5: Validate plan
            self.progress.emit("Validating delete plan...", 0, 0)
            validation = self._validator.validate(plan)

            if not validation.is_valid:
                error_msgs = [e.message for e in validation.errors]
                self.error.emit("ValidationError", "; ".join(error_msgs))
                return

            # Step 2: Check for locks
            self.progress.emit("Checking database locks...", 0, 0)
            db_paths = [op.db_path for op in plan.operations]
            lock_reports = self._lock_resolver.check_all(db_paths)

            locked_reports = [r for r in lock_reports if r.is_locked]
            if locked_reports:
                self.lock_detected.emit(locked_reports)
                return

            if self._cancelled:
                self.progress.emit("Clean cancelled", 0, 0)
                return

            # Step 3: Execute the plan
            mode = "DRY RUN" if self._dry_run else "DELETING"
            total_ops = len(plan.operations)

            for i, op in enumerate(plan.operations):
                if self._cancelled:
                    self.progress.emit("Clean cancelled", i, total_ops)
                    return

                self.progress.emit(
                    f"{mode}: {op.browser}/{op.profile}",
                    i + 1,
                    total_ops,
                )

            # Execute the full plan
            self.progress.emit(
                f"{'Simulating' if self._dry_run else 'Executing'} delete plan...",
                0,
                total_ops,
            )
            report = self._delete_executor.execute(plan, dry_run=self._dry_run)

            # Log to audit log
            cookie_count = report.total_would_delete if self._dry_run else report.total_deleted
            if cookie_count > 0 or not self._dry_run:
                log_clean_operation(
                    domains_deleted=[t.normalized_domain for op in plan.operations for t in op.targets],
                    cookie_count=cookie_count,
                    browsers_affected=list({op.browser for op in plan.operations}),
                    dry_run=self._dry_run,
                )

            # Emit completion
            if self._dry_run:
                self.progress.emit(
                    f"Dry run complete: {report.total_would_delete} cookies would be deleted",
                    total_ops,
                    total_ops,
                )
            else:
                self.progress.emit(
                    f"Clean complete: {report.total_deleted} cookies deleted",
                    total_ops,
                    total_ops,
                )
            self.finished.emit(report)

        except ProcessGateError as e:
            # Browser process gate failed - user must close browsers
            logger.warning("Process gate error: %s", e)
            self.browsers_running.emit(e.running_browsers)
        except Exception as e:
            logger.exception("Clean failed with error")
            self.error.emit(type(e).__name__, str(e))

