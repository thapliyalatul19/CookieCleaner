"""Tests for logging configuration."""

import logging
from unittest.mock import patch

import pytest

from src.core.logging_config import (
    setup_logging,
    get_audit_logger,
    log_clean_operation,
    AUDIT_LOGGER_NAME,
)


class TestLoggingSetup:
    """Tests for logging setup."""

    def test_setup_creates_loggers(self, temp_dir):
        """setup_logging creates debug and audit loggers."""
        with patch("src.core.logging_config.LOGS_DIR", temp_dir):
            with patch("src.core.logging_config.DEBUG_LOG_FILE", temp_dir / "debug.log"):
                with patch("src.core.logging_config.AUDIT_LOG_FILE", temp_dir / "audit.log"):
                    setup_logging()

                    root = logging.getLogger()
                    audit = logging.getLogger(AUDIT_LOGGER_NAME)

                    assert root.level == logging.DEBUG
                    assert audit.level == logging.INFO

    def test_debug_mode_adds_console_handler(self, temp_dir):
        """Debug mode adds console handler to root logger."""
        with patch("src.core.logging_config.LOGS_DIR", temp_dir):
            with patch("src.core.logging_config.DEBUG_LOG_FILE", temp_dir / "debug.log"):
                with patch("src.core.logging_config.AUDIT_LOG_FILE", temp_dir / "audit.log"):
                    setup_logging(debug_mode=True)

                    root = logging.getLogger()
                    handler_types = [type(h).__name__ for h in root.handlers]

                    assert "StreamHandler" in handler_types

    def test_get_audit_logger_returns_correct_logger(self):
        """get_audit_logger returns the audit logger."""
        logger = get_audit_logger()
        assert logger.name == AUDIT_LOGGER_NAME


class TestAuditLogging:
    """Tests for audit log operations."""

    def test_log_clean_operation_format(self, temp_dir):
        """log_clean_operation writes correctly formatted entry."""
        audit_log = temp_dir / "audit.log"

        with patch("src.core.logging_config.LOGS_DIR", temp_dir):
            with patch("src.core.logging_config.DEBUG_LOG_FILE", temp_dir / "debug.log"):
                with patch("src.core.logging_config.AUDIT_LOG_FILE", audit_log):
                    setup_logging()

                    log_clean_operation(
                        domains_deleted=["example.com", "test.com"],
                        cookie_count=15,
                        browsers_affected=["Chrome", "Firefox"],
                        dry_run=False,
                    )

                    # Force flush
                    for handler in get_audit_logger().handlers:
                        handler.flush()

                    content = audit_log.read_text()
                    assert "CLEAN" in content
                    assert "domains=2" in content
                    assert "cookies=15" in content
                    assert "Chrome,Firefox" in content

    def test_log_clean_operation_dry_run(self, temp_dir):
        """Dry run operations are logged with DRY_RUN prefix."""
        audit_log = temp_dir / "audit.log"

        with patch("src.core.logging_config.LOGS_DIR", temp_dir):
            with patch("src.core.logging_config.DEBUG_LOG_FILE", temp_dir / "debug.log"):
                with patch("src.core.logging_config.AUDIT_LOG_FILE", audit_log):
                    setup_logging()

                    log_clean_operation(
                        domains_deleted=["example.com"],
                        cookie_count=5,
                        browsers_affected=["Chrome"],
                        dry_run=True,
                    )

                    for handler in get_audit_logger().handlers:
                        handler.flush()

                    content = audit_log.read_text()
                    assert "DRY_RUN" in content

    def test_log_truncates_long_domain_list(self, temp_dir):
        """Long domain lists are truncated with ellipsis."""
        audit_log = temp_dir / "audit.log"

        with patch("src.core.logging_config.LOGS_DIR", temp_dir):
            with patch("src.core.logging_config.DEBUG_LOG_FILE", temp_dir / "debug.log"):
                with patch("src.core.logging_config.AUDIT_LOG_FILE", audit_log):
                    setup_logging()

                    domains = [f"domain{i}.com" for i in range(20)]
                    log_clean_operation(
                        domains_deleted=domains,
                        cookie_count=100,
                        browsers_affected=["Chrome"],
                        dry_run=False,
                    )

                    for handler in get_audit_logger().handlers:
                        handler.flush()

                    content = audit_log.read_text()
                    assert "..." in content
