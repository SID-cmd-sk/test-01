# firebase_client.py
"""
Firebase REST API client.
Handles Auth, Firestore CRUD, token refresh, and all collection helpers.
"""

import requests
import time
import threading
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

# ── CONFIG ────────────────────────────────────────────────────────────────────
FIREBASE_API_KEY    = "AIzaSyA0zVKt6GgirSbH_gAWIoAffyu47VXEuDI"
FIREBASE_PROJECT_ID = "srlog-7e429"

AUTH_BASE      = "https://identitytoolkit.googleapis.com/v1"
FIRESTORE_BASE = (
    f"https://firestore.googleapis.com/v1/projects/"
    f"{FIREBASE_PROJECT_ID}/databases/(default)/documents"
)


# ── ERRORS ────────────────────────────────────────────────────────────────────
class FirebaseAuthError(Exception):
    pass

class FirebaseNetworkError(Exception):
    pass


# ── CLIENT ────────────────────────────────────────────────────────────────────
class FirebaseClient:
    def __init__(self):
        self._id_token:      Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expiry:  float         = 0
        self._uid:           Optional[str] = None
        self._lock = threading.Lock()

    # ── Auth ──────────────────────────────────────────────────────────────────

    def login(self, email: str, password: str) -> Dict:
        url = f"{AUTH_BASE}/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
        try:
            res = requests.post(url, json={
                "email": email, "password": password, "returnSecureToken": True
            }, timeout=10)
        except requests.exceptions.ConnectionError:
            raise FirebaseNetworkError("No internet connection.")

        data = res.json()
        if res.status_code != 200:
            msg = data.get("error", {}).get("message", "")
            if msg in ("EMAIL_NOT_FOUND", "INVALID_LOGIN_CREDENTIALS", "INVALID_PASSWORD"):
                raise FirebaseAuthError("Invalid email or password.")
            raise FirebaseAuthError(msg or "Login failed.")

        with self._lock:
            self._id_token      = data["idToken"]
            self._refresh_token = data["refreshToken"]
            self._token_expiry  = time.time() + int(data["expiresIn"]) - 60
            self._uid           = data["localId"]

        return {"uid": self._uid, "email": data["email"]}

    def logout(self):
        with self._lock:
            self._id_token = self._refresh_token = self._uid = None
            self._token_expiry = 0

    def create_user(self, email: str, password: str) -> str:
        """Create Firebase Auth user; returns UID."""
        url = f"{AUTH_BASE}/accounts:signUp?key={FIREBASE_API_KEY}"
        try:
            res = requests.post(url, json={
                "email": email, "password": password, "returnSecureToken": True
            }, timeout=10)
        except requests.exceptions.ConnectionError:
            raise FirebaseNetworkError("No internet connection.")

        data = res.json()
        if res.status_code != 200:
            msg = data.get("error", {}).get("message", "")
            if "EMAIL_EXISTS" in msg:
                raise FirebaseAuthError("An account with this email already exists.")
            raise FirebaseAuthError(msg or "Failed to create user.")
        return data["localId"]

    def _refresh_if_needed(self):
        with self._lock:
            if not self._refresh_token or time.time() < self._token_expiry:
                return
            rt = self._refresh_token
        try:
            res = requests.post(
                f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}",
                json={"grant_type": "refresh_token", "refresh_token": rt}, timeout=10
            )
            if res.status_code == 200:
                d = res.json()
                with self._lock:
                    self._id_token     = d["id_token"]
                    self._token_expiry = time.time() + int(d["expires_in"]) - 60
        except Exception:
            pass

    def _headers(self) -> Dict:
        self._refresh_if_needed()
        with self._lock:
            token = self._id_token
        if not token:
            raise FirebaseAuthError("Not logged in.")
        return {"Authorization": f"Bearer {token}"}

    @property
    def uid(self) -> Optional[str]:
        return self._uid

    # ── Firestore serialization ───────────────────────────────────────────────

    def _to_fs(self, data: dict) -> dict:
        fields = {}
        for k, v in data.items():
            if v is None:
                fields[k] = {"nullValue": None}
            elif isinstance(v, bool):
                fields[k] = {"booleanValue": v}
            elif isinstance(v, int):
                fields[k] = {"integerValue": str(v)}
            elif isinstance(v, float):
                fields[k] = {"doubleValue": v}
            elif isinstance(v, list):
                fields[k] = {"arrayValue": {"values": [
                    self._val_to_fs(i) for i in v
                ]}}
            elif isinstance(v, dict):
                fields[k] = {"mapValue": {"fields": self._to_fs(v)}}
            else:
                fields[k] = {"stringValue": str(v)}
        return fields

    def _val_to_fs(self, v: Any) -> dict:
        if v is None:        return {"nullValue": None}
        if isinstance(v, bool):  return {"booleanValue": v}
        if isinstance(v, int):   return {"integerValue": str(v)}
        if isinstance(v, float): return {"doubleValue": v}
        if isinstance(v, dict):  return {"mapValue": {"fields": self._to_fs(v)}}
        if isinstance(v, list):  return {"arrayValue": {"values": [self._val_to_fs(i) for i in v]}}
        return {"stringValue": str(v)}

    def _from_fs(self, doc: dict) -> dict:
        result = {}
        for k, v in doc.get("fields", {}).items():
            result[k] = self._parse_val(v)
        result["id"] = doc["name"].split("/")[-1]
        return result

    def _parse_val(self, v: dict) -> Any:
        if "stringValue"    in v: return v["stringValue"]
        if "integerValue"   in v: return int(v["integerValue"])
        if "doubleValue"    in v: return float(v["doubleValue"])
        if "booleanValue"   in v: return v["booleanValue"]
        if "nullValue"      in v: return None
        if "timestampValue" in v: return v["timestampValue"]
        if "arrayValue"     in v:
            return [self._parse_val(i) for i in v["arrayValue"].get("values", [])]
        if "mapValue"       in v:
            return {k2: self._parse_val(v2) for k2, v2 in v["mapValue"].get("fields", {}).items()}
        return str(v)

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def get_document(self, collection: str, doc_id: str) -> Optional[dict]:
        url = f"{FIRESTORE_BASE}/{collection}/{doc_id}"
        try:
            res = requests.get(url, headers=self._headers(), timeout=10)
        except requests.exceptions.ConnectionError:
            raise FirebaseNetworkError("No internet connection.")
        if res.status_code == 404:
            return None
        if res.status_code != 200:
            raise Exception(f"Fetch failed: {res.status_code}")
        return self._from_fs(res.json())

    def get_collection(self, collection: str) -> List[dict]:
        url = f"{FIRESTORE_BASE}/{collection}"
        try:
            res = requests.get(url, headers=self._headers(), timeout=10)
        except requests.exceptions.ConnectionError:
            raise FirebaseNetworkError("No internet connection.")
        if res.status_code != 200:
            return []
        return [self._from_fs(d) for d in res.json().get("documents", [])]

    def create_document(self, collection: str, data: dict,
                        doc_id: Optional[str] = None) -> dict:
        url = f"{FIRESTORE_BASE}/{collection}"
        if doc_id:
            url += f"?documentId={doc_id}"
        try:
            res = requests.post(url, headers=self._headers(),
                                json={"fields": self._to_fs(data)}, timeout=10)
        except requests.exceptions.ConnectionError:
            raise FirebaseNetworkError("No internet connection.")
        if res.status_code not in (200, 201):
            raise Exception(f"Create failed: {res.text}")
        return self._from_fs(res.json())

    def update_document(self, collection: str, doc_id: str, data: dict) -> None:
        mask = "&".join(f"updateMask.fieldPaths={k}" for k in data)
        url  = f"{FIRESTORE_BASE}/{collection}/{doc_id}?{mask}"
        try:
            res = requests.patch(url, headers=self._headers(),
                                 json={"fields": self._to_fs(data)}, timeout=10)
        except requests.exceptions.ConnectionError:
            raise FirebaseNetworkError("No internet connection.")
        if res.status_code != 200:
            raise Exception(f"Update failed: {res.text}")

    def delete_document(self, collection: str, doc_id: str) -> None:
        url = f"{FIRESTORE_BASE}/{collection}/{doc_id}"
        try:
            res = requests.delete(url, headers=self._headers(), timeout=10)
        except requests.exceptions.ConnectionError:
            raise FirebaseNetworkError("No internet connection.")
        if res.status_code not in (200, 204):
            raise Exception(f"Delete failed: {res.status_code}")

    def query_collection(self, collection: str, field: str,
                         op: str, value: Any) -> List[dict]:
        """Simple field equality / comparison query."""
        url     = f"{FIRESTORE_BASE}:runQuery"
        fs_val  = self._val_to_fs(value)
        payload = {"structuredQuery": {
            "from": [{"collectionId": collection}],
            "where": {"fieldFilter": {
                "field": {"fieldPath": field}, "op": op, "value": fs_val
            }}
        }}
        try:
            res = requests.post(url, headers=self._headers(),
                                json=payload, timeout=10)
        except requests.exceptions.ConnectionError:
            raise FirebaseNetworkError("No internet connection.")
        return [self._from_fs(item["document"])
                for item in res.json() if "document" in item]

    # ── Convenience helpers ───────────────────────────────────────────────────

    def update_status(self, sr_id: str, status: str) -> None:
        self.update_document("service_requests", sr_id, {
            "status":     status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    def get_my_srs(self, uid: str) -> List[dict]:
        return [sr for sr in self.get_collection("service_requests")
                if sr.get("assigned_to") == uid or sr.get("created_by") == uid]


# Singleton
firebase = FirebaseClient()
