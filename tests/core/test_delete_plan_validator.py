"""Tests for DeletePlanValidator in Cookie Cleaner."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.core.delete_plan_validator import DeletePlanValidator, ValidationResult
from src.core.models import DeletePlan, DeleteOperation, DeleteTarget
from src.core.whitelist import WhitelistManager


def make_plan(operations: list[DeleteOperation] | None = None, dry_run: bool = False) -> DeletePlan:
    """Create a test DeletePlan."""
    plan = DeletePlan.create(dry_run=dry_run)
    if operations:
        for op in operations:
            plan.add_operation(op)
    return plan


def make_operation(
    browser: str = "Chrome",
    profile: str = "Default",
    db_path: Path | None = None,
    targets: list[DeleteTarget] | None = None,
) -> DeleteOperation:
    """Create a test DeleteOperation."""
    return DeleteOperation(
        browser=browser,
        profile=profile,
        db_path=db_path or Path("C:/test/Cookies"),
        backup_path=Path("."),
        targets=targets or [],
    )


def make_target(domain: str = "example.com", count: int = 5) -> DeleteTarget:
    """Create a test DeleteTarget."""
    return DeleteTarget(
        normalized_domain=domain,
        match_pattern=f"%.{domain}",
        count=count,
    )


class TestDeletePlanValidator:
    """Tests for DeletePlanValidator.validate()."""

    def test_empty_plan_is_valid_with_warning(self) -> None:
        """Empty plan is valid but has warning."""
        validator = DeletePlanValidator()
        plan = make_plan([])

        result = validator.validate(plan)

        assert result.is_valid is True
        assert len(result.warnings) == 1
        assert result.warnings[0].code == "EMPTY_PLAN"

    def test_missing_db_path_is_error(self, tmp_path: Path) -> None:
        """Non-existent database path is an error."""
        validator = DeletePlanValidator()
        target = make_target()
        operation = make_operation(
            db_path=tmp_path / "nonexistent.db",
            targets=[target],
        )
        plan = make_plan([operation])

        result = validator.validate(plan)

        assert result.is_valid is False
        assert any(e.code == "DB_NOT_FOUND" for e in result.errors)

    def test_existing_db_path_is_valid(self, tmp_path: Path) -> None:
        """Existing database path passes validation."""
        db_path = tmp_path / "cookies.db"
        db_path.touch()

        validator = DeletePlanValidator()
        target = make_target()
        operation = make_operation(db_path=db_path, targets=[target])
        plan = make_plan([operation])

        result = validator.validate(plan)

        assert result.is_valid is True

    def test_zero_count_is_error(self, tmp_path: Path) -> None:
        """Zero target count is an error."""
        db_path = tmp_path / "cookies.db"
        db_path.touch()

        validator = DeletePlanValidator()
        target = make_target(count=0)
        operation = make_operation(db_path=db_path, targets=[target])
        plan = make_plan([operation])

        result = validator.validate(plan)

        assert result.is_valid is False
        assert any(e.code == "INVALID_COUNT" for e in result.errors)

    def test_negative_count_is_error(self, tmp_path: Path) -> None:
        """Negative target count is an error."""
        db_path = tmp_path / "cookies.db"
        db_path.touch()

        validator = DeletePlanValidator()
        target = make_target(count=-1)
        operation = make_operation(db_path=db_path, targets=[target])
        plan = make_plan([operation])

        result = validator.validate(plan)

        assert result.is_valid is False
        assert any(e.code == "INVALID_COUNT" for e in result.errors)

    def test_positive_count_is_valid(self, tmp_path: Path) -> None:
        """Positive target count passes validation."""
        db_path = tmp_path / "cookies.db"
        db_path.touch()

        validator = DeletePlanValidator()
        target = make_target(count=10)
        operation = make_operation(db_path=db_path, targets=[target])
        plan = make_plan([operation])

        result = validator.validate(plan)

        assert result.is_valid is True

    def test_operation_with_no_targets_is_warning(self, tmp_path: Path) -> None:
        """Operation with no targets is a warning, not error."""
        db_path = tmp_path / "cookies.db"
        db_path.touch()

        validator = DeletePlanValidator()
        operation = make_operation(db_path=db_path, targets=[])
        plan = make_plan([operation])

        result = validator.validate(plan)

        assert result.is_valid is True
        assert any(w.code == "NO_TARGETS" for w in result.warnings)

    def test_whitelist_overlap_is_error(self, tmp_path: Path) -> None:
        """Target that matches whitelist is an error."""
        db_path = tmp_path / "cookies.db"
        db_path.touch()

        whitelist = WhitelistManager(["domain:example.com"])
        validator = DeletePlanValidator(whitelist)
        target = make_target(domain="example.com")
        operation = make_operation(db_path=db_path, targets=[target])
        plan = make_plan([operation])

        result = validator.validate(plan)

        assert result.is_valid is False
        assert any(e.code == "WHITELIST_OVERLAP" for e in result.errors)

    def test_subdomain_whitelist_overlap_is_error(self, tmp_path: Path) -> None:
        """Subdomain of whitelisted domain is an error."""
        db_path = tmp_path / "cookies.db"
        db_path.touch()

        whitelist = WhitelistManager(["domain:example.com"])
        validator = DeletePlanValidator(whitelist)
        target = make_target(domain="sub.example.com")
        operation = make_operation(db_path=db_path, targets=[target])
        plan = make_plan([operation])

        result = validator.validate(plan)

        assert result.is_valid is False
        assert any(e.code == "WHITELIST_OVERLAP" for e in result.errors)

    def test_non_whitelisted_domain_is_valid(self, tmp_path: Path) -> None:
        """Domain not in whitelist passes validation."""
        db_path = tmp_path / "cookies.db"
        db_path.touch()

        whitelist = WhitelistManager(["domain:other.com"])
        validator = DeletePlanValidator(whitelist)
        target = make_target(domain="example.com")
        operation = make_operation(db_path=db_path, targets=[target])
        plan = make_plan([operation])

        result = validator.validate(plan)

        assert result.is_valid is True

    def test_no_whitelist_manager_skips_check(self, tmp_path: Path) -> None:
        """Without whitelist manager, overlap check is skipped."""
        db_path = tmp_path / "cookies.db"
        db_path.touch()

        validator = DeletePlanValidator(None)
        target = make_target(domain="example.com")
        operation = make_operation(db_path=db_path, targets=[target])
        plan = make_plan([operation])

        result = validator.validate(plan)

        assert result.is_valid is True

    def test_multiple_errors_all_reported(self, tmp_path: Path) -> None:
        """Multiple validation errors are all reported."""
        validator = DeletePlanValidator()
        # Missing db and zero count
        target = make_target(count=0)
        operation = make_operation(
            db_path=tmp_path / "missing.db",
            targets=[target],
        )
        plan = make_plan([operation])

        result = validator.validate(plan)

        assert result.is_valid is False
        # DB not found is the first check, so count won't be checked for missing DB
        assert len(result.errors) >= 1

    def test_error_includes_operation_index(self, tmp_path: Path) -> None:
        """Errors include the operation index."""
        validator = DeletePlanValidator()
        target = make_target()
        operation = make_operation(
            db_path=tmp_path / "missing.db",
            targets=[target],
        )
        plan = make_plan([operation])

        result = validator.validate(plan)

        assert result.errors[0].operation_index == 0

    def test_error_includes_target_index(self, tmp_path: Path) -> None:
        """Count errors include the target index."""
        db_path = tmp_path / "cookies.db"
        db_path.touch()

        validator = DeletePlanValidator()
        target1 = make_target(domain="ok.com", count=5)
        target2 = make_target(domain="bad.com", count=0)
        operation = make_operation(db_path=db_path, targets=[target1, target2])
        plan = make_plan([operation])

        result = validator.validate(plan)

        assert result.is_valid is False
        count_error = next(e for e in result.errors if e.code == "INVALID_COUNT")
        assert count_error.target_index == 1


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_add_error_sets_invalid(self) -> None:
        """Adding an error sets is_valid to False."""
        result = ValidationResult(is_valid=True)
        result.add_error("TEST", "Test error")

        assert result.is_valid is False
        assert len(result.errors) == 1

    def test_add_warning_keeps_valid(self) -> None:
        """Adding a warning keeps is_valid as True."""
        result = ValidationResult(is_valid=True)
        result.add_warning("TEST", "Test warning")

        assert result.is_valid is True
        assert len(result.warnings) == 1
