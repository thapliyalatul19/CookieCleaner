"""Shared pytest fixtures for Cookie Cleaner tests."""

import json
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    path = Path(tempfile.mkdtemp())
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def temp_config_file(temp_dir):
    """Create a temporary config file path."""
    return temp_dir / "config.json"


@pytest.fixture
def valid_config_data():
    """Return valid configuration data."""
    return {
        "version": 1,
        "settings": {
            "confirm_before_clean": True,
            "backup_retention_days": 7,
            "theme": "system",
        },
        "whitelist": [
            "domain:google.com",
            "exact:github.com",
            "ip:127.0.0.1",
        ],
        "last_run": None,
    }


@pytest.fixture
def temp_config_with_data(temp_config_file, valid_config_data):
    """Create a temporary config file with valid data."""
    temp_config_file.parent.mkdir(parents=True, exist_ok=True)
    with open(temp_config_file, "w", encoding="utf-8") as f:
        json.dump(valid_config_data, f)
    return temp_config_file


@pytest.fixture
def sample_browser_store():
    """Return sample BrowserStore data."""
    return {
        "browser_name": "Chrome",
        "profile_id": "Default",
        "db_path": "C:/Users/test/AppData/Local/Google/Chrome/User Data/Default/Network/Cookies",
        "is_chromium": True,
        "local_state_path": "C:/Users/test/AppData/Local/Google/Chrome/User Data/Local State",
    }


@pytest.fixture
def sample_cookie_record(sample_browser_store):
    """Return sample CookieRecord data."""
    return {
        "domain": "google.com",
        "raw_host_key": ".google.com",
        "name": "session_id",
        "store": sample_browser_store,
        "expires": "2026-12-31T23:59:59",
        "is_secure": True,
    }
