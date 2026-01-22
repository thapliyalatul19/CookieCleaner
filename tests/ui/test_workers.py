"""Tests for UI worker threads."""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

# Skip all tests if PyQt6 is not available
pytest.importorskip("PyQt6")

from src.core.models import BrowserStore, CookieRecord, DomainAggregate, DeletePlan
from src.core.whitelist import WhitelistManager
from src.execution import DeleteReport, LockReport

from src.ui.workers.scan_worker import ScanWorker
from src.ui.workers.clean_worker import CleanWorker


class TestScanWorker:
    """Tests for ScanWorker."""

    @pytest.fixture
    def whitelist_manager(self):
        """Create a WhitelistManager for testing."""
        return WhitelistManager(["domain:google.com"])

    def test_scan_worker_creates_without_error(self, whitelist_manager):
        """ScanWorker should create successfully."""
        worker = ScanWorker(whitelist_manager)
        assert worker is not None

    def test_scan_worker_set_whitelist_manager(self, whitelist_manager):
        """set_whitelist_manager() should update the manager."""
        worker = ScanWorker()

        new_manager = WhitelistManager(["domain:test.com"])
        worker.set_whitelist_manager(new_manager)
        assert worker._whitelist_manager is new_manager

    def test_scan_worker_cancel(self, whitelist_manager):
        """cancel() should set the cancelled flag."""
        worker = ScanWorker(whitelist_manager)

        worker.cancel()
        assert worker._cancelled is True

    @patch("src.ui.workers.scan_worker.ProfileResolver")
    @patch("src.ui.workers.scan_worker.create_reader")
    def test_scan_worker_emits_finished_signal(
        self, mock_create_reader, mock_resolver_class, qtbot, whitelist_manager
    ):
        """ScanWorker should emit finished signal with results."""
        # Setup mocks
        mock_resolver = MagicMock()
        mock_resolver.discover_all.return_value = []
        mock_resolver_class.return_value = mock_resolver

        worker = ScanWorker(whitelist_manager)

        with qtbot.waitSignal(worker.finished, timeout=5000) as blocker:
            worker.start()
            worker.wait()

        assert blocker.signal_triggered
        assert isinstance(blocker.args[0], list)

    @patch("src.ui.workers.scan_worker.ProfileResolver")
    @patch("src.ui.workers.scan_worker.create_reader")
    def test_scan_worker_aggregates_cookies(
        self, mock_create_reader, mock_resolver_class, qtbot, whitelist_manager
    ):
        """ScanWorker should aggregate cookies by domain."""
        # Setup mocks
        store = BrowserStore(
            browser_name="Chrome",
            profile_id="Default",
            db_path=Path("C:/fake/Cookies"),
            is_chromium=True,
        )

        mock_resolver = MagicMock()
        mock_resolver.discover_all.return_value = [store]
        mock_resolver_class.return_value = mock_resolver

        mock_reader = MagicMock()
        mock_reader.read_cookies.return_value = [
            CookieRecord(
                domain="example.com",
                raw_host_key=".example.com",
                name="cookie1",
                store=store,
            ),
            CookieRecord(
                domain="example.com",
                raw_host_key=".example.com",
                name="cookie2",
                store=store,
            ),
        ]
        mock_create_reader.return_value = mock_reader

        worker = ScanWorker(whitelist_manager)

        with qtbot.waitSignal(worker.finished, timeout=5000) as blocker:
            worker.start()
            worker.wait()

        results = blocker.args[0]
        assert len(results) == 1
        assert results[0].normalized_domain == "example.com"
        assert results[0].cookie_count == 2


class TestCleanWorker:
    """Tests for CleanWorker."""

    @pytest.fixture
    def sample_domains(self):
        """Create sample domains for testing."""
        store = BrowserStore(
            browser_name="Chrome",
            profile_id="Default",
            db_path=Path("C:/fake/Cookies"),
            is_chromium=True,
        )
        return [
            DomainAggregate(
                normalized_domain="example.com",
                cookie_count=2,
                browsers={"Chrome"},
                records=[
                    CookieRecord(
                        domain="example.com",
                        raw_host_key=".example.com",
                        name="cookie1",
                        store=store,
                    ),
                ],
                raw_host_keys={".example.com"},
            ),
        ]

    def test_clean_worker_creates_without_error(self, sample_domains):
        """CleanWorker should create successfully."""
        worker = CleanWorker(sample_domains, dry_run=True)
        assert worker is not None

    def test_clean_worker_set_domains(self, sample_domains):
        """set_domains() should update the domains list."""
        worker = CleanWorker()

        worker.set_domains(sample_domains)
        assert worker._domains is sample_domains

    def test_clean_worker_set_dry_run(self):
        """set_dry_run() should update the dry run flag."""
        worker = CleanWorker()

        worker.set_dry_run(True)
        assert worker._dry_run is True

        worker.set_dry_run(False)
        assert worker._dry_run is False

    def test_clean_worker_cancel(self):
        """cancel() should set the cancelled flag."""
        worker = CleanWorker()

        worker.cancel()
        assert worker._cancelled is True

    def test_clean_worker_empty_domains_emits_finished(self, qtbot):
        """CleanWorker with empty domains should emit finished immediately."""
        worker = CleanWorker(domains_to_delete=[], dry_run=True)

        with qtbot.waitSignal(worker.finished, timeout=5000) as blocker:
            worker.start()
            worker.wait()

        assert blocker.signal_triggered
        report = blocker.args[0]
        assert isinstance(report, DeleteReport)
        assert report.total_deleted == 0

    def test_clean_worker_emits_lock_detected_on_locked_db(
        self, qtbot, sample_domains, tmp_path
    ):
        """CleanWorker should emit lock_detected when databases are locked."""
        # Create a real temp database file so validation passes
        db_path = tmp_path / "Cookies"
        db_path.touch()

        # Update sample_domains to use real path
        for domain in sample_domains:
            for record in domain.records:
                record.store.db_path = db_path

        worker = CleanWorker(sample_domains, dry_run=False)

        # Mock lock detection
        lock_report = LockReport(
            db_path=db_path,
            is_locked=True,
            blocking_processes=["chrome.exe"],
        )
        worker._lock_resolver = MagicMock()
        worker._lock_resolver.check_all.return_value = [lock_report]
        worker._lock_resolver.get_running_browsers.return_value = set()

        with qtbot.waitSignal(worker.lock_detected, timeout=5000) as blocker:
            worker.start()
            worker.wait()

        assert blocker.signal_triggered
        reports = blocker.args[0]
        assert len(reports) == 1
        assert reports[0].is_locked

    def test_clean_worker_uses_delete_planner(self, sample_domains):
        """CleanWorker should use DeletePlanner for plan building."""
        worker = CleanWorker(sample_domains, dry_run=True)

        # Verify the planner is available
        assert hasattr(worker, '_planner')
        from src.core.delete_planner import DeletePlanner
        assert isinstance(worker._planner, DeletePlanner)
