# services/whatsapp_service.py
"""
WhatsApp messaging.
Mode "qr"   → uses embedded WhatsApp Web (QWebEngineView) — user scans QR once.
Mode "meta" → uses Meta Cloud API (company number).
Mode is set in Admin Settings → global_config.whatsapp_mode
"""

import os
import threading
from collections import Counter
from typing import Optional


# ── Meta Cloud API sender ─────────────────────────────────────────────────────

def _send_via_meta(to_number: str, message: str) -> None:
    import requests
    from services.config_service import global_config
    cfg          = global_config.get()
    phone_id     = cfg.get("meta_phone_id", "").strip()
    access_token = cfg.get("meta_access_token", "").strip()

    if not phone_id or not access_token:
        raise RuntimeError(
            "Meta Cloud API is not configured.\n"
            "Set Phone Number ID and Access Token in Admin Settings."
        )

    to = to_number.lstrip("+").replace(" ", "")
    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message},
    }
    resp = requests.post(
        url, json=payload,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"Meta API error ({resp.status_code}): {resp.text}")


# ── QR / WhatsApp Web sender ──────────────────────────────────────────────────
# This is handled by the QR widget in ui/whatsapp_qr_widget.py.
# Messages are queued here and the widget's JS bridge picks them up.

_qr_message_queue: list = []
_qr_lock = threading.Lock()
_qr_send_callback = None   # set by the QR widget once connected


def register_qr_callback(fn) -> None:
    """Called by WhatsAppQRWidget when it's ready to send."""
    global _qr_send_callback
    _qr_send_callback = fn


def _send_via_qr(to_number: str, message: str) -> None:
    if _qr_send_callback is None:
        raise RuntimeError(
            "WhatsApp QR session is not active.\n"
            "Open Admin → WhatsApp Settings and scan the QR code."
        )
    _qr_send_callback(to_number, message)


# ── Public API ────────────────────────────────────────────────────────────────

def send_whatsapp_message(to_number: str, message: str) -> None:
    from services.config_service import global_config
    mode = global_config.get_val("whatsapp_mode", "qr")
    if mode == "meta":
        _send_via_meta(to_number, message)
    else:
        _send_via_qr(to_number, message)


def broadcast_message(message: str, roles: Optional[list] = None) -> None:
    """
    Send message to all users whose role is in `roles`.
    If roles is None, sends to admins and managers.
    Runs in background thread — non-blocking.
    """
    def _do():
        try:
            from db import storage
            users = storage.get_collection("users")
            target_roles = roles or ["admin", "manager"]
            for u in users:
                if u.get("role") in target_roles:
                    num = u.get("whatsapp_number", "").strip()
                    if num:
                        try:
                            send_whatsapp_message(num, message)
                        except Exception:
                            pass
        except Exception:
            pass
    threading.Thread(target=_do, daemon=True).start()


def notify_sr_event(event: str, sr: dict, extra: str = "") -> None:
    """
    Send a contextual notification for an SR event.
    event: "created" | "assigned" | "step_done" | "closed"
    """
    from services.config_service import global_config
    cfg = global_config.get()

    if cfg.get(f"notify_{event}", "false") != "true":
        return

    company = cfg.get("company_name", "SR Manager")
    title   = sr.get("title", "SR")
    status  = sr.get("status", "").replace("_", " ").title()

    messages = {
        "sr_created":  f"📋 [{company}] New SR created: '{title}'",
        "sr_assigned": f"📌 [{company}] SR assigned to you: '{title}'",
        "step_done":   f"✅ [{company}] Step completed on SR: '{title}'. {extra}",
        "sr_closed":   f"🔒 [{company}] SR closed: '{title}'",
    }
    msg = messages.get(event, f"[{company}] SR update: {title}")

    # Notify the assigned user + managers
    def _do():
        try:
            from db import storage
            users    = storage.get_collection("users")
            user_map = {u.get("uid", u.get("id", "")): u for u in users}

            targets = set()
            assigned_uid = sr.get("assigned_to", "")
            if assigned_uid:
                targets.add(assigned_uid)
            for u in users:
                if u.get("role") in ("admin", "manager"):
                    targets.add(u.get("uid", u.get("id", "")))

            for uid in targets:
                user = user_map.get(uid, {})
                num  = user.get("whatsapp_number", "").strip()
                if num:
                    try:
                        send_whatsapp_message(num, msg)
                    except Exception:
                        pass
        except Exception:
            pass

    threading.Thread(target=_do, daemon=True).start()


def send_daily_report() -> None:
    from db import storage
    from services.config_service import global_config
    cfg    = global_config.get()
    srs    = storage.get_collection("service_requests")
    counts = Counter(sr.get("status", "unknown") for sr in srs)
    lines  = [f"  • {s.replace('_',' ').title()}: {c}" for s, c in sorted(counts.items())]
    report = "\n".join(lines) or "  No service requests found."

    from datetime import datetime
    date_str = datetime.now().strftime("%d %b %Y")
    full     = f"Date: {date_str}\nTotal: {len(srs)}\n\n{report}"

    template = cfg.get("whatsapp_template", "{company_name} Daily SR Report\n{report}")
    msg      = template.format(company_name=cfg.get("company_name", "SR Manager"), report=full)

    broadcast_message(msg, roles=["admin", "manager"])
