"""Application state machine for Cookie Cleaner.

Implements strict FSM enforcement per PRD Section 3.2:
    Idle --[Scan]--> Scanning --[Success]--> Ready
                           |--[Error]--> Error
    Ready --[Clean]--> Cleaning --[Success]--> Ready
                            |--[Error]--> Error
    Error --[User Ack]--> Idle
"""

from __future__ import annotations

import logging
from enum import Enum

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class AppState(Enum):
    """Application state enumeration."""

    IDLE = "idle"
    SCANNING = "scanning"
    READY = "ready"
    CLEANING = "cleaning"
    ERROR = "error"


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    pass


class StateManager(QObject):
    """
    Manages application state transitions with validation.

    Emits state_changed signal when transitions occur.
    Enforces valid state transitions per the FSM diagram.
    """

    state_changed = pyqtSignal(AppState)

    VALID_TRANSITIONS: dict[AppState, set[AppState]] = {
        AppState.IDLE: {AppState.SCANNING},
        AppState.SCANNING: {AppState.READY, AppState.ERROR},
        AppState.READY: {AppState.SCANNING, AppState.CLEANING},
        AppState.CLEANING: {AppState.READY, AppState.ERROR},
        AppState.ERROR: {AppState.IDLE, AppState.SCANNING},  # Allow scan from error state
    }

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize the StateManager in IDLE state."""
        super().__init__(parent)
        self._state = AppState.IDLE
        self._error_message: str = ""

    @property
    def state(self) -> AppState:
        """Return the current application state."""
        return self._state

    @property
    def error_message(self) -> str:
        """Return the current error message, if in ERROR state."""
        return self._error_message

    def can_transition_to(self, new_state: AppState) -> bool:
        """
        Check if transition to the given state is valid.

        Args:
            new_state: The target state

        Returns:
            True if the transition is valid
        """
        return new_state in self.VALID_TRANSITIONS.get(self._state, set())

    def transition_to(self, new_state: AppState, error_message: str = "") -> bool:
        """
        Attempt to transition to a new state.

        Args:
            new_state: The target state
            error_message: Error message if transitioning to ERROR state

        Returns:
            True if transition succeeded, False otherwise

        Raises:
            InvalidTransitionError: If transition is not valid
        """
        if not self.can_transition_to(new_state):
            msg = f"Invalid transition: {self._state.value} -> {new_state.value}"
            logger.warning(msg)
            raise InvalidTransitionError(msg)

        old_state = self._state
        self._state = new_state

        if new_state == AppState.ERROR:
            self._error_message = error_message
        else:
            self._error_message = ""

        logger.info("State transition: %s -> %s", old_state.value, new_state.value)
        self.state_changed.emit(new_state)
        return True

    def reset(self) -> None:
        """Reset the state machine to IDLE (for use after error acknowledgment)."""
        if self._state == AppState.ERROR:
            self.transition_to(AppState.IDLE)
        else:
            logger.warning("Reset called from non-ERROR state: %s", self._state.value)

    # Convenience methods for common transitions

    def start_scan(self) -> bool:
        """Transition from IDLE or READY to SCANNING."""
        return self.transition_to(AppState.SCANNING)

    def scan_complete(self) -> bool:
        """Transition from SCANNING to READY."""
        return self.transition_to(AppState.READY)

    def scan_error(self, message: str) -> bool:
        """Transition from SCANNING to ERROR."""
        return self.transition_to(AppState.ERROR, message)

    def start_clean(self) -> bool:
        """Transition from READY to CLEANING."""
        return self.transition_to(AppState.CLEANING)

    def clean_complete(self) -> bool:
        """Transition from CLEANING to READY."""
        return self.transition_to(AppState.READY)

    def clean_error(self, message: str) -> bool:
        """Transition from CLEANING to ERROR."""
        return self.transition_to(AppState.ERROR, message)

    def acknowledge_error(self) -> bool:
        """Transition from ERROR to IDLE (user acknowledgment)."""
        return self.transition_to(AppState.IDLE)
