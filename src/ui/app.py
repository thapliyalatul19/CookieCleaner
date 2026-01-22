"""Application initialization for Cookie Cleaner.

Creates and configures the QApplication instance with theming support.
"""

from __future__ import annotations

import sys
from typing import Sequence

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QPalette, QColor
from PyQt6.QtCore import Qt

from src.core.constants import APP_NAME, APP_VERSION


def create_application(argv: Sequence[str] | None = None) -> QApplication:
    """
    Create and configure the QApplication instance.

    Args:
        argv: Command line arguments. Defaults to sys.argv.

    Returns:
        Configured QApplication instance
    """
    if argv is None:
        argv = sys.argv

    app = QApplication(list(argv))
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("CookieCleaner")

    # Set default font
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    return app


def apply_theme(app: QApplication, theme: str) -> None:
    """
    Apply a theme to the application.

    Args:
        app: The QApplication instance
        theme: Theme name - "light", "dark", or "system"
    """
    from src.ui.styles.themes import get_palette, get_stylesheet

    if theme == "system":
        # Use system default
        app.setStyleSheet("")
        app.setPalette(app.style().standardPalette())
    else:
        palette = get_palette(theme)
        stylesheet = get_stylesheet(theme)
        app.setPalette(palette)
        app.setStyleSheet(stylesheet)
