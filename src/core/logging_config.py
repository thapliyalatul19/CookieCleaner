"""Logging configuration for Cookie Cleaner."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .constants import (
    LOGS_DIR,
    DEBUG_LOG_FILE,
    AUDIT_LOG_FILE,
    DEBUG_LOG_MAX_BYTES,
    DEBUG_LOG_BACKUP_COUNT,
)

# Logger names
AUDIT_LOGGER_NAME = "audit"

# Format strings
DEBUG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
AUDIT_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"


def _ensure_log_directory() -> None:
    """Create log directory if it doesn't exist."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def setup_logging(debug_mode: bool = False) -> None:
    """
    Configure application logging.

    Sets up two log targets:
    1. Debug log: Rotating file handler with DEBUG level
    2. Audit log: Append-only file for clean operations

    Args:
        debug_mode: If True, also output DEBUG to console
    """
    _ensure_log_directory()

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Debug file handler (rotating)
    debug_handler = RotatingFileHandler(
        DEBUG_LOG_FILE,
        maxBytes=DEBUG_LOG_MAX_BYTES,
        backupCount=DEBUG_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(logging.Formatter(DEBUG_FORMAT))
    root_logger.addHandler(debug_handler)

    # Console handler (only in debug mode)
    if debug_mode:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(logging.Formatter(DEBUG_FORMAT))
        root_logger.addHandler(console_handler)

    # Configure audit logger (separate logger with its own handler)
    audit_logger = logging.getLogger(AUDIT_LOGGER_NAME)
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False  # Don't send to root logger

    audit_handler = logging.FileHandler(
        AUDIT_LOG_FILE,
        mode="a",
        encoding="utf-8",
    )
    audit_handler.setLevel(logging.INFO)
    audit_handler.setFormatter(logging.Formatter(AUDIT_FORMAT))
    audit_logger.addHandler(audit_handler)


def get_audit_logger() -> logging.Logger:
    """Return the audit logger instance."""
    return logging.getLogger(AUDIT_LOGGER_NAME)


def log_clean_operation(
    domains_deleted: list[str],
    cookie_count: int,
    browsers_affected: list[str],
    dry_run: bool = False,
) -> None:
    """
    Log a clean operation to the audit log.

    Args:
        domains_deleted: List of domain names that were cleaned
        cookie_count: Total number of cookies deleted
        browsers_affected: List of browser names involved
        dry_run: Whether this was a dry run
    """
    audit = get_audit_logger()
    mode = "DRY_RUN" if dry_run else "CLEAN"
    audit.info(
        "%s | domains=%d | cookies=%d | browsers=%s | domains_list=%s",
        mode,
        len(domains_deleted),
        cookie_count,
        ",".join(browsers_affected),
        ",".join(domains_deleted[:10]) + ("..." if len(domains_deleted) > 10 else ""),
    )
