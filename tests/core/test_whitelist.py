"""Tests for the whitelist engine."""

import pytest

from src.core.whitelist import WhitelistManager, WhitelistEntry
from src.core.constants import PUBLIC_SUFFIXES


class TestWhitelistEntry:
    """Tests for WhitelistEntry dataclass."""

    def test_instantiation(self):
        """WhitelistEntry can be instantiated with all fields."""
        entry = WhitelistEntry(
            prefix="domain",
            value="google.com",
            original="domain:google.com",
            label_count=2,
        )
        assert entry.prefix == "domain"
        assert entry.value == "google.com"
        assert entry.original == "domain:google.com"
        assert entry.label_count == 2

    def test_frozen(self):
        """WhitelistEntry is immutable."""
        entry = WhitelistEntry(
            prefix="exact",
            value="login.example.com",
            original="exact:login.example.com",
            label_count=3,
        )
        with pytest.raises(AttributeError):
            entry.value = "modified.com"


class TestWhitelistManagerInit:
    """Tests for WhitelistManager initialization."""

    def test_empty_init(self):
        """WhitelistManager can be initialized without entries."""
        wm = WhitelistManager()
        assert len(wm) == 0

    def test_init_with_entries(self):
        """WhitelistManager can be initialized with entries."""
        wm = WhitelistManager(["domain:google.com", "exact:github.com"])
        assert len(wm) == 2

    def test_init_with_invalid_entries_skips(self):
        """Invalid entries are rejected during init."""
        wm = WhitelistManager(["domain:google.com"])
        success, _ = wm.add_entry("invalid:entry")
        assert success is False
        assert len(wm) == 1


class TestNormalization:
    """Tests for domain/value normalization."""

    def test_lowercase(self):
        """Values are normalized to lowercase."""
        assert WhitelistManager.normalize_value("GOOGLE.COM") == "google.com"
        assert WhitelistManager.normalize_value("GitHub.Com") == "github.com"

    def test_strip_whitespace(self):
        """Whitespace is stripped."""
        assert WhitelistManager.normalize_value("  google.com  ") == "google.com"
        assert WhitelistManager.normalize_value("\tgoogle.com\n") == "google.com"

    def test_strip_leading_dots(self):
        """Leading dots are removed."""
        assert WhitelistManager.normalize_value(".google.com") == "google.com"
        assert WhitelistManager.normalize_value("..google.com") == "google.com"

    def test_combined_normalization(self):
        """All normalization rules apply together."""
        assert WhitelistManager.normalize_value("  .GOOGLE.COM  ") == "google.com"


class TestValidateEntry:
    """Tests for entry validation."""

    def test_valid_domain_entry(self):
        """Valid domain: entries pass validation."""
        valid, error = WhitelistManager.validate_entry("domain:google.com")
        assert valid is True
        assert error == ""

    def test_valid_exact_entry(self):
        """Valid exact: entries pass validation."""
        valid, error = WhitelistManager.validate_entry("exact:login.example.com")
        assert valid is True
        assert error == ""

    def test_valid_ip_entry(self):
        """Valid ip: entries pass validation."""
        valid, error = WhitelistManager.validate_entry("ip:192.168.1.1")
        assert valid is True
        assert error == ""

    def test_valid_ip_boundary_values(self):
        """IP addresses at boundary values pass validation."""
        valid, _ = WhitelistManager.validate_entry("ip:0.0.0.0")
        assert valid is True

        valid, _ = WhitelistManager.validate_entry("ip:255.255.255.255")
        assert valid is True

    def test_invalid_prefix(self):
        """Invalid prefixes are rejected."""
        valid, error = WhitelistManager.validate_entry("wildcard:*.google.com")
        assert valid is False
        assert "must start with" in error

    def test_missing_prefix(self):
        """Entries without prefix are rejected."""
        valid, error = WhitelistManager.validate_entry("google.com")
        assert valid is False
        assert "must start with" in error

    def test_empty_value(self):
        """Entries with empty value after prefix are rejected."""
        valid, error = WhitelistManager.validate_entry("domain:")
        assert valid is False
        assert "cannot be empty" in error

    def test_invalid_ip_format(self):
        """Invalid IP addresses are rejected."""
        valid, error = WhitelistManager.validate_entry("ip:999.999.999.999")
        assert valid is False
        assert "Invalid IP address" in error

    def test_invalid_ip_not_number(self):
        """Non-numeric IPs are rejected."""
        valid, error = WhitelistManager.validate_entry("ip:abc.def.ghi.jkl")
        assert valid is False
        assert "Invalid IP address" in error

    def test_invalid_domain_label(self):
        """Invalid domain labels are rejected."""
        valid, error = WhitelistManager.validate_entry("domain:goo_gle.com")
        assert valid is False
        assert "Invalid domain label" in error

    def test_domain_label_too_long(self):
        """Domain labels over 63 characters are rejected."""
        long_label = "a" * 64
        valid, error = WhitelistManager.validate_entry(f"domain:{long_label}.com")
        assert valid is False
        assert "too long" in error

    def test_empty_string_rejected(self):
        """Empty string is rejected."""
        valid, error = WhitelistManager.validate_entry("")
        assert valid is False
        assert "non-empty string" in error

    def test_none_rejected(self):
        """None is rejected."""
        valid, error = WhitelistManager.validate_entry(None)
        assert valid is False
        assert "non-empty string" in error


class TestPublicSuffixGuardrail:
    """Tests for public suffix rejection."""

    def test_reject_tld_com(self):
        """domain:com is rejected as public suffix."""
        valid, error = WhitelistManager.validate_entry("domain:com")
        assert valid is False
        assert "Public suffix" in error

    def test_reject_tld_org(self):
        """domain:org is rejected as public suffix."""
        valid, error = WhitelistManager.validate_entry("domain:org")
        assert valid is False
        assert "Public suffix" in error

    def test_reject_country_tld(self):
        """Country TLDs are rejected."""
        valid, error = WhitelistManager.validate_entry("domain:uk")
        assert valid is False
        assert "Public suffix" in error

    def test_reject_second_level_tld(self):
        """Second-level TLDs like co.uk are rejected."""
        valid, error = WhitelistManager.validate_entry("domain:co.uk")
        assert valid is False
        assert "Public suffix" in error

    def test_allow_domain_under_public_suffix(self):
        """Domains under public suffixes are allowed."""
        valid, _ = WhitelistManager.validate_entry("domain:google.com")
        assert valid is True

        valid, _ = WhitelistManager.validate_entry("domain:example.co.uk")
        assert valid is True

    def test_exact_rejects_public_suffix(self):
        """exact: prefix rejects public suffixes (PRD requirement)."""
        valid, error = WhitelistManager.validate_entry("exact:com")
        assert valid is False
        assert "Public suffix" in error

    def test_public_suffixes_constant_exists(self):
        """PUBLIC_SUFFIXES constant contains expected entries."""
        assert "com" in PUBLIC_SUFFIXES
        assert "co.uk" in PUBLIC_SUFFIXES
        assert "io" in PUBLIC_SUFFIXES


class TestIsWhitelisted:
    """Tests for whitelist matching logic."""

    def test_exact_match(self):
        """exact: matches only the exact domain."""
        wm = WhitelistManager(["exact:login.live.com"])
        assert wm.is_whitelisted("login.live.com") is True
        assert wm.is_whitelisted("live.com") is False
        assert wm.is_whitelisted("mail.live.com") is False
        assert wm.is_whitelisted("sub.login.live.com") is False

    def test_domain_matches_exact_domain(self):
        """domain: matches the exact domain."""
        wm = WhitelistManager(["domain:google.com"])
        assert wm.is_whitelisted("google.com") is True

    def test_domain_matches_subdomains(self):
        """domain: matches all subdomains recursively."""
        wm = WhitelistManager(["domain:google.com"])
        assert wm.is_whitelisted("mail.google.com") is True
        assert wm.is_whitelisted("a.b.c.google.com") is True
        assert wm.is_whitelisted("www.google.com") is True

    def test_domain_no_partial_match(self):
        """domain: does not match partial domain names."""
        wm = WhitelistManager(["domain:google.com"])
        assert wm.is_whitelisted("fakegoogle.com") is False
        assert wm.is_whitelisted("mygoogle.com") is False

    def test_ip_exact_match(self):
        """ip: matches exact IP address."""
        wm = WhitelistManager(["ip:192.168.1.1"])
        assert wm.is_whitelisted("192.168.1.1") is True
        assert wm.is_whitelisted("192.168.1.2") is False

    def test_case_insensitive(self):
        """Matching is case-insensitive."""
        wm = WhitelistManager(["domain:Google.Com"])
        assert wm.is_whitelisted("GOOGLE.COM") is True
        assert wm.is_whitelisted("google.com") is True
        assert wm.is_whitelisted("MAIL.GOOGLE.COM") is True

    def test_leading_dot_stripped(self):
        """Leading dots are stripped during matching."""
        wm = WhitelistManager(["domain:google.com"])
        assert wm.is_whitelisted(".google.com") is True
        assert wm.is_whitelisted(".mail.google.com") is True

    def test_empty_domain_not_whitelisted(self):
        """Empty domain is not whitelisted."""
        wm = WhitelistManager(["domain:google.com"])
        assert wm.is_whitelisted("") is False
        assert wm.is_whitelisted(None) is False

    def test_non_matching_domain(self):
        """Non-matching domains return False."""
        wm = WhitelistManager(["domain:google.com"])
        assert wm.is_whitelisted("facebook.com") is False
        assert wm.is_whitelisted("microsoft.com") is False


class TestConflictResolution:
    """Tests for conflict resolution between entry types."""

    def test_exact_takes_priority_over_domain(self):
        """exact: matches are checked before domain:."""
        wm = WhitelistManager([
            "domain:live.com",
            "exact:login.live.com",
        ])
        # Both should match login.live.com
        assert wm.is_whitelisted("login.live.com") is True

    def test_multiple_domain_entries(self):
        """Multiple domain entries work together."""
        wm = WhitelistManager([
            "domain:google.com",
            "domain:microsoft.com",
        ])
        assert wm.is_whitelisted("google.com") is True
        assert wm.is_whitelisted("mail.google.com") is True
        assert wm.is_whitelisted("microsoft.com") is True
        assert wm.is_whitelisted("outlook.microsoft.com") is True
        assert wm.is_whitelisted("facebook.com") is False

    def test_mixed_entry_types(self):
        """All entry types work together."""
        wm = WhitelistManager([
            "domain:google.com",
            "exact:specific.site.com",
            "ip:10.0.0.1",
        ])
        assert wm.is_whitelisted("google.com") is True
        assert wm.is_whitelisted("mail.google.com") is True
        assert wm.is_whitelisted("specific.site.com") is True
        assert wm.is_whitelisted("other.site.com") is False
        assert wm.is_whitelisted("10.0.0.1") is True
        assert wm.is_whitelisted("10.0.0.2") is False


class TestAddEntry:
    """Tests for dynamic entry addition."""

    def test_add_valid_entry(self):
        """Valid entries can be added."""
        wm = WhitelistManager()
        success, error = wm.add_entry("domain:google.com")
        assert success is True
        assert error == ""
        assert len(wm) == 1

    def test_add_invalid_entry_returns_error(self):
        """Invalid entries return error message."""
        wm = WhitelistManager()
        success, error = wm.add_entry("invalid:entry")
        assert success is False
        assert "must start with" in error
        assert len(wm) == 0

    def test_add_multiple_entries(self):
        """Multiple entries can be added sequentially."""
        wm = WhitelistManager()
        wm.add_entry("domain:google.com")
        wm.add_entry("exact:github.com")
        wm.add_entry("ip:127.0.0.1")
        assert len(wm) == 3


class TestRemoveEntry:
    """Tests for dynamic entry removal."""

    def test_remove_existing_entry(self):
        """Existing entries can be removed."""
        wm = WhitelistManager(["domain:google.com", "exact:github.com"])
        assert wm.is_whitelisted("google.com") is True

        removed = wm.remove_entry("domain:google.com")
        assert removed is True
        assert wm.is_whitelisted("google.com") is False
        assert len(wm) == 1

    def test_remove_nonexistent_entry(self):
        """Removing nonexistent entry returns False."""
        wm = WhitelistManager(["domain:google.com"])
        removed = wm.remove_entry("domain:facebook.com")
        assert removed is False
        assert len(wm) == 1

    def test_remove_invalid_entry(self):
        """Removing invalid entry returns False."""
        wm = WhitelistManager(["domain:google.com"])
        removed = wm.remove_entry("invalid:entry")
        assert removed is False

    def test_remove_and_re_add(self):
        """Entries can be removed and re-added."""
        wm = WhitelistManager(["domain:google.com"])
        wm.remove_entry("domain:google.com")
        assert wm.is_whitelisted("google.com") is False

        wm.add_entry("domain:google.com")
        assert wm.is_whitelisted("google.com") is True


class TestGetEntries:
    """Tests for retrieving entries."""

    def test_get_entries_returns_originals(self):
        """get_entries returns original entry strings."""
        entries = ["domain:Google.Com", "exact:GitHub.Com"]
        wm = WhitelistManager(entries)
        result = wm.get_entries()
        assert "domain:Google.Com" in result
        assert "exact:GitHub.Com" in result

    def test_get_entries_preserves_order(self):
        """get_entries preserves insertion order."""
        entries = ["domain:first.com", "exact:second.com", "ip:1.2.3.4"]
        wm = WhitelistManager(entries)
        result = wm.get_entries()
        assert result[0] == "domain:first.com"
        assert result[1] == "exact:second.com"
        assert result[2] == "ip:1.2.3.4"

    def test_get_entries_empty(self):
        """get_entries returns empty list for empty manager."""
        wm = WhitelistManager()
        assert wm.get_entries() == []


class TestContainsProtocol:
    """Tests for __contains__ protocol."""

    def test_in_operator(self):
        """'in' operator works for whitelist checking."""
        wm = WhitelistManager(["domain:google.com"])
        assert "google.com" in wm
        assert "mail.google.com" in wm
        assert "facebook.com" not in wm


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_single_label_domain(self):
        """Single-label domains (localhost) are handled."""
        wm = WhitelistManager(["exact:localhost"])
        assert wm.is_whitelisted("localhost") is True

    def test_deep_subdomain_hierarchy(self):
        """Deep subdomain hierarchies are matched."""
        wm = WhitelistManager(["domain:example.com"])
        assert wm.is_whitelisted("a.b.c.d.e.f.g.example.com") is True

    def test_numeric_subdomain(self):
        """Numeric subdomains are handled."""
        wm = WhitelistManager(["domain:example.com"])
        assert wm.is_whitelisted("123.example.com") is True

    def test_hyphenated_domain(self):
        """Hyphenated domains are valid."""
        valid, _ = WhitelistManager.validate_entry("domain:my-site.com")
        assert valid is True

        wm = WhitelistManager(["domain:my-site.com"])
        assert wm.is_whitelisted("my-site.com") is True
        assert wm.is_whitelisted("sub.my-site.com") is True

    def test_whitespace_in_entries_handled(self):
        """Whitespace in entries is handled gracefully."""
        wm = WhitelistManager(["  domain:google.com  "])
        assert wm.is_whitelisted("google.com") is True

    def test_default_whitelist_valid(self):
        """All entries in DEFAULT_WHITELIST are valid."""
        from src.core.constants import DEFAULT_WHITELIST

        for entry in DEFAULT_WHITELIST:
            valid, error = WhitelistManager.validate_entry(entry)
            assert valid is True, f"Default entry '{entry}' invalid: {error}"

    def test_default_whitelist_loads(self):
        """DEFAULT_WHITELIST can be loaded into WhitelistManager."""
        from src.core.constants import DEFAULT_WHITELIST

        wm = WhitelistManager(DEFAULT_WHITELIST)
        assert len(wm) == len(DEFAULT_WHITELIST)
        # Check a known default entry
        assert wm.is_whitelisted("google.com") is True
        assert wm.is_whitelisted("mail.google.com") is True
