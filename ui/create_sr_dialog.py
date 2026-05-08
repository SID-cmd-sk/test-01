# ui/create_sr_dialog.py
"""
Create Service Request Dialog.

Features:
  - Full SR form: title, type, priority, customer info, description, pipeline
  - SR number auto-generated from admin pattern (DDMMYYSR{NNNN} etc.)
  - Admin can configure pattern + starting counter + suffix in SR Settings tab
  - Validation before save
  - Fires automation events on creation
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QTextEdit, QComboBox, QPushButton, QGroupBox, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot


SR_TYPES = [
    "Installation", "Activation", "Complaint", "Service",
    "Maintenance", "AMC", "Demo", "Inspection",
    "Escalation", "Purchase Request", "Internal Request", "Custom",
]

SR_PRIORITIES = ["Low", "Medium", "High", "Critical"]

SR_STATUSES = [
    "Pending", "Assigned", "In Progress", "Waiting Approval",
    "Completed", "Closed", "Escalated", "Cancelled",
]


class CreateSRWorker(QThread):
    done  = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, data: dict):
        super().__init__()
        self.data = data

    def run(self):
        try:
            import uuid
            from db import storage
            from utils.helpers import utc_now_iso, next_sr_number
            from utils.auth import session

            sr_id     = str(uuid.uuid4())
            sr_number = next_sr_number()

            doc = {
                "id":             sr_id,
                "sr_id":          sr_id,
                "sr_number":      sr_number,
                "title":          self.data["title"],
                "sr_type":        self.data["sr_type"],
                "priority":       self.data["priority"],
                "status":         self.data["status"],
                "description":    self.data["description"],
                "customer_name":  self.data["customer_name"],
                "customer_phone": self.data["customer_phone"],
                "customer_email": self.data["customer_email"],
                "customer_address": self.data["customer_address"],
                "assigned_to":    self.data.get("assigned_to", ""),
                "created_by":     session.uid,
                "pipeline_state": {},
                "comments":       [],
                "attachments":    [],
                "created_at":     utc_now_iso(),
                "updated_at":     utc_now_iso(),
                "_dirty":         True,
            }

            storage.create_document("service_requests", doc, doc_id=sr_id)

            # Fire automation
            try:
                from services.automation_engine import fire_event
                fire_event("sr_created", doc)
            except Exception:
                pass

            # Audit
            try:
                from services.audit_service import log_action
                log_action("sr_created", f"SR {sr_number}: {self.data['title']}", sr_id)
            except Exception:
                pass

            # Desktop notification
            try:
                from services.notification_service import notify
                notify("SR Created", f"SR {sr_number} — {self.data['title']}", "info")
            except Exception:
                pass

            self.done.emit(doc)
        except Exception as e:
            self.error.emit(str(e))


class CreateSRDialog(QDialog):
    sr_created = pyqtSignal(dict)

    def __init__(self, parent=None, users: list = None):
        super().__init__(parent)
        self._users  = users or []
        self._worker = None
        self.setWindowTitle("Create New Service Request")
        self.setMinimumWidth(580)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QFrame()
        hdr.setStyleSheet("background: #1E3A5F; padding: 0;")
        hdr.setFixedHeight(72)
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 0, 24, 0)
        icon = QLabel("📋")
        icon.setStyleSheet("font-size: 28px; color: white; background: transparent;")
        ttl  = QLabel("New Service Request")
        ttl.setStyleSheet("font-size: 18px; font-weight: bold; color: white; background: transparent;")
        # SR number preview
        try:
            from services.config_service import global_config
            from utils.helpers import generate_sr_number
            cfg     = global_config.get()
            pattern = cfg.get("sr_number_pattern", "SR{NNNN}")
            suffix  = cfg.get("sr_number_suffix",  "")
            counter = int(cfg.get("sr_number_counter", "1"))
            preview = generate_sr_number(pattern, counter, suffix)
        except Exception:
            preview = "SR0001"
        self._sr_num_lbl = QLabel(f"#{preview}")
        self._sr_num_lbl.setStyleSheet(
            "font-size: 13px; color: #93C5FD; background: transparent;"
            "font-family: 'Consolas', monospace; font-weight: bold;"
        )
        hl.addWidget(icon)
        hl.addWidget(ttl)
        hl.addStretch()
        hl.addWidget(self._sr_num_lbl)
        lay.addWidget(hdr)

        # ── Body ──────────────────────────────────────────────────────────────
        body = QFrame()
        body.setStyleSheet("background: #FFFFFF;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(24, 20, 24, 20)
        bl.setSpacing(16)

        # ── SR Details group ──────────────────────────────────────────────────
        grp1 = QGroupBox("SR Details")
        f1   = QFormLayout(grp1); f1.setSpacing(10); f1.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Brief description of the issue or request")
        self.title_input.setFixedHeight(38)
        f1.addRow("Title *", self.title_input)

        row_type = QHBoxLayout(); row_type.setSpacing(12)
        self.type_combo = QComboBox(); self.type_combo.addItems(SR_TYPES); self.type_combo.setFixedHeight(38)
        self.priority_combo = QComboBox(); self.priority_combo.addItems(SR_PRIORITIES)
        self.priority_combo.setCurrentText("Medium"); self.priority_combo.setFixedHeight(38)
        self.status_combo = QComboBox(); self.status_combo.addItems(SR_STATUSES)
        self.status_combo.setCurrentText("Pending"); self.status_combo.setFixedHeight(38)
        row_type.addWidget(self._lbl_col("Type", self.type_combo))
        row_type.addWidget(self._lbl_col("Priority", self.priority_combo))
        row_type.addWidget(self._lbl_col("Status", self.status_combo))
        f1.addRow("", row_type)

        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("Detailed description, steps to reproduce, or special instructions…")
        self.desc_input.setFixedHeight(90)
        f1.addRow("Description", self.desc_input)

        bl.addWidget(grp1)

        # ── Customer group ────────────────────────────────────────────────────
        grp2 = QGroupBox("Customer Details")
        f2   = QFormLayout(grp2); f2.setSpacing(10); f2.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.cust_name = QLineEdit(); self.cust_name.setPlaceholderText("Customer full name"); self.cust_name.setFixedHeight(38)
        f2.addRow("Customer Name *", self.cust_name)

        row_contact = QHBoxLayout(); row_contact.setSpacing(12)
        self.cust_phone = QLineEdit(); self.cust_phone.setPlaceholderText("+91 XXXXXXXXXX"); self.cust_phone.setFixedHeight(38)
        self.cust_email = QLineEdit(); self.cust_email.setPlaceholderText("customer@email.com"); self.cust_email.setFixedHeight(38)
        row_contact.addWidget(self._lbl_col("Phone", self.cust_phone))
        row_contact.addWidget(self._lbl_col("Email", self.cust_email))
        f2.addRow("", row_contact)

        self.cust_addr = QLineEdit(); self.cust_addr.setPlaceholderText("Site / delivery address"); self.cust_addr.setFixedHeight(38)
        f2.addRow("Address", self.cust_addr)

        bl.addWidget(grp2)

        # ── Assignment group ──────────────────────────────────────────────────
        grp3 = QGroupBox("Assignment (optional)")
        f3   = QFormLayout(grp3); f3.setSpacing(10); f3.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.assign_combo = QComboBox(); self.assign_combo.setFixedHeight(38)
        self.assign_combo.addItem("Unassigned", "")
        for u in self._users:
            name = u.get("name", u.get("email", "Unknown"))
            role = u.get("role", "")
            self.assign_combo.addItem(f"{name}  [{role}]", u.get("uid") or u.get("id", ""))
        f3.addRow("Assign To", self.assign_combo)
        bl.addWidget(grp3)

        # ── Error label ───────────────────────────────────────────────────────
        self.err_lbl = QLabel("")
        self.err_lbl.setObjectName("error_label")
        self.err_lbl.setWordWrap(True)
        self.err_lbl.setVisible(False)
        bl.addWidget(self.err_lbl)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("btn_secondary")
        cancel_btn.setFixedHeight(40)
        cancel_btn.clicked.connect(self.reject)
        self.create_btn = QPushButton("✅  Create SR")
        self.create_btn.setObjectName("btn_primary")
        self.create_btn.setFixedHeight(40)
        self.create_btn.setMinimumWidth(160)
        self.create_btn.clicked.connect(self._submit)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.create_btn)
        bl.addLayout(btn_row)

        lay.addWidget(body)

    @staticmethod
    def _lbl_col(label: str, widget) -> QFrame:
        """Wrap a label + widget in a small column frame."""
        frame = QFrame()
        frame.setStyleSheet("background: transparent;")
        fl = QVBoxLayout(frame); fl.setContentsMargins(0, 0, 0, 0); fl.setSpacing(4)
        lbl = QLabel(label)
        lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #374151;")
        fl.addWidget(lbl)
        fl.addWidget(widget)
        return frame

    def _submit(self):
        title = self.title_input.text().strip()
        cname = self.cust_name.text().strip()
        if not title:
            return self._err("Title is required.")
        if not cname:
            return self._err("Customer name is required.")

        self._set_busy(True)
        data = {
            "title":            title,
            "sr_type":          self.type_combo.currentText(),
            "priority":         self.priority_combo.currentText().lower(),
            "status":           self.status_combo.currentText().lower().replace(" ", "_"),
            "description":      self.desc_input.toPlainText().strip(),
            "customer_name":    cname,
            "customer_phone":   self.cust_phone.text().strip(),
            "customer_email":   self.cust_email.text().strip(),
            "customer_address": self.cust_addr.text().strip(),
            "assigned_to":      self.assign_combo.currentData() or "",
        }
        self._worker = CreateSRWorker(data)
        self._worker.done.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    @pyqtSlot(dict)
    def _on_done(self, doc: dict):
        self._set_busy(False)
        self.sr_created.emit(doc)
        self.accept()

    @pyqtSlot(str)
    def _on_error(self, msg: str):
        self._set_busy(False)
        self._err(f"Failed to create SR: {msg}")

    def _err(self, msg: str):
        self.err_lbl.setText(f"⚠  {msg}")
        self.err_lbl.setVisible(True)

    def _set_busy(self, busy: bool):
        self.create_btn.setEnabled(not busy)
        self.create_btn.setText("Creating…" if busy else "✅  Create SR")
        for w in (self.title_input, self.cust_name, self.cust_phone,
                  self.cust_email, self.cust_addr, self.type_combo,
                  self.priority_combo, self.status_combo, self.assign_combo):
            w.setEnabled(not busy)
        self.err_lbl.setVisible(False)
