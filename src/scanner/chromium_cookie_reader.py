"""Chromium-based browser cookie reader."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from src.core.models import BrowserStore, CookieRecord
from src.scanner.cookie_reader import BaseCookieReader
from src.scanner.db_copy import cleanup_temp_db, copy_db_to_temp

logger = logging.getLogger(__name__)

# Chromium timestamp epoch offset
# Windows FILETIME epoch: 1601-01-01
# Unix epoch: 1970-01-01
# Difference: 11644473600 seconds
CHROMIUM_EPOCH_OFFSET = 11644473600


def chromium_time_to_datetime(microseconds: int) -> datetime | None:
    """
    Convert Chromium timestamp to datetime.

    Chromium stores timestamps as microseconds since 1601-01-01 (Windows FILETIME).

    Args:
        microseconds: Chromium timestamp value.

    Returns:
        datetime object in UTC, or None for session cookies (value 0).
    """
    if microseconds == 0:
        return None  # Session cookie - no expiry

    try:
        seconds = (microseconds / 1_000_000) - CHROMIUM_EPOCH_OFFSET
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        # Handle invalid timestamps gracefully
        logger.debug("Invalid Chromium timestamp: %d", microseconds)
        return None


def normalize_domain(host_key: str) -> str:
    """
    Normalize domain by stripping leading dot.

    Args:
        host_key: Raw host_key from database (e.g., ".google.com").

    Returns:
        Normalized domain (e.g., "google.com").
    """
    return host_key.lstrip(".")


class ChromiumCookieReader(BaseCookieReader):
    """Cookie reader for Chromium-based browsers (Chrome, Edge, Brave, etc.)."""

    # Required columns for cookie reading
    REQUIRED_COLUMNS = {"host_key", "name", "is_secure", "expires_utc"}

    def read_cookies(self) -> list[CookieRecord]:
        """Read all cookies from the Chromium database."""
        return list(self.iter_cookies())

    def iter_cookies(self) -> Iterator[CookieRecord]:
        """Yield cookies from the Chromium database one at a time."""
        if not self.store.db_path.exists():
            logger.warning("Cookie database not found: %s", self.store.db_path)
            return

        temp_db: Path | None = None
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
                    "SELECT host_key, name, is_secure, expires_utc FROM cookies"
                )

                for row in cursor:
                    yield CookieRecord(
                        domain=normalize_domain(row["host_key"]),
                        raw_host_key=row["host_key"],
                        name=row["name"],
                        store=self.store,
                        expires=chromium_time_to_datetime(row["expires_utc"]),
                        is_secure=bool(row["is_secure"]),
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
        Verify the cookies table exists and has required columns.

        Uses PRAGMA table_info for dynamic column detection to handle
        both 20-column (Chrome) and 22-column (Edge) schemas.

        Args:
            conn: SQLite connection.

        Returns:
            True if schema is valid, False otherwise.
        """
        try:
            # Check if cookies table exists
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='cookies'"
            )
            if cursor.fetchone() is None:
                logger.warning(
                    "No cookies table in %s (%s)",
                    self.store.browser_name,
                    self.store.profile_id,
                )
                return False

            # Get column names
            cursor = conn.execute("PRAGMA table_info(cookies)")
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
