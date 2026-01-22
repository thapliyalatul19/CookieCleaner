"""Integration tests for browser process detection gate."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.execution.lock_resolver import LockResolver, BROWSER_EXECUTABLES


class TestProcessDetectionGate:
    """Integration tests for browser process detection."""

    def test_browser_executables_constant(self) -> None:
        """All major browsers are defined in BROWSER_EXECUTABLES."""
        expected = {"chrome.exe", "msedge.exe", "brave.exe", "firefox.exe", "opera.exe", "vivaldi.exe"}
        assert BROWSER_EXECUTABLES == expected

    def test_get_running_browsers_returns_set(self) -> None:
        """get_running_browsers returns a set of browser names."""
        resolver = LockResolver()
        result = resolver.get_running_browsers()

        assert isinstance(result, set)
        # All returned items should be browser executables
        for item in result:
            assert item in BROWSER_EXECUTABLES

    def test_preflight_browser_check_empty_when_no_browsers(self) -> None:
        """preflight_browser_check returns empty when no browsers running."""
        resolver = LockResolver()

        with patch.object(resolver, "get_running_browsers", return_value=set()):
            result = resolver.preflight_browser_check([
                Path("C:/Users/test/AppData/Local/Google/Chrome/User Data/Default/Network/Cookies"),
            ])

        assert result == {}

    def test_preflight_browser_check_maps_paths_to_browsers(self) -> None:
        """preflight_browser_check correctly maps database paths to browsers."""
        resolver = LockResolver()

        paths = [
            Path("C:/Users/test/AppData/Local/Google/Chrome/User Data/Default/Network/Cookies"),
            Path("C:/Users/test/AppData/Local/Microsoft/Edge/User Data/Default/Network/Cookies"),
            Path("C:/Users/test/AppData/Roaming/Mozilla/Firefox/Profiles/abc/cookies.sqlite"),
        ]

        with patch.object(resolver, "get_running_browsers", return_value={"chrome.exe", "msedge.exe", "firefox.exe"}):
            result = resolver.preflight_browser_check(paths)

        assert "chrome.exe" in result
        assert "msedge.exe" in result
        assert "firefox.exe" in result

    def test_preflight_check_only_returns_running_browsers(self) -> None:
        """preflight_browser_check only returns browsers that are actually running."""
        resolver = LockResolver()

        paths = [
            Path("C:/Users/test/AppData/Local/Google/Chrome/User Data/Default/Network/Cookies"),
            Path("C:/Users/test/AppData/Local/Microsoft/Edge/User Data/Default/Network/Cookies"),
        ]

        # Only Chrome is running, not Edge
        with patch.object(resolver, "get_running_browsers", return_value={"chrome.exe"}):
            result = resolver.preflight_browser_check(paths)

        assert "chrome.exe" in result
        assert "msedge.exe" not in result

    def test_get_browser_pids_integration(self) -> None:
        """get_browser_pids returns PIDs for specified browser."""
        resolver = LockResolver()

        # Mock process iteration
        mock_procs = [
            MagicMock(info={"name": "chrome.exe", "pid": 1234}),
            MagicMock(info={"name": "chrome.exe", "pid": 5678}),
            MagicMock(info={"name": "notepad.exe", "pid": 9999}),
        ]

        with patch("psutil.process_iter", return_value=mock_procs):
            pids = resolver.get_browser_pids("chrome.exe")

        assert 1234 in pids
        assert 5678 in pids
        assert 9999 not in pids

    def test_terminate_browser_graceful_only(self) -> None:
        """terminate_browser only tries graceful termination (no force kill)."""
        resolver = LockResolver()

        # Mock process that doesn't terminate gracefully
        mock_proc = MagicMock()
        mock_proc.pid = 1234

        with patch.object(resolver, "get_browser_pids", side_effect=[[1234], [1234]]):
            with patch("psutil.Process", return_value=mock_proc):
                with patch("psutil.wait_procs", return_value=([], [mock_proc])):
                    result = resolver.terminate_browser("chrome.exe")

        # Should try terminate
        mock_proc.terminate.assert_called_once()
        # Should NOT force kill (removed to avoid browser profile corruption)
        mock_proc.kill.assert_not_called()
        # Returns False since process didn't terminate
        assert result is False

    def test_check_lock_detects_blocking_process(self, tmp_path: Path) -> None:
        """check_lock identifies which browser is blocking."""
        resolver = LockResolver()

        # Create a test file in Chrome path
        chrome_db = tmp_path / "Google" / "Chrome" / "User Data" / "Default" / "Network" / "Cookies"
        chrome_db.parent.mkdir(parents=True)
        chrome_db.write_bytes(b"test")

        with patch.object(resolver, "get_running_browsers", return_value={"chrome.exe"}):
            with patch.object(resolver, "_check_with_win32", return_value=(True, 32)):
                report = resolver.check_lock(chrome_db)

        assert report.is_locked is True
        assert "chrome.exe" in report.blocking_processes


class TestDeleteExecutorPreflightGate:
    """Integration tests for preflight checks in DeleteExecutor."""

    def test_preflight_passes_for_unlocked_db(self, tmp_path: Path) -> None:
        """Preflight check passes for unlocked database."""
        import sqlite3
        from src.execution.delete_executor import DeleteExecutor

        # Create test database
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.commit()
        conn.close()

        executor = DeleteExecutor()
        can_proceed, error = executor._preflight_lock_check(db_path)

        assert can_proceed is True
        assert error is None

    def test_preflight_fails_for_locked_db(self, tmp_path: Path) -> None:
        """Preflight check fails for locked database."""
        import sqlite3
        from src.execution.delete_executor import DeleteExecutor

        # Create test database and hold lock
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.commit()

        # Hold exclusive lock
        conn.execute("BEGIN EXCLUSIVE")

        try:
            executor = DeleteExecutor()
            can_proceed, error = executor._preflight_lock_check(db_path)

            assert can_proceed is False
            assert error is not None
        finally:
            conn.rollback()
            conn.close()
