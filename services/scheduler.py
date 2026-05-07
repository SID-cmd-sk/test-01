# services/scheduler.py
"""Background daemon: sends daily WhatsApp report at configured time."""

from __future__ import annotations
import threading, time
from datetime import datetime


class DailyReportScheduler:
    def __init__(self):
        self._thread:        threading.Thread | None = None
        self._stop:          threading.Event         = threading.Event()
        self._last_run_date: str | None              = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="DailyScheduler")
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.is_set():
            self._check()
            self._stop.wait(60)

    def _check(self):
        try:
            from services.config_service  import global_config
            from services.whatsapp_service import send_daily_report
            cfg   = global_config.get()
            rt    = cfg.get("report_time", "09:00").strip()
            now   = datetime.now()
            today = now.strftime("%Y-%m-%d")
            if now.strftime("%H:%M") == rt and self._last_run_date != today:
                send_daily_report()
                self._last_run_date = today
        except Exception:
            pass


daily_report_scheduler = DailyReportScheduler()
