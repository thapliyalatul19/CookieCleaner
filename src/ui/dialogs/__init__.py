"""Dialog windows package for Cookie Cleaner."""

from src.ui.dialogs.confirm_clean import CleanConfirmationDialog
from src.ui.dialogs.blocking_apps import BlockingAppsDialog
from src.ui.dialogs.restore_backup import RestoreBackupDialog
from src.ui.dialogs.settings import SettingsDialog
from src.ui.dialogs.error_dialog import ErrorDialog

__all__ = [
    "CleanConfirmationDialog",
    "BlockingAppsDialog",
    "RestoreBackupDialog",
    "SettingsDialog",
    "ErrorDialog",
]
