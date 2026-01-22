"""Delete plan validation for Cookie Cleaner.

Validates DeletePlan instances before execution to catch errors early.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from src.core.models import DeletePlan
from src.core.whitelist import WhitelistManager

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
    """

    def __init__(self, whitelist_manager: WhitelistManager | None = None) -> None:
        """
        Initialize the validator.

        Args:
            whitelist_manager: Optional WhitelistManager for checking overlap
        """
        self._whitelist_manager = whitelist_manager

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
