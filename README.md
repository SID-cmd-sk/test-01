# Local-First Scan/PDF to DXF CAD Converter

This project provides a **working local pipeline** for converting PDF/PNG/JPG engineering drawings to DXF with a deterministic learning memory in SQLite.

## What is implemented
- Local FastAPI backend (`127.0.0.1:8080`) for upload, processing, export, and correction APIs.
- Deterministic processing pipeline stages: ingest, preprocess, geometry detection, OCR stage placeholder, reconstruction, DXF export.
- PDF ingest support (page enumeration + vector heuristic) and image ingest support.
- OpenCV preprocessing + Hough line detection + DXF generation via `ezdxf`.
- SQLite learning memory for corrections + similarity-based reuse (`learning/services.py`).
- One-command startup: `./start.sh` (creates venv, installs deps, bootstraps storage, launches app).

## Quick start
```bash
./start.sh
```

Then open API docs at `http://127.0.0.1:8080/docs`.

## API flow
1. `POST /api/jobs` with `file` (pdf/png/jpg)
2. Receive `job_id` and export URL
3. Download DXF from `GET /api/export/{job_id}`
4. Store corrections with `POST /api/corrections`
5. Inspect learning memory with `GET /api/rules`

## Local storage
- SQLite DB: `data/learning.db`
- uploads: `data/uploads`
- jobs: `data/jobs`
- dxf exports: `data/exports`
- state/checkpoints: `jobs/state`

## Assumptions
- Tesseract binary may be unavailable by default on some systems; OCR stage remains deterministic and non-blocking.
- For scanned PDFs, preprocessing currently uses fallback raster behavior from generated/intermediate image path.
