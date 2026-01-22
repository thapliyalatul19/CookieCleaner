"""Transactional cookie deletion executor for Cookie Cleaner.

SAFETY CONTRACT:
- DELETE statements are ONLY executed in this module
- Lock check MUST pass before any backup or delete
- Backup MUST succeed before any DELETE statement
- All DELETEs are wrapped in BEGIN IMMEDIATE / COMMIT
- Any failure triggers ROLLBACK + restore from backup
- dry_run=True skips backup creation and DELETE execution
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from src.core.models import DeletePlan, DeleteOperation, DeleteTarget
from src.execution.lock_resolver import LockResolver
from src.execution.backup_manager import BackupManager

logger = logging.getLogger(__name__)


@dataclass
class DeleteResult:
    """Result of a delete operation on a single browser profile."""

    browser: str
    profile: str
    deleted_count: int
    success: bool
    error: str | None = None
    backup_path: Path | None = None


@dataclass
class DeleteReport:
    """Complete report of a delete plan execution."""

    plan_id: str
    dry_run: bool
    results: list[DeleteResult] = field(default_factory=list)
    total_deleted: int = 0
    total_failed: int = 0

    @property
    def success(self) -> bool:
        """Return True if all operations succeeded."""
        return self.total_failed == 0


class DeleteExecutor:
    """
    Executes cookie deletion with mandatory safety checks.

    Transaction Flow:
    1. LockResolver.check_lock() → Abort if locked
    2. BackupManager.create_backup() → Abort if backup fails
    3. BEGIN IMMEDIATE transaction
    4. Execute DELETE for each target
    5. COMMIT (or ROLLBACK on error)
    6. Return DeleteResult
    """

    def __init__(
        self,
        lock_resolver: LockResolver | None = None,
        backup_manager: BackupManager | None = None,
    ) -> None:
        """
        Initialize the DeleteExecutor.

        Args:
            lock_resolver: LockResolver instance. Creates new one if None.
            backup_manager: BackupManager instance. Creates new one if None.
        """
        self.lock_resolver = lock_resolver or LockResolver()
        self.backup_manager = backup_manager or BackupManager()

    def execute(self, plan: DeletePlan, dry_run: bool = False) -> DeleteReport:
        """
        Execute a deletion plan.

        Args:
            plan: DeletePlan containing operations to execute
            dry_run: If True, simulate without making changes

        Returns:
            DeleteReport with results for each operation
        """
        report = DeleteReport(plan_id=plan.plan_id, dry_run=dry_run)

        for operation in plan.operations:
            result = self._execute_operation(operation, dry_run)
            report.results.append(result)

            if result.success:
                report.total_deleted += result.deleted_count
            else:
                report.total_failed += 1

        return report

    def _execute_operation(self, op: DeleteOperation, dry_run: bool) -> DeleteResult:
        """
        Execute a single delete operation.

        Args:
            op: DeleteOperation for a single browser profile
            dry_run: If True, simulate without making changes

        Returns:
            DeleteResult with operation outcome
        """
        # Step 1: Check if database is locked
        lock_report = self.lock_resolver.check_lock(op.db_path)
        if lock_report.is_locked:
            processes = ", ".join(lock_report.blocking_processes) or "unknown process"
            error = f"Database locked by {processes}"
            logger.warning("Cannot delete from %s: %s", op.db_path, error)
            return DeleteResult(
                browser=op.browser,
                profile=op.profile,
                deleted_count=0,
                success=False,
                error=error,
            )

        # Step 2: Create backup (skip for dry run)
        backup_path = None
        if not dry_run:
            backup_result = self.backup_manager.create_backup(
                op.db_path, op.browser, op.profile
            )
            if not backup_result.success:
                error = f"Backup failed: {backup_result.error}"
                logger.error("Cannot delete from %s: %s", op.db_path, error)
                return DeleteResult(
                    browser=op.browser,
                    profile=op.profile,
                    deleted_count=0,
                    success=False,
                    error=error,
                )
            backup_path = backup_result.backup_path

        # Determine if this is a Chromium or Firefox database
        is_chromium = self._is_chromium_db(op.db_path)

        # Step 3-5: Execute deletion within transaction
        if dry_run:
            # Dry run: just count what would be deleted
            deleted_count = self._count_targets(op, is_chromium)
            logger.info(
                "DRY RUN: Would delete %d cookies from %s/%s",
                deleted_count, op.browser, op.profile
            )
            return DeleteResult(
                browser=op.browser,
                profile=op.profile,
                deleted_count=deleted_count,
                success=True,
            )

        # Real execution
        try:
            deleted_count = self._execute_deletes(op, is_chromium)
            logger.info(
                "Deleted %d cookies from %s/%s",
                deleted_count, op.browser, op.profile
            )
            return DeleteResult(
                browser=op.browser,
                profile=op.profile,
                deleted_count=deleted_count,
                success=True,
                backup_path=backup_path,
            )
        except Exception as e:
            error = str(e)
            logger.error("Delete failed for %s/%s: %s", op.browser, op.profile, error)

            # Attempt restoration from backup
            if backup_path:
                logger.info("Attempting restoration from backup: %s", backup_path)
                if self.backup_manager.restore_backup(backup_path, op.db_path):
                    logger.info("Successfully restored from backup")
                else:
                    logger.error("Failed to restore from backup!")

            return DeleteResult(
                browser=op.browser,
                profile=op.profile,
                deleted_count=0,
                success=False,
                error=error,
                backup_path=backup_path,
            )

    def _execute_deletes(self, op: DeleteOperation, is_chromium: bool) -> int:
        """
        Execute DELETE statements within a transaction.

        Args:
            op: DeleteOperation with targets
            is_chromium: True for Chromium schema, False for Firefox

        Returns:
            Total number of rows deleted
        """
        total_deleted = 0

        conn = sqlite3.connect(str(op.db_path), timeout=5.0)
        try:
            cursor = conn.cursor()

            # Use IMMEDIATE to acquire write lock at transaction start
            cursor.execute("BEGIN IMMEDIATE")

            try:
                for target in op.targets:
                    sql = self._build_delete_sql(target, is_chromium)
                    cursor.execute(sql, (target.match_pattern,))
                    total_deleted += cursor.rowcount

                cursor.execute("COMMIT")
            except Exception:
                cursor.execute("ROLLBACK")
                raise
        finally:
            conn.close()

        return total_deleted

    def _count_targets(self, op: DeleteOperation, is_chromium: bool) -> int:
        """
        Count cookies that would be deleted (for dry run).

        Args:
            op: DeleteOperation with targets
            is_chromium: True for Chromium schema, False for Firefox

        Returns:
            Total count of cookies that would be deleted
        """
        if not op.db_path.exists():
            return sum(t.count for t in op.targets)

        total_count = 0

        try:
            conn = sqlite3.connect(str(op.db_path), timeout=5.0)
            try:
                cursor = conn.cursor()
                for target in op.targets:
                    sql = self._build_count_sql(target, is_chromium)
                    cursor.execute(sql, (target.match_pattern,))
                    result = cursor.fetchone()
                    total_count += result[0] if result else 0
            finally:
                conn.close()
        except sqlite3.Error:
            # Fall back to target counts if database is inaccessible
            total_count = sum(t.count for t in op.targets)

        return total_count

    def _build_delete_sql(self, target: DeleteTarget, is_chromium: bool) -> str:
        """
        Build DELETE SQL statement for a target.

        Args:
            target: DeleteTarget with match pattern
            is_chromium: True for Chromium schema, False for Firefox

        Returns:
            DELETE SQL statement with placeholder
        """
        if is_chromium:
            return "DELETE FROM cookies WHERE host_key LIKE ?"
        else:
            return "DELETE FROM moz_cookies WHERE host LIKE ?"

    def _build_count_sql(self, target: DeleteTarget, is_chromium: bool) -> str:
        """
        Build SELECT COUNT SQL statement for a target.

        Args:
            target: DeleteTarget with match pattern
            is_chromium: True for Chromium schema, False for Firefox

        Returns:
            SELECT COUNT SQL statement with placeholder
        """
        if is_chromium:
            return "SELECT COUNT(*) FROM cookies WHERE host_key LIKE ?"
        else:
            return "SELECT COUNT(*) FROM moz_cookies WHERE host LIKE ?"

    def _is_chromium_db(self, db_path: Path) -> bool:
        """
        Determine if a database is Chromium or Firefox format.

        Args:
            db_path: Path to the database

        Returns:
            True if Chromium (has 'cookies' table), False if Firefox
        """
        if not db_path.exists():
            # Infer from path
            path_lower = str(db_path).lower()
            return "firefox" not in path_lower and "mozilla" not in path_lower

        try:
            conn = sqlite3.connect(str(db_path), timeout=5.0)
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='cookies'"
                )
                has_cookies_table = cursor.fetchone() is not None
                return has_cookies_table
            finally:
                conn.close()
        except sqlite3.Error:
            # Fall back to path inference
            path_lower = str(db_path).lower()
            return "firefox" not in path_lower and "mozilla" not in path_lower
