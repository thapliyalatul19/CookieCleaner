"""Application entry point for Cookie Cleaner.

Initializes logging, creates the application and main window, and starts the event loop.
"""

import logging
import sys

from src.core.config import ConfigManager
from src.core.logging_config import setup_logging
from src.execution.backup_manager import BackupManager
from src.ui.app import create_application
from src.ui.main_window import MainWindow

logger = logging.getLogger(__name__)


def _cleanup_old_backups() -> None:
    """Clean up old backups based on retention settings."""
    try:
        config = ConfigManager()
        retention_days = config.settings.get("backup_retention_days", 7)

        backup_manager = BackupManager()
        deleted_count = backup_manager.cleanup_old_backups(retention_days)

        if deleted_count > 0:
            logger.info("Cleaned up %d old backup(s) on startup", deleted_count)
    except Exception as e:
        logger.warning("Failed to cleanup old backups on startup: %s", e)


def main() -> int:
    """
    Application entry point.

    Returns:
        Exit code (0 for success)
    """
    # Initialize logging
    setup_logging()

    # Cleanup old backups on startup
    _cleanup_old_backups()

    # Create application
    app = create_application(sys.argv)

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run event loop
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
