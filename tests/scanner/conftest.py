"""Test fixtures for scanner module."""

import sqlite3

import pytest
from pathlib import Path

from src.core.models import BrowserStore


@pytest.fixture
def mock_chromium_user_data(tmp_path: Path) -> Path:
    """Create a mock Chromium User Data directory structure."""
    user_data = tmp_path / "User Data"
    user_data.mkdir()

    # Create Local State file
    (user_data / "Local State").write_text("{}")

    # Create Default profile with modern cookie path
    default_profile = user_data / "Default" / "Network"
    default_profile.mkdir(parents=True)
    (default_profile / "Cookies").write_bytes(b"")

    # Create Profile 1 with legacy cookie path
    profile1 = user_data / "Profile 1"
    profile1.mkdir()
    (profile1 / "Cookies").write_bytes(b"")

    # Create directories that should be skipped
    (user_data / "Crashpad").mkdir()
    (user_data / "Safe Browsing").mkdir()
    (user_data / "ShaderCache").mkdir()

    return user_data


@pytest.fixture
def mock_firefox_root(tmp_path: Path) -> Path:
    """Create a mock Firefox root directory with profiles.ini."""
    firefox_root = tmp_path / "Mozilla" / "Firefox"
    firefox_root.mkdir(parents=True)

    # Create profiles.ini
    profiles_ini = firefox_root / "profiles.ini"
    profiles_ini.write_text(
        "[General]\n"
        "StartWithLastProfile=1\n"
        "\n"
        "[Profile0]\n"
        "Name=default\n"
        "IsRelative=1\n"
        "Path=Profiles/abc123.default\n"
        "Default=1\n"
        "\n"
        "[Profile1]\n"
        "Name=dev\n"
        "IsRelative=1\n"
        "Path=Profiles/xyz789.dev\n"
    )

    # Create profile directories with cookies.sqlite
    profile0 = firefox_root / "Profiles" / "abc123.default"
    profile0.mkdir(parents=True)
    (profile0 / "cookies.sqlite").write_bytes(b"")

    profile1 = firefox_root / "Profiles" / "xyz789.dev"
    profile1.mkdir(parents=True)
    (profile1 / "cookies.sqlite").write_bytes(b"")

    return firefox_root


@pytest.fixture
def mock_firefox_no_cookies(tmp_path: Path) -> Path:
    """Create a mock Firefox profile without cookies.sqlite."""
    firefox_root = tmp_path / "Mozilla" / "Firefox"
    firefox_root.mkdir(parents=True)

    profiles_ini = firefox_root / "profiles.ini"
    profiles_ini.write_text(
        "[Profile0]\n"
        "Name=empty\n"
        "IsRelative=1\n"
        "Path=Profiles/empty.profile\n"
    )

    # Create profile directory WITHOUT cookies.sqlite
    profile = firefox_root / "Profiles" / "empty.profile"
    profile.mkdir(parents=True)

    return firefox_root


@pytest.fixture
def mock_firefox_absolute_path(tmp_path: Path) -> Path:
    """Create a mock Firefox profile with absolute path."""
    firefox_root = tmp_path / "Mozilla" / "Firefox"
    firefox_root.mkdir(parents=True)

    # Create profile in a different location
    external_profile = tmp_path / "ExternalProfiles" / "myprofile"
    external_profile.mkdir(parents=True)
    (external_profile / "cookies.sqlite").write_bytes(b"")

    profiles_ini = firefox_root / "profiles.ini"
    profiles_ini.write_text(
        "[Profile0]\n"
        "Name=external\n"
        "IsRelative=0\n"
        f"Path={external_profile}\n"
    )

    return firefox_root


# Chromium epoch offset: microseconds since 1601-01-01
# To convert a Unix timestamp (seconds since 1970) to Chromium time:
# chromium_time = (unix_time + 11644473600) * 1_000_000
CHROMIUM_EPOCH_OFFSET = 11644473600


def unix_to_chromium_time(unix_seconds: int) -> int:
    """Convert Unix timestamp to Chromium microseconds since 1601."""
    return (unix_seconds + CHROMIUM_EPOCH_OFFSET) * 1_000_000


@pytest.fixture
def mock_chromium_cookie_db(tmp_path: Path) -> Path:
    """Create mock Chromium cookies database with test data (20 columns)."""
    db_path = tmp_path / "Cookies"

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE cookies (
            creation_utc INTEGER NOT NULL,
            host_key TEXT NOT NULL,
            top_frame_site_key TEXT NOT NULL,
            name TEXT NOT NULL,
            value TEXT NOT NULL,
            encrypted_value BLOB NOT NULL,
            path TEXT NOT NULL,
            expires_utc INTEGER NOT NULL,
            is_secure INTEGER NOT NULL,
            is_httponly INTEGER NOT NULL,
            last_access_utc INTEGER NOT NULL,
            has_expires INTEGER NOT NULL,
            is_persistent INTEGER NOT NULL,
            priority INTEGER NOT NULL,
            samesite INTEGER NOT NULL,
            source_scheme INTEGER NOT NULL,
            source_port INTEGER NOT NULL,
            is_same_party INTEGER NOT NULL,
            last_update_utc INTEGER NOT NULL,
            source_type INTEGER NOT NULL
        )
    """)

    # Insert test cookies
    # Use Unix timestamp 1735689600 = 2025-01-01 00:00:00 UTC
    expires_chromium = unix_to_chromium_time(1735689600)
    creation_chromium = unix_to_chromium_time(1704067200)  # 2024-01-01

    test_cookies = [
        (".google.com", "NID", expires_chromium, 1),
        (".google.com", "SID", expires_chromium, 1),
        ("accounts.google.com", "LSID", expires_chromium, 1),
        (".facebook.com", "c_user", expires_chromium, 1),
        (".facebook.com", "xs", expires_chromium, 1),
        (".github.com", "_gh_sess", 0, 0),  # Session cookie (expires=0)
        ("example.com", "session_id", expires_chromium, 0),  # Not secure
    ]

    for host_key, name, expires, is_secure in test_cookies:
        conn.execute(
            """
            INSERT INTO cookies (
                creation_utc, host_key, top_frame_site_key, name, value,
                encrypted_value, path, expires_utc, is_secure, is_httponly,
                last_access_utc, has_expires, is_persistent, priority, samesite,
                source_scheme, source_port, is_same_party, last_update_utc, source_type
            ) VALUES (?, ?, '', ?, '', X'', '/', ?, ?, 0, ?, 1, 1, 1, 0, 2, 443, 0, ?, 0)
            """,
            (creation_chromium, host_key, name, expires, is_secure, creation_chromium, creation_chromium),
        )

    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def mock_edge_cookie_db(tmp_path: Path) -> Path:
    """Create mock Edge cookies database with 22 columns."""
    db_path = tmp_path / "Cookies"

    conn = sqlite3.connect(db_path)
    # Edge has 22 columns (2 extra: partition_key, has_cross_site_ancestor)
    conn.execute("""
        CREATE TABLE cookies (
            creation_utc INTEGER NOT NULL,
            host_key TEXT NOT NULL,
            top_frame_site_key TEXT NOT NULL,
            name TEXT NOT NULL,
            value TEXT NOT NULL,
            encrypted_value BLOB NOT NULL,
            path TEXT NOT NULL,
            expires_utc INTEGER NOT NULL,
            is_secure INTEGER NOT NULL,
            is_httponly INTEGER NOT NULL,
            last_access_utc INTEGER NOT NULL,
            has_expires INTEGER NOT NULL,
            is_persistent INTEGER NOT NULL,
            priority INTEGER NOT NULL,
            samesite INTEGER NOT NULL,
            source_scheme INTEGER NOT NULL,
            source_port INTEGER NOT NULL,
            is_same_party INTEGER NOT NULL,
            last_update_utc INTEGER NOT NULL,
            source_type INTEGER NOT NULL,
            partition_key TEXT NOT NULL,
            has_cross_site_ancestor INTEGER NOT NULL
        )
    """)

    expires_chromium = unix_to_chromium_time(1735689600)
    creation_chromium = unix_to_chromium_time(1704067200)

    test_cookies = [
        (".microsoft.com", "MUID", expires_chromium, 1),
        (".bing.com", "SRCHD", expires_chromium, 0),
    ]

    for host_key, name, expires, is_secure in test_cookies:
        conn.execute(
            """
            INSERT INTO cookies (
                creation_utc, host_key, top_frame_site_key, name, value,
                encrypted_value, path, expires_utc, is_secure, is_httponly,
                last_access_utc, has_expires, is_persistent, priority, samesite,
                source_scheme, source_port, is_same_party, last_update_utc, source_type,
                partition_key, has_cross_site_ancestor
            ) VALUES (?, ?, '', ?, '', X'', '/', ?, ?, 0, ?, 1, 1, 1, 0, 2, 443, 0, ?, 0, '', 0)
            """,
            (creation_chromium, host_key, name, expires, is_secure, creation_chromium, creation_chromium),
        )

    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def mock_firefox_cookie_db(tmp_path: Path) -> Path:
    """Create mock Firefox cookies database with test data."""
    db_path = tmp_path / "cookies.sqlite"

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE moz_cookies (
            id INTEGER PRIMARY KEY,
            originAttributes TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL,
            value TEXT NOT NULL,
            host TEXT NOT NULL,
            path TEXT NOT NULL DEFAULT '/',
            expiry INTEGER NOT NULL,
            lastAccessed INTEGER NOT NULL,
            creationTime INTEGER NOT NULL,
            isSecure INTEGER NOT NULL DEFAULT 0,
            isHttpOnly INTEGER NOT NULL DEFAULT 0,
            inBrowserElement INTEGER NOT NULL DEFAULT 0,
            sameSite INTEGER NOT NULL DEFAULT 0,
            rawSameSite INTEGER NOT NULL DEFAULT 0,
            schemeMap INTEGER NOT NULL DEFAULT 0,
            isPartitionedAttributeSet INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Firefox uses Unix seconds for expiry
    expires_unix = 1735689600  # 2025-01-01
    creation = 1704067200 * 1000000  # creationTime is microseconds

    test_cookies = [
        ("mozilla.org", "session", expires_unix, 1),
        (".mozilla.org", "tracking_id", expires_unix, 0),
        ("addons.mozilla.org", "api_token", expires_unix, 1),
        ("reddit.com", "token", 0, 0),  # Session cookie
    ]

    for host, name, expiry, is_secure in test_cookies:
        conn.execute(
            """
            INSERT INTO moz_cookies (
                originAttributes, name, value, host, path, expiry,
                lastAccessed, creationTime, isSecure, isHttpOnly,
                inBrowserElement, sameSite, rawSameSite, schemeMap,
                isPartitionedAttributeSet
            ) VALUES ('', ?, 'test_value', ?, '/', ?, ?, ?, ?, 0, 0, 0, 0, 0, 0)
            """,
            (name, host, expiry, creation, creation, is_secure),
        )

    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def mock_empty_chromium_db(tmp_path: Path) -> Path:
    """Create empty Chromium cookies database (table exists but no rows)."""
    db_path = tmp_path / "Cookies"

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE cookies (
            creation_utc INTEGER NOT NULL,
            host_key TEXT NOT NULL,
            top_frame_site_key TEXT NOT NULL,
            name TEXT NOT NULL,
            value TEXT NOT NULL,
            encrypted_value BLOB NOT NULL,
            path TEXT NOT NULL,
            expires_utc INTEGER NOT NULL,
            is_secure INTEGER NOT NULL,
            is_httponly INTEGER NOT NULL,
            last_access_utc INTEGER NOT NULL,
            has_expires INTEGER NOT NULL,
            is_persistent INTEGER NOT NULL,
            priority INTEGER NOT NULL,
            samesite INTEGER NOT NULL,
            source_scheme INTEGER NOT NULL,
            source_port INTEGER NOT NULL,
            is_same_party INTEGER NOT NULL,
            last_update_utc INTEGER NOT NULL,
            source_type INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def mock_corrupted_db(tmp_path: Path) -> Path:
    """Create a corrupted/invalid database file."""
    db_path = tmp_path / "Corrupted"
    db_path.write_bytes(b"This is not a valid SQLite database")
    return db_path


@pytest.fixture
def chromium_store(mock_chromium_cookie_db: Path) -> BrowserStore:
    """Create a BrowserStore for the mock Chromium database."""
    return BrowserStore(
        browser_name="Chrome",
        profile_id="Default",
        db_path=mock_chromium_cookie_db,
        is_chromium=True,
        local_state_path=None,
    )


@pytest.fixture
def edge_store(mock_edge_cookie_db: Path) -> BrowserStore:
    """Create a BrowserStore for the mock Edge database."""
    return BrowserStore(
        browser_name="Edge",
        profile_id="Default",
        db_path=mock_edge_cookie_db,
        is_chromium=True,
        local_state_path=None,
    )


@pytest.fixture
def firefox_store(mock_firefox_cookie_db: Path) -> BrowserStore:
    """Create a BrowserStore for the mock Firefox database."""
    return BrowserStore(
        browser_name="Firefox",
        profile_id="default",
        db_path=mock_firefox_cookie_db,
        is_chromium=False,
        local_state_path=None,
    )
