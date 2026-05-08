# utils/helpers.py
"""
Shared helpers — every function used anywhere in the codebase lives here.

Functions:
  utc_now_iso()             — current UTC time as ISO string
  format_datetime(s)        — pretty-print ISO datetime
  validate_email(s)         — basic email check, returns bool
  validate_password(s)      — password policy check, returns (bool, msg)
  validate_time(s)          — HH:MM format check, returns bool
  validate_required(v, f)   — non-empty check, returns (bool, msg)
  truncate(s, n)            — shorten string with ellipsis
  days_since(iso)           — integer days since an ISO datetime
  status_color(s)           — hex colour for SR status string
  priority_color(s)         — hex colour for priority string
  role_badge_color(s)       — hex colour for role string
  availability_color(n)     — (hex, label) for active-SR count
  generate_sr_number(p,n,s) — build SR number from pattern
  next_sr_number()          — generate + auto-increment counter
  build_stylesheet(primary) — full app-wide QSS string
"""

import re
from datetime import datetime, timezone
from typing import Tuple


# ── Time helpers ──────────────────────────────────────────────────────────────

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def format_datetime(iso_str: str | None) -> str:
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y  %H:%M")
    except Exception:
        return iso_str[:16] if iso_str else "—"


def days_since(iso_str: str | None) -> int:
    """Return integer days elapsed since an ISO datetime string. Returns 0 on error."""
    if not iso_str:
        return 0
    try:
        dt  = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, (now - dt).days)
    except Exception:
        return 0


# ── Validation helpers ────────────────────────────────────────────────────────

def validate_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", (email or "").strip()))


def validate_password(password: str) -> Tuple[bool, str]:
    password = password or ""
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return False, "Password must include at least one letter and one number."
    return True, ""


def validate_time(time_str: str) -> bool:
    """Return True if time_str is HH:MM format (00:00 – 23:59)."""
    try:
        h, m = time_str.strip().split(":")
        return 0 <= int(h) <= 23 and 0 <= int(m) <= 59
    except Exception:
        return False


def validate_required(value: str, field_name: str = "Field") -> Tuple[bool, str]:
    """Return (True, '') if value is non-empty, else (False, error message)."""
    if value and str(value).strip():
        return True, ""
    return False, f"{field_name} is required."


# ── String helpers ────────────────────────────────────────────────────────────

def truncate(text: str | None, max_len: int = 40) -> str:
    """Shorten text to max_len characters, appending '…' if trimmed."""
    if not text:
        return "—"
    s = str(text)
    return s if len(s) <= max_len else s[:max_len - 1] + "…"


# ── Colour helpers ────────────────────────────────────────────────────────────

def status_color(status: str) -> str:
    return {
        "open":           "#3B82F6",
        "pending":        "#F59E0B",
        "assigned":       "#8B5CF6",
        "in progress":    "#06B6D4",
        "in_progress":    "#06B6D4",
        "waiting":        "#F97316",
        "waiting approval": "#F97316",
        "waiting_approval": "#F97316",
        "completed":      "#10B981",
        "closed":         "#6B7280",
        "escalated":      "#EF4444",
        "cancelled":      "#9CA3AF",
        "reopened":       "#F59E0B",
    }.get((status or "").lower().strip(), "#64748B")


def priority_color(priority: str) -> str:
    return {
        "low":      "#10B981",
        "medium":   "#F59E0B",
        "high":     "#EF4444",
        "critical": "#7C3AED",
    }.get((priority or "").lower(), "#64748B")


def role_badge_color(role: str) -> str:
    return {
        "master_admin": "#DC2626",
        "admin":        "#3B82F6",
        "manager":      "#8B5CF6",
        "technical":    "#10B981",
        "viewer":       "#6B7280",
    }.get((role or "").lower(), "#64748B")


def availability_color(active_count: int) -> Tuple[str, str]:
    """Return (hex_colour, label) based on how many active SRs a user has."""
    if active_count == 0:
        return "#10B981", "Available"
    elif active_count <= 3:
        return "#F59E0B", "Busy"
    else:
        return "#EF4444", "Overloaded"


# ── SR Number helpers ─────────────────────────────────────────────────────────

def generate_sr_number(pattern: str, counter: int, suffix: str = "") -> str:
    """
    Build an SR number from a pattern string.

    Pattern tokens:
      DD    — day   (2 digits, zero-padded)
      MM    — month (2 digits, zero-padded)
      YY    — year  (2 digits)
      YYYY  — year  (4 digits)
      {N…}  — counter, zero-padded to the number of N characters

    Examples (counter=5, date=01 May 2024):
      "SR{NNNN}"           → "SR0005"
      "DDMMYYSR{NNNN}"     → "010524SR0005"
      "{NNNN}SRDDMMYY"     → "0005SR010524"

    suffix is always appended at the very end.
    """
    import re as _re
    now    = datetime.now()
    result = str(pattern)

    # Date substitutions (order matters — YYYY before YY)
    result = result.replace("YYYY", now.strftime("%Y"))
    result = result.replace("DD",   now.strftime("%d"))
    result = result.replace("MM",   now.strftime("%m"))
    result = result.replace("YY",   now.strftime("%y"))

    # Counter token {N+}
    m = _re.search(r'\{(N+)\}', result)
    if m:
        width  = len(m.group(1))
        result = result[:m.start()] + str(counter).zfill(width) + result[m.end():]
    else:
        result = result + str(counter).zfill(4)

    if suffix:
        result = result + str(suffix)
    return result


def next_sr_number() -> str:
    """
    Read SR number pattern + counter from global_config,
    generate the next SR number, and increment + save the counter.
    """
    try:
        from services.config_service import global_config
        cfg     = global_config.get()
        pattern = cfg.get("sr_number_pattern", "SR{NNNN}")
        suffix  = cfg.get("sr_number_suffix",  "")
        counter = int(cfg.get("sr_number_counter", "1"))
        num     = generate_sr_number(pattern, counter, suffix)
        global_config.save({**cfg, "sr_number_counter": str(counter + 1)})
        return num
    except Exception:
        import random
        return "SR{}{:04d}".format(
            datetime.now().strftime("%d%m%y"),
            random.randint(1, 9999)
        )


# ── Stylesheet ────────────────────────────────────────────────────────────────

def build_stylesheet(primary: str = "#3B82F6") -> str:
    """
    Full app-wide QSS.

    All foreground colours are EXPLICITLY set — nothing inherits white-on-white.
    Covers: base widgets, sidebar, buttons, inputs, combos, tables, tabs,
            group boxes, checkboxes, scrollbars, dialogs, message boxes, tooltips.
    """
    def darken(hex_color: str, factor: float = 0.85) -> str:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return "#{:02X}{:02X}{:02X}".format(
            int(r * factor), int(g * factor), int(b * factor))

    dark  = darken(primary)
    light = "#EFF6FF"

    return f"""
/* ══════════════════════════════════════════════════════════
   SR Manager Enterprise — Global QSS
   Every widget has an explicit foreground colour.
   Nothing is allowed to be white-on-white.
   ══════════════════════════════════════════════════════════ */

/* ── Base ── */
QMainWindow, QWidget {{
    background-color: #F1F5F9;
    color: #1E293B;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}}
QDialog {{
    background: #FFFFFF;
    color: #1E293B;
}}

/* Force ALL labels to dark text */
QLabel {{
    color: #1E293B;
    background: transparent;
}}

/* ── Sidebar ── */
QWidget#sidebar {{
    background-color: #1E293B;
}}
QPushButton#sidebar_nav {{
    background: transparent;
    color: #CBD5E1;
    border: none;
    text-align: left;
    padding: 10px 20px;
    font-size: 13px;
    border-radius: 6px;
    margin: 2px 8px;
    font-weight: normal;
}}
QPushButton#sidebar_nav:hover   {{ background: #334155; color: #F1F5F9; }}
QPushButton#sidebar_nav:checked {{ background: {primary}; color: #FFFFFF; font-weight: bold; }}

/* ── Buttons — base (un-named buttons get neutral look) ── */
QPushButton {{
    background: #E2E8F0;
    color: #334155;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 7px 18px;
    font-weight: bold;
    font-size: 13px;
}}
QPushButton:hover   {{ background: #CBD5E1; color: #1E293B; }}
QPushButton:pressed {{ background: #94A3B8; color: #1E293B; }}
QPushButton:disabled {{ background: #F1F5F9; color: #94A3B8; border-color: #E2E8F0; }}

QPushButton#btn_primary {{
    background: {primary};
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: bold;
}}
QPushButton#btn_primary:hover    {{ background: {dark};   color: #FFFFFF; }}
QPushButton#btn_primary:pressed  {{ background: {darken(primary, 0.75)}; color: #FFFFFF; }}
QPushButton#btn_primary:disabled {{ background: #93C5FD; color: #FFFFFF; border: none; }}

QPushButton#btn_secondary {{
    background: #FFFFFF;
    color: #334155;
    border: 1.5px solid #CBD5E1;
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: bold;
}}
QPushButton#btn_secondary:hover {{ background: #F1F5F9; color: #1E293B; }}

QPushButton#btn_success {{
    background: #10B981; color: #FFFFFF;
    border: none; border-radius: 6px; padding: 8px 20px; font-weight: bold;
}}
QPushButton#btn_success:hover {{ background: #059669; }}

QPushButton#btn_danger {{
    background: #EF4444; color: #FFFFFF;
    border: none; border-radius: 6px; padding: 8px 20px; font-weight: bold;
}}
QPushButton#btn_danger:hover {{ background: #DC2626; }}

QPushButton#btn_warning {{
    background: #F59E0B; color: #FFFFFF;
    border: none; border-radius: 6px; padding: 8px 20px; font-weight: bold;
}}
QPushButton#btn_warning:hover {{ background: #D97706; }}

/* ── Inputs — always dark text on white/light bg ── */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background: #FFFFFF;
    color: #1E293B;
    border: 1.5px solid #CBD5E1;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    selection-background-color: {light};
    selection-color: #1E293B;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {primary};
    background: #FFFFFF;
}}
QLineEdit:disabled, QTextEdit:disabled {{
    background: #F8FAFC;
    color: #94A3B8;
    border-color: #E2E8F0;
}}
QLineEdit[echoMode="2"] {{   /* password fields */
    letter-spacing: 2px;
}}

/* ── ComboBox ── */
QComboBox {{
    background: #FFFFFF;
    color: #1E293B;
    border: 1.5px solid #CBD5E1;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
}}
QComboBox:focus  {{ border-color: {primary}; }}
QComboBox:disabled {{ background: #F8FAFC; color: #94A3B8; }}
QComboBox::drop-down {{
    border: none;
    padding-right: 10px;
    width: 20px;
}}
QComboBox::down-arrow {{
    image: none;
    width: 0; height: 0;
    border-left:  4px solid transparent;
    border-right: 4px solid transparent;
    border-top:   6px solid #64748B;
}}
QComboBox QAbstractItemView {{
    background: #FFFFFF;
    color: #1E293B;
    border: 1px solid #CBD5E1;
    border-radius: 4px;
    selection-background-color: {light};
    selection-color: #1E293B;
    outline: none;
    padding: 4px;
}}
QComboBox QAbstractItemView::item {{
    padding: 6px 10px;
    min-height: 28px;
    color: #1E293B;
}}
QComboBox QAbstractItemView::item:hover {{
    background: {light};
    color: #1E293B;
}}

/* ── SpinBox ── */
QSpinBox, QDoubleSpinBox {{
    background: #FFFFFF;
    color: #1E293B;
    border: 1.5px solid #CBD5E1;
    border-radius: 6px;
    padding: 6px 10px;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {primary}; }}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: #F1F5F9;
    border: none;
    width: 18px;
}}

/* ── Tables ── */
QTableWidget {{
    background: #FFFFFF;
    color: #1E293B;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    gridline-color: #F1F5F9;
    alternate-background-color: #F8FAFC;
    selection-background-color: {light};
    selection-color: #1E293B;
    outline: none;
}}
QTableWidget::item {{
    padding: 8px 12px;
    color: #1E293B;
    border-bottom: 1px solid #F1F5F9;
}}
QTableWidget::item:selected {{
    background: {light};
    color: #1E293B;
}}
QTableWidget::item:hover {{
    background: #F8FAFC;
}}
QHeaderView::section {{
    background: #F8FAFC;
    color: #374151;
    font-weight: bold;
    font-size: 12px;
    padding: 10px 12px;
    border: none;
    border-bottom: 2px solid #E2E8F0;
    border-right: 1px solid #E2E8F0;
}}
QHeaderView::section:checked {{
    background: {light};
}}

/* ── Tab widget ── */
QTabWidget::pane {{
    border: 1px solid #E2E8F0;
    background: #FFFFFF;
    border-radius: 0 8px 8px 8px;
}}
QTabBar::tab {{
    background: #F1F5F9;
    color: #475569;
    border: 1px solid #E2E8F0;
    border-bottom: none;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: bold;
    min-width: 80px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {primary};
    color: #FFFFFF;
    border-color: {primary};
}}
QTabBar::tab:hover:!selected {{
    background: #E2E8F0;
    color: #1E293B;
}}

/* ── Group boxes ── */
QGroupBox {{
    color: #1E293B;
    font-weight: bold;
    font-size: 13px;
    border: 1.5px solid #CBD5E1;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 8px;
    background: #FFFFFF;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: #1E293B;
    background: #FFFFFF;
}}

/* ── CheckBox & RadioButton ── */
QCheckBox, QRadioButton {{
    color: #1E293B;
    background: transparent;
    spacing: 8px;
    font-size: 13px;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px; height: 16px;
    border: 1.5px solid #CBD5E1;
    border-radius: 4px;
    background: #FFFFFF;
}}
QCheckBox::indicator:checked {{
    background: {primary};
    border-color: {primary};
}}
QRadioButton::indicator {{ border-radius: 8px; }}
QRadioButton::indicator:checked {{
    background: {primary};
    border-color: {primary};
}}

/* ── Scrollbars ── */
QScrollBar:vertical {{
    background: #F1F5F9; width: 8px; border-radius: 4px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #CBD5E1; border-radius: 4px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: #94A3B8; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: #F1F5F9; height: 8px; border-radius: 4px; margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: #CBD5E1; border-radius: 4px; min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Named labels ── */
QLabel#section_title {{
    font-size: 18px; font-weight: bold; color: #0F172A; background: transparent;
}}
QLabel#error_label {{
    color: #EF4444; font-size: 12px;
    background: #FEF2F2; border-radius: 6px; padding: 8px 12px;
}}
QLabel#info_label  {{ color: #64748B; font-size: 12px; background: transparent; }}
QLabel#badge       {{
    border-radius: 4px; padding: 2px 8px;
    font-size: 11px; font-weight: bold;
}}

/* ── Frames / Cards ── */
QFrame#stat_card {{
    background: #FFFFFF;
    border-radius: 10px;
    border: 1px solid #E2E8F0;
}}
QFrame#login_card {{
    background: #FFFFFF;
    border-radius: 16px;
    border: none;
}}
QFrame#content_area {{ background: #FFFFFF; }}

/* ── Progress bar ── */
QProgressBar {{
    background: #E2E8F0;
    border-radius: 4px;
    border: none;
    color: transparent;
    text-align: center;
}}
QProgressBar::chunk {{
    background: {primary};
    border-radius: 4px;
}}

/* ── Tooltips ── */
QToolTip {{
    background: #1E293B;
    color: #F1F5F9;
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}}

/* ── Menu bar / menus ── */
QMenuBar {{
    background: #1E293B;
    color: #CBD5E1;
}}
QMenuBar::item:selected {{ background: #334155; color: #F1F5F9; }}
QMenu {{
    background: #FFFFFF;
    color: #1E293B;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{ padding: 8px 20px; border-radius: 4px; }}
QMenu::item:selected {{ background: {light}; color: #1E293B; }}

/* ── Message boxes ── */
QMessageBox {{
    background: #FFFFFF;
    color: #1E293B;
}}
QMessageBox QLabel {{
    color: #1E293B;
    font-size: 13px;
    background: transparent;
}}
QMessageBox QPushButton {{
    min-width: 80px;
    padding: 6px 16px;
}}

/* ── Dialogs inner widgets ── */
QDialog QLabel  {{ color: #1E293B; background: transparent; }}
QDialog QWidget {{ background: #FFFFFF; color: #1E293B; }}
"""
