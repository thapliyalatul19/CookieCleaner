"""Delete plan validation for Cookie Cleaner.

Validates DeletePlan instances before execution to catch errors early.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from src.core.models import DeletePlan, DeleteOperation
from src.core.whitelist import WhitelistManager
from src.scanner.db_copy import copy_db_to_temp, cleanup_temp_db

logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    """A single validation error."""

    code: str
    message: str
    operation_index: int | None = None
    target_index: int | None = None


@dataclass
class ValidationResult:
    """Result of plan validation."""

    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)

    def add_error(
        self,
        code: str,
        message: str,
        operation_index: int | None = None,
        target_index: int | None = None,
    ) -> None:
        """Add a validation error."""
        self.errors.append(ValidationError(code, message, operation_index, target_index))
        self.is_valid = False

    def add_warning(
        self,
        code: str,
        message: str,
        operation_index: int | None = None,
        target_index: int | None = None,
    ) -> None:
        """Add a validation warning."""
        self.warnings.append(ValidationError(code, message, operation_index, target_index))


class DeletePlanValidator:
    """
    Validates DeletePlan instances before execution.

    Checks:
    - Database paths exist
    - Target counts are positive
    - No overlap with whitelist entries
    - Optional: DB count verification
    """

    def __init__(
        self,
        whitelist_manager: WhitelistManager | None = None,
        verify_counts: bool = False,
    ) -> None:
        """
        Initialize the validator.

        Args:
            whitelist_manager: Optional WhitelistManager for checking overlap
            verify_counts: If True, verify target counts match database
        """
        self._whitelist_manager = whitelist_manager
        self._verify_counts = verify_counts

    def validate(self, plan: DeletePlan) -> ValidationResult:
        """
        Validate a DeletePlan.

        Args:
            plan: The DeletePlan to validate

        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult(is_valid=True)

        if not plan.operations:
            result.add_warning("EMPTY_PLAN", "Plan has no operations to execute")
            return result

        for op_idx, operation in enumerate(plan.operations):
            # Check database path exists
            if not operation.db_path.exists():
                result.add_error(
                    "DB_NOT_FOUND",
                    f"Database not found: {operation.db_path}",
                    operation_index=op_idx,
                )
                continue

            # Check targets
            if not operation.targets:
                result.add_warning(
                    "NO_TARGETS",
                    f"Operation {op_idx} ({operation.browser}/{operation.profile}) has no targets",
                    operation_index=op_idx,
                )
                continue

            for target_idx, target in enumerate(operation.targets):
                # Check count is positive
                if target.count <= 0:
                    result.add_error(
                        "INVALID_COUNT",
                        f"Target count must be positive: {target.normalized_domain} has count={target.count}",
                        operation_index=op_idx,
                        target_index=target_idx,
                    )

                # Check whitelist overlap
                if self._whitelist_manager:
                    if self._whitelist_manager.is_whitelisted(target.normalized_domain):
                        result.add_error(
                            "WHITELIST_OVERLAP",
                            f"Target '{target.normalized_domain}' is whitelisted and should not be deleted",
                            operation_index=op_idx,
                            target_index=target_idx,
                        )

            # Optional: Verify counts match database (uses temp copy for safety)
            if self._verify_counts:
                count_mismatches = self._verify_db_counts(operation)
                for target_idx, (expected, actual) in count_mismatches:
                    target = operation.targets[target_idx]
                    # Count mismatches are errors - stale data could lead to wrong deletions
                    result.add_error(
                        "COUNT_MISMATCH",
                        f"Target '{target.normalized_domain}' count mismatch: "
                        f"expected {expected}, found {actual} in database",
                        operation_index=op_idx,
                        target_index=target_idx,
                    )

        if result.errors:
            logger.warning(
                "Plan validation failed with %d errors: %s",
                len(result.errors),
                [e.message for e in result.errors],
            )
        elif result.warnings:
            logger.info(
                "Plan validation passed with %d warnings: %s",
                len(result.warnings),
                [w.message for w in result.warnings],
            )
        else:
            logger.debug("Plan validation passed for plan %s", plan.plan_id)

        return result

    def _verify_db_counts(
        self, operation: DeleteOperation
    ) -> list[tuple[int, tuple[int, int]]]:
        """
        Verify target counts match actual database counts.

        Uses a temporary copy of the database to avoid locking issues
        when the browser is running.

        Args:
            operation: DeleteOperation to verify

        Returns:
            List of (target_index, (expected_count, actual_count)) for mismatches
        """
        mismatches = []

        if not operation.db_path.exists():
            return mismatches

        temp_db = None
        try:
            # Copy database to temp location for safe reading
            temp_db = copy_db_to_temp(operation.db_path)
            conn = sqlite3.connect(str(temp_db), timeout=5.0)
            try:
                cursor = conn.cursor()

                # Determine if Chromium or Firefox
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='cookies'"
                )
                is_chromium = cursor.fetchone() is not None

                for target_idx, target in enumerate(operation.targets):
                    if is_chromium:
                        sql = "SELECT COUNT(*) FROM cookies WHERE host_key LIKE ?"
                    else:
                        sql = "SELECT COUNT(*) FROM moz_cookies WHERE host LIKE ?"

                    cursor.execute(sql, (target.match_pattern,))
                    result = cursor.fetchone()
                    actual_count = result[0] if result else 0

                    if actual_count != target.count:
                        mismatches.append((target_idx, (target.count, actual_count)))

            finally:
                conn.close()
        except (sqlite3.Error, OSError) as e:
            logger.warning("Could not verify counts for %s: %s", operation.db_path, e)
        finally:
            # Always clean up the temp database
            if temp_db is not None:
                cleanup_temp_db(temp_db)

        return mismatches
