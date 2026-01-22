"""Core data models for Cookie Cleaner."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class BrowserStore:
    """Represents a browser profile's cookie store location."""

    browser_name: str  # e.g., "Chrome", "Firefox", "Edge"
    profile_id: str  # e.g., "Default", "Profile 1"
    db_path: Path  # Full path to cookie database
    is_chromium: bool  # Determines reader strategy
    local_state_path: Optional[Path] = None  # For DPAPI key (Chromium only)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "browser_name": self.browser_name,
            "profile_id": self.profile_id,
            "db_path": str(self.db_path),
            "is_chromium": self.is_chromium,
            "local_state_path": str(self.local_state_path) if self.local_state_path else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> BrowserStore:
        """Create instance from dictionary."""
        return cls(
            browser_name=data["browser_name"],
            profile_id=data["profile_id"],
            db_path=Path(data["db_path"]),
            is_chromium=data["is_chromium"],
            local_state_path=Path(data["local_state_path"]) if data.get("local_state_path") else None,
        )


@dataclass
class CookieRecord:
    """Represents a single cookie from any browser."""

    domain: str  # Normalized: "google.com"
    raw_host_key: str  # As stored: ".google.com"
    name: str  # Cookie name
    store: BrowserStore  # Source reference
    expires: Optional[datetime] = None
    is_secure: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "domain": self.domain,
            "raw_host_key": self.raw_host_key,
            "name": self.name,
            "store": self.store.to_dict(),
            "expires": self.expires.isoformat() if self.expires else None,
            "is_secure": self.is_secure,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CookieRecord:
        """Create instance from dictionary."""
        return cls(
            domain=data["domain"],
            raw_host_key=data["raw_host_key"],
            name=data["name"],
            store=BrowserStore.from_dict(data["store"]),
            expires=datetime.fromisoformat(data["expires"]) if data.get("expires") else None,
            is_secure=data.get("is_secure", False),
        )


@dataclass
class DomainAggregate:
    """Aggregates cookies by domain across all browsers/profiles."""

    normalized_domain: str  # "google.com" (for display/matching)
    cookie_count: int  # Total across all sources
    browsers: set[str]  # {"Chrome", "Firefox"}
    records: list[CookieRecord] = field(default_factory=list)
    raw_host_keys: set[str] = field(default_factory=set)  # {".google.com", "google.com"}

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "normalized_domain": self.normalized_domain,
            "cookie_count": self.cookie_count,
            "browsers": list(self.browsers),
            "records": [r.to_dict() for r in self.records],
            "raw_host_keys": list(self.raw_host_keys),
        }

    @classmethod
    def from_dict(cls, data: dict) -> DomainAggregate:
        """Create instance from dictionary."""
        return cls(
            normalized_domain=data["normalized_domain"],
            cookie_count=data["cookie_count"],
            browsers=set(data["browsers"]),
            records=[CookieRecord.from_dict(r) for r in data.get("records", [])],
            raw_host_keys=set(data.get("raw_host_keys", [])),
        )


@dataclass
class DeleteTarget:
    """A single domain target within a delete operation."""

    normalized_domain: str
    match_pattern: str  # SQL LIKE pattern: "%.doubleclick.net"
    count: int

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> DeleteTarget:
        """Create instance from dictionary."""
        return cls(**data)


@dataclass
class DeleteOperation:
    """Represents delete operations for a single browser profile."""

    browser: str
    profile: str
    db_path: Path
    backup_path: Path
    browser_executable: str = ""  # e.g., "chrome.exe" for process gate check
    targets: list[DeleteTarget] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "browser": self.browser,
            "profile": self.profile,
            "db_path": str(self.db_path),
            "backup_path": str(self.backup_path),
            "browser_executable": self.browser_executable,
            "targets": [t.to_dict() for t in self.targets],
        }

    @classmethod
    def from_dict(cls, data: dict) -> DeleteOperation:
        """Create instance from dictionary."""
        return cls(
            browser=data["browser"],
            profile=data["profile"],
            db_path=Path(data["db_path"]),
            backup_path=Path(data["backup_path"]),
            browser_executable=data.get("browser_executable", ""),
            targets=[DeleteTarget.from_dict(t) for t in data.get("targets", [])],
        )


@dataclass
class DeletePlan:
    """
    Complete deletion plan for execution.

    Generated before any delete operation to ensure deterministic
    behavior and support for dry-run functionality.
    """

    plan_id: str  # UUID v4
    timestamp: datetime
    dry_run: bool
    operations: list[DeleteOperation] = field(default_factory=list)
    total_cookies_to_delete: int = 0
    affected_profiles: int = 0

    @classmethod
    def create(cls, dry_run: bool = False) -> DeletePlan:
        """Create a new DeletePlan with generated ID and current timestamp."""
        return cls(
            plan_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            dry_run=dry_run,
        )

    def add_operation(self, operation: DeleteOperation) -> None:
        """Add an operation and update summary counts."""
        self.operations.append(operation)
        self.total_cookies_to_delete += sum(t.count for t in operation.targets)
        self.affected_profiles = len(self.operations)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "plan_id": self.plan_id,
            "timestamp": self.timestamp.isoformat() + "Z",
            "dry_run": self.dry_run,
            "operations": [op.to_dict() for op in self.operations],
            "summary": {
                "total_cookies_to_delete": self.total_cookies_to_delete,
                "affected_profiles": self.affected_profiles,
            },
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict) -> DeletePlan:
        """Create instance from dictionary."""
        timestamp_str = data["timestamp"]
        if timestamp_str.endswith("Z"):
            timestamp_str = timestamp_str[:-1]
        return cls(
            plan_id=data["plan_id"],
            timestamp=datetime.fromisoformat(timestamp_str),
            dry_run=data["dry_run"],
            operations=[DeleteOperation.from_dict(op) for op in data.get("operations", [])],
            total_cookies_to_delete=data.get("summary", {}).get("total_cookies_to_delete", 0),
            affected_profiles=data.get("summary", {}).get("affected_profiles", 0),
        )

    @classmethod
    def from_json(cls, json_str: str) -> DeletePlan:
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))
