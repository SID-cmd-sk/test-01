# ui/stats_panel.py
"""
Statistics Dashboard — one screen, role-filtered, with visual charts.
Uses only PyQt6 (no matplotlib dependency) — charts are drawn with QPainter.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox, QScrollArea, QSizePolicy, QTableWidget,
    QTableWidgetItem, QHeaderView, QTabWidget, QGridLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QRect, QTimer
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QLinearGradient

from utils.auth import session
from utils.helpers import format_datetime, status_color, priority_color, availability_color
from services.stats_service import stats_service, StatsResult


# ── Mini bar chart widget ─────────────────────────────────────────────────────

class BarChartWidget(QWidget):
    def __init__(self, data: dict, color: str = "#3B82F6", parent=None):
        super().__init__(parent)
        self.data  = data    # {label: value}
        self.color = color
        self.setMinimumHeight(140)

    def update_data(self, data: dict, color: str = None):
        self.data  = data
        if color:
            self.color = color
        self.update()

    def paintEvent(self, event):
        if not self.data:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h    = self.width(), self.height()
        pad_l   = 36
        pad_b   = 32
        pad_top = 10
        pad_r   = 10
        chart_w = w - pad_l - pad_r
        chart_h = h - pad_b - pad_top

        max_val = max(self.data.values()) if self.data else 1
        if max_val == 0:
            max_val = 1

        keys    = list(self.data.keys())
        n       = len(keys)
        bar_w   = max(10, (chart_w - (n + 1) * 4) // n)
        gap     = (chart_w - bar_w * n) // (n + 1)

        # Axes
        p.setPen(QPen(QColor("#E2E8F0"), 1))
        for i in range(5):
            y = pad_top + chart_h * i // 4
            p.drawLine(pad_l, y, w - pad_r, y)

        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QColor("#94A3B8"))
        for i in range(5):
            val = max_val * (4 - i) // 4
            y   = pad_top + chart_h * i // 4
            p.drawText(0, y - 6, pad_l - 4, 14, Qt.AlignmentFlag.AlignRight, str(int(val)))

        # Bars
        for i, key in enumerate(keys):
            val    = self.data[key]
            bh     = int(chart_h * val / max_val)
            x      = pad_l + gap + i * (bar_w + gap)
            y      = pad_top + chart_h - bh

            grad = QLinearGradient(x, y, x, y + bh)
            grad.setColorAt(0, QColor(self.color))
            grad.setColorAt(1, QColor(self.color).darker(130))
            p.setBrush(QBrush(grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(x, y, bar_w, bh, 3, 3)

            # Value on top
            p.setPen(QColor("#374151"))
            p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            p.drawText(x, y - 14, bar_w, 14, Qt.AlignmentFlag.AlignCenter, str(int(val)))

            # Label below
            p.setPen(QColor("#64748B"))
            p.setFont(QFont("Segoe UI", 7))
            label = key[:8] + "…" if len(key) > 9 else key
            p.drawText(x - 4, h - pad_b + 4, bar_w + 8, 20,
                       Qt.AlignmentFlag.AlignCenter, label)

        p.end()


# ── Mini line chart ───────────────────────────────────────────────────────────

class LineChartWidget(QWidget):
    def __init__(self, data: dict, color: str = "#3B82F6", parent=None):
        super().__init__(parent)
        self.data  = data   # {label: value}  ordered
        self.color = color
        self.setMinimumHeight(140)

    def update_data(self, data: dict):
        self.data = data
        self.update()

    def paintEvent(self, event):
        if not self.data:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h    = self.width(), self.height()
        pad_l, pad_b, pad_top, pad_r = 36, 28, 10, 10
        chart_w = w - pad_l - pad_r
        chart_h = h - pad_b - pad_top

        values  = list(self.data.values())
        labels  = list(self.data.keys())
        n       = len(values)
        max_val = max(values) if values else 1
        if max_val == 0: max_val = 1

        # Grid
        p.setPen(QPen(QColor("#E2E8F0"), 1))
        for i in range(5):
            y = pad_top + chart_h * i // 4
            p.drawLine(pad_l, y, w - pad_r, y)

        # Y axis labels
        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QColor("#94A3B8"))
        for i in range(5):
            val = max_val * (4 - i) // 4
            y   = pad_top + chart_h * i // 4
            p.drawText(0, y - 6, pad_l - 4, 14, Qt.AlignmentFlag.AlignRight, str(int(val)))

        if n < 2:
            p.end(); return

        # Line + fill
        step = chart_w / (n - 1)
        pts  = [(int(pad_l + i * step),
                 int(pad_top + chart_h - chart_h * v / max_val))
                for i, v in enumerate(values)]

        from PyQt6.QtGui import QPolygon, QPolygonF
        from PyQt6.QtCore import QPointF

        poly_pts = [QPointF(x, y) for x, y in pts]
        poly_pts.append(QPointF(pts[-1][0], pad_top + chart_h))
        poly_pts.append(QPointF(pts[0][0],  pad_top + chart_h))

        fill_grad = QLinearGradient(0, pad_top, 0, pad_top + chart_h)
        fill_grad.setColorAt(0, QColor(self.color + "55"))
        fill_grad.setColorAt(1, QColor(self.color + "00"))
        p.setBrush(QBrush(fill_grad))
        p.setPen(Qt.PenStyle.NoPen)
        from PyQt6.QtGui import QPolygonF
        p.drawPolygon(QPolygonF(poly_pts))

        # Line
        pen = QPen(QColor(self.color), 2)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(len(pts) - 1):
            p.drawLine(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1])

        # Dots
        p.setBrush(QColor(self.color))
        p.setPen(QPen(QColor("white"), 1))
        for x, y in pts:
            p.drawEllipse(x - 3, y - 3, 6, 6)

        # X labels (show every nth)
        step_label = max(1, n // 6)
        p.setFont(QFont("Segoe UI", 7)); p.setPen(QColor("#94A3B8"))
        for i, (x, y) in enumerate(pts):
            if i % step_label == 0:
                lbl = labels[i]
                p.drawText(x - 20, h - pad_b + 4, 40, 20, Qt.AlignmentFlag.AlignCenter, lbl)

        p.end()


# ── Stat card ─────────────────────────────────────────────────────────────────

def make_stat_card(label: str, value: str, color: str,
                   sub: str = "") -> QFrame:
    card = QFrame(); card.setObjectName("stat_card")
    card.setStyleSheet(f"""
        QFrame#stat_card {{
            background: white; border-radius: 10px;
            border: 1px solid #E2E8F0; border-top: 4px solid {color};
        }}
    """)
    lay = QVBoxLayout(card); lay.setContentsMargins(14, 12, 14, 12); lay.setSpacing(3)
    val_lbl = QLabel(value)
    val_lbl.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {color};")
    lbl = QLabel(label); lbl.setStyleSheet("font-size: 12px; color: #64748B;")
    lay.addWidget(val_lbl); lay.addWidget(lbl)
    if sub:
        sub_lbl = QLabel(sub); sub_lbl.setStyleSheet("font-size: 10px; color: #94A3B8;")
        lay.addWidget(sub_lbl)
    card._val_label = val_lbl
    card._sub_label = QLabel(sub) if sub else None
    return card


# ── Stats Worker ──────────────────────────────────────────────────────────────

class StatsWorker(QThread):
    done  = pyqtSignal(object, list, list)   # StatsResult, srs, users
    error = pyqtSignal(str)

    def __init__(self, filter_uid=None):
        super().__init__()
        self.filter_uid = filter_uid

    def run(self):
        try:
            from db import storage
            srs   = storage.get_collection("service_requests")
            users = storage.get_collection("users")
            result = stats_service.compute(srs, users, self.filter_uid)
            self.done.emit(result, srs, users)
        except Exception as e:
            self.error.emit(str(e))


# ── Main Stats Panel ──────────────────────────────────────────────────────────

class StatsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._result: StatsResult = StatsResult()
        self._users:  list        = []
        self._srs:    list        = []
        self._worker  = None
        self._build_ui()
        self._refresh()

        # Auto-refresh every 30 seconds
        self._timer = QTimer()
        self._timer.setInterval(30_000)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        # Header + filters
        hdr = QHBoxLayout()
        ttl = QLabel("📊  Statistics"); ttl.setObjectName("section_title"); hdr.addWidget(ttl)
        hdr.addStretch()

        if session.can("view_all_reports"):
            self.user_filter = QComboBox()
            self.user_filter.addItem("All Users", None)
            self.user_filter.setFixedHeight(34)
            self.user_filter.currentIndexChanged.connect(self._on_filter_change)
            hdr.addWidget(QLabel("Filter:")); hdr.addWidget(self.user_filter)
        else:
            self.user_filter = None

        refresh_btn = QPushButton("🔄 Refresh"); refresh_btn.setObjectName("btn_secondary")
        refresh_btn.setFixedHeight(34); refresh_btn.clicked.connect(self._refresh)
        hdr.addWidget(refresh_btn)
        outer.addLayout(hdr)

        # Scrollable content
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget(); self._content_lay = QVBoxLayout(content)
        self._content_lay.setSpacing(16); self._content_lay.setContentsMargins(0, 0, 0, 0)

        # ── Top KPI cards ──────────────────────────────────────────────────────
        kpi_row = QHBoxLayout()
        self.card_total    = make_stat_card("Total SRs",      "—", "#3B82F6")
        self.card_open     = make_stat_card("Open",           "—", "#F59E0B")
        self.card_progress = make_stat_card("In Progress",    "—", "#8B5CF6")
        self.card_done     = make_stat_card("Completed",      "—", "#10B981")
        self.card_overdue  = make_stat_card("Overdue",        "—", "#EF4444")
        self.card_avg      = make_stat_card("Avg Resolution", "—", "#06B6D4", "days")
        for c in (self.card_total, self.card_open, self.card_progress,
                  self.card_done, self.card_overdue, self.card_avg):
            kpi_row.addWidget(c)
        self._content_lay.addLayout(kpi_row)

        # ── Tabs ───────────────────────────────────────────────────────────────
        tabs = QTabWidget()

        # Tab 1: SR Trend
        trend_tab = QWidget()
        tl = QVBoxLayout(trend_tab); tl.setContentsMargins(12, 12, 12, 12)
        tl.addWidget(QLabel("Service Requests Created — Last 30 Days"))
        self.trend_chart = LineChartWidget({}, "#3B82F6")
        self.trend_chart.setMinimumHeight(180)
        tl.addWidget(self.trend_chart)
        tabs.addTab(trend_tab, "📈 SR Trend")

        # Tab 2: Status & Priority
        breakdown_tab = QWidget()
        bl = QHBoxLayout(breakdown_tab); bl.setContentsMargins(12, 12, 12, 12); bl.setSpacing(20)

        status_grp = QVBoxLayout()
        status_grp.addWidget(QLabel("Status Breakdown"))
        self.status_chart = BarChartWidget({}, "#3B82F6")
        self.status_chart.setMinimumHeight(160)
        status_grp.addWidget(self.status_chart)
        bl.addLayout(status_grp, 1)

        pri_grp = QVBoxLayout()
        pri_grp.addWidget(QLabel("Priority Breakdown"))
        self.priority_chart = BarChartWidget({}, "#F59E0B")
        self.priority_chart.setMinimumHeight(160)
        pri_grp.addWidget(self.priority_chart)
        bl.addLayout(pri_grp, 1)

        tabs.addTab(breakdown_tab, "🍩 Breakdown")

        # Tab 3: Technician workload
        tech_tab = QWidget()
        tecl = QVBoxLayout(tech_tab); tecl.setContentsMargins(12, 12, 12, 12)
        tecl.addWidget(QLabel("Technician Workload"))
        self.workload_chart = BarChartWidget({}, "#8B5CF6")
        self.workload_chart.setMinimumHeight(160)
        tecl.addWidget(self.workload_chart)

        self.workload_table = QTableWidget()
        self.workload_table.setColumnCount(5)
        self.workload_table.setHorizontalHeaderLabels(
            ["Name", "Availability", "Active SRs", "Completed", "Avg Resolution"])
        self.workload_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.workload_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.workload_table.verticalHeader().setVisible(False)
        self.workload_table.setMaximumHeight(200)
        tecl.addWidget(self.workload_table)
        tabs.addTab(tech_tab, "👥 Workload")

        # Tab 4: Pipeline stats
        pipe_tab = QWidget()
        pl = QVBoxLayout(pipe_tab); pl.setContentsMargins(12, 12, 12, 12)
        pl.addWidget(QLabel("Resolution Time by Pipeline Template"))
        self.pipeline_chart = BarChartWidget({}, "#10B981")
        self.pipeline_chart.setMinimumHeight(160)
        pl.addWidget(self.pipeline_chart)
        tabs.addTab(pipe_tab, "🔧 Pipelines")

        # Tab 5: Overdue SRs
        overdue_tab = QWidget()
        ol = QVBoxLayout(overdue_tab); ol.setContentsMargins(12, 12, 12, 12)
        ol.addWidget(QLabel("Overdue Service Requests (open > 3 days)"))
        self.overdue_table = QTableWidget()
        self.overdue_table.setColumnCount(5)
        self.overdue_table.setHorizontalHeaderLabels(
            ["Title", "Priority", "Assigned To", "Created", "Days Open"])
        self.overdue_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.overdue_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.overdue_table.verticalHeader().setVisible(False)
        ol.addWidget(self.overdue_table)
        tabs.addTab(overdue_tab, "⚠ Overdue")

        self._content_lay.addWidget(tabs)
        self._content_lay.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    # ── Data loading ───────────────────────────────────────────────────────────

    def _on_filter_change(self):
        self._refresh()

    def _refresh(self):
        filter_uid = None
        if self.user_filter:
            filter_uid = self.user_filter.currentData()
        elif not session.can("view_all_reports"):
            filter_uid = session.uid

        self._worker = StatsWorker(filter_uid)
        self._worker.done.connect(self._on_data)
        self._worker.error.connect(lambda e: None)
        self._worker.start()

    def populate_user_filter(self, users: list):
        if not self.user_filter:
            return
        current = self.user_filter.currentData()
        self.user_filter.blockSignals(True)
        self.user_filter.clear()
        self.user_filter.addItem("All Users", None)
        for u in users:
            uid  = u.get("uid", u.get("id", ""))
            name = u.get("name", u.get("email", uid))
            self.user_filter.addItem(name, uid)
        # Restore selection
        for i in range(self.user_filter.count()):
            if self.user_filter.itemData(i) == current:
                self.user_filter.setCurrentIndex(i)
                break
        self.user_filter.blockSignals(False)

    @pyqtSlot(object, list, list)
    def _on_data(self, result: StatsResult, srs: list, users: list):
        self._result = result
        self._srs    = srs
        self._users  = users

        if self.user_filter and not self._users:
            pass
        elif self.user_filter:
            self.populate_user_filter(users)

        # KPI cards
        self.card_total._val_label.setText(str(result.total_srs))
        self.card_open._val_label.setText(str(result.open_count))
        self.card_progress._val_label.setText(str(result.in_progress_count))
        self.card_done._val_label.setText(str(result.completed_count))
        self.card_overdue._val_label.setText(str(result.overdue_count))
        self.card_avg._val_label.setText(str(result.avg_resolution_days))

        # Trend chart
        self.trend_chart.update_data(result.sr_trend)

        # Status chart
        self.status_chart.update_data({
            k.replace("_", " ").title(): v
            for k, v in result.status_breakdown.items()
        })

        # Priority chart
        self.priority_chart.update_data(result.priority_breakdown)

        # Workload chart
        workload_active = {name: d["active"] for name, d in result.technician_workload.items()}
        self.workload_chart.update_data(workload_active, "#8B5CF6")

        # Workload table
        user_map = {u.get("uid", u.get("id", "")): u for u in users}
        rows     = list(result.technician_workload.items())
        self.workload_table.setRowCount(len(rows))
        for row, (name, d) in enumerate(rows):
            color, label = availability_color(d["active"])
            cells = [name, label, str(d["active"]), str(d["completed"]),
                     f"{d['avg_days']} days"]
            for col, text in enumerate(cells):
                from PyQt6.QtWidgets import QTableWidgetItem
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                if col == 1:
                    from PyQt6.QtGui import QColor
                    item.setForeground(QColor(color))
                self.workload_table.setItem(row, col, item)

        # Pipeline chart
        pipe_data = {name: d["avg_days"] for name, d in result.pipeline_stats.items()}
        self.pipeline_chart.update_data(pipe_data, "#10B981")

        # Overdue table
        self.overdue_table.setRowCount(len(result.overdue_srs))
        for row, sr in enumerate(result.overdue_srs):
            uid  = sr.get("assigned_to", "")
            user = user_map.get(uid, {})
            name = user.get("name", "Unassigned")
            from utils.helpers import days_since
            days = days_since(sr.get("created_at"))
            cells = [
                sr.get("title", "—"),
                sr.get("priority", "medium").capitalize(),
                name,
                format_datetime(sr.get("created_at")),
                f"{days} days" if days is not None else "—",
            ]
            for col, text in enumerate(cells):
                from PyQt6.QtWidgets import QTableWidgetItem
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                if col == 4 and days and days >= 3:
                    from PyQt6.QtGui import QColor
                    item.setForeground(QColor("#EF4444"))
                self.overdue_table.setItem(row, col, item)
