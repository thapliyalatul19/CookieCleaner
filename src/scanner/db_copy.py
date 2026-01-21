"""Database copy utility for safe cookie reading."""

from __future__ import annotations

import hashlib
import logging
import shutil
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Directory name for temp copies
TEMP_SUBDIR = "CookieCleaner"


def copy_db_to_temp(db_path: Path) -> Path:
    """
    Copy SQLite database to temp directory for safe reading.

    This avoids "database is locked" errors when the browser is running.
    The temp file includes a hash suffix to avoid collisions.

    Args:
        db_path: Path to the original database file.

    Returns:
        Path to the temporary copy.

    Raises:
        FileNotFoundError: If the source database doesn't exist.
        OSError: If copying fails.
    """
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    temp_dir = Path(tempfile.gettempdir()) / TEMP_SUBDIR
    temp_dir.mkdir(exist_ok=True)

    # Include hash to avoid collisions from different browser profiles
    hash_suffix = hashlib.md5(str(db_path).encode()).hexdigest()[:8]
    temp_file = temp_dir / f"cookies_{hash_suffix}.db"

    logger.debug("Copying database %s to %s", db_path, temp_file)
    shutil.copy2(db_path, temp_file)

    return temp_file


def cleanup_temp_db(temp_path: Path) -> None:
    """
    Remove a temporary database copy.

    Args:
        temp_path: Path to the temporary file to remove.
    """
    try:
        if temp_path.exists():
            temp_path.unlink()
            logger.debug("Cleaned up temp database: %s", temp_path)
    except OSError as e:
        logger.warning("Failed to cleanup temp database %s: %s", temp_path, e)
