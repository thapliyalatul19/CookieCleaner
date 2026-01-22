"""Application entry point for Cookie Cleaner.

Initializes logging, creates the application and main window, and starts the event loop.
"""

import sys

from src.core.logging_config import setup_logging
from src.ui.app import create_application
from src.ui.main_window import MainWindow


def main() -> int:
    """
    Application entry point.

    Returns:
        Exit code (0 for success)
    """
    # Initialize logging
    setup_logging()

    # Create application
    app = create_application(sys.argv)

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run event loop
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
