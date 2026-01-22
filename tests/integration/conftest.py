"""Integration test fixtures with golden fixture factory.

Provides pre-built SQLite databases for testing edge cases:
- Fixture A: Domain boundary (ample.com vs trample.com)
- Fixture B: Host key forms (dot vs non-dot)
- Fixture C: Multi-profile lock simulation
- Fixture D: Conflicting whitelist scenarios
- Fixture E: Corrupted/empty databases
"""

import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

from src.core.models import BrowserStore, DeleteOperation, DeletePlan, DeleteTarget
from src.core.config import ConfigManager
from src.core.whitelist import WhitelistManager
from src.execution.backup_manager import BackupManager
from src.execution.delete_executor import DeleteExecutor
from src.execution.lock_resolver import LockResolver, LockReport
from src.scanner.chromium_cookie_reader import ChromiumCookieReader
from src.scanner.firefox_cookie_reader import FirefoxCookieReader


# Chromium epoch offset: microseconds since 1601-01-01
CHROMIUM_EPOCH_OFFSET = 11644473600


def unix_to_chromium_time(unix_seconds: int) -> int:
    """Convert Unix timestamp to Chromium microseconds since 1601."""
    return (unix_seconds + CHROMIUM_EPOCH_OFFSET) * 1_000_000


# Default expiry: 2030-01-01
DEFAULT_EXPIRY_UNIX = 1893456000
DEFAULT_EXPIRY_CHROMIUM = unix_to_chromium_time(DEFAULT_EXPIRY_UNIX)
DEFAULT_CREATION_CHROMIUM = unix_to_chromium_time(1704067200)  # 2024-01-01


class GoldenFixtureFactory:
    """Factory for creating golden test databases."""

    @staticmethod
    def create_chromium_db(
        db_path: Path,
        cookies: list[tuple[str, str, int | None, int]],
        schema_columns: int = 20,
    ) -> Path:
        """
        Create a Chromium-style cookie database.

        Args:
            db_path: Path to create the database at
            cookies: List of (host_key, name, expires_chromium, is_secure) tuples
            schema_columns: 20 for Chrome, 22 for Edge

        Returns:
            Path to created database
        """
        conn = sqlite3.connect(db_path)

        if schema_columns == 22:
            # Edge schema with partition_key and has_cross_site_ancestor
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
            for host_key, name, expires, is_secure in cookies:
                if expires is None:
                    expires = DEFAULT_EXPIRY_CHROMIUM
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
                    (DEFAULT_CREATION_CHROMIUM, host_key, name, expires, is_secure,
                     DEFAULT_CREATION_CHROMIUM, DEFAULT_CREATION_CHROMIUM),
                )
        else:
            # Standard Chrome schema (20 columns)
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
            for host_key, name, expires, is_secure in cookies:
                if expires is None:
                    expires = DEFAULT_EXPIRY_CHROMIUM
                conn.execute(
                    """
                    INSERT INTO cookies (
                        creation_utc, host_key, top_frame_site_key, name, value,
                        encrypted_value, path, expires_utc, is_secure, is_httponly,
                        last_access_utc, has_expires, is_persistent, priority, samesite,
                        source_scheme, source_port, is_same_party, last_update_utc, source_type
                    ) VALUES (?, ?, '', ?, '', X'', '/', ?, ?, 0, ?, 1, 1, 1, 0, 2, 443, 0, ?, 0)
                    """,
                    (DEFAULT_CREATION_CHROMIUM, host_key, name, expires, is_secure,
                     DEFAULT_CREATION_CHROMIUM, DEFAULT_CREATION_CHROMIUM),
                )

        conn.commit()
        conn.close()
        return db_path

    @staticmethod
    def create_firefox_db(
        db_path: Path,
        cookies: list[tuple[str, str, int | None, int]],
    ) -> Path:
        """
        Create a Firefox-style cookie database.

        Args:
            db_path: Path to create the database at
            cookies: List of (host, name, expiry_unix, is_secure) tuples

        Returns:
            Path to created database
        """
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

        creation = 1704067200 * 1000000  # microseconds

        for host, name, expiry, is_secure in cookies:
            if expiry is None:
                expiry = DEFAULT_EXPIRY_UNIX
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

    @staticmethod
    def create_empty_chromium_db(db_path: Path) -> Path:
        """Create Chromium database with table but no cookies."""
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

    @staticmethod
    def create_corrupted_db(db_path: Path) -> Path:
        """Create an invalid SQLite file."""
        db_path.write_bytes(b"This is not a valid SQLite database file")
        return db_path

    @staticmethod
    def create_missing_table_db(db_path: Path) -> Path:
        """Create SQLite database without cookies table."""
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE other_table (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()
        return db_path


@pytest.fixture
def golden_factory() -> GoldenFixtureFactory:
    """Return the golden fixture factory."""
    return GoldenFixtureFactory()


@pytest.fixture
def integration_temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for integration tests."""
    path = Path(tempfile.mkdtemp(prefix="cookie_cleaner_int_"))
    yield path
    shutil.rmtree(path, ignore_errors=True)


# =============================================================================
# Fixture A: Domain Boundary Test
# Verifies ample.com deletion doesn't affect trample.com
# =============================================================================

@pytest.fixture
def fixture_a_domain_boundary(
    integration_temp_dir: Path, golden_factory: GoldenFixtureFactory
) -> dict[str, Path]:
    """
    Fixture A: Domain boundary test databases.

    Creates Chromium and Firefox DBs with similar-looking domains:
    - ample.com (target for deletion)
    - trample.com (should NOT be deleted)
    - example.com (should NOT be deleted)
    """
    fixtures = {}

    # Chrome database
    chrome_path = integration_temp_dir / "chrome" / "Default" / "Network" / "Cookies"
    chrome_path.parent.mkdir(parents=True)
    golden_factory.create_chromium_db(chrome_path, [
        (".ample.com", "session", None, 1),
        (".ample.com", "tracking", None, 0),
        ("www.ample.com", "user_pref", None, 1),
        (".trample.com", "session", None, 1),
        (".trample.com", "analytics", None, 0),
        ("sub.trample.com", "data", None, 1),
        (".example.com", "test", None, 0),
        ("example.com", "other", None, 1),
    ])
    fixtures["chrome"] = chrome_path

    # Firefox database
    firefox_path = integration_temp_dir / "firefox" / "profile" / "cookies.sqlite"
    firefox_path.parent.mkdir(parents=True)
    golden_factory.create_firefox_db(firefox_path, [
        ("ample.com", "ff_session", None, 1),
        (".ample.com", "ff_prefs", None, 0),
        ("trample.com", "ff_session", None, 1),
        (".trample.com", "ff_data", None, 0),
        ("example.com", "ff_test", None, 1),
    ])
    fixtures["firefox"] = firefox_path

    return fixtures


@pytest.fixture
def fixture_a_stores(fixture_a_domain_boundary: dict[str, Path]) -> dict[str, BrowserStore]:
    """Create BrowserStores for Fixture A databases."""
    return {
        "chrome": BrowserStore(
            browser_name="Chrome",
            profile_id="Default",
            db_path=fixture_a_domain_boundary["chrome"],
            is_chromium=True,
        ),
        "firefox": BrowserStore(
            browser_name="Firefox",
            profile_id="profile",
            db_path=fixture_a_domain_boundary["firefox"],
            is_chromium=False,
        ),
    }


# =============================================================================
# Fixture B: Host Key Forms
# Tests .example.com and example.com deletion patterns
# =============================================================================

@pytest.fixture
def fixture_b_host_key_forms(
    integration_temp_dir: Path, golden_factory: GoldenFixtureFactory
) -> dict[str, Path]:
    """
    Fixture B: Host key form variations.

    Tests different host_key formats:
    - .example.com (domain-wide)
    - example.com (exact host)
    - www.example.com (subdomain)
    """
    fixtures = {}

    chrome_path = integration_temp_dir / "chrome" / "Default" / "Network" / "Cookies"
    chrome_path.parent.mkdir(parents=True)
    golden_factory.create_chromium_db(chrome_path, [
        # Various forms of example.com
        (".example.com", "domain_cookie", None, 1),
        ("example.com", "host_cookie", None, 1),
        ("www.example.com", "www_cookie", None, 1),
        ("api.example.com", "api_cookie", None, 1),
        ("sub.api.example.com", "deep_cookie", None, 1),
        # Another domain to ensure isolation
        (".other.com", "other_cookie", None, 1),
    ])
    fixtures["chrome"] = chrome_path

    return fixtures


@pytest.fixture
def fixture_b_store(fixture_b_host_key_forms: dict[str, Path]) -> BrowserStore:
    """Create BrowserStore for Fixture B database."""
    return BrowserStore(
        browser_name="Chrome",
        profile_id="Default",
        db_path=fixture_b_host_key_forms["chrome"],
        is_chromium=True,
    )


# =============================================================================
# Fixture C: Multi-Profile Lock Scenario
# Tests locked profile handling
# =============================================================================

@pytest.fixture
def fixture_c_multi_profile(
    integration_temp_dir: Path, golden_factory: GoldenFixtureFactory
) -> dict[str, Path]:
    """
    Fixture C: Multi-profile setup for lock testing.

    Creates multiple profiles:
    - Chrome Default (accessible)
    - Chrome Profile 1 (accessible)
    - Edge Default (will be "locked" via mock)
    """
    fixtures = {}

    # Chrome Default
    chrome_default = integration_temp_dir / "chrome" / "Default" / "Network" / "Cookies"
    chrome_default.parent.mkdir(parents=True)
    golden_factory.create_chromium_db(chrome_default, [
        (".google.com", "pref", None, 1),
        (".facebook.com", "session", None, 1),
    ])
    fixtures["chrome_default"] = chrome_default

    # Chrome Profile 1
    chrome_p1 = integration_temp_dir / "chrome" / "Profile 1" / "Network" / "Cookies"
    chrome_p1.parent.mkdir(parents=True)
    golden_factory.create_chromium_db(chrome_p1, [
        (".google.com", "alt_pref", None, 1),
        (".twitter.com", "session", None, 1),
    ])
    fixtures["chrome_profile1"] = chrome_p1

    # Edge Default (will simulate as locked)
    edge_default = integration_temp_dir / "edge" / "Default" / "Network" / "Cookies"
    edge_default.parent.mkdir(parents=True)
    golden_factory.create_chromium_db(edge_default, [
        (".bing.com", "muid", None, 1),
        (".microsoft.com", "session", None, 1),
    ], schema_columns=22)
    fixtures["edge_default"] = edge_default

    return fixtures


@pytest.fixture
def fixture_c_stores(fixture_c_multi_profile: dict[str, Path]) -> dict[str, BrowserStore]:
    """Create BrowserStores for Fixture C databases."""
    return {
        "chrome_default": BrowserStore(
            browser_name="Chrome",
            profile_id="Default",
            db_path=fixture_c_multi_profile["chrome_default"],
            is_chromium=True,
        ),
        "chrome_profile1": BrowserStore(
            browser_name="Chrome",
            profile_id="Profile 1",
            db_path=fixture_c_multi_profile["chrome_profile1"],
            is_chromium=True,
        ),
        "edge_default": BrowserStore(
            browser_name="Edge",
            profile_id="Default",
            db_path=fixture_c_multi_profile["edge_default"],
            is_chromium=True,
        ),
    }


# =============================================================================
# Fixture D: Conflicting Whitelist
# Tests domain:google.com + exact:accounts.google.com
# =============================================================================

@pytest.fixture
def fixture_d_conflicting_whitelist(
    integration_temp_dir: Path, golden_factory: GoldenFixtureFactory
) -> Path:
    """
    Fixture D: Conflicting whitelist scenario.

    Database contains google.com hierarchy:
    - google.com
    - www.google.com
    - accounts.google.com
    - mail.google.com
    - docs.google.com
    """
    chrome_path = integration_temp_dir / "chrome" / "Default" / "Network" / "Cookies"
    chrome_path.parent.mkdir(parents=True)
    golden_factory.create_chromium_db(chrome_path, [
        (".google.com", "NID", None, 1),
        ("google.com", "PREF", None, 0),
        ("www.google.com", "session", None, 1),
        ("accounts.google.com", "LSID", None, 1),
        ("accounts.google.com", "HSID", None, 1),
        ("mail.google.com", "GMAIL_AT", None, 1),
        ("docs.google.com", "docspref", None, 1),
        # Non-google domain
        (".facebook.com", "c_user", None, 1),
    ])
    return chrome_path


@pytest.fixture
def fixture_d_store(fixture_d_conflicting_whitelist: Path) -> BrowserStore:
    """Create BrowserStore for Fixture D database."""
    return BrowserStore(
        browser_name="Chrome",
        profile_id="Default",
        db_path=fixture_d_conflicting_whitelist,
        is_chromium=True,
    )


# =============================================================================
# Fixture E: Corrupted/Empty Databases
# Tests graceful error handling
# =============================================================================

@pytest.fixture
def fixture_e_edge_cases(
    integration_temp_dir: Path, golden_factory: GoldenFixtureFactory
) -> dict[str, Path]:
    """
    Fixture E: Edge case databases.

    - empty: Valid schema but no cookies
    - corrupted: Invalid SQLite file
    - missing_table: SQLite without cookies table
    - missing_file: Path that doesn't exist
    """
    fixtures = {}

    # Empty database
    empty_path = integration_temp_dir / "empty" / "Cookies"
    empty_path.parent.mkdir(parents=True)
    golden_factory.create_empty_chromium_db(empty_path)
    fixtures["empty"] = empty_path

    # Corrupted database
    corrupted_path = integration_temp_dir / "corrupted" / "Cookies"
    corrupted_path.parent.mkdir(parents=True)
    golden_factory.create_corrupted_db(corrupted_path)
    fixtures["corrupted"] = corrupted_path

    # Missing table
    missing_table_path = integration_temp_dir / "missing_table" / "Cookies"
    missing_table_path.parent.mkdir(parents=True)
    golden_factory.create_missing_table_db(missing_table_path)
    fixtures["missing_table"] = missing_table_path

    # Missing file (path exists but no file)
    missing_file_path = integration_temp_dir / "missing" / "Cookies"
    missing_file_path.parent.mkdir(parents=True)
    fixtures["missing_file"] = missing_file_path

    return fixtures


# =============================================================================
# Multi-Profile Scanning Fixture
# For testing full scan workflows
# =============================================================================

@pytest.fixture
def multi_profile_setup(
    integration_temp_dir: Path, golden_factory: GoldenFixtureFactory
) -> dict[str, Path | BrowserStore]:
    """
    Create a realistic multi-browser, multi-profile environment.

    - Chrome: Default + Profile 1
    - Firefox: default profile
    """
    result = {"paths": {}, "stores": []}

    # Chrome Default
    chrome_default = integration_temp_dir / "Chrome" / "Default" / "Network" / "Cookies"
    chrome_default.parent.mkdir(parents=True)
    golden_factory.create_chromium_db(chrome_default, [
        (".google.com", "NID", None, 1),
        (".google.com", "SID", None, 1),
        (".facebook.com", "c_user", None, 1),
        (".amazon.com", "session-id", None, 1),
        (".tracker.com", "uid", None, 0),
    ])
    result["paths"]["chrome_default"] = chrome_default
    result["stores"].append(BrowserStore(
        browser_name="Chrome",
        profile_id="Default",
        db_path=chrome_default,
        is_chromium=True,
    ))

    # Chrome Profile 1
    chrome_p1 = integration_temp_dir / "Chrome" / "Profile 1" / "Network" / "Cookies"
    chrome_p1.parent.mkdir(parents=True)
    golden_factory.create_chromium_db(chrome_p1, [
        (".google.com", "PREF", None, 1),
        (".twitter.com", "auth_token", None, 1),
        (".tracker.com", "visitor", None, 0),
    ])
    result["paths"]["chrome_profile1"] = chrome_p1
    result["stores"].append(BrowserStore(
        browser_name="Chrome",
        profile_id="Profile 1",
        db_path=chrome_p1,
        is_chromium=True,
    ))

    # Firefox
    firefox_path = integration_temp_dir / "Firefox" / "profile.default" / "cookies.sqlite"
    firefox_path.parent.mkdir(parents=True)
    golden_factory.create_firefox_db(firefox_path, [
        ("google.com", "session", None, 1),
        (".mozilla.org", "pref", None, 1),
        ("tracker.com", "id", None, 0),
    ])
    result["paths"]["firefox"] = firefox_path
    result["stores"].append(BrowserStore(
        browser_name="Firefox",
        profile_id="profile.default",
        db_path=firefox_path,
        is_chromium=False,
    ))

    return result


# =============================================================================
# Performance Testing Fixture
# For testing search performance with 1000+ domains
# =============================================================================

@pytest.fixture
def performance_db(
    integration_temp_dir: Path, golden_factory: GoldenFixtureFactory
) -> tuple[Path, BrowserStore]:
    """
    Create database with 1000+ domains for performance testing.
    """
    db_path = integration_temp_dir / "performance" / "Cookies"
    db_path.parent.mkdir(parents=True)

    cookies = []
    # Generate 1000 unique domains
    for i in range(1000):
        domain = f".domain{i:04d}.com"
        cookies.append((domain, f"cookie_{i}", None, i % 2))

    # Add some realistic domains too
    cookies.extend([
        (".google.com", "NID", None, 1),
        (".facebook.com", "c_user", None, 1),
        (".amazon.com", "session", None, 1),
    ])

    golden_factory.create_chromium_db(db_path, cookies)

    store = BrowserStore(
        browser_name="Chrome",
        profile_id="Performance",
        db_path=db_path,
        is_chromium=True,
    )

    return db_path, store


# =============================================================================
# Helper Fixtures
# =============================================================================

@pytest.fixture
def mock_lock_resolver() -> LockResolver:
    """Create a LockResolver that reports no locks by default."""
    resolver = LockResolver()
    return resolver


@pytest.fixture
def unlocked_lock_resolver() -> MagicMock:
    """Create a mock LockResolver that always reports unlocked."""
    from pathlib import Path
    mock = MagicMock(spec=LockResolver)
    # Use a side_effect to dynamically set db_path
    def check_lock_side_effect(db_path):
        return LockReport(db_path=db_path, is_locked=False, blocking_processes=[])
    mock.check_lock.side_effect = check_lock_side_effect
    # find_blocking_processes returns (list, bool) tuple
    mock.find_blocking_processes.return_value = ([], True)
    return mock


@pytest.fixture
def locked_lock_resolver() -> MagicMock:
    """Create a mock LockResolver that always reports locked."""
    from pathlib import Path
    mock = MagicMock(spec=LockResolver)
    # Use a side_effect to dynamically set db_path
    def check_lock_side_effect(db_path):
        return LockReport(db_path=db_path, is_locked=True, blocking_processes=["chrome.exe"])
    mock.check_lock.side_effect = check_lock_side_effect
    # find_blocking_processes returns (list, bool) tuple
    mock.find_blocking_processes.return_value = (["chrome.exe"], False)
    return mock


@pytest.fixture
def temp_backup_dir(integration_temp_dir: Path) -> Path:
    """Create a temporary backup directory."""
    backup_dir = integration_temp_dir / "backups"
    backup_dir.mkdir(parents=True)
    return backup_dir


@pytest.fixture
def temp_config_dir(integration_temp_dir: Path) -> Path:
    """Create a temporary config directory."""
    config_dir = integration_temp_dir / "config"
    config_dir.mkdir(parents=True)
    return config_dir


def count_cookies_in_chromium_db(db_path: Path) -> int:
    """Count total cookies in a Chromium database."""
    if not db_path.exists():
        return 0
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT COUNT(*) FROM cookies")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def count_cookies_by_domain_in_chromium_db(db_path: Path, domain_pattern: str) -> int:
    """Count cookies matching a domain pattern in Chromium database."""
    if not db_path.exists():
        return 0
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT COUNT(*) FROM cookies WHERE host_key LIKE ?", (domain_pattern,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


def count_cookies_in_firefox_db(db_path: Path) -> int:
    """Count total cookies in a Firefox database."""
    if not db_path.exists():
        return 0
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT COUNT(*) FROM moz_cookies")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def count_cookies_by_domain_in_firefox_db(db_path: Path, domain_pattern: str) -> int:
    """Count cookies matching a domain pattern in Firefox database."""
    if not db_path.exists():
        return 0
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT COUNT(*) FROM moz_cookies WHERE host LIKE ?", (domain_pattern,))
    count = cursor.fetchone()[0]
    conn.close()
    return count
