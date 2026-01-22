"""Pytest fixtures for UI tests."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.core.models import BrowserStore, CookieRecord, DomainAggregate


@pytest.fixture
def sample_browser_store() -> BrowserStore:
    """Create a sample BrowserStore for testing."""
    return BrowserStore(
        browser_name="Chrome",
        profile_id="Default",
        db_path=Path("C:/fake/path/Cookies"),
        is_chromium=True,
        local_state_path=Path("C:/fake/path/Local State"),
    )


@pytest.fixture
def sample_cookie_record(sample_browser_store: BrowserStore) -> CookieRecord:
    """Create a sample CookieRecord for testing."""
    return CookieRecord(
        domain="example.com",
        raw_host_key=".example.com",
        name="session",
        store=sample_browser_store,
    )


@pytest.fixture
def sample_domain_aggregates(sample_browser_store: BrowserStore) -> list[DomainAggregate]:
    """Create sample DomainAggregate instances for testing."""
    return [
        DomainAggregate(
            normalized_domain="example.com",
            cookie_count=5,
            browsers={"Chrome"},
            records=[
                CookieRecord(
                    domain="example.com",
                    raw_host_key=".example.com",
                    name=f"cookie_{i}",
                    store=sample_browser_store,
                )
                for i in range(5)
            ],
            raw_host_keys={".example.com"},
        ),
        DomainAggregate(
            normalized_domain="test.org",
            cookie_count=3,
            browsers={"Chrome", "Firefox"},
            records=[
                CookieRecord(
                    domain="test.org",
                    raw_host_key=".test.org",
                    name=f"cookie_{i}",
                    store=sample_browser_store,
                )
                for i in range(3)
            ],
            raw_host_keys={".test.org"},
        ),
    ]


@pytest.fixture
def mock_config_manager():
    """Create a mock ConfigManager."""
    mock = MagicMock()
    mock.whitelist = ["domain:google.com", "domain:microsoft.com"]
    mock.settings = {
        "theme": "system",
        "backup_retention_days": 7,
        "confirm_before_clean": True,
    }
    return mock
