"""Background scan worker for Cookie Cleaner.

Runs cookie scanning in a separate thread to prevent UI blocking.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from PyQt6.QtCore import QThread, pyqtSignal

from src.core.models import BrowserStore, CookieRecord, DomainAggregate
from src.core.whitelist import WhitelistManager
from src.scanner import ProfileResolver, create_reader

logger = logging.getLogger(__name__)


class ScanWorker(QThread):
    """
    Background worker for scanning browser cookies.

    Discovers profiles, reads cookies, aggregates by domain,
    and filters out whitelisted domains.
    """

    progress = pyqtSignal(str)  # Status messages
    finished = pyqtSignal(list)  # list[DomainAggregate]
    error = pyqtSignal(str, str)  # (error_type, error_message)

    def __init__(
        self,
        whitelist_manager: WhitelistManager | None = None,
        parent=None,
    ) -> None:
        """
        Initialize the ScanWorker.

        Args:
            whitelist_manager: WhitelistManager for filtering
            parent: Parent QObject
        """
        super().__init__(parent)
        self._whitelist_manager = whitelist_manager or WhitelistManager()
        self._cancelled = False

    def set_whitelist_manager(self, manager: WhitelistManager) -> None:
        """Update the whitelist manager."""
        self._whitelist_manager = manager

    def cancel(self) -> None:
        """Request cancellation of the scan."""
        self._cancelled = True

    def run(self) -> None:
        """
        Execute the scan in a background thread.

        Emits:
            progress: Status messages during scan
            finished: List of DomainAggregate results
            error: Error details if scan fails
        """
        self._cancelled = False

        try:
            # Step 1: Discover browser profiles
            self.progress.emit("Discovering browser profiles...")
            resolver = ProfileResolver()
            stores = resolver.discover_all()

            if not stores:
                self.progress.emit("No browser profiles found")
                self.finished.emit([])
                return

            self.progress.emit(f"Found {len(stores)} browser profiles")

            # Step 2: Read cookies from each profile
            all_cookies: list[CookieRecord] = []

            for store in stores:
                if self._cancelled:
                    self.progress.emit("Scan cancelled")
                    return

                self.progress.emit(f"Scanning {store.browser_name}/{store.profile_id}...")

                try:
                    reader = create_reader(store)
                    cookies = reader.read_cookies()
                    all_cookies.extend(cookies)
                    self.progress.emit(
                        f"Found {len(cookies)} cookies in {store.browser_name}/{store.profile_id}"
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to read cookies from %s/%s: %s",
                        store.browser_name,
                        store.profile_id,
                        e,
                    )
                    self.progress.emit(
                        f"Warning: Could not read {store.browser_name}/{store.profile_id}"
                    )

            if self._cancelled:
                self.progress.emit("Scan cancelled")
                return

            # Step 3: Aggregate by domain
            self.progress.emit("Aggregating cookies by domain...")
            aggregates = self._aggregate_cookies(all_cookies)

            # Step 4: Filter out whitelisted domains
            self.progress.emit("Filtering whitelisted domains...")
            filtered = self._filter_whitelisted(aggregates)

            self.progress.emit(
                f"Scan complete: {len(filtered)} domains, "
                f"{sum(a.cookie_count for a in filtered)} cookies to delete"
            )
            self.finished.emit(filtered)

        except Exception as e:
            logger.exception("Scan failed with error")
            self.error.emit(type(e).__name__, str(e))

    def _aggregate_cookies(
        self, cookies: list[CookieRecord]
    ) -> list[DomainAggregate]:
        """
        Aggregate cookies by normalized domain.

        Args:
            cookies: List of CookieRecord instances

        Returns:
            List of DomainAggregate instances
        """
        domain_map: dict[str, DomainAggregate] = {}

        for cookie in cookies:
            domain = cookie.domain

            if domain not in domain_map:
                domain_map[domain] = DomainAggregate(
                    normalized_domain=domain,
                    cookie_count=0,
                    browsers=set(),
                    records=[],
                    raw_host_keys=set(),
                )

            agg = domain_map[domain]
            agg.cookie_count += 1
            agg.browsers.add(cookie.store.browser_name)
            agg.records.append(cookie)
            agg.raw_host_keys.add(cookie.raw_host_key)

        # Sort by domain name
        return sorted(domain_map.values(), key=lambda a: a.normalized_domain)

    def _filter_whitelisted(
        self, aggregates: list[DomainAggregate]
    ) -> list[DomainAggregate]:
        """
        Filter out whitelisted domains.

        Args:
            aggregates: List of DomainAggregate instances

        Returns:
            Filtered list with whitelisted domains removed
        """
        return [
            agg
            for agg in aggregates
            if not self._whitelist_manager.is_whitelisted(agg.normalized_domain)
        ]
