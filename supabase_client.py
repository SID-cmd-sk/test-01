# supabase_client.py
"""
Supabase REST API client — drop-in replacement for firebase_client.py.
Handles Auth (email/password via GoTrue), PostgREST CRUD, token refresh.

SETUP STEPS:
  1. Go to https://supabase.com → New Project (free)
  2. Copy your Project URL and anon key from Settings → API
  3. Paste them into SUPABASE_URL and SUPABASE_ANON_KEY below
  4. Run the SQL in supabase_schema.sql inside Supabase SQL Editor

Collections map to Postgres tables:
  Firestore collection        → Supabase table
  ─────────────────────────────────────────────
  service_requests            → service_requests
  users                       → users
  roles                       → roles
  audit_log                   → audit_log
  settings                    → settings
  pipeline_templates          → pipeline_templates
"""

import requests
import time
import threading
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

# ── CONFIG — replace these with your Supabase project values ──────────────────
SUPABASE_URL      = "https://YOUR_PROJECT_ID.supabase.co"   # e.g. https://abcdef.supabase.co
SUPABASE_ANON_KEY = "YOUR_ANON_KEY"                          # Settings → API → anon/public key

AUTH_URL = f"{SUPABASE_URL}/auth/v1"
REST_URL = f"{SUPABASE_URL}/rest/v1"


# ── ERRORS ─────────────────────────────────────────────────────────────────────
class FirebaseAuthError(Exception):
    """Kept as FirebaseAuthError so all existing code that catches this works."""
    pass

class FirebaseNetworkError(Exception):
    """Kept as FirebaseNetworkError so all existing code that catches this works."""
    pass


# ── CLIENT ─────────────────────────────────────────────────────────────────────
class SupabaseClient:
    """
    API-compatible replacement for FirebaseClient.
    All public method signatures are identical so no other file needs changes.
    """

    def __init__(self):
        self._access_token:  Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expiry:  float         = 0
        self._uid:           Optional[str] = None
        self._lock = threading.Lock()

    # ── Auth ───────────────────────────────────────────────────────────────────

    def login(self, email: str, password: str) -> Dict:
        url = f"{AUTH_URL}/token?grant_type=password"
        try:
            res = requests.post(url, json={"email": email, "password": password},
                                headers=self._anon_headers(), timeout=10)
        except requests.exceptions.ConnectionError:
            raise FirebaseNetworkError("No internet connection.")

        data = res.json()
        if res.status_code != 200:
            msg = data.get("error_description") or data.get("msg") or data.get("error", "")
            if "invalid" in str(msg).lower() or "credentials" in str(msg).lower():
                raise FirebaseAuthError("Invalid email or password.")
            raise FirebaseAuthError(msg or "Login failed.")

        with self._lock:
            self._access_token  = data["access_token"]
            self._refresh_token = data["refresh_token"]
            self._token_expiry  = time.time() + int(data.get("expires_in", 3600)) - 60
            self._uid           = data["user"]["id"]

        return {"uid": self._uid, "email": data["user"]["email"]}

    def logout(self):
        # Revoke token server-side
        try:
            requests.post(f"{AUTH_URL}/logout",
                          headers=self._bearer_headers(), timeout=5)
        except Exception:
            pass
        with self._lock:
            self._access_token = self._refresh_token = self._uid = None
            self._token_expiry = 0

    def create_user(self, email: str, password: str) -> str:
        """Create a new user. Returns UID string."""
        # Use admin signUp endpoint (works with anon key if email confirmations are OFF)
        url = f"{AUTH_URL}/signup"
        try:
            res = requests.post(url, json={"email": email, "password": password},
                                headers=self._anon_headers(), timeout=10)
        except requests.exceptions.ConnectionError:
            raise FirebaseNetworkError("No internet connection.")

        data = res.json()
        if res.status_code not in (200, 201):
            msg = data.get("msg") or data.get("error_description") or data.get("error", "")
            if "already" in str(msg).lower() or "exists" in str(msg).lower():
                raise FirebaseAuthError("An account with this email already exists.")
            raise FirebaseAuthError(msg or "Failed to create user.")

        uid = data.get("id") or (data.get("user") or {}).get("id", "")
        return uid

    def _refresh_if_needed(self):
        with self._lock:
            if not self._refresh_token or time.time() < self._token_expiry:
                return
            rt = self._refresh_token
        try:
            res = requests.post(
                f"{AUTH_URL}/token?grant_type=refresh_token",
                json={"refresh_token": rt},
                headers=self._anon_headers(), timeout=10
            )
            if res.status_code == 200:
                d = res.json()
                with self._lock:
                    self._access_token  = d["access_token"]
                    self._refresh_token = d.get("refresh_token", rt)
                    self._token_expiry  = time.time() + int(d.get("expires_in", 3600)) - 60
        except Exception:
            pass

    def _anon_headers(self) -> Dict:
        return {
            "apikey":       SUPABASE_ANON_KEY,
            "Content-Type": "application/json",
        }

    def _bearer_headers(self) -> Dict:
        self._refresh_if_needed()
        with self._lock:
            token = self._access_token
        if not token:
            raise FirebaseAuthError("Not logged in.")
        return {
            "apikey":        SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
            "Prefer":        "return=representation",
        }

    @property
    def uid(self) -> Optional[str]:
        return self._uid

    # ── CRUD ───────────────────────────────────────────────────────────────────

    def get_document(self, collection: str, doc_id: str) -> Optional[dict]:
        """Fetch a single row by its `id` column."""
        url = f"{REST_URL}/{collection}"
        try:
            res = requests.get(url, headers=self._bearer_headers(),
                               params={"id": f"eq.{doc_id}", "limit": "1"},
                               timeout=10)
        except requests.exceptions.ConnectionError:
            raise FirebaseNetworkError("No internet connection.")
        if res.status_code == 404:
            return None
        if res.status_code != 200:
            raise Exception(f"Fetch failed: {res.status_code} {res.text}")
        rows = res.json()
        return rows[0] if rows else None

    def get_collection(self, collection: str) -> List[dict]:
        """Fetch all rows from a table."""
        url = f"{REST_URL}/{collection}"
        try:
            res = requests.get(url, headers=self._bearer_headers(), timeout=10)
        except requests.exceptions.ConnectionError:
            raise FirebaseNetworkError("No internet connection.")
        if res.status_code != 200:
            return []
        return res.json()

    def create_document(self, collection: str, data: dict,
                        doc_id: Optional[str] = None) -> dict:
        """Insert a row. If doc_id given, sets the id column."""
        if doc_id:
            data = dict(data)
            data["id"] = doc_id
        url = f"{REST_URL}/{collection}"
        try:
            res = requests.post(url, headers=self._bearer_headers(),
                                json=data, timeout=10)
        except requests.exceptions.ConnectionError:
            raise FirebaseNetworkError("No internet connection.")
        if res.status_code not in (200, 201):
            raise Exception(f"Create failed: {res.text}")
        rows = res.json()
        return rows[0] if isinstance(rows, list) and rows else (rows or data)

    def update_document(self, collection: str, doc_id: str, data: dict) -> None:
        """Update specific columns of a row identified by id."""
        url = f"{REST_URL}/{collection}"
        try:
            res = requests.patch(url, headers=self._bearer_headers(),
                                 params={"id": f"eq.{doc_id}"},
                                 json=data, timeout=10)
        except requests.exceptions.ConnectionError:
            raise FirebaseNetworkError("No internet connection.")
        if res.status_code not in (200, 204):
            raise Exception(f"Update failed: {res.text}")

    def delete_document(self, collection: str, doc_id: str) -> None:
        """Delete a row by id."""
        url = f"{REST_URL}/{collection}"
        try:
            res = requests.delete(url, headers=self._bearer_headers(),
                                  params={"id": f"eq.{doc_id}"}, timeout=10)
        except requests.exceptions.ConnectionError:
            raise FirebaseNetworkError("No internet connection.")
        if res.status_code not in (200, 204):
            raise Exception(f"Delete failed: {res.status_code}")

    def query_collection(self, collection: str, field: str,
                         op: str, value: Any) -> List[dict]:
        """
        Query with a filter. op mirrors Firestore operators:
          EQUAL               → eq
          LESS_THAN           → lt
          LESS_THAN_OR_EQUAL  → lte
          GREATER_THAN        → gt
          GREATER_THAN_OR_EQUAL → gte
        """
        op_map = {
            "EQUAL":                   "eq",
            "LESS_THAN":               "lt",
            "LESS_THAN_OR_EQUAL":      "lte",
            "GREATER_THAN":            "gt",
            "GREATER_THAN_OR_EQUAL":   "gte",
            "ARRAY_CONTAINS":          "cs",   # PostgREST contains (arrays)
            # Pass raw postgrest ops directly too
            "eq": "eq", "lt": "lt", "lte": "lte",
            "gt": "gt", "gte": "gte", "cs": "cs",
        }
        pg_op = op_map.get(op, "eq")
        url = f"{REST_URL}/{collection}"
        try:
            res = requests.get(url, headers=self._bearer_headers(),
                               params={field: f"{pg_op}.{value}"}, timeout=10)
        except requests.exceptions.ConnectionError:
            raise FirebaseNetworkError("No internet connection.")
        if res.status_code != 200:
            return []
        return res.json()

    # ── Convenience helpers (same signatures as firebase_client) ──────────────

    def update_status(self, sr_id: str, status: str) -> None:
        self.update_document("service_requests", sr_id, {
            "status":     status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    def get_my_srs(self, uid: str) -> List[dict]:
        """Return SRs where assigned_to OR created_by matches uid."""
        assigned = self.query_collection("service_requests", "assigned_to", "EQUAL", uid)
        created  = self.query_collection("service_requests", "created_by",  "EQUAL", uid)
        # Merge, deduplicate by id
        seen = set()
        result = []
        for sr in assigned + created:
            if sr.get("id") not in seen:
                seen.add(sr.get("id"))
                result.append(sr)
        return result


# ── Singleton — same name as before so all imports work unchanged ──────────────
firebase = SupabaseClient()
