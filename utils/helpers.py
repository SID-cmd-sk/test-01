# utils/helpers.py
"""Shared helpers: formatting, validation, dynamic stylesheet builder."""

import re
from datetime import datetime, timezone
from typing import Tuple


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


def validate_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))


def validate_password(password: str) -> bool:
    return len(password) >= 8


def status_color(status: str) -> str:
    colors = {
        "open":          "#3B82F6",
        "pending":       "#F59E0B",
        "assigned":      "#8B5CF6",
        "in progress":   "#06B6D4",
        "in_progress":   "#06B6D4",
        "waiting":       "#F97316",
        "completed":     "#10B981",
        "closed":        "#6B7280",
        "escalated":     "#EF4444",
        "cancelled":     "#9CA3AF",
        "reopened":      "#F59E0B",
    }
    return colors.get((status or "").lower(), "#64748B")


def priority_color(priority: str) -> str:
    return {"low": "#10B981", "medium": "#F59E0B", "high": "#EF4444",
            "critical": "#7C3AED"}.get((priority or "").lower(), "#64748B")


def role_badge_color(role: str) -> str:
    colors = {
        "admin":     "#3B82F6",
        "manager":   "#8B5CF6",
        "technical": "#10B981",
        "viewer":    "#6B7280",
    }
    return colors.get((role or "").lower(), "#64748B")


def availability_color(active_count: int) -> Tuple[str, str]:
    if active_count == 0:
        return "#10B981", "Available"
    elif active_count <= 3:
        return "#F59E0B", "Busy"
    else:
        return "#EF4444", "Overloaded"


# ── SR Number Pattern ─────────────────────────────────────────────────────────

def generate_sr_number(pattern: str, counter: int, suffix: str = "") -> str:
    """
    Generate a formatted SR number from a pattern.

    Pattern variables:
        DD    - day (2 digits)
        MM    - month (2 digits)
        YY    - year (2 digits)
        YYYY  - year (4 digits)
        NNNN  - zero-padded counter (width = number of Ns)

    Examples:
        pattern="DDMMYYSR{NNNN}" counter=5  → "010524SR0005"
        pattern="SR{NNNN}"        counter=69 → "SR0069"
        pattern="{NNNN}SRDDMMYY"  counter=1  → "0001SR010524"

    suffix is appended at the end if non-empty.
    """
    now = datetime.now()
    result = pattern
    # Date substitutions
    result = result.replace("YYYY", now.strftime("%Y"))
    result = result.replace("DD",   now.strftime("%d"))
    result = result.replace("MM",   now.strftime("%m"))
    result = result.replace("YY",   now.strftime("%y"))

    # Counter: find {N+} pattern and pad accordingly
    import re as _re
    m = _re.search(r'\{(N+)\}', result)
    if m:
        width = len(m.group(1))
        result = result[:m.start()] + str(counter).zfill(width) + result[m.end():]
    else:
        # fallback: append padded counter
        result = result + str(counter).zfill(4)

    if suffix:
        result = result + suffix
    return result


def next_sr_number() -> str:
    """Read pattern + counter from config, generate number, increment counter."""
    try:
        from services.config_service import global_config
        from db import storage
        cfg     = global_config.get()
        pattern = cfg.get("sr_number_pattern", "SR{NNNN}")
        suffix  = cfg.get("sr_number_suffix",  "")
        counter = int(cfg.get("sr_number_counter", "1"))
        num     = generate_sr_number(pattern, counter, suffix)
        # Save incremented counter
        global_config.save({**cfg, "sr_number_counter": str(counter + 1)})
        return num
    except Exception:
        from datetime import datetime as _dt
        return f"SR{_dt.now().strftime('%d%m%y')}{str(__import__('random').randint(1,9999)).zfill(4)}"


# ── Dynamic stylesheet ────────────────────────────────────────────────────────

def build_stylesheet(primary: str = "#3B82F6") -> str:
    """
    Full app-wide QSS. All text is explicitly dark so nothing is white-on-white.
    Inputs, labels, dialogs, combo boxes — all have enforced contrast.
    """
    def darken(hex_color: str, factor: float = 0.85) -> str:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return "#{:02X}{:02X}{:02X}".format(
            int(r * factor), int(g * factor), int(b * factor))

    dark  = darken(primary)
    light = "#EFF6FF"   # pale blue tint for selected rows

    return f"""
/* ══════════════════════════════════════════════════════
   SR Manager Enterprise — Global Stylesheet
   All foreground colours are explicitly set so nothing
   is ever white-on-white or invisible.
   ══════════════════════════════════════════════════════ */

/* ── Base ── */
QMainWindow, QDialog, QWidget {{
    background-color: #F1F5F9;
    color: #1E293B;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}}

/* Force all plain labels to dark text */
QLabel {{
    color: #1E293B;
    background: transparent;
}}

/* ── Dialogs get white bg with dark text ── */
QDialog {{
    background: #FFFFFF;
    color: #1E293B;
}}
QDialog QLabel {{
    color: #1E293B;
}}
QDialog QLineEdit, QDialog QTextEdit,
QDialog QComboBox, QDialog QSpinBox {{
    background: #FFFFFF;
    color: #1E293B;
    border: 1.5px solid #CBD5E1;
    border-radius: 6px;
    padding: 7px 10px;
}}
QDialog QLineEdit:focus, QDialog QTextEdit:focus,
QDialog QComboBox:focus, QDialog QSpinBox:focus {{
    border-color: {primary};
}}

/* ── Sidebar ── */
#sidebar {{
    background-color: #1E293B;
    color: #CBD5E1;
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
#sidebar_nav:checked {{ background: {primary}; color: #FFFFFF; font-weight: bold; }}

/* ── Buttons ── */
QPushButton {{
    color: #1E293B;
    background: #E2E8F0;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: bold;
}}
QPushButton:hover {{ background: #CBD5E1; }}

QPushButton#btn_primary {{
    background: {primary}; color: #FFFFFF;
    border: none; border-radius: 6px;
    padding: 8px 20px; font-weight: bold;
}}
QPushButton#btn_primary:hover    {{ background: {dark};   color: #FFFFFF; }}
QPushButton#btn_primary:disabled {{ background: #93C5FD; color: #FFFFFF; }}

QPushButton#btn_secondary {{
    background: #E2E8F0; color: #334155;
    border: 1px solid #CBD5E1;
    border-radius: 6px; padding: 8px 20px; font-weight: bold;
}}
QPushButton#btn_secondary:hover {{ background: #CBD5E1; color: #1E293B; }}

QPushButton#btn_success {{
    background: #10B981; color: #FFFFFF;
    border: none; border-radius: 6px;
    padding: 8px 20px; font-weight: bold;
}}
QPushButton#btn_success:hover {{ background: #059669; }}

QPushButton#btn_danger {{
    background: #EF4444; color: #FFFFFF;
    border: none; border-radius: 6px;
    padding: 8px 20px; font-weight: bold;
}}
QPushButton#btn_danger:hover {{ background: #DC2626; }}

QPushButton#btn_warning {{
    background: #F59E0B; color: #FFFFFF;
    border: none; border-radius: 6px;
    padding: 8px 20px; font-weight: bold;
}}
QPushButton#btn_warning:hover {{ background: #D97706; }}

/* ── Inputs — always dark text on white bg ── */
QLineEdit, QTextEdit, QPlainTextEdit,
QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit {{
    background: #FFFFFF;
    color: #1E293B;
    border: 1.5px solid #CBD5E1;
    border-radius: 6px;
    padding: 7px 10px;
}}
QLineEdit:focus, QTextEdit:focus,
QComboBox:focus, QSpinBox:focus {{
    border-color: {primary};
    outline: none;
}}
QLineEdit:disabled, QTextEdit:disabled,
QComboBox:disabled, QSpinBox:disabled {{
    background: #F1F5F9;
    color: #94A3B8;
}}

/* ComboBox dropdown list — dark text */
QComboBox QAbstractItemView {{
    background: #FFFFFF;
    color: #1E293B;
    selection-background-color: {light};
    selection-color: #1E293B;
    border: 1px solid #CBD5E1;
    outline: none;
}}
QComboBox::drop-down {{ border: none; padding-right: 8px; }}
QComboBox::down-arrow {{
    width: 12px; height: 12px;
}}

/* ── Tables ── */
QTableWidget {{
    background: #FFFFFF;
    color: #1E293B;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    gridline-color: #F1F5F9;
    selection-background-color: {light};
    selection-color: #1E293B;
    alternate-background-color: #F8FAFC;
}}
QTableWidget::item {{
    padding: 8px 12px;
    border-bottom: 1px solid #F1F5F9;
    color: #1E293B;
}}
QTableWidget::item:selected {{
    background: {light};
    color: #1E293B;
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

/* ── Tabs ── */
QTabWidget::pane {{
    border: 1px solid #E2E8F0;
    background: #FFFFFF;
    border-radius: 8px;
}}
QTabBar::tab {{
    background: #F1F5F9;
    color: #475569;
    border: 1px solid #E2E8F0;
    border-bottom: none;
    padding: 8px 18px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: bold;
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
    border: 1.5px solid #CBD5E1;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 10px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #1E293B;
    background: #F1F5F9;
}}

/* ── CheckBox & RadioButton ── */
QCheckBox, QRadioButton {{
    color: #1E293B;
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1.5px solid #CBD5E1;
    border-radius: 4px;
    background: #FFFFFF;
}}
QCheckBox::indicator:checked {{
    background: {primary};
    border-color: {primary};
}}

/* ── Scrollbars ── */
QScrollBar:vertical {{
    background: #F1F5F9; width: 8px; border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: #CBD5E1; border-radius: 4px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: #94A3B8; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: #F1F5F9; height: 8px; border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: #CBD5E1; border-radius: 4px; min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Named labels ── */
QLabel#section_title {{
    font-size: 18px; font-weight: bold; color: #0F172A;
}}
QLabel#error_label {{
    color: #EF4444; font-size: 12px;
    background: #FEF2F2; border-radius: 6px; padding: 6px 10px;
}}
QLabel#info_label  {{ color: #64748B; font-size: 12px; }}

/* ── Frames / Cards ── */
QFrame#stat_card {{
    background: #FFFFFF; border-radius: 10px; border: 1px solid #E2E8F0;
}}
QFrame#login_card {{
    background: #FFFFFF; border-radius: 14px; border: 1px solid #E2E8F0;
    padding: 10px;
}}
QFrame#content_area {{
    background: #FFFFFF;
}}

/* ── Tooltips ── */
QToolTip {{
    background: #1E293B; color: #F1F5F9;
    border: none; border-radius: 4px; padding: 4px 8px;
}}

/* ── Message boxes ── */
QMessageBox {{
    background: #FFFFFF;
    color: #1E293B;
}}
QMessageBox QLabel {{
    color: #1E293B;
}}
"""
