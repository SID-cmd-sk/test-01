# services/auth_service.py
"""
Microsoft Login / MSAL Authentication — Phase 3.

Supports:
  - Interactive browser login (opens system browser)
  - Device-code flow (for headless / corporate environments)
  - Token caching (remember device between sessions)
  - Offline session recovery from cached token

Prerequisites:
  pip install msal

Azure Setup:
  1. Register an app in Azure Portal → App Registrations
  2. Set Redirect URI to: http://localhost (for desktop apps)
  3. Enable "Mobile and desktop applications" platform
  4. Copy the Application (client) ID into Admin Settings → Microsoft Login
  5. Set Tenant ID (use "common" for multi-tenant / personal accounts)

Configuration is stored in global_config (not hardcoded here).
"""

from __future__ import annotations

import importlib
import json
import os
import threading
from pathlib import Path
from typing import Optional, Tuple

from PyQt6.QtCore import QThread, pyqtSignal


# Cache file path — stores encrypted MSAL token cache between sessions
MSAL_CACHE_PATH = Path("cache/msal_token_cache.json")


class MSALAuthError(Exception):
    pass


class MicrosoftAuthService:
    """Wrapper around MSAL for Microsoft / Azure AD login."""

    SCOPES = ["User.Read", "openid", "profile", "email"]

    def __init__(self) -> None:
        self._app          = None
        self._lock         = threading.Lock()
        self._token_cache  = None

    def _get_config(self) -> Tuple[str, str]:
        """Return (client_id, tenant_id) from global_config."""
        from services.config_service import global_config
        cfg       = global_config.get()
        client_id = cfg.get("azure_client_id", "").strip() or os.getenv("AZURE_CLIENT_ID", "")
        tenant_id = cfg.get("azure_tenant_id", "common").strip() or "common"
        return client_id, tenant_id

    def is_configured(self) -> bool:
        client_id, _ = self._get_config()
        return bool(client_id)

    def _init_app(self) -> bool:
        """Lazy-init the MSAL PublicClientApplication."""
        with self._lock:
            if self._app is not None:
                return True
            client_id, tenant_id = self._get_config()
            if not client_id:
                return False
            try:
                msal = importlib.import_module("msal")

                # Load or create token cache
                MSAL_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
                cache = msal.SerializableTokenCache()
                if MSAL_CACHE_PATH.exists():
                    try:
                        from services.encryption_service import encryption_service
                        raw = encryption_service.decrypt_bytes(MSAL_CACHE_PATH.read_bytes())
                        cache.deserialize(raw.decode("utf-8"))
                    except Exception:
                        pass   # corrupted or legacy plaintext cache — start fresh

                self._token_cache = cache
                authority = f"https://login.microsoftonline.com/{tenant_id}"

                self._app = msal.PublicClientApplication(
                    client_id,
                    authority=authority,
                    token_cache=cache,
                )
                return True
            except ImportError:
                raise MSALAuthError(
                    "msal is not installed.\nRun: pip install msal"
                )
            except Exception as e:
                raise MSALAuthError(f"MSAL init failed: {e}")

    def _save_cache(self) -> None:
        if self._token_cache and self._token_cache.has_state_changed:
            try:
                from services.encryption_service import encryption_service
                MSAL_CACHE_PATH.write_bytes(
                    encryption_service.encrypt_bytes(self._token_cache.serialize().encode("utf-8"))
                )
            except Exception:
                pass

    def login_interactive(self) -> dict:
        """
        Open the system browser for Microsoft login.
        Returns user profile dict on success.
        Raises MSALAuthError on failure.
        """
        if not self._init_app():
            raise MSALAuthError("Microsoft login is not configured. Set Client ID in Admin Settings.")

        # Try silent first (cached token)
        result = self._try_silent()
        if result:
            self._save_cache()
            return self._extract_user(result)

        # Interactive login
        try:
            result = self._app.acquire_token_interactive(scopes=self.SCOPES)
        except Exception as e:
            raise MSALAuthError(f"Interactive login failed: {e}")

        if "error" in result:
            raise MSALAuthError(
                f"Login failed: {result.get('error_description', result['error'])}"
            )

        self._save_cache()
        return self._extract_user(result)

    def login_device_code(self, callback=None) -> dict:
        """
        Device-code flow — prints a URL and code the user enters in a browser.
        `callback(url, code)` is called with the URL and code for display in the UI.
        Returns user profile dict on success.
        """
        if not self._init_app():
            raise MSALAuthError("Microsoft login is not configured.")

        result = self._try_silent()
        if result:
            self._save_cache()
            return self._extract_user(result)

        try:
            flow = self._app.initiate_device_flow(scopes=self.SCOPES)
        except Exception as e:
            raise MSALAuthError(f"Device flow init failed: {e}")

        if "error" in flow:
            raise MSALAuthError(
                f"Device flow error: {flow.get('error_description', flow['error'])}"
            )

        if callback:
            callback(
                flow.get("verification_uri", ""),
                flow.get("user_code", ""),
                flow.get("message", ""),
            )

        result = self._app.acquire_token_by_device_flow(flow)
        if "error" in result:
            raise MSALAuthError(
                f"Authentication failed: {result.get('error_description', result['error'])}"
            )

        self._save_cache()
        return self._extract_user(result)

    def logout(self) -> None:
        """Clear cached tokens."""
        try:
            if MSAL_CACHE_PATH.exists():
                MSAL_CACHE_PATH.unlink()
            with self._lock:
                self._app = None
                self._token_cache = None
        except Exception:
            pass

    def _try_silent(self) -> Optional[dict]:
        """Try to get a token silently from cache."""
        try:
            accounts = self._app.get_accounts()
            if accounts:
                result = self._app.acquire_token_silent(
                    scopes=self.SCOPES, account=accounts[0]
                )
                if result and "access_token" in result:
                    return result
        except Exception:
            pass
        return None

    def _extract_user(self, result: dict) -> dict:
        """Extract user profile from MSAL result."""
        claims = result.get("id_token_claims", {})
        return {
            "email":      claims.get("preferred_username", claims.get("email", "")),
            "name":       claims.get("name", ""),
            "oid":        claims.get("oid", ""),           # Azure Object ID
            "tenant_id":  claims.get("tid", ""),
            "access_token": result.get("access_token", ""),
        }


microsoft_auth = MicrosoftAuthService()


# ── QThread worker ────────────────────────────────────────────────────────────

class MicrosoftLoginWorker(QThread):
    """
    Run Microsoft login in a background thread.
    On success emits: (email, name, azure_oid)
    On error emits: error message string
    """
    success      = pyqtSignal(str, str, str)   # email, name, oid
    device_code  = pyqtSignal(str, str, str)   # url, code, message
    error        = pyqtSignal(str)

    def __init__(self, mode: str = "interactive"):
        super().__init__()
        self.mode = mode   # "interactive" | "device_code"

    def run(self):
        try:
            if self.mode == "device_code":
                def _code_callback(url, code, msg):
                    self.device_code.emit(url, code, msg)

                user = microsoft_auth.login_device_code(callback=_code_callback)
            else:
                user = microsoft_auth.login_interactive()

            # Find or create a local user record mapped to this Azure account
            local_user = _find_or_create_azure_user(user)
            self.success.emit(
                local_user.get("email", user["email"]),
                local_user.get("name",  user["name"]),
                user.get("oid", ""),
            )
        except MSALAuthError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Unexpected error: {e}")


def _find_or_create_azure_user(azure_user: dict) -> dict:
    """
    Map an Azure AD user to a local user record.
    If none exists, create one with 'viewer' role (admin must approve/elevate).
    """
    from db import storage
    from utils.helpers import utc_now_iso

    email = azure_user.get("email", "").strip().lower()
    if not email:
        raise MSALAuthError("No email returned from Microsoft. Check your Azure app permissions.")

    # Look up by email
    existing = None
    for u in storage.get_collection("users"):
        if u.get("email", "").strip().lower() == email:
            existing = u
            break

    if existing:
        if not existing.get("active", True):
            raise MSALAuthError("Your account is inactive. Contact your admin.")
        return existing

    # Create new user from Azure profile — pending admin approval
    uid = f"azure-{azure_user.get('oid', email)}"
    storage.create_document("users", {
        "uid":          uid,
        "email":        email,
        "name":         azure_user.get("name", email.split("@")[0]),
        "role":         "viewer",         # lowest role — admin must elevate
        "azure_oid":    azure_user.get("oid", ""),
        "active":       True,
        "created_at":   utc_now_iso(),
        "auth_provider": "microsoft",
    }, doc_id=uid)

    from services.audit_service import log_action
    log_action("azure_user_created",
               f"New user created via Microsoft Login: {email}", uid)

    return storage.get_document("users", uid) or {"email": email, "name": azure_user.get("name", "")}
