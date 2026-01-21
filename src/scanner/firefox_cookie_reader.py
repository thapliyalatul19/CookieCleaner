"""Firefox browser cookie reader."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Iterator

from src.core.models import BrowserStore, CookieRecord
from src.scanner.cookie_reader import BaseCookieReader
from src.scanner.db_copy import cleanup_temp_db, copy_db_to_temp

logger = logging.getLogger(__name__)


def firefox_time_to_datetime(unix_seconds: int) -> datetime | None:
    """
    Convert Firefox timestamp to datetime.

    Firefox stores timestamps as Unix seconds since 1970-01-01.

    Args:
        unix_seconds: Unix timestamp value.

    Returns:
        datetime object in UTC, or None for session cookies (value 0).
    """
    if unix_seconds == 0:
        return None  # Session cookie - no expiry

    try:
        return datetime.fromtimestamp(unix_seconds, tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        # Handle invalid timestamps gracefully
        logger.debug("Invalid Firefox timestamp: %d", unix_seconds)
        return None


def normalize_domain(host: str) -> str:
    """
    Normalize domain by stripping leading dot.

    Firefox typically doesn't store leading dots, but normalize anyway.

    Args:
        host: Raw host from database.

    Returns:
        Normalized domain.
    """
    return host.lstrip(".")


class FirefoxCookieReader(BaseCookieReader):
    """Cookie reader for Firefox browser."""

    # Required columns for cookie reading
    REQUIRED_COLUMNS = {"host", "name", "isSecure", "expiry"}

    def read_cookies(self) -> list[CookieRecord]:
        """Read all cookies from the Firefox database."""
        return list(self.iter_cookies())

    def iter_cookies(self) -> Iterator[CookieRecord]:
        """Yield cookies from the Firefox database one at a time."""
        if not self.store.db_path.exists():
            logger.warning("Cookie database not found: %s", self.store.db_path)
            return

        temp_db = None
        try:
            # Copy to temp to avoid lock issues
            temp_db = copy_db_to_temp(self.store.db_path)

            conn = sqlite3.connect(f"file:{temp_db}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            try:
                # Verify table exists and get columns
                if not self._verify_schema(conn):
                    return

                cursor = conn.execute(
                    "SELECT host, name, isSecure, expiry FROM moz_cookies"
                )

                for row in cursor:
                    yield CookieRecord(
                        domain=normalize_domain(row["host"]),
                        raw_host_key=row["host"],
                        name=row["name"],
                        store=self.store,
                        expires=firefox_time_to_datetime(row["expiry"]),
                        is_secure=bool(row["isSecure"]),
                    )
            finally:
                conn.close()

        except sqlite3.Error as e:
            logger.error(
                "Failed to read cookies from %s (%s): %s",
                self.store.browser_name,
                self.store.profile_id,
                e,
            )
        finally:
            if temp_db:
                cleanup_temp_db(temp_db)

    def _verify_schema(self, conn: sqlite3.Connection) -> bool:
        """
        Verify the moz_cookies table exists and has required columns.

        Args:
            conn: SQLite connection.

        Returns:
            True if schema is valid, False otherwise.
        """
        try:
            # Check if moz_cookies table exists
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='moz_cookies'"
            )
            if cursor.fetchone() is None:
                logger.warning(
                    "No moz_cookies table in %s (%s)",
                    self.store.browser_name,
                    self.store.profile_id,
                )
                return False

            # Get column names
            cursor = conn.execute("PRAGMA table_info(moz_cookies)")
            columns = {row[1] for row in cursor.fetchall()}

            # Verify required columns exist
            missing = self.REQUIRED_COLUMNS - columns
            if missing:
                logger.warning(
                    "Missing columns in %s (%s): %s",
                    self.store.browser_name,
                    self.store.profile_id,
                    missing,
                )
                return False

            logger.debug(
                "%s (%s) has %d columns",
                self.store.browser_name,
                self.store.profile_id,
                len(columns),
            )
            return True

        except sqlite3.Error as e:
            logger.error("Failed to verify schema: %s", e)
            return False
