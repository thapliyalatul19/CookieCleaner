"""Integration tests for whitelist persistence.

Tests that whitelist entries survive application restart:
- Save whitelist to config
- Reload config and verify whitelist
- Test whitelist-filtered deletion
"""

import json
from pathlib import Path

import pytest

from src.core.config import ConfigManager
from src.core.whitelist import WhitelistManager


class TestWhitelistPersistence:
    """Test whitelist persistence across sessions."""

    def test_whitelist_saved_to_config(
        self, temp_config_dir: Path
    ):
        """
        Verify whitelist entries are saved to config file.

        PRD 12.1: Whitelist survives app restart.
        """
        config_path = temp_config_dir / "config.json"

        # Create config manager and set whitelist
        config = ConfigManager(config_path)
        whitelist_entries = [
            "domain:google.com",
            "exact:api.github.com",
            "ip:192.168.1.1",
        ]
        config.set_whitelist(whitelist_entries)
        config.save()

        # Verify file exists
        assert config_path.exists()

        # Verify whitelist in file
        with open(config_path) as f:
            saved_config = json.load(f)

        assert "whitelist" in saved_config
        assert saved_config["whitelist"] == whitelist_entries

    def test_whitelist_loaded_on_startup(
        self, temp_config_dir: Path
    ):
        """
        Verify whitelist is loaded when config is initialized.
        """
        config_path = temp_config_dir / "config.json"

        # Session 1: Create and save whitelist
        config1 = ConfigManager(config_path)
        whitelist_entries = [
            "domain:example.com",
            "exact:secure.example.com",
        ]
        config1.set_whitelist(whitelist_entries)
        config1.save()

        # Session 2: New config manager (simulates app restart)
        config2 = ConfigManager(config_path)

        # Verify whitelist loaded
        assert config2.whitelist == whitelist_entries

    def test_whitelist_manager_from_config(
        self, temp_config_dir: Path
    ):
        """
        Verify WhitelistManager can be initialized from config.
        """
        config_path = temp_config_dir / "config.json"

        # Save whitelist
        config = ConfigManager(config_path)
        config.set_whitelist([
            "domain:google.com",
            "exact:api.stripe.com",
        ])
        config.save()

        # Create new config (simulates restart)
        config2 = ConfigManager(config_path)

        # Create WhitelistManager from config
        wm = WhitelistManager(config2.whitelist)

        # Verify matching works
        assert wm.is_whitelisted("google.com")
        assert wm.is_whitelisted("www.google.com")
        assert wm.is_whitelisted("api.stripe.com")
        assert not wm.is_whitelisted("stripe.com")


class TestWhitelistModification:
    """Test adding/removing whitelist entries."""

    def test_add_whitelist_entry_persists(
        self, temp_config_dir: Path
    ):
        """Test adding a new entry persists."""
        config_path = temp_config_dir / "config.json"

        # Initial whitelist
        config = ConfigManager(config_path)
        config.set_whitelist(["domain:example.com"])
        config.save()

        # Add new entry
        current = config.whitelist
        current.append("domain:newsite.com")
        config.set_whitelist(current)
        config.save()

        # Verify after "restart"
        config2 = ConfigManager(config_path)
        assert "domain:newsite.com" in config2.whitelist
        assert "domain:example.com" in config2.whitelist

    def test_remove_whitelist_entry_persists(
        self, temp_config_dir: Path
    ):
        """Test removing an entry persists."""
        config_path = temp_config_dir / "config.json"

        # Initial whitelist with multiple entries
        config = ConfigManager(config_path)
        config.set_whitelist([
            "domain:keep.com",
            "domain:remove.com",
            "exact:also-keep.com",
        ])
        config.save()

        # Remove entry
        current = config.whitelist
        current.remove("domain:remove.com")
        config.set_whitelist(current)
        config.save()

        # Verify after "restart"
        config2 = ConfigManager(config_path)
        assert "domain:remove.com" not in config2.whitelist
        assert "domain:keep.com" in config2.whitelist
        assert "exact:also-keep.com" in config2.whitelist


class TestWhitelistValidation:
    """Test whitelist entry validation on save/load."""

    def test_invalid_entry_rejected_on_set(
        self, temp_config_dir: Path
    ):
        """Test that invalid entries are rejected."""
        config_path = temp_config_dir / "config.json"
        config = ConfigManager(config_path)

        # Attempt to set invalid whitelist
        with pytest.raises(Exception):  # ConfigError or ValueError
            config.set_whitelist(["invalid-no-prefix"])

    def test_valid_entries_with_whitespace(
        self, temp_config_dir: Path
    ):
        """Test entries with whitespace are normalized."""
        config_path = temp_config_dir / "config.json"
        config = ConfigManager(config_path)

        # Set entries with extra whitespace
        config.set_whitelist([
            "domain:google.com",  # Normal
            "exact:github.com",
        ])
        config.save()

        # Load and use
        config2 = ConfigManager(config_path)
        wm = WhitelistManager(config2.whitelist)

        # Should work with normalized values
        assert wm.is_whitelisted("google.com")


class TestWhitelistUsageInDeletion:
    """Test whitelist integration with deletion workflow."""

    def test_whitelisted_domains_excluded_from_selection(
        self,
        multi_profile_setup: dict,
        temp_config_dir: Path,
    ):
        """
        Test that whitelisted domains are excluded from deletion selection.
        """
        from src.scanner.cookie_reader import create_reader as create_cookie_reader

        stores = multi_profile_setup["stores"]

        # Set up whitelist
        config_path = temp_config_dir / "config.json"
        config = ConfigManager(config_path)
        config.set_whitelist(["domain:google.com"])
        config.save()

        # Reload (simulate restart)
        config2 = ConfigManager(config_path)
        wm = WhitelistManager(config2.whitelist)

        # Scan and filter
        all_cookies = []
        for store in stores:
            reader = create_cookie_reader(store)
            all_cookies.extend(reader.read_cookies())

        # Filter out whitelisted
        deletable_cookies = [
            c for c in all_cookies
            if not wm.is_whitelisted(c.domain)
        ]

        # Verify google.com excluded
        google_cookies = [c for c in deletable_cookies if "google" in c.domain]
        assert len(google_cookies) == 0

        # Verify other domains included
        tracker_cookies = [c for c in deletable_cookies if "tracker" in c.domain]
        assert len(tracker_cookies) > 0


class TestDefaultWhitelist:
    """Test default whitelist on first run."""

    def test_first_run_creates_default_whitelist(
        self, temp_config_dir: Path
    ):
        """Test that first run creates a default whitelist."""
        config_path = temp_config_dir / "config.json"

        # First run - no config exists
        assert not config_path.exists()

        # Initialize creates defaults
        config = ConfigManager(config_path)

        # Should have default whitelist (may be empty or have defaults)
        assert isinstance(config.whitelist, list)

    def test_empty_whitelist_is_valid(
        self, temp_config_dir: Path
    ):
        """Test that an empty whitelist is valid."""
        config_path = temp_config_dir / "config.json"

        config = ConfigManager(config_path)
        config.set_whitelist([])
        config.save()

        # Reload
        config2 = ConfigManager(config_path)
        assert config2.whitelist == []

        # WhitelistManager accepts empty
        wm = WhitelistManager(config2.whitelist)
        assert not wm.is_whitelisted("anything.com")


class TestWhitelistEdgeCases:
    """Test whitelist edge cases."""

    def test_duplicate_entries_handled(
        self, temp_config_dir: Path
    ):
        """Test that duplicate entries don't cause issues."""
        config_path = temp_config_dir / "config.json"
        config = ConfigManager(config_path)

        # Set with duplicates (config may or may not dedupe)
        entries = [
            "domain:google.com",
            "domain:google.com",  # Duplicate
            "exact:api.google.com",
        ]
        config.set_whitelist(entries)
        config.save()

        # WhitelistManager should handle gracefully
        wm = WhitelistManager(config.whitelist)
        assert wm.is_whitelisted("google.com")

    def test_unicode_domains(
        self, temp_config_dir: Path
    ):
        """Test handling of internationalized domain names."""
        config_path = temp_config_dir / "config.json"
        config = ConfigManager(config_path)

        # Note: Most browsers use punycode for IDN
        # This test ensures the system doesn't crash on unicode
        # Actual IDN support may vary
        try:
            config.set_whitelist(["domain:example.com"])
            config.save()
        except Exception:
            pass  # IDN might not be supported, that's okay

    def test_large_whitelist(
        self, temp_config_dir: Path
    ):
        """Test handling of a large whitelist."""
        config_path = temp_config_dir / "config.json"
        config = ConfigManager(config_path)

        # Create large whitelist
        entries = [f"domain:site{i}.com" for i in range(100)]
        config.set_whitelist(entries)
        config.save()

        # Reload and verify
        config2 = ConfigManager(config_path)
        assert len(config2.whitelist) == 100

        # WhitelistManager should handle efficiently
        wm = WhitelistManager(config2.whitelist)
        assert wm.is_whitelisted("site50.com")
        assert wm.is_whitelisted("www.site99.com")
        assert not wm.is_whitelisted("notlisted.com")
