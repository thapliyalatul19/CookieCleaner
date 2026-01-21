"""Configuration management for Cookie Cleaner."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import (
    CONFIG_DIR,
    CONFIG_FILE,
    CONFIG_VERSION,
    DEFAULT_SETTINGS,
    DEFAULT_WHITELIST,
    LOGS_DIR,
    BACKUPS_DIR,
    VALID_WHITELIST_PREFIXES,
)

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when configuration is invalid."""
    pass


class ConfigManager:
    """Manages application configuration loading, validation, and persistence."""

    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or CONFIG_FILE
        self._config: dict[str, Any] = {}
        self._ensure_directories()
        self.load()

    def _ensure_directories(self) -> None:
        """Create application directories if they don't exist."""
        for directory in (CONFIG_DIR, LOGS_DIR, BACKUPS_DIR):
            directory.mkdir(parents=True, exist_ok=True)

    def _create_default_config(self) -> dict[str, Any]:
        """Generate default configuration."""
        return {
            "version": CONFIG_VERSION,
            "settings": DEFAULT_SETTINGS.copy(),
            "whitelist": DEFAULT_WHITELIST.copy(),
            "last_run": None,
        }

    def _validate_whitelist_entry(self, entry: str) -> bool:
        """Validate a single whitelist entry has a valid prefix."""
        for prefix in VALID_WHITELIST_PREFIXES:
            if entry.startswith(prefix):
                # Ensure there's content after the prefix
                return len(entry) > len(prefix)
        return False

    def _validate_config(self, config: dict[str, Any]) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        if not isinstance(config.get("version"), int):
            errors.append("Missing or invalid 'version' field")

        if not isinstance(config.get("settings"), dict):
            errors.append("Missing or invalid 'settings' field")

        whitelist = config.get("whitelist", [])
        if not isinstance(whitelist, list):
            errors.append("'whitelist' must be a list")
        else:
            for i, entry in enumerate(whitelist):
                if not isinstance(entry, str):
                    errors.append(f"Whitelist entry {i} is not a string")
                elif not self._validate_whitelist_entry(entry):
                    errors.append(
                        f"Invalid whitelist entry '{entry}': must start with "
                        f"one of {', '.join(sorted(VALID_WHITELIST_PREFIXES))}"
                    )

        return errors

    def load(self) -> None:
        """Load configuration from file, creating defaults if needed."""
        if not self.config_path.exists():
            logger.info("Config file not found, creating defaults at %s", self.config_path)
            self._config = self._create_default_config()
            self.save()
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                loaded_config = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON in config file: {e}") from e

        errors = self._validate_config(loaded_config)
        if errors:
            for error in errors:
                logger.error("Config validation error: %s", error)
            raise ConfigError(f"Configuration validation failed: {'; '.join(errors)}")

        self._config = loaded_config
        logger.debug("Configuration loaded from %s", self.config_path)

    def save(self) -> None:
        """Save current configuration to file."""
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2)
        logger.debug("Configuration saved to %s", self.config_path)

    @property
    def config(self) -> dict[str, Any]:
        """Return a copy of the current configuration."""
        return self._config.copy()

    @property
    def settings(self) -> dict[str, Any]:
        """Return application settings."""
        return self._config.get("settings", {}).copy()

    @property
    def whitelist(self) -> list[str]:
        """Return the whitelist entries."""
        return self._config.get("whitelist", []).copy()

    def update_settings(self, **kwargs: Any) -> None:
        """Update settings with provided values."""
        self._config.setdefault("settings", {}).update(kwargs)

    def set_whitelist(self, entries: list[str]) -> None:
        """Replace the whitelist with new entries after validation."""
        for entry in entries:
            if not self._validate_whitelist_entry(entry):
                raise ConfigError(
                    f"Invalid whitelist entry '{entry}': must start with "
                    f"one of {', '.join(sorted(VALID_WHITELIST_PREFIXES))}"
                )
        self._config["whitelist"] = entries

    def update_last_run(self) -> None:
        """Update the last_run timestamp to now."""
        self._config["last_run"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
