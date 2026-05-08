# services/automation_engine.py
"""
Automation Engine — IF/THEN rule processing.

Rules are stored in local_storage under "automation_rules".
Each rule has:
  trigger:    { event: "sr_created" | "sr_assigned" | "step_done" | "sr_overdue" | ... }
  conditions: [ { field: "sr_type", op: "eq", value: "Installation" }, ... ]
  actions:    [ { type: "send_email" | "send_whatsapp" | "notify" | "assign" | ... }, ... ]

The engine is triggered by calling fire_event() from pipeline_service,
sr_service, or any other service that generates events.

Examples:
  IF sr_type == "Installation" AND status == "Completed"
    → send_email to customer
    → notify manager

  IF created_at > 48h AND status == "Pending"
    → assign to manager
    → send_whatsapp escalation
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List


# ── Condition evaluator ───────────────────────────────────────────────────────

def _evaluate_condition(cond: dict, context: dict) -> bool:
    """Evaluate a single IF condition against the event context."""
    field = cond.get("field", "")
    op    = cond.get("op", "eq")
    value = cond.get("value", "")

    actual = context.get(field, "")
    if actual is None:
        actual = ""

    try:
        if op == "eq":
            return str(actual).lower() == str(value).lower()
        elif op == "neq":
            return str(actual).lower() != str(value).lower()
        elif op == "contains":
            return str(value).lower() in str(actual).lower()
        elif op == "gt":
            return float(actual) > float(value)
        elif op == "lt":
            return float(actual) < float(value)
        elif op == "in":
            options = [v.strip().lower() for v in str(value).split(",")]
            return str(actual).lower() in options
        elif op == "is_overdue":
            # Special op: check if SR created_at is older than N days
            days = int(value) if str(value).isdigit() else 3
            created = context.get("created_at", "")
            if not created:
                return False
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            age = datetime.now(timezone.utc) - created_dt
            return age > timedelta(days=days)
        elif op == "is_empty":
            return not str(actual).strip()
        elif op == "not_empty":
            return bool(str(actual).strip())
    except Exception:
        pass
    return False


def _evaluate_all_conditions(conditions: List[dict], context: dict) -> bool:
    """All conditions must be True (AND logic)."""
    if not conditions:
        return True
    return all(_evaluate_condition(c, context) for c in conditions)


# ── Action executor ───────────────────────────────────────────────────────────

def _execute_action(action: dict, context: dict) -> None:
    """Execute a single THEN action."""
    action_type = action.get("type", "")

    try:
        if action_type == "notify":
            _action_notify(action, context)
        elif action_type == "send_email":
            _action_email(action, context)
        elif action_type == "send_whatsapp":
            _action_whatsapp(action, context)
        elif action_type == "assign":
            _action_assign(action, context)
        elif action_type == "update_status":
            _action_update_status(action, context)
        elif action_type == "log":
            _action_log(action, context)
    except Exception as e:
        # Never crash the main app over an automation failure
        _log_automation_error(action_type, str(e), context)


def _resolve_template(template: str, context: dict) -> str:
    """Replace {field} placeholders with context values."""
    result = template
    for key, val in context.items():
        result = result.replace(f"{{{key}}}", str(val or ""))
    return result


def _action_notify(action: dict, context: dict) -> None:
    from services.notification_service import notify, push_in_app
    title   = _resolve_template(action.get("title", "Automation Alert"), context)
    message = _resolve_template(action.get("message", ""), context)
    level   = action.get("level", "info")
    notify(title, message, level)
    push_in_app(title, message, level)


def _action_email(action: dict, context: dict) -> None:
    from services.email_service import send_email
    to      = _resolve_template(action.get("to", context.get("customer_email", "")), context)
    subject = _resolve_template(action.get("subject", "SR Manager Notification"), context)
    body    = _resolve_template(action.get("body", ""), context)
    if to and body:
        send_email(subject, body, to)


def _action_whatsapp(action: dict, context: dict) -> None:
    from services.whatsapp_service import send_whatsapp_message
    to      = _resolve_template(action.get("to", context.get("customer_phone", "")), context)
    message = _resolve_template(action.get("message", ""), context)
    if to and message:
        send_whatsapp_message(to, message)


def _action_assign(action: dict, context: dict) -> None:
    from db import storage
    sr_id   = context.get("id") or context.get("sr_id")
    uid     = action.get("assign_to_uid", "")
    if sr_id and uid:
        storage.update_document("service_requests", sr_id, {
            "assigned_to": uid,
            "updated_at":  datetime.now(timezone.utc).isoformat(),
        })


def _action_update_status(action: dict, context: dict) -> None:
    from db import storage
    sr_id  = context.get("id") or context.get("sr_id")
    status = action.get("status", "")
    if sr_id and status:
        storage.update_document("service_requests", sr_id, {
            "status":     status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })


def _action_log(action: dict, context: dict) -> None:
    from services.audit_service import log_action
    message = _resolve_template(action.get("message", "Automation rule fired."), context)
    log_action("automation", message, context.get("id", ""))


def _log_automation_error(action_type: str, error: str, context: dict) -> None:
    try:
        from services.audit_service import log_action
        log_action(
            "automation_error",
            f"Action '{action_type}' failed: {error}",
            context.get("id", ""),
        )
    except Exception:
        pass


# ── Main public API ───────────────────────────────────────────────────────────

def fire_event(event_name: str, context: dict) -> int:
    """
    Fire a named event and run all matching automation rules.

    Args:
        event_name: e.g. "sr_created", "sr_assigned", "step_done", "sr_overdue"
        context:    dict containing the SR/task/user data for this event

    Returns:
        Number of rules that fired.
    """
    try:
        from services.local_storage_service import local_storage
        rules = local_storage.get_collection("automation_rules")
    except Exception:
        return 0

    fired = 0
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        trigger = rule.get("trigger", {})
        if trigger.get("event") != event_name:
            continue
        conditions = rule.get("conditions", [])
        if not _evaluate_all_conditions(conditions, context):
            continue

        # Run each action in a background thread — never block the caller
        actions = rule.get("actions", [])
        rule_name = rule.get("name", rule.get("id", "rule"))
        for action in actions:
            threading.Thread(
                target=_execute_action,
                args=(action, context),
                daemon=True,
                name=f"automation-{rule_name}",
            ).start()
        fired += 1

    return fired


def check_overdue_srs() -> int:
    """
    Scan all open SRs and fire "sr_overdue" for any that exceed the SLA threshold.
    Called by the daily scheduler.
    Returns number of overdue SRs found.
    """
    try:
        from services.local_storage_service import local_storage
        from services.config_service import global_config
        overdue_days = global_config.overdue_days()

        srs    = local_storage.get_collection("service_requests")
        now    = datetime.now(timezone.utc)
        count  = 0

        for sr in srs:
            if sr.get("status", "").lower() in ("completed", "closed", "cancelled"):
                continue
            created = sr.get("created_at", "")
            if not created:
                continue
            try:
                created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                if (now - created_dt) > timedelta(days=overdue_days):
                    fire_event("sr_overdue", sr)
                    count += 1
            except Exception:
                continue
        return count
    except Exception:
        return 0


# ── Built-in rule templates (used by UI rule builder) ────────────────────────

RULE_TEMPLATES = [
    {
        "name":       "Escalate overdue SRs (2 days)",
        "trigger":    {"event": "sr_overdue"},
        "conditions": [{"field": "created_at", "op": "is_overdue", "value": "2"}],
        "actions": [
            {"type": "notify",  "title": "SR Overdue",
             "message": "SR #{sr_number} — {title} is overdue.", "level": "warning"},
            {"type": "log",     "message": "SR #{sr_number} flagged as overdue."},
        ],
    },
    {
        "name":       "Email customer on completion",
        "trigger":    {"event": "sr_closed"},
        "conditions": [{"field": "customer_email", "op": "not_empty", "value": ""}],
        "actions": [
            {"type": "send_email",
             "to":      "{customer_email}",
             "subject": "Your service request has been resolved",
             "body":    "Dear {customer_name},\n\nYour SR #{sr_number} ({title}) "
                        "has been resolved.\n\nThank you."},
        ],
    },
    {
        "name":       "WhatsApp customer on assignment",
        "trigger":    {"event": "sr_assigned"},
        "conditions": [{"field": "customer_phone", "op": "not_empty", "value": ""}],
        "actions": [
            {"type": "send_whatsapp",
             "to":      "{customer_phone}",
             "message": "Dear {customer_name}, your SR #{sr_number} has been assigned "
                        "and our team will be in touch shortly."},
        ],
    },
    {
        "name":       "Notify on Installation SR created",
        "trigger":    {"event": "sr_created"},
        "conditions": [{"field": "sr_type", "op": "eq", "value": "Installation"}],
        "actions": [
            {"type": "notify", "title": "New Installation SR",
             "message": "SR #{sr_number} — {title} requires scheduling.", "level": "info"},
        ],
    },
]
