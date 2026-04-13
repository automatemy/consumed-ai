"""
Local encrypted vault — Fernet-based credential storage.

Extracted from consumed-bot's storage/vault_local.py for the pip package.
Stores API keys encrypted on disk. Never logs credential values.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class LocalVault:
    """Fernet-encrypted local credential store."""

    def __init__(self, data_dir: str = ""):
        self.data_dir = Path(data_dir) if data_dir else Path.home() / ".consumed-ai"
        self.vault_dir = self.data_dir / "vault"
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        self._fernet = None
        self._init_encryption()

    def _init_encryption(self):
        """Initialize Fernet encryption with a persistent key."""
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            logger.warning("cryptography not installed — vault will use plaintext (NOT for production)")
            return

        key_file = self.vault_dir / ".vault_key"
        if key_file.exists():
            key = key_file.read_bytes()
        else:
            key = Fernet.generate_key()
            key_file.write_bytes(key)
            key_file.chmod(0o600)

        self._fernet = Fernet(key)

    def store(self, key: str, value: str) -> bool:
        """Store an encrypted credential."""
        try:
            if self._fernet:
                encrypted = self._fernet.encrypt(value.encode()).decode()
            else:
                encrypted = value  # Fallback: plaintext

            cred_file = self.vault_dir / f"{key}.enc"
            cred_file.write_text(encrypted)
            cred_file.chmod(0o600)
            logger.info(f"Stored credential: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to store credential {key}: {e}")
            return False

    def get(self, key: str) -> Optional[str]:
        """Retrieve a decrypted credential."""
        cred_file = self.vault_dir / f"{key}.enc"
        if not cred_file.exists():
            return None
        try:
            encrypted = cred_file.read_text()
            if self._fernet:
                return self._fernet.decrypt(encrypted.encode()).decode()
            return encrypted
        except Exception as e:
            logger.error(f"Failed to decrypt credential {key}: {e}")
            return None

    def delete_secret(self, key: str) -> bool:
        """Delete a stored credential."""
        cred_file = self.vault_dir / f"{key}.enc"
        if cred_file.exists():
            cred_file.unlink()
            return True
        return False

    def list_keys(self):
        """List stored credential keys (not values)."""
        return [f.stem for f in self.vault_dir.glob("*.enc")]

    @property
    def count(self) -> int:
        return len(self.list_keys())
