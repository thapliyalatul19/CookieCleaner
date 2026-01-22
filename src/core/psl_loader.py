"""Public Suffix List loader for Cookie Cleaner.

Provides functions to load and query the Public Suffix List (PSL)
for domain validation in whitelist entries.

Note on PSL parsing limitations:
- Wildcard rules (e.g., *.ck) are handled by adding the base suffix
- Exception rules (e.g., !www.ck) are not fully handled
- Full PSL parsing is complex; this implementation covers common cases
"""

from __future__ import annotations

import logging
import sys
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)


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
def load_public_suffixes() -> frozenset[str]:
    """
    Load public suffixes from the data file.

    Uses LRU cache to avoid repeated file reads.

    Returns:
        Frozenset of public suffix strings
    """
    psl_path = _get_psl_path()

    if not psl_path.exists():
        logger.debug("PSL data file not found at %s, using fallback list", psl_path)
        return _FALLBACK_SUFFIXES

    try:
        suffixes = set()
        with open(psl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                # Skip comments and blank lines
                if not line or line.startswith("//"):
                    continue

                # Handle wildcard rules (e.g., *.ck)
                # Add the base suffix for wildcards
                if line.startswith("*."):
                    suffixes.add(line[2:])
                    continue

                # Skip exception rules (e.g., !www.ck) - these are complex to handle
                # Exception rules indicate domains that are NOT public suffixes
                # despite the wildcard rule above them
                if line.startswith("!"):
                    continue

                suffixes.add(line)

        logger.info("Loaded %d public suffixes from %s", len(suffixes), psl_path)
        return frozenset(suffixes)

    except OSError as e:
        logger.warning("Failed to load PSL file: %s, using fallback", e)
        return _FALLBACK_SUFFIXES


def is_public_suffix(domain: str) -> bool:
    """
    Check if a domain is a public suffix.

    Args:
        domain: Domain to check (e.g., "co.uk", "com")

    Returns:
        True if the domain is a public suffix
    """
    domain = domain.lower().strip().lstrip(".")
    suffixes = load_public_suffixes()

    # Direct match
    if domain in suffixes:
        return True

    # Check if it's a registered domain under a public suffix
    # e.g., "example.co.uk" is not a public suffix, but "co.uk" is
    # We want to return True only for the suffix itself

    return False


def get_public_suffix(domain: str) -> str | None:
    """
    Get the public suffix for a domain.

    Args:
        domain: Full domain to check (e.g., "www.example.co.uk")

    Returns:
        The public suffix if found (e.g., "co.uk"), or None
    """
    domain = domain.lower().strip().lstrip(".")
    suffixes = load_public_suffixes()
    labels = domain.split(".")

    # Try progressively longer suffixes from the right
    # e.g., for "www.example.co.uk", try "uk", then "co.uk"
    for i in range(len(labels)):
        candidate = ".".join(labels[i:])
        if candidate in suffixes:
            return candidate

    return None


def clear_cache() -> None:
    """Clear the LRU cache for testing purposes."""
    load_public_suffixes.cache_clear()
