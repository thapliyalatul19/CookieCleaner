"""Integration tests for full Public Suffix List validation."""

from __future__ import annotations

import pytest

from src.core.psl_loader import load_public_suffixes, is_public_suffix, get_public_suffix, clear_cache
from src.core.whitelist import WhitelistManager


@pytest.fixture(autouse=True)
def reset_cache():
    """Clear PSL cache before and after each test."""
    clear_cache()
    yield
    clear_cache()


class TestPSLDataFile:
    """Tests for the PSL data file."""

    def test_psl_file_loads_successfully(self) -> None:
        """PSL data file loads without errors."""
        suffixes = load_public_suffixes()
        assert len(suffixes) > 0

    def test_psl_contains_generic_tlds(self) -> None:
        """PSL contains all major generic TLDs."""
        suffixes = load_public_suffixes()

        generic_tlds = ["com", "net", "org", "edu", "gov", "info", "biz"]
        for tld in generic_tlds:
            assert tld in suffixes, f"Missing generic TLD: {tld}"

    def test_psl_contains_country_codes(self) -> None:
        """PSL contains major country code TLDs."""
        suffixes = load_public_suffixes()

        country_codes = ["uk", "de", "fr", "jp", "cn", "au", "ca", "br", "in", "us"]
        for cc in country_codes:
            assert cc in suffixes, f"Missing country code: {cc}"

    def test_psl_contains_second_level_domains(self) -> None:
        """PSL contains common second-level domains."""
        suffixes = load_public_suffixes()

        second_levels = [
            "co.uk", "org.uk", "ac.uk",
            "com.au", "net.au",
            "co.jp", "ne.jp",
            "com.br", "com.cn",
        ]
        for sl in second_levels:
            assert sl in suffixes, f"Missing second-level: {sl}"

    def test_psl_contains_new_gtlds(self) -> None:
        """PSL contains newer generic TLDs."""
        suffixes = load_public_suffixes()

        new_gtlds = ["io", "co", "app", "dev", "ai"]
        for gtld in new_gtlds:
            assert gtld in suffixes, f"Missing new gTLD: {gtld}"


class TestWhitelistPSLEnforcement:
    """Tests for whitelist enforcement of PSL rules."""

    def test_domain_prefix_rejects_generic_tld(self) -> None:
        """domain: prefix rejects generic TLDs."""
        manager = WhitelistManager([])

        for tld in ["com", "net", "org", "info"]:
            is_valid, error = manager.validate_entry(f"domain:{tld}")
            assert is_valid is False, f"Should reject domain:{tld}"
            assert "public suffix" in error.lower()

    def test_domain_prefix_rejects_country_codes(self) -> None:
        """domain: prefix rejects country code TLDs."""
        manager = WhitelistManager([])

        for cc in ["uk", "de", "fr", "jp"]:
            is_valid, error = manager.validate_entry(f"domain:{cc}")
            assert is_valid is False, f"Should reject domain:{cc}"
            assert "public suffix" in error.lower()

    def test_domain_prefix_rejects_second_level(self) -> None:
        """domain: prefix rejects second-level public suffixes."""
        manager = WhitelistManager([])

        for sl in ["co.uk", "com.au", "co.jp"]:
            is_valid, error = manager.validate_entry(f"domain:{sl}")
            assert is_valid is False, f"Should reject domain:{sl}"
            assert "public suffix" in error.lower()

    def test_domain_prefix_accepts_valid_domains(self) -> None:
        """domain: prefix accepts valid registered domains."""
        manager = WhitelistManager([])

        valid_domains = [
            "google.com",
            "example.co.uk",
            "subdomain.example.com",
            "my-site.io",
        ]

        for domain in valid_domains:
            is_valid, error = manager.validate_entry(f"domain:{domain}")
            assert is_valid is True, f"Should accept domain:{domain}, got error: {error}"

    def test_exact_prefix_allows_public_suffix(self) -> None:
        """exact: prefix allows public suffixes (for edge cases)."""
        manager = WhitelistManager([])

        # These should be allowed (with warning logged)
        for suffix in ["com", "co.uk"]:
            is_valid, error = manager.validate_entry(f"exact:{suffix}")
            assert is_valid is True, f"exact: should allow {suffix}"


class TestPSLHelperFunctions:
    """Tests for PSL helper functions."""

    def test_is_public_suffix_tld(self) -> None:
        """is_public_suffix returns True for TLDs."""
        assert is_public_suffix("com") is True
        assert is_public_suffix("net") is True
        assert is_public_suffix("uk") is True

    def test_is_public_suffix_second_level(self) -> None:
        """is_public_suffix returns True for second-level suffixes."""
        assert is_public_suffix("co.uk") is True
        assert is_public_suffix("com.au") is True

    def test_is_public_suffix_registered_domain(self) -> None:
        """is_public_suffix returns False for registered domains."""
        assert is_public_suffix("google.com") is False
        assert is_public_suffix("example.co.uk") is False

    def test_get_public_suffix_simple(self) -> None:
        """get_public_suffix extracts TLD suffix."""
        assert get_public_suffix("google.com") == "com"
        assert get_public_suffix("example.net") == "net"

    def test_get_public_suffix_multi_level(self) -> None:
        """get_public_suffix extracts multi-level suffix."""
        assert get_public_suffix("example.co.uk") == "co.uk"
        assert get_public_suffix("site.com.au") == "com.au"

    def test_get_public_suffix_deep_subdomain(self) -> None:
        """get_public_suffix handles deep subdomains."""
        assert get_public_suffix("www.mail.google.com") == "com"
        assert get_public_suffix("api.v2.example.co.uk") == "co.uk"


class TestPSLEdgeCases:
    """Tests for PSL edge cases."""

    def test_case_insensitive(self) -> None:
        """PSL matching is case insensitive."""
        assert is_public_suffix("COM") is True
        assert is_public_suffix("Co.Uk") is True
        assert get_public_suffix("GOOGLE.COM") == "com"

    def test_leading_dot_handled(self) -> None:
        """Leading dots are handled correctly."""
        assert is_public_suffix(".com") is True
        assert get_public_suffix(".google.com") == "com"

    def test_whitespace_handled(self) -> None:
        """Whitespace is handled correctly."""
        assert is_public_suffix(" com ") is True
        assert is_public_suffix("  co.uk  ") is True

    def test_platform_suffixes_included(self) -> None:
        """Common platform suffixes are included."""
        suffixes = load_public_suffixes()

        platforms = ["github.io", "herokuapp.com", "netlify.app"]
        for platform in platforms:
            assert platform in suffixes, f"Missing platform suffix: {platform}"
