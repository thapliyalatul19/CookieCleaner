"""Core module for Cookie Cleaner."""

from .config import ConfigManager, ConfigError
from .logging_config import setup_logging, get_audit_logger, log_clean_operation
from .models import (
    BrowserStore,
    CookieRecord,
    DomainAggregate,
    DeleteTarget,
    DeleteOperation,
    DeletePlan,
)
from .whitelist import WhitelistManager, WhitelistEntry
from .delete_planner import DeletePlanner
from .delete_plan_validator import DeletePlanValidator, ValidationResult, ValidationError

__all__ = [
    # Config
    "ConfigManager",
    "ConfigError",
    # Logging
    "setup_logging",
    "get_audit_logger",
    "log_clean_operation",
    # Models
    "BrowserStore",
    "CookieRecord",
    "DomainAggregate",
    "DeleteTarget",
    "DeleteOperation",
    "DeletePlan",
    # Whitelist
    "WhitelistManager",
    "WhitelistEntry",
    # Planning
    "DeletePlanner",
    "DeletePlanValidator",
    "ValidationResult",
    "ValidationError",
]
