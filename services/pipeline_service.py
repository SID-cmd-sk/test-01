# services/pipeline_service.py
"""
Pipeline / approval process service.
Templates are stored in Firestore: pipeline_templates/{id}
SR pipeline state is stored inside the SR document: pipeline_state dict
"""

from typing import List, Dict, Optional, Any
from utils.helpers import utc_now_iso


# ── Template structure ─────────────────────────────────────────────────────────
# {
#   "id": "...",
#   "name": "Enterprise Installation",
#   "description": "Full process for enterprise clients",
#   "steps": [
#     {
#       "index": 0,
#       "name": "Welcome Letter",
#       "description": "Send welcome letter to client",
#       "approver_role": "manager",
#       "required": true,
#       "skippable": false
#     }, ...
#   ],
#   "created_by": "uid",
#   "created_at": "iso",
# }

# ── SR pipeline_state structure ───────────────────────────────────────────────
# {
#   "template_id": "...",
#   "template_name": "...",
#   "current_step": 0,
#   "total_steps": 4,
#   "steps_state": [
#     {
#       "index": 0,
#       "name": "Welcome Letter",
#       "status": "pending" | "in_progress" | "done" | "skipped",
#       "completed_by": "uid",
#       "completed_at": "iso",
#       "skip_reason": "",
#       "notes": ""
#     }, ...
#   ]
# }


class PipelineService:

    # ── Template CRUD ──────────────────────────────────────────────────────────

    def get_templates(self) -> List[Dict]:
        from firebase_client import firebase
        return firebase.get_collection("pipeline_templates")

    def get_template(self, template_id: str) -> Optional[Dict]:
        from firebase_client import firebase
        return firebase.get_document("pipeline_templates", template_id)

    def save_template(self, template: Dict) -> Dict:
        from firebase_client import firebase
        from utils.auth import session

        template["updated_at"] = utc_now_iso()
        if not template.get("created_at"):
            template["created_at"] = utc_now_iso()
        if not template.get("created_by"):
            template["created_by"] = session.uid

        tid = template.get("id")
        if tid:
            firebase.update_document("pipeline_templates", tid, template)
            return template
        else:
            return firebase.create_document("pipeline_templates", template)

    def delete_template(self, template_id: str) -> None:
        from firebase_client import firebase
        firebase.delete_document("pipeline_templates", template_id)

    # ── SR pipeline state helpers ──────────────────────────────────────────────

    def init_pipeline_state(self, template: Dict) -> Dict:
        """Create initial pipeline_state for an SR from a template."""
        steps = template.get("steps", [])
        return {
            "template_id":   template.get("id", ""),
            "template_name": template.get("name", ""),
            "current_step":  0,
            "total_steps":   len(steps),
            "steps_state": [
                {
                    "index":        s.get("index", i),
                    "name":         s.get("name", f"Step {i+1}"),
                    "description":  s.get("description", ""),
                    "approver_role": s.get("approver_role", "technical"),
                    "required":     s.get("required", True),
                    "skippable":    s.get("skippable", True),
                    "status":       "pending",
                    "completed_by": "",
                    "completed_at": "",
                    "skip_reason":  "",
                    "notes":        "",
                }
                for i, s in enumerate(steps)
            ],
        }

    def advance_step(self, sr_id: str, pipeline_state: Dict,
                     notes: str = "", actor_uid: str = "") -> Dict:
        """
        Mark current step as done and advance pointer.
        Returns updated pipeline_state dict.
        """
        steps   = pipeline_state.get("steps_state", [])
        current = pipeline_state.get("current_step", 0)

        if current < len(steps):
            steps[current]["status"]       = "done"
            steps[current]["completed_by"] = actor_uid
            steps[current]["completed_at"] = utc_now_iso()
            steps[current]["notes"]        = notes

        next_step = current + 1
        pipeline_state["current_step"] = next_step
        pipeline_state["steps_state"]  = steps

        # Persist to Firestore
        from firebase_client import firebase
        firebase.update_document("service_requests", sr_id, {
            "pipeline_state": pipeline_state,
            "updated_at":     utc_now_iso(),
        })

        # Notify
        try:
            from firebase_client import firebase as fb
            sr = fb.get_document("service_requests", sr_id) or {}
            step_name = steps[current].get("name", "Step") if current < len(steps) else ""
            from services.whatsapp_service import notify_sr_event
            notify_sr_event("step_done", sr, extra=f"'{step_name}' completed.")
        except Exception:
            pass

        return pipeline_state

    def skip_step(self, sr_id: str, pipeline_state: Dict,
                  reason: str, actor_uid: str = "") -> Dict:
        """Skip the current step with a mandatory reason."""
        steps   = pipeline_state.get("steps_state", [])
        current = pipeline_state.get("current_step", 0)

        if current < len(steps):
            steps[current]["status"]       = "skipped"
            steps[current]["skip_reason"]  = reason
            steps[current]["completed_by"] = actor_uid
            steps[current]["completed_at"] = utc_now_iso()

        pipeline_state["current_step"]  = current + 1
        pipeline_state["steps_state"]   = steps

        from firebase_client import firebase
        firebase.update_document("service_requests", sr_id, {
            "pipeline_state": pipeline_state,
            "updated_at":     utc_now_iso(),
        })
        return pipeline_state

    def is_pipeline_complete(self, pipeline_state: Dict) -> bool:
        total   = pipeline_state.get("total_steps", 0)
        current = pipeline_state.get("current_step", 0)
        return current >= total

    def current_step_info(self, pipeline_state: Dict) -> Optional[Dict]:
        steps   = pipeline_state.get("steps_state", [])
        current = pipeline_state.get("current_step", 0)
        if current < len(steps):
            return steps[current]
        return None


pipeline_service = PipelineService()
