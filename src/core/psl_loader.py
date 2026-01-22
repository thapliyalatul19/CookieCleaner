"""Public Suffix List loader for Cookie Cleaner.

Provides functions to load and query the Public Suffix List (PSL)
for domain validation in whitelist entries.

This implementation properly handles:
- Standard suffix rules (e.g., com, co.uk)
- Wildcard rules (e.g., *.ck means any subdomain of ck is a public suffix)
- Exception rules (e.g., !www.ck means www.ck is NOT a public suffix)
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class PSLData:
    """Parsed Public Suffix List data."""

    suffixes: frozenset[str] = field(default_factory=frozenset)
    wildcards: frozenset[str] = field(default_factory=frozenset)  # Base domains with wildcard rules (e.g., "ck" for "*.ck")
    exceptions: frozenset[str] = field(default_factory=frozenset)  # Exception domains (e.g., "www.ck" for "!www.ck")


def _get_psl_path() -> Path:
    """Get the path to the PSL data file, handling frozen builds."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        base_path = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        return base_path / "data" / "public_suffix_list.dat"
    else:
        # Running from source
        return Path(__file__).parent.parent.parent / "data" / "public_suffix_list.dat"

# Fallback minimal PSL if file not found
_FALLBACK_SUFFIXES = frozenset({
    # Generic TLDs
    "com", "net", "org", "edu", "gov", "mil", "int", "info", "biz",
    # Country code TLDs
    "uk", "de", "fr", "jp", "cn", "au", "ca", "ru", "br", "in", "us",
    "es", "it", "nl", "be", "ch", "at", "pl", "se", "no", "dk", "fi",
    "pt", "ie", "nz", "za", "mx", "ar", "cl", "kr", "tw", "hk", "sg",
    # Common second-level TLDs
    "co.uk", "org.uk", "ac.uk", "gov.uk", "me.uk", "ltd.uk", "plc.uk",
    "com.au", "net.au", "org.au", "edu.au", "gov.au", "asn.au",
    "co.jp", "ne.jp", "or.jp", "ac.jp", "go.jp", "ed.jp",
    "com.br", "net.br", "org.br", "gov.br", "edu.br",
    "co.in", "net.in", "org.in", "gov.in", "ac.in",
    "co.nz", "net.nz", "org.nz", "govt.nz", "ac.nz",
    "co.za", "net.za", "org.za", "gov.za", "ac.za",
    "com.mx", "net.mx", "org.mx", "gob.mx", "edu.mx",
    "com.ar", "net.ar", "org.ar", "gob.ar", "edu.ar",
    "co.kr", "ne.kr", "or.kr", "go.kr", "ac.kr",
    "com.tw", "net.tw", "org.tw", "gov.tw", "edu.tw",
    "com.hk", "net.hk", "org.hk", "gov.hk", "edu.hk",
    "com.sg", "net.sg", "org.sg", "gov.sg", "edu.sg",
    # European country code TLDs with common second levels
    "co.de", "com.de", "org.de",
    "co.fr", "com.fr", "org.fr",
    "co.it", "com.it", "org.it",
    "co.es", "com.es", "org.es",
    "co.nl", "com.nl", "org.nl",
    "co.be", "com.be", "org.be",
    "co.at", "or.at", "ac.at",
    "co.ch", "com.ch", "org.ch",
    # Generic new TLDs
    "io", "co", "app", "dev", "ai", "me", "tv", "cc", "ws", "ly", "to",
    # Special TLDs
    "eu", "asia", "mobi", "tel", "travel", "jobs", "museum", "coop",
    # GitHub Pages and common platforms
    "github.io", "gitlab.io", "herokuapp.com", "netlify.app", "vercel.app",
    "azurewebsites.net", "cloudfront.net", "amazonaws.com",
    "blogspot.com", "wordpress.com", "tumblr.com",
})


@lru_cache(maxsize=1)
def load_public_suffixes() -> PSLData:
    """
    Load public suffixes from the data file.

    Uses LRU cache to avoid repeated file reads.

    Returns:
        PSLData containing suffixes, wildcards, and exceptions
    """
    psl_path = _get_psl_path()

    if not psl_path.exists():
        logger.debug("PSL data file not found at %s, using fallback list", psl_path)
        return PSLData(suffixes=_FALLBACK_SUFFIXES)

    try:
        suffixes = set()
        wildcards = set()
        exceptions = set()

        with open(psl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                # Skip comments and blank lines
                if not line or line.startswith("//"):
                    continue

                # Handle exception rules (e.g., !www.ck)
                # These indicate domains that are NOT public suffixes
                # despite a wildcard rule that would otherwise match
                if line.startswith("!"):
                    exception_domain = line[1:]  # Remove the "!"
                    exceptions.add(exception_domain)
                    continue

                # Handle wildcard rules (e.g., *.ck)
                # These mean any single label + base is a public suffix
                if line.startswith("*."):
                    base = line[2:]
                    wildcards.add(base)
                    # Also add the base itself as a suffix
                    suffixes.add(base)
                    continue

                suffixes.add(line)

        logger.info(
            "Loaded PSL: %d suffixes, %d wildcards, %d exceptions from %s",
            len(suffixes),
            len(wildcards),
            len(exceptions),
            psl_path,
        )
        return PSLData(
            suffixes=frozenset(suffixes),
            wildcards=frozenset(wildcards),
            exceptions=frozenset(exceptions),
        )

    except OSError as e:
        logger.warning("Failed to load PSL file: %s, using fallback", e)
        return PSLData(suffixes=_FALLBACK_SUFFIXES)


def is_public_suffix(domain: str) -> bool:
    """
    Check if a domain is a public suffix.

    Properly handles PSL rules including wildcards and exceptions:
    - Direct suffixes (e.g., "com", "co.uk") -> True
    - Wildcard matches (e.g., "foo.ck" matches "*.ck") -> True
    - Exception matches (e.g., "www.ck" with "!www.ck" rule) -> False

    Args:
        domain: Domain to check (e.g., "co.uk", "com")

    Returns:
        True if the domain is a public suffix
    """
    domain = domain.lower().strip().lstrip(".")
    psl_data = load_public_suffixes()

    # Check exception rules first - if the domain is an exception, it's NOT a public suffix
    if domain in psl_data.exceptions:
        return False

    # Direct match
    if domain in psl_data.suffixes:
        return True

    # Check wildcard rules
    # A wildcard rule "*.ck" means any single label + ck is a public suffix
    # e.g., "foo.ck" matches "*.ck"
    labels = domain.split(".")
    if len(labels) >= 2:
        # Check if the domain minus first label matches a wildcard base
        base = ".".join(labels[1:])
        if base in psl_data.wildcards:
            return True

    return False


def get_public_suffix(domain: str) -> str | None:
    """
    Get the public suffix for a domain.

    Properly handles PSL rules including wildcards and exceptions.

    Args:
        domain: Full domain to check (e.g., "www.example.co.uk")

    Returns:
        The public suffix if found (e.g., "co.uk"), or None
    """
    domain = domain.lower().strip().lstrip(".")
    psl_data = load_public_suffixes()
    labels = domain.split(".")

    # Try progressively longer suffixes from the right
    # e.g., for "www.example.co.uk", try "uk", then "co.uk"
    for i in range(len(labels)):
        candidate = ".".join(labels[i:])

        # Check exception first - exceptions are NOT public suffixes
        if candidate in psl_data.exceptions:
            continue

        # Direct match
        if candidate in psl_data.suffixes:
            return candidate

        # Check wildcard match
        # If candidate is "foo.ck" and we have wildcard "*.ck" (stored as "ck" in wildcards)
        candidate_labels = candidate.split(".")
        if len(candidate_labels) >= 2:
            base = ".".join(candidate_labels[1:])
            if base in psl_data.wildcards:
                return candidate

    return None


def clear_cache() -> None:
    """Clear the LRU cache for testing purposes."""
    load_public_suffixes.cache_clear()
