"""Whitelist engine for Cookie Cleaner.

Implements grammar-based matching with domain:, exact:, and ip: prefixes.
This module contains matching logic only - NO deletion operations.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Tuple

from .constants import VALID_WHITELIST_PREFIXES
from .psl_loader import load_public_suffixes, is_public_suffix, get_public_suffix

logger = logging.getLogger(__name__)


# IPv4 pattern for validation
_IPV4_PATTERN = re.compile(
    r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
    r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
)

# Valid domain label pattern (simplified)
_DOMAIN_LABEL_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")


@dataclass(frozen=True)
class WhitelistEntry:
    """Represents a parsed whitelist entry."""

    prefix: str  # "domain", "exact", or "ip"
    value: str  # Normalized domain/IP
    original: str  # Original entry string
    label_count: int  # Number of domain labels (for conflict resolution)


class WhitelistManager:
    """
    Manages whitelist entries and cookie domain matching.

    Supports three prefix types:
    - domain: Recursive matching (domain + all subdomains)
    - exact: Literal matching (only exact host)
    - ip: Direct IP address matching

    All matching is case-insensitive.
    """

    def __init__(self, entries: list[str] | None = None):
        """
        Initialize WhitelistManager with optional entries.

        Args:
            entries: List of whitelist entry strings (e.g., ["domain:google.com"])
        """
        self._exact_set: set[str] = set()
        self._ip_set: set[str] = set()
        self._domain_map: dict[str, WhitelistEntry] = {}
        self._entries: list[WhitelistEntry] = []

        if entries:
            for entry in entries:
                self.add_entry(entry)

    @staticmethod
    def normalize_value(value: str) -> str:
        """
        Normalize a domain or IP value.

        - Converts to lowercase
        - Strips leading/trailing whitespace
        - Removes leading dots

        Args:
            value: The domain or IP to normalize

        Returns:
            Normalized value
        """
        normalized = value.strip().lower()
        while normalized.startswith("."):
            normalized = normalized[1:]
        return normalized

    @staticmethod
    def validate_entry(entry: str) -> Tuple[bool, str]:
        """
        Validate a whitelist entry string.

        Args:
            entry: Entry string to validate (e.g., "domain:google.com")

        Returns:
            Tuple of (is_valid, error_message). If valid, error_message is empty.
        """
        if not entry or not isinstance(entry, str):
            return False, "Entry must be a non-empty string"

        entry = entry.strip()

        # Check for valid prefix
        prefix = None
        value = None
        for p in VALID_WHITELIST_PREFIXES:
            if entry.startswith(p):
                prefix = p.rstrip(":")
                value = entry[len(p):]
                break

        if prefix is None:
            valid_prefixes = ", ".join(sorted(VALID_WHITELIST_PREFIXES))
            return False, f"Entry must start with one of: {valid_prefixes}"

        # Normalize value
        value = WhitelistManager.normalize_value(value)

        if not value:
            return False, f"Entry value after '{prefix}:' cannot be empty"

        # Validate based on prefix type
        if prefix == "ip":
            if not _IPV4_PATTERN.match(value):
                return False, f"Invalid IP address: '{value}'"
            return True, ""

        # For domain and exact: validate domain format
        labels = value.split(".")
        if not labels or labels == [""]:
            return False, f"Invalid domain: '{value}'"

        for label in labels:
            if not label:
                return False, f"Invalid domain: empty label in '{value}'"
            if len(label) > 63:
                return False, f"Domain label too long: '{label}'"
            if not _DOMAIN_LABEL_PATTERN.match(label):
                return False, f"Invalid domain label: '{label}'"

        # For domain: prefix, reject public suffixes
        if prefix == "domain":
            psl_data = load_public_suffixes()
            if value in psl_data.suffixes:
                return False, f"Public suffix '{value}' cannot be used with domain: prefix (too broad)"
            # Also check multi-part suffixes
            if len(labels) >= 2:
                two_part = f"{labels[-2]}.{labels[-1]}"
                if value == two_part and two_part in psl_data.suffixes:
                    return False, f"Public suffix '{value}' cannot be used with domain: prefix (too broad)"

        # For exact: prefix, reject public suffixes (PRD requirement)
        if prefix == "exact":
            if is_public_suffix(value):
                return False, f"Public suffix '{value}' cannot be used with exact: prefix (too broad)"

        return True, ""

    def add_entry(self, entry: str) -> Tuple[bool, str]:
        """
        Add a whitelist entry after validation.

        Args:
            entry: Entry string to add (e.g., "domain:google.com")

        Returns:
            Tuple of (success, error_message). If success, error_message is empty.
        """
        is_valid, error = self.validate_entry(entry)
        if not is_valid:
            return False, error

        entry = entry.strip()

        # Parse prefix and value
        for p in VALID_WHITELIST_PREFIXES:
            if entry.startswith(p):
                prefix = p.rstrip(":")
                value = self.normalize_value(entry[len(p):])
                break

        label_count = len(value.split(".")) if prefix != "ip" else 0

        whitelist_entry = WhitelistEntry(
            prefix=prefix,
            value=value,
            original=entry,
            label_count=label_count,
        )

        # Add to appropriate data structure
        if prefix == "exact":
            self._exact_set.add(value)
        elif prefix == "ip":
            self._ip_set.add(value)
        else:  # domain
            # For domain entries, check for conflict resolution
            # Longer (more specific) entries take precedence
            existing = self._domain_map.get(value)
            if existing is None or whitelist_entry.label_count >= existing.label_count:
                self._domain_map[value] = whitelist_entry

        self._entries.append(whitelist_entry)
        return True, ""

    def remove_entry(self, entry: str) -> bool:
        """
        Remove a whitelist entry.

        Args:
            entry: Entry string to remove (e.g., "domain:google.com")

        Returns:
            True if entry was found and removed, False otherwise.
        """
        entry = entry.strip()

        # Parse prefix and value
        prefix = None
        value = None
        for p in VALID_WHITELIST_PREFIXES:
            if entry.startswith(p):
                prefix = p.rstrip(":")
                value = self.normalize_value(entry[len(p):])
                break

        if prefix is None:
            return False

        # Remove from appropriate data structure
        removed = False
        if prefix == "exact" and value in self._exact_set:
            self._exact_set.discard(value)
            removed = True
        elif prefix == "ip" and value in self._ip_set:
            self._ip_set.discard(value)
            removed = True
        elif prefix == "domain" and value in self._domain_map:
            del self._domain_map[value]
            removed = True

        # Remove from entries list
        if removed:
            self._entries = [e for e in self._entries if not (e.prefix == prefix and e.value == value)]

        return removed

    def get_entries(self) -> list[str]:
        """
        Get all whitelist entries as original strings.

        Returns:
            List of entry strings in the order they were added.
        """
        return [e.original for e in self._entries]

    def is_whitelisted(self, domain: str) -> bool:
        """
        Check if a domain is whitelisted.

        Matching priority (from PRD 6.3):
        1. exact: matches checked first (highest priority)
        2. ip: matches for IP addresses
        3. domain: recursive matching (walks up hierarchy)

        Args:
            domain: The domain to check (will be normalized)

        Returns:
            True if domain matches any whitelist entry.
        """
        if not domain:
            return False

        normalized = self.normalize_value(domain)

        # Priority 1: Check exact matches (O(1))
        if normalized in self._exact_set:
            return True

        # Priority 2: Check IP matches (O(1))
        if _IPV4_PATTERN.match(normalized) and normalized in self._ip_set:
            return True

        # Priority 3: Check domain hierarchy (O(n) where n = label count)
        # Walk up the hierarchy: a.b.c.google.com -> b.c.google.com -> c.google.com -> google.com
        parts = normalized.split(".")
        for i in range(len(parts)):
            check_domain = ".".join(parts[i:])
            if check_domain in self._domain_map:
                return True

        return False

    def __len__(self) -> int:
        """Return the number of whitelist entries."""
        return len(self._entries)

    def __contains__(self, domain: str) -> bool:
        """Check if a domain is whitelisted (alias for is_whitelisted)."""
        return self.is_whitelisted(domain)
