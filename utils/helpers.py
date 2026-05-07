# utils/helpers.py
"""Shared helpers: formatting, validation, dynamic stylesheet builder."""

import re
from datetime import datetime, timezone
from typing import Optional, Tuple


# ── Formatting ────────────────────────────────────────────────────────────────

def format_datetime(ts: Optional[str]) -> str:
    if not ts:
        return "—"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%d %b %Y, %I:%M %p")
    except Exception:
        return ts[:19] if len(ts) >= 19 else ts


def format_date(ts: Optional[str]) -> str:
    if not ts:
        return "—"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y")
    except Exception:
        return ts[:10]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def status_color(status: str) -> str:
    return {
        "open":        "#3B82F6",
        "in_progress": "#F59E0B",
        "completed":   "#10B981",
        "closed":      "#6B7280",
        "pending":     "#8B5CF6",
    }.get((status or "").lower(), "#6B7280")


def priority_color(priority: str) -> str:
    return {
        "low":    "#10B981",
        "medium": "#F59E0B",
        "high":   "#EF4444",
    }.get((priority or "").lower(), "#6B7280")


def role_badge_color(role: str) -> str:
    colors = {
        "admin":     "#EF4444",
        "manager":   "#8B5CF6",
        "technical": "#06B6D4",
    }
    return colors.get((role or "").lower(), "#64748B")


def availability_color(active_count: int) -> Tuple[str, str]:
    """Returns (hex_color, label) based on active SR count."""
    if active_count == 0:
        return "#10B981", "🟢 Available"
    if active_count <= 2:
        return "#F59E0B", "🟡 Moderate"
    return "#EF4444", "🔴 Busy"


def truncate(text: str, max_len: int = 60) -> str:
    if not text:
        return ""
    return text if len(text) <= max_len else text[: max_len - 3] + "..."


def days_since(ts: Optional[str]) -> Optional[int]:
    if not ts:
        return None
    try:
        dt  = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return (now - dt).days
    except Exception:
        return None


# ── Validation ────────────────────────────────────────────────────────────────

def validate_email(email: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
                         email.strip()))


def validate_password(pwd: str) -> Tuple[bool, str]:
    if len(pwd) < 6:
        return False, "Password must be at least 6 characters."
    return True, ""


def validate_required(value: str, field: str = "Field") -> Tuple[bool, str]:
    if not value or not value.strip():
        return False, f"{field} is required."
    return True, ""


def validate_time(t: str) -> bool:
    return bool(re.match(r"^([01]\d|2[0-3]):[0-5]\d$", t.strip()))


# ── Dynamic stylesheet ────────────────────────────────────────────────────────

def build_stylesheet(primary: str = "#3B82F6") -> str:
    """
    Build the app-wide QSS stylesheet.
    primary — hex colour used for buttons, active sidebar items, focus rings.
    """
    # Derive a darker shade for hover states
    def darken(hex_color: str, factor: float = 0.85) -> str:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return "#{:02X}{:02X}{:02X}".format(
            int(r * factor), int(g * factor), int(b * factor))

    dark = darken(primary)

    return f"""
QMainWindow, QDialog {{
    background-color: #F1F5F9;
}}
QWidget {{
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
    color: #1E293B;
}}

/* ── Sidebar ── */
#sidebar {{
    background-color: #1E293B;
}}
#sidebar_nav {{
    background: transparent;
    color: #CBD5E1;
    border: none;
    text-align: left;
    padding: 10px 20px;
    font-size: 13px;
    border-radius: 6px;
    margin: 2px 8px;
}}
#sidebar_nav:hover   {{ background: #334155; color: #F1F5F9; }}
#sidebar_nav:checked {{ background: {primary}; color: white; font-weight: bold; }}

/* ── Buttons ── */
QPushButton#btn_primary {{
    background: {primary}; color: white;
    border: none; border-radius: 6px;
    padding: 8px 20px; font-weight: bold;
}}
QPushButton#btn_primary:hover    {{ background: {dark}; }}
QPushButton#btn_primary:disabled {{ background: #93C5FD; }}

QPushButton#btn_secondary {{
    background: #E2E8F0; color: #475569;
    border: none; border-radius: 6px;
    padding: 8px 20px; font-weight: bold;
}}
QPushButton#btn_secondary:hover {{ background: #CBD5E1; }}

QPushButton#btn_success {{
    background: #10B981; color: white;
    border: none; border-radius: 6px;
    padding: 8px 20px; font-weight: bold;
}}
QPushButton#btn_success:hover {{ background: #059669; }}

QPushButton#btn_danger {{
    background: #EF4444; color: white;
    border: none; border-radius: 6px;
    padding: 8px 20px; font-weight: bold;
}}
QPushButton#btn_danger:hover {{ background: #DC2626; }}

QPushButton#btn_warning {{
    background: #F59E0B; color: white;
    border: none; border-radius: 6px;
    padding: 8px 20px; font-weight: bold;
}}
QPushButton#btn_warning:hover {{ background: #D97706; }}

/* ── Inputs ── */
QLineEdit, QTextEdit, QComboBox, QSpinBox {{
    background: white;
    border: 1.5px solid #CBD5E1;
    border-radius: 6px;
    padding: 7px 10px;
    color: #1E293B;
}}
QLineEdit:focus, QTextEdit:focus,
QComboBox:focus, QSpinBox:focus {{
    border-color: {primary};
}}
QComboBox::drop-down {{ border: none; padding-right: 8px; }}

/* ── Table ── */
QTableWidget {{
    background: white;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    gridline-color: #F1F5F9;
    selection-background-color: #EFF6FF;
    selection-color: #1E293B;
    alternate-background-color: #F8FAFC;
}}
QTableWidget::item {{
    padding: 8px 12px;
    border-bottom: 1px solid #F1F5F9;
}}
QHeaderView::section {{
    background: #F8FAFC;
    color: #64748B;
    font-weight: bold;
    font-size: 12px;
    padding: 10px 12px;
    border: none;
    border-bottom: 2px solid #E2E8F0;
}}

/* ── Scrollbar ── */
QScrollBar:vertical {{
    background: #F1F5F9; width: 8px; border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: #CBD5E1; border-radius: 4px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: #94A3B8; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

/* ── Labels ── */
QLabel#section_title {{ font-size: 18px; font-weight: bold; color: #0F172A; }}
QLabel#error_label   {{ color: #EF4444; font-size: 12px; }}
QLabel#info_label    {{ color: #64748B;  font-size: 12px; }}
QLabel#badge         {{ border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: bold; }}

/* ── Cards ── */
QFrame#stat_card {{
    background: white; border-radius: 10px; border: 1px solid #E2E8F0;
}}
QFrame#login_card {{
    background: white; border-radius: 14px; border: 1px solid #E2E8F0;
}}
QFrame#pipeline_step {{
    background: white; border-radius: 8px;
    border: 1.5px solid #E2E8F0;
}}
QFrame#pipeline_step_active {{
    background: #EFF6FF; border-radius: 8px;
    border: 2px solid {primary};
}}
QFrame#pipeline_step_done {{
    background: #F0FDF4; border-radius: 8px;
    border: 1.5px solid #10B981;
}}

/* ── GroupBox ── */
QGroupBox {{
    border: 1.5px solid #E2E8F0; border-radius: 8px;
    margin-top: 12px; padding-top: 8px;
    font-weight: bold; color: #475569;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 12px; padding: 0 6px;
}}

/* ── Tab bar (used in stats) ── */
QTabWidget::pane {{
    border: 1px solid #E2E8F0; border-radius: 8px; background: white;
}}
QTabBar::tab {{
    background: #F1F5F9; color: #64748B;
    padding: 8px 20px; border-radius: 6px; margin-right: 4px;
    font-weight: bold; font-size: 12px;
}}
QTabBar::tab:selected {{ background: {primary}; color: white; }}
QTabBar::tab:hover    {{ background: #E2E8F0; }}
"""


# Default stylesheet (can be replaced at runtime)
APP_STYLE = build_stylesheet()
