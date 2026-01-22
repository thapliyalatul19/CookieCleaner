"""Background clean worker for Cookie Cleaner.

Runs cookie deletion in a separate thread to prevent UI blocking.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from src.core.models import (
    DomainAggregate,
    DeletePlan,
    DeleteOperation,
    DeleteTarget,
)
from src.execution import LockResolver, LockReport, DeleteExecutor, DeleteReport

logger = logging.getLogger(__name__)


class CleanWorker(QThread):
    """
    Background worker for deleting cookies.

    Checks locks, creates backups, and executes deletion plan.
    """

    progress = pyqtSignal(str, int, int)  # (message, current, total)
    finished = pyqtSignal(object)  # DeleteReport
    lock_detected = pyqtSignal(list)  # list[LockReport]
    error = pyqtSignal(str, str)  # (error_type, error_message)

    def __init__(
        self,
        domains_to_delete: list[DomainAggregate] | None = None,
        dry_run: bool = False,
        parent=None,
    ) -> None:
        """
        Initialize the CleanWorker.

        Args:
            domains_to_delete: List of DomainAggregate instances to delete
            dry_run: If True, simulate deletion without making changes
            parent: Parent QObject
        """
        super().__init__(parent)
        self._domains = domains_to_delete or []
        self._dry_run = dry_run
        self._cancelled = False
        self._lock_resolver = LockResolver()
        self._delete_executor = DeleteExecutor()

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
            error: Error details if clean fails
        """
        self._cancelled = False

        try:
            if not self._domains:
                self.progress.emit("No domains to delete", 0, 0)
                report = DeleteReport(plan_id="empty", dry_run=self._dry_run)
                self.finished.emit(report)
                return

            # Step 1: Build delete plan
            self.progress.emit("Building delete plan...", 0, 0)
            plan = self._build_plan()

            if not plan.operations:
                self.progress.emit("No operations to execute", 0, 0)
                report = DeleteReport(plan_id=plan.plan_id, dry_run=self._dry_run)
                self.finished.emit(report)
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

            # Emit completion
            self.progress.emit(
                f"Clean complete: {report.total_deleted} cookies deleted",
                total_ops,
                total_ops,
            )
            self.finished.emit(report)

        except Exception as e:
            logger.exception("Clean failed with error")
            self.error.emit(type(e).__name__, str(e))

    def _build_plan(self) -> DeletePlan:
        """
        Build a DeletePlan from the domains to delete.

        Groups cookies by browser/profile and creates operations.

        Returns:
            DeletePlan with operations for each browser profile
        """
        plan = DeletePlan.create(dry_run=self._dry_run)

        # Group records by (browser, profile, db_path)
        profile_records: dict[tuple, list] = defaultdict(list)

        for domain in self._domains:
            for record in domain.records:
                key = (
                    record.store.browser_name,
                    record.store.profile_id,
                    record.store.db_path,
                )
                profile_records[key].append(record)

        # Create operations for each profile
        for (browser, profile, db_path), records in profile_records.items():
            # Group by domain to create targets
            domain_counts: dict[str, int] = defaultdict(int)
            for record in records:
                domain_counts[record.raw_host_key] += 1

            targets = []
            for host_key, count in domain_counts.items():
                # Build SQL LIKE pattern
                if host_key.startswith("."):
                    pattern = f"%{host_key}"
                else:
                    pattern = host_key
                targets.append(DeleteTarget(
                    normalized_domain=host_key.lstrip("."),
                    match_pattern=pattern,
                    count=count,
                ))

            # Determine backup path (used by BackupManager)
            backup_path = Path(".")  # Placeholder, BackupManager generates actual path

            operation = DeleteOperation(
                browser=browser,
                profile=profile,
                db_path=db_path,
                backup_path=backup_path,
                targets=targets,
            )
            plan.add_operation(operation)

        return plan
