# services/stats_service.py
"""
Statistics calculation service.
All heavy computation happens here, off the UI thread.
"""

from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from utils.helpers import utc_now_iso


class StatsResult:
    def __init__(self):
        self.total_srs:         int   = 0
        self.open_count:        int   = 0
        self.in_progress_count: int   = 0
        self.completed_count:   int   = 0
        self.closed_count:      int   = 0
        self.overdue_count:     int   = 0

        self.avg_resolution_days: float = 0.0
        self.avg_response_hours:  float = 0.0

        # {date_str: count}  — last 30 days
        self.sr_trend:          Dict[str, int] = {}

        # {status: count}
        self.status_breakdown:  Dict[str, int] = {}

        # {priority: count}
        self.priority_breakdown: Dict[str, int] = {}

        # {user_name: {"active": n, "completed": n, "avg_days": f}}
        self.technician_workload: Dict[str, Dict] = {}

        # {template_name: {"count": n, "avg_days": f}}
        self.pipeline_stats:    Dict[str, Dict] = {}

        # {step_name: avg_days_stuck}
        self.bottlenecks:       Dict[str, float] = {}

        # List of SR dicts that are overdue (open > 3 days)
        self.overdue_srs:       List[Dict] = []


class StatsService:

    OVERDUE_DAYS = 3   # SRs open longer than this are "overdue"

    def compute(self, srs: List[Dict], users: List[Dict],
                filter_uid: Optional[str] = None) -> StatsResult:
        """
        Compute all statistics.
        filter_uid: if set, only count SRs assigned to / created by that user.
        """
        if filter_uid:
            srs = [s for s in srs
                   if s.get("assigned_to") == filter_uid
                   or s.get("created_by")  == filter_uid]

        result = StatsResult()
        result.total_srs = len(srs)

        user_map = {u.get("uid", u.get("id", "")): u for u in users}

        now = datetime.now(timezone.utc)

        # ── Status counts ──────────────────────────────────────────────────────
        status_counts = Counter(s.get("status", "unknown") for s in srs)
        result.open_count        = status_counts.get("open", 0)
        result.in_progress_count = status_counts.get("in_progress", 0)
        result.completed_count   = status_counts.get("completed", 0)
        result.closed_count      = status_counts.get("closed", 0)
        result.status_breakdown  = dict(status_counts)

        # ── Priority breakdown ─────────────────────────────────────────────────
        result.priority_breakdown = dict(Counter(s.get("priority", "medium") for s in srs))

        # ── Overdue ────────────────────────────────────────────────────────────
        overdue = []
        for sr in srs:
            if sr.get("status") in ("open", "in_progress"):
                created = self._parse_ts(sr.get("created_at"))
                if created and (now - created).days >= self.OVERDUE_DAYS:
                    overdue.append(sr)
        result.overdue_count = len(overdue)
        result.overdue_srs   = overdue

        # ── Avg resolution time (completed/closed SRs) ─────────────────────────
        resolution_days = []
        for sr in srs:
            if sr.get("status") in ("completed", "closed"):
                created   = self._parse_ts(sr.get("created_at"))
                completed = self._parse_ts(sr.get("completed_at") or sr.get("updated_at"))
                if created and completed and completed > created:
                    resolution_days.append((completed - created).total_seconds() / 86400)
        result.avg_resolution_days = (
            round(sum(resolution_days) / len(resolution_days), 1) if resolution_days else 0.0
        )

        # ── SR trend (last 30 days) ────────────────────────────────────────────
        trend: Dict[str, int] = {}
        for i in range(29, -1, -1):
            day = (now - timedelta(days=i)).strftime("%d %b")
            trend[day] = 0
        for sr in srs:
            created = self._parse_ts(sr.get("created_at"))
            if created:
                days_ago = (now - created).days
                if 0 <= days_ago < 30:
                    day_key = created.astimezone().strftime("%d %b")
                    if day_key in trend:
                        trend[day_key] += 1
        result.sr_trend = trend

        # ── Technician workload ────────────────────────────────────────────────
        workload: Dict[str, Dict] = {}
        for sr in srs:
            uid  = sr.get("assigned_to", "")
            user = user_map.get(uid, {})
            name = user.get("name", uid or "Unassigned")
            if name not in workload:
                workload[name] = {"active": 0, "completed": 0, "total": 0, "res_days": []}
            workload[name]["total"] += 1
            if sr.get("status") in ("open", "in_progress"):
                workload[name]["active"] += 1
            if sr.get("status") in ("completed", "closed"):
                workload[name]["completed"] += 1
                c = self._parse_ts(sr.get("created_at"))
                e = self._parse_ts(sr.get("completed_at") or sr.get("updated_at"))
                if c and e and e > c:
                    workload[name]["res_days"].append((e - c).total_seconds() / 86400)

        result.technician_workload = {
            name: {
                "active":    d["active"],
                "completed": d["completed"],
                "total":     d["total"],
                "avg_days":  round(sum(d["res_days"]) / len(d["res_days"]), 1)
                             if d["res_days"] else 0.0,
            }
            for name, d in workload.items()
        }

        # ── Pipeline stats ─────────────────────────────────────────────────────
        pipe: Dict[str, Dict] = {}
        for sr in srs:
            ps = sr.get("pipeline_state")
            if not ps or not isinstance(ps, dict):
                continue
            tname = ps.get("template_name", "Unknown")
            if tname not in pipe:
                pipe[tname] = {"count": 0, "res_days": []}
            pipe[tname]["count"] += 1
            if sr.get("status") in ("completed", "closed"):
                c = self._parse_ts(sr.get("created_at"))
                e = self._parse_ts(sr.get("completed_at") or sr.get("updated_at"))
                if c and e and e > c:
                    pipe[tname]["res_days"].append((e - c).total_seconds() / 86400)

        result.pipeline_stats = {
            name: {
                "count":    d["count"],
                "avg_days": round(sum(d["res_days"]) / len(d["res_days"]), 1)
                            if d["res_days"] else 0.0,
            }
            for name, d in pipe.items()
        }

        return result

    @staticmethod
    def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            return None


stats_service = StatsService()
