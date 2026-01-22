"""User interface package for Cookie Cleaner."""

from src.ui.state_machine import AppState, StateManager, InvalidTransitionError
from src.ui.app import create_application, apply_theme
from src.ui.main_window import MainWindow

__all__ = [
    # State machine
    "AppState",
    "StateManager",
    "InvalidTransitionError",
    # App
    "create_application",
    "apply_theme",
    # Main window
    "MainWindow",
]
