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

    # Also copy WAL and SHM files if they exist (for WAL mode databases)
    wal_path = Path(str(db_path) + "-wal")
    shm_path = Path(str(db_path) + "-shm")

    if wal_path.exists():
        wal_temp = Path(str(temp_file) + "-wal")
        shutil.copy2(wal_path, wal_temp)
        logger.debug("Copied WAL file: %s", wal_temp)

    if shm_path.exists():
        shm_temp = Path(str(temp_file) + "-shm")
        shutil.copy2(shm_path, shm_temp)
        logger.debug("Copied SHM file: %s", shm_temp)

    return temp_file


def cleanup_temp_db(temp_path: Path) -> None:
    """
    Remove a temporary database copy and its WAL/SHM files.

    Args:
        temp_path: Path to the temporary file to remove.
    """
    try:
        # Clean up WAL and SHM files first
        wal_path = Path(str(temp_path) + "-wal")
        shm_path = Path(str(temp_path) + "-shm")

        if wal_path.exists():
            wal_path.unlink()
            logger.debug("Cleaned up temp WAL: %s", wal_path)

        if shm_path.exists():
            shm_path.unlink()
            logger.debug("Cleaned up temp SHM: %s", shm_path)

        # Clean up the main database file
        if temp_path.exists():
            temp_path.unlink()
            logger.debug("Cleaned up temp database: %s", temp_path)
    except OSError as e:
        logger.warning("Failed to cleanup temp database %s: %s", temp_path, e)
