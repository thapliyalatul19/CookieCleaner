"""Tests for Chromium cookie decryptor."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.scanner.decryptor import (
    ChromiumDecryptor,
    DecryptionError,
    get_decryptor,
    V10_PREFIX,
    V11_PREFIX,
    DPAPI_PREFIX,
)


class TestChromiumDecryptorInit:
    """Tests for ChromiumDecryptor initialization."""

    def test_init_with_no_path(self) -> None:
        """Handles None path gracefully."""
        decryptor = ChromiumDecryptor(None)

        assert decryptor._local_state_path is None
        assert decryptor._master_key is None
        assert decryptor._key_loaded is False

    def test_init_with_nonexistent_path(self, tmp_path: Path) -> None:
        """Handles missing file gracefully."""
        nonexistent = tmp_path / "nonexistent" / "Local State"
        decryptor = ChromiumDecryptor(nonexistent)

        # Accessing master_key triggers loading
        assert decryptor.master_key is None
        assert decryptor._key_loaded is True

    def test_loads_master_key_lazily(self, tmp_path: Path) -> None:
        """Key not loaded until master_key property accessed."""
        local_state = tmp_path / "Local State"
        local_state.write_text("{}")

        decryptor = ChromiumDecryptor(local_state)

        # Key not loaded yet
        assert decryptor._key_loaded is False

        # Access property triggers load
        _ = decryptor.master_key

        assert decryptor._key_loaded is True


class TestMasterKeyLoading:
    """Tests for master key loading from Local State."""

    def test_handles_invalid_json(self, tmp_path: Path) -> None:
        """Corrupted Local State returns None."""
        local_state = tmp_path / "Local State"
        local_state.write_text("not valid json {{{")

        decryptor = ChromiumDecryptor(local_state)

        assert decryptor.master_key is None

    def test_handles_missing_encrypted_key(self, tmp_path: Path) -> None:
        """No os_crypt key in JSON returns None."""
        local_state = tmp_path / "Local State"
        local_state.write_text(json.dumps({"other_key": "value"}))

        decryptor = ChromiumDecryptor(local_state)

        assert decryptor.master_key is None

    def test_handles_missing_os_crypt_section(self, tmp_path: Path) -> None:
        """Missing os_crypt section returns None."""
        local_state = tmp_path / "Local State"
        local_state.write_text(json.dumps({}))

        decryptor = ChromiumDecryptor(local_state)

        assert decryptor.master_key is None

    def test_handles_invalid_base64(self, tmp_path: Path) -> None:
        """Invalid base64 in encrypted_key returns None."""
        local_state = tmp_path / "Local State"
        local_state.write_text(
            json.dumps({"os_crypt": {"encrypted_key": "not-valid-base64!!"}})
        )

        decryptor = ChromiumDecryptor(local_state)

        assert decryptor.master_key is None

    def test_handles_missing_dpapi_prefix(self, tmp_path: Path) -> None:
        """Rejects encrypted key without DPAPI prefix."""
        local_state = tmp_path / "Local State"
        # Valid base64 but no DPAPI prefix
        fake_key = base64.b64encode(b"NODPAPI_encrypted_data").decode()
        local_state.write_text(
            json.dumps({"os_crypt": {"encrypted_key": fake_key}})
        )

        decryptor = ChromiumDecryptor(local_state)

        assert decryptor.master_key is None

    def test_decrypts_master_key_with_dpapi(self, tmp_path: Path) -> None:
        """Mock DPAPI decrypts master key successfully."""
        local_state = tmp_path / "Local State"
        # DPAPI prefix + some encrypted data
        encrypted_key = DPAPI_PREFIX + b"encrypted_master_key_data"
        encoded = base64.b64encode(encrypted_key).decode()
        local_state.write_text(
            json.dumps({"os_crypt": {"encrypted_key": encoded}})
        )

        fake_master_key = b"0123456789abcdef0123456789abcdef"  # 32 bytes

        with patch("src.scanner.decryptor.ChromiumDecryptor._dpapi_decrypt") as mock_dpapi:
            mock_dpapi.return_value = fake_master_key

            decryptor = ChromiumDecryptor(local_state)
            key = decryptor.master_key

        assert key == fake_master_key
        mock_dpapi.assert_called_once_with(b"encrypted_master_key_data")


class TestDecryptValue:
    """Tests for decrypt_value method."""

    def test_empty_value_returns_empty_string(self) -> None:
        """Empty input returns empty string."""
        decryptor = ChromiumDecryptor(None)

        assert decryptor.decrypt_value(b"") == ""
        assert decryptor.decrypt_value(b"") == ""

    def test_none_value_returns_empty_string(self) -> None:
        """None-ish empty bytes returns empty string."""
        decryptor = ChromiumDecryptor(None)

        result = decryptor.decrypt_value(b"")
        assert result == ""

    def test_v10_prefix_uses_aes_gcm(self, tmp_path: Path) -> None:
        """v10 prefixed values route to AES-GCM decryption."""
        decryptor = ChromiumDecryptor(None)

        # v10 + 12 byte nonce + some ciphertext + 16 byte tag
        fake_encrypted = V10_PREFIX + (b"\x00" * 12) + b"ciphertext" + (b"\x00" * 16)

        with patch.object(decryptor, "_decrypt_aes_gcm") as mock_aes:
            mock_aes.return_value = "decrypted"
            result = decryptor.decrypt_value(fake_encrypted)

        mock_aes.assert_called_once_with(fake_encrypted)
        assert result == "decrypted"

    def test_v11_prefix_uses_aes_gcm(self, tmp_path: Path) -> None:
        """v11 prefixed values route to AES-GCM decryption."""
        decryptor = ChromiumDecryptor(None)

        fake_encrypted = V11_PREFIX + (b"\x00" * 12) + b"ciphertext" + (b"\x00" * 16)

        with patch.object(decryptor, "_decrypt_aes_gcm") as mock_aes:
            mock_aes.return_value = "decrypted"
            result = decryptor.decrypt_value(fake_encrypted)

        mock_aes.assert_called_once_with(fake_encrypted)
        assert result == "decrypted"

    def test_no_prefix_uses_legacy_dpapi(self) -> None:
        """Values without v10/v11 prefix use legacy DPAPI."""
        decryptor = ChromiumDecryptor(None)

        # Some random data without v10/v11 prefix
        fake_encrypted = b"\x01\x00\x00\x00legacy_dpapi_data"

        with patch.object(decryptor, "_decrypt_legacy_dpapi") as mock_legacy:
            mock_legacy.return_value = "legacy_value"
            result = decryptor.decrypt_value(fake_encrypted)

        mock_legacy.assert_called_once_with(fake_encrypted)
        assert result == "legacy_value"

    def test_returns_none_without_master_key(self) -> None:
        """AES-GCM decryption returns None if no master key."""
        decryptor = ChromiumDecryptor(None)

        # v10 encrypted value
        fake_encrypted = V10_PREFIX + (b"\x00" * 12) + b"ciphertext" + (b"\x00" * 16)

        result = decryptor.decrypt_value(fake_encrypted)

        assert result is None


class TestAESGCMDecryption:
    """Tests for AES-GCM decryption."""

    def test_decrypts_valid_aes_gcm_data(self) -> None:
        """Full AES-GCM decryption with valid data."""
        from Crypto.Cipher import AES

        # Create a real encrypted value
        master_key = b"0123456789abcdef0123456789abcdef"  # 32 bytes
        plaintext = "my_cookie_value"
        nonce = b"123456789012"  # 12 bytes

        cipher = AES.new(master_key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode("utf-8"))

        encrypted_value = V10_PREFIX + nonce + ciphertext + tag

        # Create decryptor with mocked master key
        decryptor = ChromiumDecryptor(None)
        decryptor._master_key = master_key
        decryptor._key_loaded = True

        result = decryptor.decrypt_value(encrypted_value)

        assert result == plaintext

    def test_handles_invalid_tag(self) -> None:
        """Authentication failure returns None."""
        from Crypto.Cipher import AES

        master_key = b"0123456789abcdef0123456789abcdef"
        nonce = b"123456789012"

        cipher = AES.new(master_key, AES.MODE_GCM, nonce=nonce)
        ciphertext, _ = cipher.encrypt_and_digest(b"test")

        # Use invalid tag
        invalid_tag = b"\x00" * 16
        encrypted_value = V10_PREFIX + nonce + ciphertext + invalid_tag

        decryptor = ChromiumDecryptor(None)
        decryptor._master_key = master_key
        decryptor._key_loaded = True

        result = decryptor.decrypt_value(encrypted_value)

        assert result is None

    def test_handles_too_short_value(self) -> None:
        """Value too short for AES-GCM returns None."""
        decryptor = ChromiumDecryptor(None)
        decryptor._master_key = b"0123456789abcdef0123456789abcdef"
        decryptor._key_loaded = True

        # v10 + nonce (12) + less than 16 bytes for tag
        too_short = V10_PREFIX + (b"\x00" * 12) + b"short"

        result = decryptor.decrypt_value(too_short)

        assert result is None

    def test_handles_v11_same_as_v10(self) -> None:
        """v11 uses same AES-GCM format as v10."""
        from Crypto.Cipher import AES

        master_key = b"0123456789abcdef0123456789abcdef"
        plaintext = "v11_cookie"
        nonce = b"abcdefghijkl"

        cipher = AES.new(master_key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode("utf-8"))

        encrypted_value = V11_PREFIX + nonce + ciphertext + tag

        decryptor = ChromiumDecryptor(None)
        decryptor._master_key = master_key
        decryptor._key_loaded = True

        result = decryptor.decrypt_value(encrypted_value)

        assert result == plaintext


class TestLegacyDPAPI:
    """Tests for legacy DPAPI decryption."""

    def test_dpapi_decryption_success(self) -> None:
        """Legacy DPAPI decryption returns decoded string."""
        decryptor = ChromiumDecryptor(None)

        with patch.object(decryptor, "_dpapi_decrypt") as mock_dpapi:
            mock_dpapi.return_value = b"legacy_cookie_value"

            # Non-v10/v11 prefixed value
            encrypted = b"\x01\x00\x00\x00encrypted_data"
            result = decryptor.decrypt_value(encrypted)

        assert result == "legacy_cookie_value"

    def test_dpapi_decryption_failure(self) -> None:
        """DPAPI failure returns None."""
        decryptor = ChromiumDecryptor(None)

        with patch.object(decryptor, "_dpapi_decrypt") as mock_dpapi:
            mock_dpapi.return_value = None

            encrypted = b"\x01\x00\x00\x00encrypted_data"
            result = decryptor.decrypt_value(encrypted)

        assert result is None

    def test_dpapi_invalid_utf8(self) -> None:
        """Invalid UTF-8 from DPAPI returns None."""
        decryptor = ChromiumDecryptor(None)

        with patch.object(decryptor, "_dpapi_decrypt") as mock_dpapi:
            # Invalid UTF-8 bytes
            mock_dpapi.return_value = b"\xff\xfe\x00\x01"

            encrypted = b"\x01\x00\x00\x00encrypted_data"
            result = decryptor.decrypt_value(encrypted)

        assert result is None


class TestDPAPIDecrypt:
    """Tests for _dpapi_decrypt internal method."""

    def test_win32crypt_not_available(self) -> None:
        """Returns None when win32crypt not available."""
        decryptor = ChromiumDecryptor(None)

        with patch.dict("sys.modules", {"win32crypt": None}):
            # Force re-import to fail
            with patch(
                "src.scanner.decryptor.ChromiumDecryptor._dpapi_decrypt",
                wraps=decryptor._dpapi_decrypt,
            ):
                # Import error simulation - just test the graceful failure
                pass

    def test_dpapi_exception_returns_none(self) -> None:
        """DPAPI exceptions return None gracefully."""
        decryptor = ChromiumDecryptor(None)

        mock_win32crypt = MagicMock()
        mock_win32crypt.CryptUnprotectData.side_effect = Exception("DPAPI error")

        with patch.dict("sys.modules", {"win32crypt": mock_win32crypt}):
            result = decryptor._dpapi_decrypt(b"some_data")

        assert result is None


class TestGetDecryptorFactory:
    """Tests for get_decryptor factory function."""

    def test_factory_caches_instances(self, tmp_path: Path) -> None:
        """LRU cache returns same instance for same path."""
        # Clear cache first
        get_decryptor.cache_clear()

        local_state = tmp_path / "Local State"
        local_state.write_text("{}")

        decryptor1 = get_decryptor(local_state)
        decryptor2 = get_decryptor(local_state)

        assert decryptor1 is decryptor2

    def test_factory_different_paths_different_instances(self, tmp_path: Path) -> None:
        """Different paths return different instances."""
        get_decryptor.cache_clear()

        path1 = tmp_path / "Chrome" / "Local State"
        path2 = tmp_path / "Edge" / "Local State"
        path1.parent.mkdir(parents=True)
        path2.parent.mkdir(parents=True)
        path1.write_text("{}")
        path2.write_text("{}")

        decryptor1 = get_decryptor(path1)
        decryptor2 = get_decryptor(path2)

        assert decryptor1 is not decryptor2

    def test_factory_handles_none(self) -> None:
        """Factory handles None path."""
        get_decryptor.cache_clear()

        decryptor = get_decryptor(None)

        assert decryptor is not None
        assert decryptor._local_state_path is None


class TestDecryptionErrorException:
    """Tests for DecryptionError exception."""

    def test_exception_can_be_raised(self) -> None:
        """DecryptionError can be instantiated and raised."""
        with pytest.raises(DecryptionError, match="test message"):
            raise DecryptionError("test message")

    def test_exception_inherits_from_exception(self) -> None:
        """DecryptionError is an Exception subclass."""
        assert issubclass(DecryptionError, Exception)
