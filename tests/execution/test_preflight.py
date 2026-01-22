"""Tests for preflight safety checks in Cookie Cleaner.

Tests browser detection, BEGIN IMMEDIATE pre-check, and process termination.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.execution.lock_resolver import LockResolver, BROWSER_EXECUTABLES


class TestPreflightBrowserCheck:
    """Tests for preflight_browser_check method."""

    def test_no_running_browsers_returns_empty(self) -> None:
        """When no browsers are running, return empty dict."""
        resolver = LockResolver()
        with patch.object(resolver, "get_running_browsers", return_value=set()):
            result = resolver.preflight_browser_check([Path("C:/Users/test/Chrome/Cookies")])
        assert result == {}

    def test_running_browser_matched_to_path(self) -> None:
        """Running browser is matched to its database path."""
        resolver = LockResolver()
        chrome_path = Path("C:/Users/test/AppData/Local/Google/Chrome/User Data/Default/Network/Cookies")

        with patch.object(resolver, "get_running_browsers", return_value={"chrome.exe"}):
            result = resolver.preflight_browser_check([chrome_path])

        assert "chrome.exe" in result
        assert chrome_path in result["chrome.exe"]

    def test_multiple_browsers_multiple_paths(self) -> None:
        """Multiple running browsers matched to their paths."""
        resolver = LockResolver()
        chrome_path = Path("C:/Users/test/AppData/Local/Google/Chrome/Cookies")
        firefox_path = Path("C:/Users/test/AppData/Roaming/Mozilla/Firefox/cookies.sqlite")

        with patch.object(resolver, "get_running_browsers", return_value={"chrome.exe", "firefox.exe"}):
            result = resolver.preflight_browser_check([chrome_path, firefox_path])

        assert "chrome.exe" in result
        assert "firefox.exe" in result

    def test_unmatched_browser_not_included(self) -> None:
        """Running browser not matching any path is not included."""
        resolver = LockResolver()
        firefox_path = Path("C:/Users/test/AppData/Roaming/Mozilla/Firefox/cookies.sqlite")

        with patch.object(resolver, "get_running_browsers", return_value={"chrome.exe"}):
            result = resolver.preflight_browser_check([firefox_path])

        assert "chrome.exe" not in result


class TestGetBrowserPids:
    """Tests for get_browser_pids method."""

    def test_returns_pids_for_browser(self) -> None:
        """Returns PIDs for matching browser processes."""
        resolver = LockResolver()

        mock_proc1 = MagicMock()
        mock_proc1.info = {"name": "chrome.exe", "pid": 1234}
        mock_proc2 = MagicMock()
        mock_proc2.info = {"name": "chrome.exe", "pid": 5678}
        mock_proc3 = MagicMock()
        mock_proc3.info = {"name": "firefox.exe", "pid": 9999}

        with patch("psutil.process_iter", return_value=[mock_proc1, mock_proc2, mock_proc3]):
            pids = resolver.get_browser_pids("chrome.exe")

        assert 1234 in pids
        assert 5678 in pids
        assert 9999 not in pids

    def test_returns_empty_for_no_matches(self) -> None:
        """Returns empty list when no matching processes."""
        resolver = LockResolver()

        mock_proc = MagicMock()
        mock_proc.info = {"name": "notepad.exe", "pid": 1234}

        with patch("psutil.process_iter", return_value=[mock_proc]):
            pids = resolver.get_browser_pids("chrome.exe")

        assert pids == []

    def test_case_insensitive_matching(self) -> None:
        """Browser name matching is case insensitive."""
        resolver = LockResolver()

        mock_proc = MagicMock()
        mock_proc.info = {"name": "Chrome.EXE", "pid": 1234}

        with patch("psutil.process_iter", return_value=[mock_proc]):
            pids = resolver.get_browser_pids("chrome.exe")

        assert 1234 in pids


class TestTerminateBrowser:
    """Tests for terminate_browser method."""

    def test_returns_true_when_no_processes(self) -> None:
        """Returns True when browser has no running processes."""
        resolver = LockResolver()

        with patch.object(resolver, "get_browser_pids", return_value=[]):
            result = resolver.terminate_browser("chrome.exe")

        assert result is True

    def test_terminates_processes_gracefully(self) -> None:
        """Terminates processes gracefully first."""
        resolver = LockResolver()

        mock_proc = MagicMock()
        mock_proc.pid = 1234

        with patch.object(resolver, "get_browser_pids", side_effect=[[1234], []]):
            with patch("psutil.Process", return_value=mock_proc):
                with patch("psutil.wait_procs", return_value=([], [])):
                    result = resolver.terminate_browser("chrome.exe")

        mock_proc.terminate.assert_called_once()
        assert result is True

    def test_force_kills_stubborn_processes(self) -> None:
        """Force kills processes that don't terminate gracefully."""
        resolver = LockResolver()

        mock_proc = MagicMock()
        mock_proc.pid = 1234

        with patch.object(resolver, "get_browser_pids", side_effect=[[1234], []]):
            with patch("psutil.Process", return_value=mock_proc):
                # Process stays alive after terminate
                with patch("psutil.wait_procs", return_value=([], [mock_proc])):
                    result = resolver.terminate_browser("chrome.exe")

        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()
        assert result is True

    def test_returns_false_when_termination_fails(self) -> None:
        """Returns False when processes cannot be terminated."""
        resolver = LockResolver()

        mock_proc = MagicMock()
        mock_proc.pid = 1234

        # Still has running processes after kill attempt
        with patch.object(resolver, "get_browser_pids", side_effect=[[1234], [1234]]):
            with patch("psutil.Process", return_value=mock_proc):
                with patch("psutil.wait_procs", return_value=([], [mock_proc])):
                    result = resolver.terminate_browser("chrome.exe")

        assert result is False


class TestPreflightLockCheck:
    """Tests for _preflight_lock_check in DeleteExecutor."""

    def test_passes_for_nonexistent_db(self, tmp_path: Path) -> None:
        """Preflight passes for non-existent database."""
        from src.execution.delete_executor import DeleteExecutor

        executor = DeleteExecutor()
        db_path = tmp_path / "nonexistent.db"

        can_proceed, error = executor._preflight_lock_check(db_path)

        assert can_proceed is True
        assert error is None

    def test_passes_for_unlocked_db(self, tmp_path: Path) -> None:
        """Preflight passes for unlocked database."""
        from src.execution.delete_executor import DeleteExecutor

        # Create a test database
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.commit()
        conn.close()

        executor = DeleteExecutor()
        can_proceed, error = executor._preflight_lock_check(db_path)

        assert can_proceed is True
        assert error is None

    def test_fails_for_locked_db(self, tmp_path: Path) -> None:
        """Preflight fails for locked database."""
        from src.execution.delete_executor import DeleteExecutor

        # Create a test database
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.commit()

        # Hold an exclusive lock
        conn.execute("BEGIN EXCLUSIVE")

        try:
            executor = DeleteExecutor()
            can_proceed, error = executor._preflight_lock_check(db_path)

            assert can_proceed is False
            assert error is not None
            assert "locked" in error.lower() or "busy" in error.lower()
        finally:
            conn.rollback()
            conn.close()


class TestBrowserExecutablesConstant:
    """Tests for BROWSER_EXECUTABLES constant."""

    def test_contains_major_browsers(self) -> None:
        """BROWSER_EXECUTABLES contains all major browsers."""
        expected = {"chrome.exe", "msedge.exe", "brave.exe", "firefox.exe", "opera.exe", "vivaldi.exe"}
        assert BROWSER_EXECUTABLES == expected
