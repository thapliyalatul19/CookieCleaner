"""Tests for core data models."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.core.models import (
    BrowserStore,
    CookieRecord,
    DomainAggregate,
    DeleteTarget,
    DeleteOperation,
    DeletePlan,
)


class TestBrowserStore:
    """Tests for BrowserStore dataclass."""

    def test_instantiation(self):
        """BrowserStore can be instantiated with required fields."""
        store = BrowserStore(
            browser_name="Chrome",
            profile_id="Default",
            db_path=Path("C:/test/Cookies"),
            is_chromium=True,
        )

        assert store.browser_name == "Chrome"
        assert store.profile_id == "Default"
        assert store.is_chromium is True
        assert store.local_state_path is None

    def test_to_dict_and_from_dict(self, sample_browser_store):
        """BrowserStore serializes and deserializes correctly."""
        store = BrowserStore.from_dict(sample_browser_store)
        result = store.to_dict()

        assert result["browser_name"] == sample_browser_store["browser_name"]
        assert result["profile_id"] == sample_browser_store["profile_id"]
        assert result["is_chromium"] == sample_browser_store["is_chromium"]


class TestCookieRecord:
    """Tests for CookieRecord dataclass."""

    def test_instantiation(self):
        """CookieRecord can be instantiated with required fields."""
        store = BrowserStore(
            browser_name="Firefox",
            profile_id="default-release",
            db_path=Path("C:/test/cookies.sqlite"),
            is_chromium=False,
        )
        record = CookieRecord(
            domain="example.com",
            raw_host_key=".example.com",
            name="session",
            store=store,
        )

        assert record.domain == "example.com"
        assert record.raw_host_key == ".example.com"
        assert record.expires is None
        assert record.is_secure is False

    def test_to_dict_and_from_dict(self, sample_cookie_record):
        """CookieRecord serializes and deserializes correctly."""
        record = CookieRecord.from_dict(sample_cookie_record)

        assert record.domain == "google.com"
        assert record.name == "session_id"
        assert record.is_secure is True

        result = record.to_dict()
        assert result["domain"] == sample_cookie_record["domain"]


class TestDomainAggregate:
    """Tests for DomainAggregate dataclass."""

    def test_instantiation(self):
        """DomainAggregate can be instantiated."""
        agg = DomainAggregate(
            normalized_domain="google.com",
            cookie_count=10,
            browsers={"Chrome", "Firefox"},
        )

        assert agg.normalized_domain == "google.com"
        assert agg.cookie_count == 10
        assert "Chrome" in agg.browsers
        assert len(agg.records) == 0

    def test_to_dict_and_from_dict(self):
        """DomainAggregate serializes and deserializes correctly."""
        agg = DomainAggregate(
            normalized_domain="example.com",
            cookie_count=5,
            browsers={"Edge"},
            raw_host_keys={".example.com", "example.com"},
        )

        data = agg.to_dict()
        restored = DomainAggregate.from_dict(data)

        assert restored.normalized_domain == agg.normalized_domain
        assert restored.cookie_count == agg.cookie_count
        assert restored.browsers == agg.browsers
        assert restored.raw_host_keys == agg.raw_host_keys


class TestDeleteTarget:
    """Tests for DeleteTarget dataclass."""

    def test_instantiation(self):
        """DeleteTarget can be instantiated."""
        target = DeleteTarget(
            normalized_domain="tracker.com",
            match_pattern="%.tracker.com",
            count=25,
        )

        assert target.normalized_domain == "tracker.com"
        assert target.match_pattern == "%.tracker.com"
        assert target.count == 25

    def test_to_dict_and_from_dict(self):
        """DeleteTarget serializes and deserializes correctly."""
        target = DeleteTarget(
            normalized_domain="ads.com",
            match_pattern="%.ads.com",
            count=10,
        )

        data = target.to_dict()
        restored = DeleteTarget.from_dict(data)

        assert restored.normalized_domain == target.normalized_domain
        assert restored.count == target.count


class TestDeleteOperation:
    """Tests for DeleteOperation dataclass."""

    def test_instantiation(self):
        """DeleteOperation can be instantiated."""
        op = DeleteOperation(
            browser="Chrome",
            profile="Default",
            db_path=Path("C:/test/Cookies"),
            backup_path=Path("C:/backup/Chrome_Default.bak"),
        )

        assert op.browser == "Chrome"
        assert len(op.targets) == 0


class TestDeletePlan:
    """Tests for DeletePlan dataclass."""

    def test_create_generates_uuid(self):
        """DeletePlan.create generates a unique UUID."""
        plan1 = DeletePlan.create()
        plan2 = DeletePlan.create()

        assert plan1.plan_id != plan2.plan_id
        assert len(plan1.plan_id) == 36  # UUID format

    def test_create_sets_timestamp(self):
        """DeletePlan.create sets current timestamp."""
        before = datetime.now(timezone.utc)
        plan = DeletePlan.create()
        after = datetime.now(timezone.utc)

        assert before <= plan.timestamp <= after

    def test_add_operation_updates_counts(self):
        """add_operation updates summary counts."""
        plan = DeletePlan.create()

        op = DeleteOperation(
            browser="Chrome",
            profile="Default",
            db_path=Path("C:/test/Cookies"),
            backup_path=Path("C:/backup/test.bak"),
            targets=[
                DeleteTarget("a.com", "%.a.com", 10),
                DeleteTarget("b.com", "%.b.com", 5),
            ],
        )

        plan.add_operation(op)

        assert plan.total_cookies_to_delete == 15
        assert plan.affected_profiles == 1

    def test_to_json_and_from_json(self):
        """DeletePlan JSON serialization round-trips correctly."""
        plan = DeletePlan.create(dry_run=True)
        plan.add_operation(
            DeleteOperation(
                browser="Firefox",
                profile="default-release",
                db_path=Path("C:/test/cookies.sqlite"),
                backup_path=Path("C:/backup/firefox.bak"),
                targets=[DeleteTarget("tracker.com", "%.tracker.com", 20)],
            )
        )

        json_str = plan.to_json()
        restored = DeletePlan.from_json(json_str)

        assert restored.plan_id == plan.plan_id
        assert restored.dry_run is True
        assert restored.total_cookies_to_delete == 20
        assert restored.affected_profiles == 1
        assert len(restored.operations) == 1
        assert restored.operations[0].browser == "Firefox"

    def test_json_format_matches_prd_spec(self):
        """JSON output matches PRD 5.2 schema."""
        plan = DeletePlan.create()
        plan.add_operation(
            DeleteOperation(
                browser="Chrome",
                profile="Default",
                db_path=Path("C:/Users/test/Cookies"),
                backup_path=Path("C:/backup/Chrome_Default.bak"),
                targets=[
                    DeleteTarget("doubleclick.net", "%.doubleclick.net", 12)
                ],
            )
        )

        data = plan.to_dict()

        # Verify structure matches PRD
        assert "plan_id" in data
        assert "timestamp" in data
        assert "dry_run" in data
        assert "operations" in data
        assert "summary" in data
        assert "total_cookies_to_delete" in data["summary"]
        assert "affected_profiles" in data["summary"]

        # Verify operation structure
        op = data["operations"][0]
        assert "browser" in op
        assert "profile" in op
        assert "db_path" in op
        assert "backup_path" in op
        assert "targets" in op

        # Verify target structure
        target = op["targets"][0]
        assert "normalized_domain" in target
        assert "match_pattern" in target
        assert "count" in target
