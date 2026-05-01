from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from processing.pipeline import JobConfig, ProcessingPipeline
from learning.services import LearningService

ROOT = Path(__file__).resolve().parents[1]
UPLOADS = ROOT / "data" / "uploads"
JOBS = ROOT / "data" / "jobs"
EXPORTS = ROOT / "data" / "exports"
DB = ROOT / "data" / "learning.db"

app = FastAPI(title="Local CAD Converter")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def health():
    return {"status": "ok"}

@app.post("/api/jobs")
async def create_job(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".pdf", ".png", ".jpg", ".jpeg"}:
        raise HTTPException(400, "Unsupported file type")
    job_id = str(uuid.uuid4())
    job_dir = JOBS / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    src = UPLOADS / f"{job_id}{suffix}"
    with src.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    pipeline = ProcessingPipeline(JobConfig(input_pdf=str(src), output_dir=str(job_dir)))
    pipeline.run()
    dxf = job_dir / "output.dxf"
    target = EXPORTS / f"{job_id}.dxf"
    shutil.copy2(dxf, target)
    return {"job_id": job_id, "dxf": f"/api/export/{job_id}", "stage_dir": str(job_dir / 'stages')}

@app.get("/api/export/{job_id}")
def export(job_id: str):
    dxf = EXPORTS / f"{job_id}.dxf"
    if not dxf.exists():
        raise HTTPException(404, "DXF not found")
    return FileResponse(dxf, media_type="application/dxf", filename=dxf.name)

@app.post("/api/corrections")
def save_correction(payload: dict):
    svc = LearningService(DB)
    cid = svc.create_correction(
        pattern_signature=payload["pattern_signature"],
        correction_payload=payload["correction_payload"],
        confidence_before=float(payload.get("confidence_before", 0.0)),
        confidence_after=float(payload.get("confidence_after", 1.0)),
        context_metadata=payload.get("context_metadata", {}),
        rule_type=payload.get("rule_type", "manual"),
        optional_notes=payload.get("notes"),
    )
    return {"correction_id": cid}

@app.get("/api/rules")
def list_rules():
    svc = LearningService(DB)
    return {"history": svc.list_rule_history(), "suggestions": svc.suggest_low_confidence_items()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)
