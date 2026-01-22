"""Delete plan builder for Cookie Cleaner.

Builds DeletePlan instances from domain aggregates, separating this logic
from the UI layer for better testability and separation of concerns.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from src.core.models import (
    DomainAggregate,
    DeletePlan,
    DeleteOperation,
    DeleteTarget,
)

logger = logging.getLogger(__name__)


class DeletePlanner:
    """
    Builds DeletePlan instances from domain aggregates.

    Separates plan building logic from the UI/worker layer.
    """

    def build_plan(
        self,
        domains: list[DomainAggregate],
        dry_run: bool = False,
        backup_dir: Path | None = None,
    ) -> DeletePlan:
        """
        Build a DeletePlan from a list of domain aggregates.

        Groups cookies by browser/profile and creates operations for each.

        Args:
            domains: List of DomainAggregate instances to delete
            dry_run: Whether this is a dry run simulation
            backup_dir: Optional directory for backups. If provided, generates
                       actual backup paths instead of placeholders.

        Returns:
            DeletePlan with operations for each browser profile
        """
        plan = DeletePlan.create(dry_run=dry_run)

        if not domains:
            return plan

        # Group records by (browser, profile, db_path)
        profile_records: dict[tuple, list] = defaultdict(list)

        for domain in domains:
            for record in domain.records:
                key = (
                    record.store.browser_name,
                    record.store.profile_id,
                    record.store.db_path,
                )
                profile_records[key].append(record)

        # Generate timestamp for backup filenames
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create operations for each profile
        for (browser, profile, db_path), records in profile_records.items():
            operation = self._build_operation(
                browser, profile, db_path, records, backup_dir, timestamp
            )
            plan.add_operation(operation)

        logger.debug(
            "Built delete plan %s with %d operations covering %d domains",
            plan.plan_id,
            len(plan.operations),
            len(domains),
        )

        return plan

    def _build_operation(
        self,
        browser: str,
        profile: str,
        db_path: Path,
        records: list,
        backup_dir: Path | None = None,
        timestamp: str | None = None,
    ) -> DeleteOperation:
        """
        Build a single DeleteOperation from cookie records.

        Args:
            browser: Browser name
            profile: Profile ID
            db_path: Path to cookie database
            records: List of CookieRecord instances
            backup_dir: Optional directory for backups
            timestamp: Optional timestamp string for backup filename

        Returns:
            DeleteOperation for this browser profile
        """
        # Group by domain to create targets
        domain_counts: dict[str, int] = defaultdict(int)
        for record in records:
            domain_counts[record.raw_host_key] += 1

        targets = []
        for host_key, count in domain_counts.items():
            # Build SQL LIKE pattern
            if host_key.startswith("."):
                pattern = f"%{host_key}"
            else:
                pattern = host_key

            targets.append(DeleteTarget(
                normalized_domain=host_key.lstrip("."),
                match_pattern=pattern,
                count=count,
            ))

        # Generate backup path if backup_dir provided
        if backup_dir is not None and timestamp:
            # Sanitize browser/profile names for filesystem
            safe_browser = browser.replace(" ", "_").replace("/", "_")
            safe_profile = profile.replace(" ", "_").replace("/", "_")
            backup_filename = f"{safe_browser}_{safe_profile}_{timestamp}.db"
            backup_path = backup_dir / backup_filename
        else:
            # Placeholder - BackupManager generates actual path during execution
            backup_path = Path(".")

        return DeleteOperation(
            browser=browser,
            profile=profile,
            db_path=db_path,
            backup_path=backup_path,
            targets=targets,
        )
