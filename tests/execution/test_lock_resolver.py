"""Tests for LockResolver."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.execution.lock_resolver import LockResolver, LockReport, BROWSER_PATH_MAPPINGS


class TestLockReport:
    """Tests for LockReport dataclass."""

    def test_can_proceed_when_not_locked(self):
        """can_proceed returns True when file is not locked."""
        report = LockReport(db_path=Path("/test"), is_locked=False)
        assert report.can_proceed is True

    def test_can_proceed_when_locked(self):
        """can_proceed returns False when file is locked."""
        report = LockReport(db_path=Path("/test"), is_locked=True)
        assert report.can_proceed is False

    def test_blocking_processes_default_empty(self):
        """blocking_processes defaults to empty list."""
        report = LockReport(db_path=Path("/test"), is_locked=False)
        assert report.blocking_processes == []


class TestLockResolver:
    """Tests for LockResolver class."""

    @pytest.fixture
    def resolver(self):
        """Create a LockResolver instance."""
        return LockResolver()

    @pytest.fixture
    def temp_file(self):
        """Create a temporary file for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            f.write(b"test data")
            path = Path(f.name)
        yield path
        if path.exists():
            path.unlink()

    def test_check_lock_nonexistent_file(self, resolver):
        """check_lock returns not locked for nonexistent file."""
        report = resolver.check_lock(Path("/nonexistent/path.db"))
        assert report.is_locked is False
        assert report.can_proceed is True

    def test_check_lock_accessible_file(self, resolver, temp_file):
        """check_lock returns not locked for accessible file."""
        report = resolver.check_lock(temp_file)
        assert report.is_locked is False
        assert report.can_proceed is True
        assert report.db_path == temp_file

    def test_check_all_multiple_files(self, resolver, temp_file):
        """check_all returns reports for all files."""
        paths = [temp_file, Path("/nonexistent/path.db")]
        reports = resolver.check_all(paths)
        assert len(reports) == 2
        assert reports[0].db_path == temp_file
        assert reports[1].db_path == Path("/nonexistent/path.db")

    @patch("src.execution.lock_resolver.psutil.process_iter")
    def test_get_running_browsers_finds_chrome(self, mock_process_iter, resolver):
        """get_running_browsers detects running Chrome."""
        mock_proc = MagicMock()
        mock_proc.info = {"name": "chrome.exe"}
        mock_process_iter.return_value = [mock_proc]

        browsers = resolver.get_running_browsers()
        assert "chrome.exe" in browsers

    @patch("src.execution.lock_resolver.psutil.process_iter")
    def test_get_running_browsers_multiple_browsers(self, mock_process_iter, resolver):
        """get_running_browsers detects multiple browsers."""
        mock_procs = [
            MagicMock(info={"name": "chrome.exe"}),
            MagicMock(info={"name": "firefox.exe"}),
            MagicMock(info={"name": "notepad.exe"}),  # Not a browser
        ]
        mock_process_iter.return_value = mock_procs

        browsers = resolver.get_running_browsers()
        assert "chrome.exe" in browsers
        assert "firefox.exe" in browsers
        assert "notepad.exe" not in browsers

    @patch("src.execution.lock_resolver.psutil.process_iter")
    def test_get_running_browsers_empty_when_no_browsers(self, mock_process_iter, resolver):
        """get_running_browsers returns empty set when no browsers running."""
        mock_process_iter.return_value = []
        browsers = resolver.get_running_browsers()
        assert browsers == set()

    @patch("src.execution.lock_resolver.psutil.process_iter")
    def test_get_running_browsers_handles_process_error(self, mock_process_iter, resolver):
        """get_running_browsers handles process enumeration errors."""
        mock_process_iter.side_effect = Exception("Process error")
        browsers = resolver.get_running_browsers()
        assert browsers == set()


class TestBrowserPathMappings:
    """Tests for browser path to executable mappings."""

    def test_chrome_path_mapping(self):
        """Chrome paths map to chrome.exe."""
        assert BROWSER_PATH_MAPPINGS["chrome"] == "chrome.exe"
        assert BROWSER_PATH_MAPPINGS["google\\chrome"] == "chrome.exe"

    def test_edge_path_mapping(self):
        """Edge paths map to msedge.exe."""
        assert BROWSER_PATH_MAPPINGS["microsoft\\edge"] == "msedge.exe"
        assert BROWSER_PATH_MAPPINGS["edge"] == "msedge.exe"

    def test_firefox_path_mapping(self):
        """Firefox paths map to firefox.exe."""
        assert BROWSER_PATH_MAPPINGS["firefox"] == "firefox.exe"
        assert BROWSER_PATH_MAPPINGS["mozilla\\firefox"] == "firefox.exe"


class TestLockDetectionWithMocks:
    """Tests for lock detection using mocks."""

    @pytest.fixture
    def resolver(self):
        """Create a LockResolver instance."""
        return LockResolver()

    @pytest.fixture
    def temp_file(self):
        """Create a temporary file for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            f.write(b"test data")
            path = Path(f.name)
        yield path
        if path.exists():
            path.unlink()

    @patch.object(LockResolver, "_check_with_win32")
    @patch.object(LockResolver, "_find_blocking_processes")
    def test_locked_file_returns_blocking_processes(
        self, mock_find_blocking, mock_check_win32, resolver, temp_file
    ):
        """Locked file includes blocking processes in report."""
        mock_check_win32.return_value = (True, 32)
        mock_find_blocking.return_value = ["chrome.exe"]

        report = resolver.check_lock(temp_file)

        assert report.is_locked is True
        assert report.error_code == 32
        assert "chrome.exe" in report.blocking_processes
