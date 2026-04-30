from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class JobStage(str, Enum):
    INGEST = "ingest"
    EXTRACT = "extract"
    OCR_FALLBACK = "ocr_fallback"
    TRANSFORM = "transform"
    COMPLETE = "complete"


@dataclass
class JobState:
    job_id: str
    current_stage: JobStage = JobStage.INGEST
    completed_stages: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)


class StateStore:
    def __init__(self, base_dir: Path = Path("jobs/state")) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, job_id: str) -> Path:
        return self.base_dir / f"{job_id}.json"

    def load(self, job_id: str) -> JobState:
        path = self._path(job_id)
        if not path.exists():
            return JobState(job_id=job_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        return JobState(
            job_id=payload["job_id"],
            current_stage=JobStage(payload["current_stage"]),
            completed_stages=payload.get("completed_stages", []),
            errors=payload.get("errors", []),
            artifacts=payload.get("artifacts", []),
        )

    def save(self, state: JobState) -> None:
        path = self._path(state.job_id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(
                {
                    "job_id": state.job_id,
                    "current_stage": state.current_stage.value,
                    "completed_stages": state.completed_stages,
                    "errors": state.errors,
                    "artifacts": state.artifacts,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        tmp.replace(path)
