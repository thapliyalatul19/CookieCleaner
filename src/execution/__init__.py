"""Secure deletion engine package for Cookie Cleaner."""

from src.execution.lock_resolver import LockResolver, LockReport
from src.execution.backup_manager import BackupManager, BackupResult
from src.execution.delete_executor import (
    DeleteExecutor,
    DeleteResult,
    DeleteReport,
    ProcessGateError,
)

__all__ = [
    "LockResolver",
    "LockReport",
    "BackupManager",
    "BackupResult",
    "DeleteExecutor",
    "DeleteResult",
    "DeleteReport",
    "ProcessGateError",
]
