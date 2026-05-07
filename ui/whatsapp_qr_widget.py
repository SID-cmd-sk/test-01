# ui/whatsapp_qr_widget.py
"""
WhatsApp Web QR widget.
Embeds WhatsApp Web in a QWebEngineView. User scans QR once per session.
Uses JavaScript bridge to send messages programmatically.

IMPORTANT: WhatsApp Web automation is against WhatsApp ToS.
Use at your own risk. For production use Meta Cloud API instead.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QMessageBox, QLineEdit, QDialog
)
from PyQt6.QtCore import Qt, QUrl, pyqtSignal, QTimer, pyqtSlot

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineScript
    from PyQt6.QtWebChannel import QWebChannel
    WEB_ENGINE_AVAILABLE = True
except ImportError:
    WEB_ENGINE_AVAILABLE = False


# ── JS bridge object ──────────────────────────────────────────────────────────

if WEB_ENGINE_AVAILABLE:
    from PyQt6.QtCore import QObject

    class WhatsAppBridge(QObject):
        message_sent   = pyqtSignal(str)
        session_ready  = pyqtSignal()
        session_lost   = pyqtSignal()

        def __init__(self):
            super().__init__()
            self._ready = False

        @pyqtSlot(str)
        def on_ready(self, status: str):
            self._ready = True
            self.session_ready.emit()

        @pyqtSlot(str)
        def on_disconnected(self, reason: str):
            self._ready = False
            self.session_lost.emit()

        @property
        def is_ready(self) -> bool:
            return self._ready


# ── Main Widget ───────────────────────────────────────────────────────────────

class WhatsAppQRWidget(QWidget):
    """
    Embeds WhatsApp Web. Shows QR for scanning, then allows programmatic
    message sending via JavaScript injection.
    """

    connected    = pyqtSignal()
    disconnected = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ready   = False
        self._view    = None
        self._bridge  = None
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        # Status bar
        status_row = QHBoxLayout()
        self.status_lbl = QLabel("⭕  Not connected — scan QR code below")
        self.status_lbl.setStyleSheet("font-size: 12px; color: #64748B; font-weight: bold;")
        status_row.addWidget(self.status_lbl)
        status_row.addStretch()

        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.setObjectName("btn_secondary")
        self.refresh_btn.setFixedHeight(30)
        self.refresh_btn.clicked.connect(self._load_wa)
        status_row.addWidget(self.refresh_btn)

        lay.addLayout(status_row)

        if not WEB_ENGINE_AVAILABLE:
            warn = QLabel(
                "⚠  PyQt6-WebEngine is not installed.\n"
                "Run:  pip install PyQt6-WebEngine\n\n"
                "Alternatively use Meta Cloud API mode in Settings."
            )
            warn.setStyleSheet("""
                background: #FEF3C7; border: 1px solid #F59E0B;
                border-radius: 8px; padding: 16px; font-size: 13px; color: #92400E;
            """)
            warn.setWordWrap(True)
            warn.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(warn)
            return

        # WebEngineView
        self._view   = QWebEngineView()
        self._bridge = WhatsAppBridge()
        self._bridge.session_ready.connect(self._on_connected)
        self._bridge.session_lost.connect(self._on_disconnected)

        lay.addWidget(self._view)
        self._load_wa()

        # Poll connection state every 5 seconds
        self._poll = QTimer()
        self._poll.setInterval(5000)
        self._poll.timeout.connect(self._check_status)
        self._poll.start()

    def _load_wa(self):
        if self._view:
            self._ready = False
            self.status_lbl.setText("⭕  Loading WhatsApp Web…")
            self._view.load(QUrl("https://web.whatsapp.com"))
            self._view.loadFinished.connect(self._inject_js)

    def _inject_js(self, ok: bool):
        if not ok or not self._view:
            return
        # JS that monitors WhatsApp Web connection state and exposes sendMessage
        js = """
        (function() {
            function isConnected() {
                return !!document.querySelector('[data-testid="chat-list"]') ||
                       !!document.querySelector('[data-icon="search"]');
            }

            window._srManagerReady = false;

            var checkInterval = setInterval(function() {
                if (isConnected() && !window._srManagerReady) {
                    window._srManagerReady = true;
                    console.log('SR_MANAGER_CONNECTED');
                }
                if (!isConnected() && window._srManagerReady) {
                    window._srManagerReady = false;
                    console.log('SR_MANAGER_DISCONNECTED');
                }
            }, 3000);

            window.srSendMessage = function(phone, message) {
                var url = 'https://web.whatsapp.com/send?phone=' +
                          phone.replace(/[^0-9]/g, '') +
                          '&text=' + encodeURIComponent(message);
                window.location.href = url;
                setTimeout(function() {
                    var sendBtn = document.querySelector('[data-testid="send"]') ||
                                  document.querySelector('[data-icon="send"]');
                    if (sendBtn) { sendBtn.click(); }
                }, 3000);
                return true;
            };
        })();
        """
        self._view.page().runJavaScript(js)

    def _check_status(self):
        if not self._view:
            return
        self._view.page().runJavaScript(
            "window._srManagerReady ? 'connected' : 'disconnected'",
            self._on_status_result
        )

    def _on_status_result(self, result: str):
        if result == "connected" and not self._ready:
            self._on_connected()
        elif result != "connected" and self._ready:
            self._on_disconnected()

    def _on_connected(self):
        self._ready = True
        self.status_lbl.setText("✅  WhatsApp connected")
        self.status_lbl.setStyleSheet("font-size: 12px; color: #10B981; font-weight: bold;")
        from services.whatsapp_service import register_qr_callback
        register_qr_callback(self.send_message)
        self.connected.emit()

    def _on_disconnected(self):
        self._ready = False
        self.status_lbl.setText("⭕  Not connected — scan QR code")
        self.status_lbl.setStyleSheet("font-size: 12px; color: #EF4444; font-weight: bold;")
        from services.whatsapp_service import register_qr_callback
        register_qr_callback(None)
        self.disconnected.emit()

    def send_message(self, phone: str, message: str) -> None:
        """Send a WhatsApp message via JS injection."""
        if not self._view or not self._ready:
            raise RuntimeError("WhatsApp not connected. Scan the QR code first.")
        phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
        safe_msg    = message.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
        js = f"window.srSendMessage('{phone_clean}', '{safe_msg}');"
        self._view.page().runJavaScript(js)

    @property
    def is_connected(self) -> bool:
        return self._ready


# ── Send Test Dialog ──────────────────────────────────────────────────────────

class SendTestDialog(QDialog):
    def __init__(self, widget: "WhatsAppQRWidget", parent=None):
        super().__init__(parent)
        self.widget = widget
        self.setWindowTitle("Test WhatsApp Message")
        self.setFixedSize(400, 200)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(10)

        from PyQt6.QtWidgets import QFormLayout
        form = QFormLayout()
        self.phone_input = QLineEdit(); self.phone_input.setPlaceholderText("+919XXXXXXXXX"); self.phone_input.setFixedHeight(36)
        self.msg_input   = QLineEdit(); self.msg_input.setPlaceholderText("Test message"); self.msg_input.setFixedHeight(36)
        form.addRow("Phone:", self.phone_input)
        form.addRow("Message:", self.msg_input)
        lay.addLayout(form)

        self.err_lbl = QLabel(""); self.err_lbl.setObjectName("error_label"); self.err_lbl.setVisible(False)
        lay.addWidget(self.err_lbl)

        btn_row = QHBoxLayout()
        cancel = QPushButton("Cancel"); cancel.setObjectName("btn_secondary"); cancel.clicked.connect(self.reject)
        send   = QPushButton("Send");   send.setObjectName("btn_primary");     send.clicked.connect(self._send)
        btn_row.addWidget(cancel); btn_row.addWidget(send)
        lay.addLayout(btn_row)

    def _send(self):
        phone = self.phone_input.text().strip()
        msg   = self.msg_input.text().strip()
        if not phone or not msg:
            self.err_lbl.setText("⚠ Both fields required."); self.err_lbl.setVisible(True); return
        try:
            self.widget.send_message(phone, msg)
            QMessageBox.information(self, "Sent", "Message dispatched via WhatsApp Web.")
            self.accept()
        except Exception as e:
            self.err_lbl.setText(f"⚠ {e}"); self.err_lbl.setVisible(True)
