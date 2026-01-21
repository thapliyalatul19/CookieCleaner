"""Base cookie reader interface and factory."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from src.core.models import BrowserStore, CookieRecord


class BaseCookieReader(ABC):
    """Abstract base class for cookie database readers."""

    def __init__(self, store: BrowserStore) -> None:
        """
        Initialize reader with a browser store.

        Args:
            store: BrowserStore containing database path and metadata.
        """
        self.store = store

    @abstractmethod
    def read_cookies(self) -> list[CookieRecord]:
        """
        Read all cookies from the database.

        Returns:
            List of CookieRecord objects.

        Raises:
            FileNotFoundError: If database doesn't exist.
            sqlite3.Error: If database is corrupted or unreadable.
        """

    @abstractmethod
    def iter_cookies(self) -> Iterator[CookieRecord]:
        """
        Yield cookies one at a time for memory-efficient processing.

        Yields:
            CookieRecord objects.
        """


def create_reader(store: BrowserStore) -> BaseCookieReader:
    """
    Factory function to create the appropriate reader for a browser store.

    Args:
        store: BrowserStore containing database info and is_chromium flag.

    Returns:
        ChromiumCookieReader for Chromium-based browsers,
        FirefoxCookieReader for Firefox.
    """
    # Import here to avoid circular imports
    from src.scanner.chromium_cookie_reader import ChromiumCookieReader
    from src.scanner.firefox_cookie_reader import FirefoxCookieReader

    if store.is_chromium:
        return ChromiumCookieReader(store)
    return FirefoxCookieReader(store)
