"""Chromium cookie value decryptor using Windows DPAPI and AES-GCM."""

from __future__ import annotations

import base64
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Version prefixes for encrypted cookie values
V10_PREFIX = b"v10"
V11_PREFIX = b"v11"
DPAPI_PREFIX = b"DPAPI"


class DecryptionError(Exception):
    """Raised when decryption fails."""


class ChromiumDecryptor:
    """
    Decrypts Chromium cookie values using DPAPI + AES-GCM.

    Chromium browsers encrypt cookie values using a master key stored in
    the Local State file. The master key itself is encrypted with Windows
    DPAPI. Cookie values are then encrypted with AES-256-GCM using this key.

    Pre-v80 cookies may use legacy DPAPI-only encryption (no v10/v11 prefix).

    Usage:
        decryptor = ChromiumDecryptor(local_state_path)
        plain_text = decryptor.decrypt_value(encrypted_value)
    """

    def __init__(self, local_state_path: Path | None) -> None:
        """
        Initialize the decryptor.

        Args:
            local_state_path: Path to Chrome's "Local State" JSON file.
                              If None, decryption will be unavailable.
        """
        self._local_state_path = local_state_path
        self._master_key: bytes | None = None
        self._key_loaded = False

    @property
    def master_key(self) -> bytes | None:
        """
        Lazy-load and return the master key.

        Returns:
            The decrypted master key, or None if unavailable.
        """
        if not self._key_loaded:
            self._load_master_key()
            self._key_loaded = True
        return self._master_key

    def decrypt_value(self, encrypted_value: bytes) -> str | None:
        """
        Decrypt an encrypted cookie value.

        Args:
            encrypted_value: The raw encrypted_value blob from the database.

        Returns:
            Decrypted string value, or None if decryption fails.
            Returns empty string for empty input.
        """
        if not encrypted_value:
            return ""

        # Check for v10/v11 prefix (AES-GCM encryption)
        if encrypted_value[:3] in (V10_PREFIX, V11_PREFIX):
            return self._decrypt_aes_gcm(encrypted_value)

        # Legacy DPAPI-only encryption (pre-v80)
        return self._decrypt_legacy_dpapi(encrypted_value)

    def _load_master_key(self) -> None:
        """
        Load and decrypt the master key from Local State.

        The master key is stored as base64 in Local State JSON under
        os_crypt.encrypted_key. It has a "DPAPI" prefix (5 bytes) followed
        by the DPAPI-encrypted key blob.
        """
        if self._local_state_path is None:
            logger.debug("No Local State path provided")
            return

        if not self._local_state_path.exists():
            logger.debug("Local State file not found: %s", self._local_state_path)
            return

        try:
            with open(self._local_state_path, "r", encoding="utf-8") as f:
                local_state = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.debug("Failed to read Local State: %s", e)
            return

        # Extract encrypted key
        try:
            encrypted_key_b64 = local_state["os_crypt"]["encrypted_key"]
        except (KeyError, TypeError):
            logger.debug("No os_crypt.encrypted_key in Local State")
            return

        try:
            encrypted_key = base64.b64decode(encrypted_key_b64)
        except (ValueError, TypeError) as e:
            logger.debug("Failed to decode encrypted_key: %s", e)
            return

        # Verify and strip DPAPI prefix
        if not encrypted_key.startswith(DPAPI_PREFIX):
            logger.debug("Encrypted key missing DPAPI prefix")
            return

        encrypted_key = encrypted_key[len(DPAPI_PREFIX) :]

        # Decrypt with DPAPI
        decrypted = self._dpapi_decrypt(encrypted_key)
        if decrypted is not None:
            self._master_key = decrypted
            logger.debug("Master key loaded successfully")

    def _dpapi_decrypt(self, data: bytes) -> bytes | None:
        """
        Decrypt data using Windows DPAPI.

        Args:
            data: DPAPI-encrypted blob.

        Returns:
            Decrypted bytes, or None on failure.
        """
        try:
            import win32crypt
        except ImportError:
            logger.debug("win32crypt not available (not Windows)")
            return None

        try:
            _, decrypted = win32crypt.CryptUnprotectData(data, None, None, None, 0)
            return decrypted
        except Exception as e:
            # DPAPI can fail for various reasons (wrong user context, etc.)
            logger.debug("DPAPI decryption failed: %s", e)
            return None

    def _decrypt_aes_gcm(self, encrypted_value: bytes) -> str | None:
        """
        Decrypt a v10/v11 AES-GCM encrypted value.

        Format: v10/v11 (3 bytes) + nonce (12 bytes) + ciphertext + tag (16 bytes)

        Args:
            encrypted_value: The encrypted blob with v10/v11 prefix.

        Returns:
            Decrypted string, or None on failure.
        """
        if self.master_key is None:
            logger.debug("Cannot decrypt AES-GCM: no master key")
            return None

        try:
            from Crypto.Cipher import AES
        except ImportError:
            logger.debug("pycryptodome not available")
            return None

        # Extract components
        # Skip prefix (3 bytes), nonce is next 12 bytes
        nonce = encrypted_value[3:15]
        # Ciphertext includes the auth tag (last 16 bytes)
        ciphertext_with_tag = encrypted_value[15:]

        if len(ciphertext_with_tag) < 16:
            logger.debug("Encrypted value too short for AES-GCM")
            return None

        # Split ciphertext and tag
        ciphertext = ciphertext_with_tag[:-16]
        tag = ciphertext_with_tag[-16:]

        try:
            cipher = AES.new(self.master_key, AES.MODE_GCM, nonce=nonce)
            decrypted = cipher.decrypt_and_verify(ciphertext, tag)
            return decrypted.decode("utf-8")
        except (ValueError, UnicodeDecodeError) as e:
            # ValueError: tag verification failed
            # UnicodeDecodeError: decrypted data isn't valid UTF-8
            logger.debug("AES-GCM decryption failed: %s", e)
            return None

    def _decrypt_legacy_dpapi(self, encrypted_value: bytes) -> str | None:
        """
        Decrypt a legacy DPAPI-only encrypted value (pre-v80).

        Args:
            encrypted_value: The encrypted blob without v10/v11 prefix.

        Returns:
            Decrypted string, or None on failure.
        """
        decrypted = self._dpapi_decrypt(encrypted_value)
        if decrypted is None:
            return None

        try:
            return decrypted.decode("utf-8")
        except UnicodeDecodeError as e:
            logger.debug("Legacy DPAPI decryption produced invalid UTF-8: %s", e)
            return None


@lru_cache(maxsize=16)
def get_decryptor(local_state_path: Path | None) -> ChromiumDecryptor:
    """
    Get a cached ChromiumDecryptor instance for the given Local State path.

    Args:
        local_state_path: Path to Chrome's "Local State" JSON file.

    Returns:
        ChromiumDecryptor instance (cached).
    """
    return ChromiumDecryptor(local_state_path)
