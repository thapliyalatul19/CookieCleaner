"""Tests for the UI state machine."""

import pytest

from src.ui.state_machine import AppState, StateManager, InvalidTransitionError


class TestAppState:
    """Tests for AppState enumeration."""

    def test_state_values(self):
        """Test that state values are correct strings."""
        assert AppState.IDLE.value == "idle"
        assert AppState.SCANNING.value == "scanning"
        assert AppState.READY.value == "ready"
        assert AppState.CLEANING.value == "cleaning"
        assert AppState.ERROR.value == "error"


class TestStateManager:
    """Tests for StateManager class."""

    def test_initial_state_is_idle(self):
        """StateManager should start in IDLE state."""
        manager = StateManager()
        assert manager.state == AppState.IDLE

    def test_valid_transition_idle_to_scanning(self):
        """IDLE -> SCANNING should be valid."""
        manager = StateManager()
        assert manager.can_transition_to(AppState.SCANNING)
        result = manager.transition_to(AppState.SCANNING)
        assert result is True
        assert manager.state == AppState.SCANNING

    def test_valid_transition_scanning_to_ready(self):
        """SCANNING -> READY should be valid."""
        manager = StateManager()
        manager.transition_to(AppState.SCANNING)
        assert manager.can_transition_to(AppState.READY)
        result = manager.transition_to(AppState.READY)
        assert result is True
        assert manager.state == AppState.READY

    def test_valid_transition_scanning_to_error(self):
        """SCANNING -> ERROR should be valid."""
        manager = StateManager()
        manager.transition_to(AppState.SCANNING)
        assert manager.can_transition_to(AppState.ERROR)
        result = manager.transition_to(AppState.ERROR, "Test error")
        assert result is True
        assert manager.state == AppState.ERROR
        assert manager.error_message == "Test error"

    def test_valid_transition_ready_to_scanning(self):
        """READY -> SCANNING should be valid (rescan)."""
        manager = StateManager()
        manager.transition_to(AppState.SCANNING)
        manager.transition_to(AppState.READY)
        assert manager.can_transition_to(AppState.SCANNING)
        result = manager.transition_to(AppState.SCANNING)
        assert result is True
        assert manager.state == AppState.SCANNING

    def test_valid_transition_ready_to_cleaning(self):
        """READY -> CLEANING should be valid."""
        manager = StateManager()
        manager.transition_to(AppState.SCANNING)
        manager.transition_to(AppState.READY)
        assert manager.can_transition_to(AppState.CLEANING)
        result = manager.transition_to(AppState.CLEANING)
        assert result is True
        assert manager.state == AppState.CLEANING

    def test_valid_transition_cleaning_to_ready(self):
        """CLEANING -> READY should be valid."""
        manager = StateManager()
        manager.transition_to(AppState.SCANNING)
        manager.transition_to(AppState.READY)
        manager.transition_to(AppState.CLEANING)
        assert manager.can_transition_to(AppState.READY)
        result = manager.transition_to(AppState.READY)
        assert result is True
        assert manager.state == AppState.READY

    def test_valid_transition_cleaning_to_error(self):
        """CLEANING -> ERROR should be valid."""
        manager = StateManager()
        manager.transition_to(AppState.SCANNING)
        manager.transition_to(AppState.READY)
        manager.transition_to(AppState.CLEANING)
        assert manager.can_transition_to(AppState.ERROR)
        result = manager.transition_to(AppState.ERROR, "Clean failed")
        assert result is True
        assert manager.state == AppState.ERROR

    def test_valid_transition_error_to_idle(self):
        """ERROR -> IDLE should be valid (user acknowledgment)."""
        manager = StateManager()
        manager.transition_to(AppState.SCANNING)
        manager.transition_to(AppState.ERROR, "Test error")
        assert manager.can_transition_to(AppState.IDLE)
        result = manager.transition_to(AppState.IDLE)
        assert result is True
        assert manager.state == AppState.IDLE
        assert manager.error_message == ""

    def test_invalid_transition_idle_to_ready(self):
        """IDLE -> READY should be invalid."""
        manager = StateManager()
        assert not manager.can_transition_to(AppState.READY)
        with pytest.raises(InvalidTransitionError):
            manager.transition_to(AppState.READY)
        assert manager.state == AppState.IDLE

    def test_invalid_transition_idle_to_cleaning(self):
        """IDLE -> CLEANING should be invalid."""
        manager = StateManager()
        assert not manager.can_transition_to(AppState.CLEANING)
        with pytest.raises(InvalidTransitionError):
            manager.transition_to(AppState.CLEANING)

    def test_invalid_transition_ready_to_idle(self):
        """READY -> IDLE should be invalid."""
        manager = StateManager()
        manager.transition_to(AppState.SCANNING)
        manager.transition_to(AppState.READY)
        assert not manager.can_transition_to(AppState.IDLE)
        with pytest.raises(InvalidTransitionError):
            manager.transition_to(AppState.IDLE)

    def test_invalid_transition_error_to_ready(self):
        """ERROR -> READY should be invalid."""
        manager = StateManager()
        manager.transition_to(AppState.SCANNING)
        manager.transition_to(AppState.ERROR, "Error")
        assert not manager.can_transition_to(AppState.READY)
        with pytest.raises(InvalidTransitionError):
            manager.transition_to(AppState.READY)

    def test_convenience_method_start_scan(self):
        """start_scan() should transition to SCANNING."""
        manager = StateManager()
        result = manager.start_scan()
        assert result is True
        assert manager.state == AppState.SCANNING

    def test_convenience_method_scan_complete(self):
        """scan_complete() should transition to READY."""
        manager = StateManager()
        manager.start_scan()
        result = manager.scan_complete()
        assert result is True
        assert manager.state == AppState.READY

    def test_convenience_method_scan_error(self):
        """scan_error() should transition to ERROR with message."""
        manager = StateManager()
        manager.start_scan()
        result = manager.scan_error("Scan failed")
        assert result is True
        assert manager.state == AppState.ERROR
        assert manager.error_message == "Scan failed"

    def test_convenience_method_start_clean(self):
        """start_clean() should transition to CLEANING from READY."""
        manager = StateManager()
        manager.start_scan()
        manager.scan_complete()
        result = manager.start_clean()
        assert result is True
        assert manager.state == AppState.CLEANING

    def test_convenience_method_clean_complete(self):
        """clean_complete() should transition to READY."""
        manager = StateManager()
        manager.start_scan()
        manager.scan_complete()
        manager.start_clean()
        result = manager.clean_complete()
        assert result is True
        assert manager.state == AppState.READY

    def test_convenience_method_acknowledge_error(self):
        """acknowledge_error() should transition to IDLE from ERROR."""
        manager = StateManager()
        manager.start_scan()
        manager.scan_error("Error")
        result = manager.acknowledge_error()
        assert result is True
        assert manager.state == AppState.IDLE

    def test_reset_from_error_state(self):
        """reset() should transition from ERROR to IDLE."""
        manager = StateManager()
        manager.start_scan()
        manager.scan_error("Error")
        manager.reset()
        assert manager.state == AppState.IDLE

    def test_full_happy_path(self):
        """Test the full happy path: IDLE -> SCANNING -> READY -> CLEANING -> READY."""
        manager = StateManager()

        assert manager.state == AppState.IDLE
        manager.start_scan()
        assert manager.state == AppState.SCANNING
        manager.scan_complete()
        assert manager.state == AppState.READY
        manager.start_clean()
        assert manager.state == AppState.CLEANING
        manager.clean_complete()
        assert manager.state == AppState.READY
        # Can scan again
        manager.start_scan()
        assert manager.state == AppState.SCANNING

    def test_error_recovery_path(self):
        """Test error recovery: IDLE -> SCANNING -> ERROR -> IDLE -> SCANNING."""
        manager = StateManager()

        manager.start_scan()
        assert manager.state == AppState.SCANNING
        manager.scan_error("Something went wrong")
        assert manager.state == AppState.ERROR
        manager.acknowledge_error()
        assert manager.state == AppState.IDLE
        # Can scan again after error recovery
        manager.start_scan()
        assert manager.state == AppState.SCANNING
