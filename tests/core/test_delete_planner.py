"""Tests for DeletePlanner in Cookie Cleaner."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.core.delete_planner import DeletePlanner
from src.core.models import DomainAggregate, BrowserStore, CookieRecord


def make_store(browser: str = "Chrome", profile: str = "Default", db_path: str = "C:/test/Cookies") -> BrowserStore:
    """Create a test BrowserStore."""
    return BrowserStore(
        browser_name=browser,
        profile_id=profile,
        db_path=Path(db_path),
        is_chromium=True,
    )


def make_record(domain: str, store: BrowserStore, raw_host_key: str | None = None) -> CookieRecord:
    """Create a test CookieRecord."""
    return CookieRecord(
        domain=domain,
        raw_host_key=raw_host_key or f".{domain}",
        name="test_cookie",
        store=store,
    )


def make_aggregate(domain: str, records: list[CookieRecord]) -> DomainAggregate:
    """Create a test DomainAggregate."""
    return DomainAggregate(
        normalized_domain=domain,
        cookie_count=len(records),
        browsers={r.store.browser_name for r in records},
        records=records,
        raw_host_keys={r.raw_host_key for r in records},
    )


class TestDeletePlanner:
    """Tests for DeletePlanner.build_plan()."""

    def test_empty_domains_returns_empty_plan(self) -> None:
        """Empty domain list returns plan with no operations."""
        planner = DeletePlanner()
        plan = planner.build_plan([])

        assert len(plan.operations) == 0

    def test_single_domain_single_browser(self) -> None:
        """Single domain from single browser creates one operation."""
        planner = DeletePlanner()
        store = make_store()
        record = make_record("example.com", store)
        aggregate = make_aggregate("example.com", [record])

        plan = planner.build_plan([aggregate])

        assert len(plan.operations) == 1
        op = plan.operations[0]
        assert op.browser == "Chrome"
        assert op.profile == "Default"
        assert len(op.targets) == 1
        assert op.targets[0].normalized_domain == "example.com"

    def test_multiple_domains_same_browser(self) -> None:
        """Multiple domains from same browser creates one operation with multiple targets."""
        planner = DeletePlanner()
        store = make_store()
        record1 = make_record("example.com", store)
        record2 = make_record("other.com", store)
        agg1 = make_aggregate("example.com", [record1])
        agg2 = make_aggregate("other.com", [record2])

        plan = planner.build_plan([agg1, agg2])

        assert len(plan.operations) == 1
        assert len(plan.operations[0].targets) == 2

    def test_same_domain_different_browsers(self) -> None:
        """Same domain from different browsers creates multiple operations."""
        planner = DeletePlanner()
        store1 = make_store("Chrome", "Default", "C:/chrome/Cookies")
        store2 = make_store("Firefox", "default", "C:/firefox/cookies.sqlite")
        record1 = make_record("example.com", store1)
        record2 = make_record("example.com", store2)
        aggregate = make_aggregate("example.com", [record1, record2])

        plan = planner.build_plan([aggregate])

        assert len(plan.operations) == 2
        browsers = {op.browser for op in plan.operations}
        assert browsers == {"Chrome", "Firefox"}

    def test_different_profiles_same_browser(self) -> None:
        """Same browser with different profiles creates separate operations."""
        planner = DeletePlanner()
        store1 = make_store("Chrome", "Default", "C:/chrome/Default/Cookies")
        store2 = make_store("Chrome", "Profile 1", "C:/chrome/Profile 1/Cookies")
        record1 = make_record("example.com", store1)
        record2 = make_record("example.com", store2)
        aggregate = make_aggregate("example.com", [record1, record2])

        plan = planner.build_plan([aggregate])

        assert len(plan.operations) == 2
        profiles = {op.profile for op in plan.operations}
        assert profiles == {"Default", "Profile 1"}

    def test_target_pattern_for_dotted_host(self) -> None:
        """Host keys starting with . get % prefix in pattern."""
        planner = DeletePlanner()
        store = make_store()
        record = make_record("example.com", store, raw_host_key=".example.com")
        aggregate = make_aggregate("example.com", [record])

        plan = planner.build_plan([aggregate])

        target = plan.operations[0].targets[0]
        assert target.match_pattern == "%.example.com"

    def test_target_pattern_for_non_dotted_host(self) -> None:
        """Host keys not starting with . use literal pattern."""
        planner = DeletePlanner()
        store = make_store()
        record = make_record("example.com", store, raw_host_key="example.com")
        aggregate = make_aggregate("example.com", [record])

        plan = planner.build_plan([aggregate])

        target = plan.operations[0].targets[0]
        assert target.match_pattern == "example.com"

    def test_target_count_accumulates(self) -> None:
        """Multiple records for same host_key accumulate count."""
        planner = DeletePlanner()
        store = make_store()
        record1 = make_record("example.com", store)
        record2 = make_record("example.com", store)
        record3 = make_record("example.com", store)
        aggregate = make_aggregate("example.com", [record1, record2, record3])

        plan = planner.build_plan([aggregate])

        target = plan.operations[0].targets[0]
        assert target.count == 3

    def test_dry_run_flag_passed_to_plan(self) -> None:
        """Dry run flag is passed to created plan."""
        planner = DeletePlanner()
        store = make_store()
        record = make_record("example.com", store)
        aggregate = make_aggregate("example.com", [record])

        plan_normal = planner.build_plan([aggregate], dry_run=False)
        plan_dry = planner.build_plan([aggregate], dry_run=True)

        assert plan_normal.dry_run is False
        assert plan_dry.dry_run is True

    def test_plan_id_is_unique(self) -> None:
        """Each plan gets a unique ID."""
        planner = DeletePlanner()
        store = make_store()
        record = make_record("example.com", store)
        aggregate = make_aggregate("example.com", [record])

        plan1 = planner.build_plan([aggregate])
        plan2 = planner.build_plan([aggregate])

        assert plan1.plan_id != plan2.plan_id
