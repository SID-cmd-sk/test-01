# ui/sr_settings_tab.py
"""
SR Number Pattern Settings — admin configures auto SR numbering.

Pattern builder:
  DD    = day   MM = month   YY = 2-digit year   YYYY = 4-digit year
  {NNNN} = padded counter (width = number of Ns)

Examples:
  DDMMYYSR{NNNN}     →  010524SR0001
  SR{NNNN}           →  SR0001
  {NNNN}SRDDMMYY     →  0001SR010524
  {NNNN}SRDDMMYYSKS  →  0001SR010524SKS  (with suffix "SKS")

Admin can:
  - Set any pattern
  - Set the starting counter (e.g. 69 → starts at SR0069)
  - Set a suffix appended after the generated number
  - Preview the result live
  - Reset counter to 1
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QSpinBox, QGroupBox, QPushButton, QFrame
)
from PyQt6.QtCore import Qt, pyqtSlot


class SRSettingsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(16)

        # ── SR Number Pattern ─────────────────────────────────────────────────
        grp = QGroupBox("SR Number Pattern")
        grp.setStyleSheet("QGroupBox { font-weight: bold; }")
        f = QFormLayout(grp); f.setSpacing(12)

        # Pattern input
        self.pattern_input = QLineEdit()
        self.pattern_input.setFixedHeight(38)
        self.pattern_input.setPlaceholderText("e.g. DDMMYYSR{NNNN}")
        self.pattern_input.textChanged.connect(self._update_preview)
        f.addRow("Pattern", self.pattern_input)

        # Variables reference
        ref = QLabel(
            "Variables:  DD = day  ·  MM = month  ·  YY = 2-digit year  ·  YYYY = 4-digit year\n"
            "            {NNNN} = counter (width = number of Ns,  e.g. {NNNN}=0001  {NNN}=001)"
        )
        ref.setStyleSheet("font-size: 11px; color: #64748B; background: #F8FAFC; "
                         "border-radius: 6px; padding: 8px 10px;")
        f.addRow("", ref)

        # Starting counter
        self.counter_spin = QSpinBox()
        self.counter_spin.setRange(1, 999999)
        self.counter_spin.setValue(1)
        self.counter_spin.setFixedHeight(38)
        self.counter_spin.setFixedWidth(140)
        self.counter_spin.valueChanged.connect(self._update_preview)
        counter_note = QLabel("  (next SR will use this number)")
        counter_note.setStyleSheet("color: #64748B; font-size: 12px;")
        counter_row = QHBoxLayout()
        counter_row.addWidget(self.counter_spin)
        counter_row.addWidget(counter_note)
        counter_row.addStretch()
        f.addRow("Next Counter", counter_row)

        # Suffix input
        self.suffix_input = QLineEdit()
        self.suffix_input.setFixedHeight(38)
        self.suffix_input.setFixedWidth(200)
        self.suffix_input.setPlaceholderText("e.g. SKS  (leave blank for none)")
        self.suffix_input.textChanged.connect(self._update_preview)
        f.addRow("Suffix (appended at end)", self.suffix_input)

        # Live preview
        preview_frame = QFrame()
        preview_frame.setStyleSheet(
            "background: #EFF6FF; border-radius: 8px; padding: 4px;"
        )
        pf = QHBoxLayout(preview_frame)
        pf.setContentsMargins(12, 8, 12, 8)
        preview_lbl = QLabel("Preview:")
        preview_lbl.setStyleSheet("font-size: 13px; color: #374151; font-weight: bold;")
        self.preview_val = QLabel("SR0001")
        self.preview_val.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #1D4ED8; "
            "font-family: 'Consolas', monospace; letter-spacing: 2px;"
        )
        pf.addWidget(preview_lbl)
        pf.addWidget(self.preview_val)
        pf.addStretch()
        f.addRow("", preview_frame)

        # Examples
        examples = QLabel(
            "Examples:\n"
            "  DDMMYYSR{NNNN}       →   010524SR0001\n"
            "  SR{NNNN}             →   SR0001\n"
            "  {NNNN}SRDDMMYY       →   0001SR010524\n"
            "  DDMMYYSR{NNNN}SKS    →   010524SR0069SKS  (pattern + suffix)"
        )
        examples.setStyleSheet(
            "font-size: 12px; color: #475569; font-family: 'Consolas', monospace; "
            "background: #F8FAFC; border-radius: 6px; padding: 10px 12px;"
        )
        f.addRow("", examples)

        lay.addWidget(grp)

        # ── SR Types management ───────────────────────────────────────────────
        types_grp = QGroupBox("SR Types (comma-separated)")
        types_grp.setStyleSheet("QGroupBox { font-weight: bold; }")
        tf = QFormLayout(types_grp); tf.setSpacing(10)
        self.types_input = QLineEdit()
        self.types_input.setFixedHeight(38)
        self.types_input.setPlaceholderText(
            "Installation, Activation, Complaint, Service, Maintenance, AMC, Demo, Inspection"
        )
        tf.addRow("Available Types", self.types_input)
        types_note = QLabel("Users see these options when creating an SR. Separate with commas.")
        types_note.setStyleSheet("font-size: 11px; color: #64748B;")
        tf.addRow("", types_note)
        lay.addWidget(types_grp)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        reset_btn = QPushButton("↺  Reset Counter to 1")
        reset_btn.setObjectName("btn_secondary")
        reset_btn.setFixedHeight(38)
        reset_btn.clicked.connect(self._reset_counter)

        self.save_btn = QPushButton("💾  Save SR Settings")
        self.save_btn.setObjectName("btn_primary")
        self.save_btn.setFixedHeight(38)
        self.save_btn.setMinimumWidth(180)
        self.save_btn.clicked.connect(self._save)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("font-size: 12px; color: #10B981; font-weight: bold;")

        btn_row.addWidget(reset_btn)
        btn_row.addWidget(self.status_lbl)
        btn_row.addStretch()
        btn_row.addWidget(self.save_btn)
        lay.addLayout(btn_row)
        lay.addStretch()

    def _load(self):
        try:
            from services.config_service import global_config
            cfg = global_config.get()
            self.pattern_input.setText(cfg.get("sr_number_pattern", "SR{NNNN}"))
            self.suffix_input.setText(cfg.get("sr_number_suffix", ""))
            try:
                self.counter_spin.setValue(int(cfg.get("sr_number_counter", "1")))
            except (ValueError, TypeError):
                self.counter_spin.setValue(1)
            from services.config_service import DEFAULT_CONFIG
            default_types = "Installation,Activation,Complaint,Service,Maintenance,AMC,Demo,Inspection,Escalation,Purchase Request,Internal Request,Custom"
            self.types_input.setText(cfg.get("sr_types", default_types))
        except Exception:
            pass
        self._update_preview()

    def _update_preview(self):
        try:
            from utils.helpers import generate_sr_number
            pattern = self.pattern_input.text().strip() or "SR{NNNN}"
            suffix  = self.suffix_input.text().strip()
            counter = self.counter_spin.value()
            preview = generate_sr_number(pattern, counter, suffix)
            self.preview_val.setText(preview)
        except Exception as e:
            self.preview_val.setText(f"Error: {e}")

    def _reset_counter(self):
        self.counter_spin.setValue(1)
        self.status_lbl.setText("Counter reset to 1 — click Save to apply.")
        self.status_lbl.setStyleSheet("font-size: 12px; color: #F59E0B; font-weight: bold;")

    def _save(self):
        try:
            from services.config_service import global_config
            cfg = global_config.get()
            cfg["sr_number_pattern"] = self.pattern_input.text().strip() or "SR{NNNN}"
            cfg["sr_number_suffix"]  = self.suffix_input.text().strip()
            cfg["sr_number_counter"] = str(self.counter_spin.value())
            cfg["sr_types"]          = self.types_input.text().strip()
            global_config.save(cfg)
            self.status_lbl.setText("✅ Saved!")
            self.status_lbl.setStyleSheet("font-size: 12px; color: #10B981; font-weight: bold;")
        except Exception as e:
            self.status_lbl.setText(f"❌ {e}")
            self.status_lbl.setStyleSheet("font-size: 12px; color: #EF4444; font-weight: bold;")
