"""Tests for configuration management."""

import json

import pytest

from src.core.config import ConfigManager, ConfigError
from src.core.constants import DEFAULT_WHITELIST, DEFAULT_SETTINGS


class TestConfigManager:
    """Tests for ConfigManager class."""

    def test_creates_default_config_on_first_run(self, temp_config_file):
        """ConfigManager creates default config when file doesn't exist."""
        cm = ConfigManager(config_path=temp_config_file)

        assert temp_config_file.exists()
        assert cm.config["version"] == 1
        assert cm.whitelist == DEFAULT_WHITELIST
        assert cm.settings == DEFAULT_SETTINGS

    def test_loads_existing_config(self, temp_config_with_data, valid_config_data):
        """ConfigManager loads existing valid config file."""
        cm = ConfigManager(config_path=temp_config_with_data)

        assert cm.whitelist == valid_config_data["whitelist"]
        assert cm.settings == valid_config_data["settings"]

    def test_save_persists_changes(self, temp_config_file):
        """Changes are persisted after save."""
        cm = ConfigManager(config_path=temp_config_file)
        cm.update_settings(backup_retention_days=14)
        cm.save()

        # Reload and verify
        cm2 = ConfigManager(config_path=temp_config_file)
        assert cm2.settings["backup_retention_days"] == 14

    def test_rejects_invalid_whitelist_prefix(self, temp_config_file):
        """Invalid whitelist prefixes are rejected."""
        cm = ConfigManager(config_path=temp_config_file)

        with pytest.raises(ConfigError, match="Invalid whitelist entry"):
            cm.set_whitelist(["invalid:example.com"])

    def test_rejects_empty_whitelist_entry(self, temp_config_file):
        """Empty whitelist entries after prefix are rejected."""
        cm = ConfigManager(config_path=temp_config_file)

        with pytest.raises(ConfigError, match="Invalid whitelist entry"):
            cm.set_whitelist(["domain:"])

    def test_accepts_valid_whitelist_entries(self, temp_config_file):
        """Valid whitelist entries are accepted."""
        cm = ConfigManager(config_path=temp_config_file)
        valid_entries = [
            "domain:example.com",
            "exact:login.example.com",
            "ip:192.168.1.1",
        ]

        cm.set_whitelist(valid_entries)
        assert cm.whitelist == valid_entries

    def test_raises_on_invalid_json(self, temp_config_file):
        """ConfigError raised when config contains invalid JSON."""
        temp_config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_config_file, "w") as f:
            f.write("{ invalid json }")

        with pytest.raises(ConfigError, match="Invalid JSON"):
            ConfigManager(config_path=temp_config_file)

    def test_raises_on_missing_version(self, temp_config_file):
        """ConfigError raised when version field is missing."""
        temp_config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_config_file, "w") as f:
            json.dump({"settings": {}, "whitelist": []}, f)

        with pytest.raises(ConfigError, match="version"):
            ConfigManager(config_path=temp_config_file)

    def test_update_last_run(self, temp_config_file):
        """update_last_run sets timestamp."""
        cm = ConfigManager(config_path=temp_config_file)
        assert cm.config.get("last_run") is None

        cm.update_last_run()
        assert cm.config["last_run"] is not None
        assert cm.config["last_run"].endswith("Z")

    def test_config_property_returns_copy(self, temp_config_file):
        """config property returns a copy, not the original."""
        cm = ConfigManager(config_path=temp_config_file)
        config_copy = cm.config
        config_copy["version"] = 999

        assert cm.config["version"] == 1  # Original unchanged
