"""Tests for Public Suffix List loader."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.psl_loader import (
    load_public_suffixes,
    is_public_suffix,
    get_public_suffix,
    clear_cache,
    _FALLBACK_SUFFIXES,
    PSLData,
)


@pytest.fixture(autouse=True)
def clear_psl_cache():
    """Clear PSL cache before and after each test."""
    clear_cache()
    yield
    clear_cache()


class TestLoadPublicSuffixes:
    """Tests for load_public_suffixes function."""

    def test_returns_psl_data(self) -> None:
        """Returns a PSLData object."""
        result = load_public_suffixes()
        assert isinstance(result, PSLData)
        assert isinstance(result.suffixes, frozenset)

    def test_contains_common_tlds(self) -> None:
        """Contains common TLDs."""
        psl_data = load_public_suffixes()
        assert "com" in psl_data.suffixes
        assert "net" in psl_data.suffixes
        assert "org" in psl_data.suffixes
        assert "uk" in psl_data.suffixes

    def test_contains_country_second_level(self) -> None:
        """Contains country code second-level domains."""
        psl_data = load_public_suffixes()
        assert "co.uk" in psl_data.suffixes
        assert "com.au" in psl_data.suffixes
        assert "co.jp" in psl_data.suffixes

    def test_uses_fallback_when_file_missing(self, tmp_path: Path) -> None:
        """Uses fallback when PSL file doesn't exist."""
        with patch("src.core.psl_loader._get_psl_path", return_value=tmp_path / "nonexistent.dat"):
            clear_cache()
            psl_data = load_public_suffixes()

        assert psl_data.suffixes == _FALLBACK_SUFFIXES

    def test_cached_result(self) -> None:
        """Returns cached result on subsequent calls."""
        result1 = load_public_suffixes()
        result2 = load_public_suffixes()
        assert result1 is result2


class TestIsPublicSuffix:
    """Tests for is_public_suffix function."""

    def test_tld_is_public_suffix(self) -> None:
        """TLDs are public suffixes."""
        assert is_public_suffix("com") is True
        assert is_public_suffix("net") is True
        assert is_public_suffix("org") is True

    def test_country_second_level_is_public_suffix(self) -> None:
        """Country code second-level domains are public suffixes."""
        assert is_public_suffix("co.uk") is True
        assert is_public_suffix("com.au") is True

    def test_normal_domain_is_not_public_suffix(self) -> None:
        """Normal domains are not public suffixes."""
        assert is_public_suffix("google.com") is False
        assert is_public_suffix("example.co.uk") is False

    def test_case_insensitive(self) -> None:
        """Matching is case insensitive."""
        assert is_public_suffix("COM") is True
        assert is_public_suffix("Co.Uk") is True

    def test_strips_leading_dot(self) -> None:
        """Strips leading dots."""
        assert is_public_suffix(".com") is True
        assert is_public_suffix(".co.uk") is True


class TestGetPublicSuffix:
    """Tests for get_public_suffix function."""

    def test_finds_tld_suffix(self) -> None:
        """Finds TLD suffix for simple domains."""
        assert get_public_suffix("google.com") == "com"
        assert get_public_suffix("example.net") == "net"

    def test_finds_multi_level_suffix(self) -> None:
        """Finds multi-level public suffixes."""
        assert get_public_suffix("example.co.uk") == "co.uk"
        assert get_public_suffix("www.bbc.co.uk") == "co.uk"

    def test_returns_none_for_public_suffix_only(self) -> None:
        """Returns the suffix itself for bare suffixes."""
        assert get_public_suffix("com") == "com"
        assert get_public_suffix("co.uk") == "co.uk"

    def test_handles_deep_subdomains(self) -> None:
        """Handles deep subdomain structures."""
        assert get_public_suffix("www.mail.google.com") == "com"
        assert get_public_suffix("api.v2.example.co.uk") == "co.uk"

    def test_case_insensitive(self) -> None:
        """Matching is case insensitive."""
        assert get_public_suffix("Example.COM") == "com"

    def test_strips_leading_dot(self) -> None:
        """Strips leading dots."""
        assert get_public_suffix(".google.com") == "com"


class TestWhitelistPSLIntegration:
    """Integration tests with whitelist validation."""

    def test_domain_prefix_rejects_tld(self) -> None:
        """domain: prefix rejects bare TLDs."""
        from src.core.whitelist import WhitelistManager

        manager = WhitelistManager([])
        is_valid, error = manager.validate_entry("domain:com")

        assert is_valid is False
        assert "public suffix" in error.lower()

    def test_domain_prefix_rejects_country_second_level(self) -> None:
        """domain: prefix rejects country code second-level domains."""
        from src.core.whitelist import WhitelistManager

        manager = WhitelistManager([])
        is_valid, error = manager.validate_entry("domain:co.uk")

        assert is_valid is False
        assert "public suffix" in error.lower()

    def test_domain_prefix_accepts_normal_domain(self) -> None:
        """domain: prefix accepts normal domains."""
        from src.core.whitelist import WhitelistManager

        manager = WhitelistManager([])
        is_valid, error = manager.validate_entry("domain:example.com")

        assert is_valid is True

    def test_exact_prefix_rejects_public_suffix(self) -> None:
        """exact: prefix rejects public suffixes (PRD requirement)."""
        from src.core.whitelist import WhitelistManager

        manager = WhitelistManager([])
        is_valid, error = manager.validate_entry("exact:co.uk")

        # Should be invalid - public suffixes are rejected for exact: prefix
        assert is_valid is False
        assert "Public suffix" in error
