"""Local-first security helpers for encrypted storage, hashes and audit metadata.

The service intentionally keeps secrets out of source control.  A per-machine key
is derived from the current OS account and machine identifiers, then used for
backup encryption and tamper hashes.  If ``cryptography`` is installed the backup
payload is protected with Fernet; otherwise a deterministic XOR stream is used as
an offline fallback so the application remains buildable in minimal environments.
"""

from __future__ import annotations

import base64
import getpass
import hashlib
import hmac
import importlib
import importlib.util
import json
import os
import platform
import secrets
import uuid
from pathlib import Path
from typing import Any, Dict


class EncryptionService:
    """Machine-bound crypto and integrity utilities."""

    META_VERSION = 1

    def __init__(self, app_salt_path: str | Path = "data/.machine_salt") -> None:
        self.app_salt_path = Path(app_salt_path)
        self.app_salt_path.parent.mkdir(parents=True, exist_ok=True)
        self._salt = self._load_or_create_salt()
        self._machine_id = self._build_machine_id()
        self._key_bytes = hashlib.sha256(
            f"{self._machine_id}:{self._salt}".encode("utf-8")
        ).digest()

    @property
    def machine_id_hash(self) -> str:
        return hashlib.sha256(self._machine_id.encode("utf-8")).hexdigest()

    def hash_password(self, password: str) -> str:
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 240_000)
        return f"pbkdf2_sha256${salt}${base64.b64encode(digest).decode()}"

    def verify_password(self, password: str, stored_hash: str) -> bool:
        if not stored_hash or "$" not in stored_hash:
            return False
        try:
            algo, salt, encoded = stored_hash.split("$", 2)
        except ValueError:
            return False
        if algo != "pbkdf2_sha256":
            return False
        expected = base64.b64decode(encoded.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 240_000)
        return hmac.compare_digest(actual, expected)

    def canonical_json(self, payload: Dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def content_hash(self, payload: Dict[str, Any]) -> str:
        return hashlib.sha256(self.canonical_json(payload).encode("utf-8")).hexdigest()

    def sign_payload(self, payload: Dict[str, Any]) -> str:
        return hmac.new(
            self._key_bytes,
            self.canonical_json(payload).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def validate_signature(self, payload: Dict[str, Any], signature: str) -> bool:
        if not signature:
            return False
        return hmac.compare_digest(self.sign_payload(payload), signature)

    def encrypt_bytes(self, data: bytes) -> bytes:
        if importlib.util.find_spec("cryptography") is not None:
            fernet_mod = importlib.import_module("cryptography.fernet")
            key = base64.urlsafe_b64encode(self._key_bytes)
            return fernet_mod.Fernet(key).encrypt(data)
        return self._xor_stream(data)

    def decrypt_bytes(self, data: bytes) -> bytes:
        if importlib.util.find_spec("cryptography") is not None:
            fernet_mod = importlib.import_module("cryptography.fernet")
            key = base64.urlsafe_b64encode(self._key_bytes)
            return fernet_mod.Fernet(key).decrypt(data)
        return self._xor_stream(data)

    def build_meta(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "version": self.META_VERSION,
            "machine_id_hash": self.machine_id_hash,
            "content_hash": self.content_hash(payload),
            "signature": self.sign_payload(payload),
        }

    def _load_or_create_salt(self) -> str:
        if self.app_salt_path.exists():
            return self.app_salt_path.read_text(encoding="utf-8").strip()
        salt = secrets.token_hex(32)
        self.app_salt_path.write_text(salt, encoding="utf-8")
        return salt

    def _build_machine_id(self) -> str:
        parts = [
            platform.node(),
            platform.system(),
            platform.machine(),
            getpass.getuser(),
            str(uuid.getnode()),
            os.environ.get("COMPUTERNAME", ""),
            os.environ.get("HOSTNAME", ""),
        ]
        return "|".join(parts)

    def _xor_stream(self, data: bytes) -> bytes:
        out = bytearray()
        counter = 0
        while len(out) < len(data):
            out.extend(hashlib.sha256(self._key_bytes + counter.to_bytes(8, "big")).digest())
            counter += 1
        return bytes(b ^ k for b, k in zip(data, out))


encryption_service = EncryptionService()
