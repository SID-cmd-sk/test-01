# PDF-to-CAD Monorepo

Production-ready monorepo scaffold for a local-first PDF-to-CAD pipeline.

## Top-level layout

- `ui/`: React application for upload, preview, correction tooling, and rule history.
- `backend/`: Local API service (localhost) orchestrating job lifecycle and error handling.
- `processing/`: PDF ingest, modality detection, preprocessing, and extraction.
- `cad/`: DXF reconstruction/export with layered output.
- `learning/`: Rule engine and similarity matching.
- `storage/`: SQLite schema and migration management.
- `contracts/`: Shared DTOs/JSON schemas and OpenAPI source of truth.
- `jobs/`: Runtime job workspaces and job artifacts.
- `logs/`: Structured service/job logs.
- `samples/`: Test PDFs, expected outputs, and fixtures.
- `scripts/`: Developer and CI helper scripts.

## Architectural boundaries

### `ui -> backend`
- Uses HTTP/JSON DTOs only from `contracts/json-schemas`.
- Never imports internals from `processing`, `cad`, `learning`, or `storage`.

### `backend -> processing | cad | learning | storage`
- Backend is the only orchestration layer.
- Internal module calls use well-defined interfaces documented under each package.
- External data exchange at boundaries uses DTOs under `contracts/`.

### `processing -> cad`
- `processing` emits a canonical extraction payload schema.
- `cad` consumes canonical extraction + layer strategy config.

### `learning -> backend`
- `learning` proposes rule candidates and similarity results.
- Backend persists accepted rules in `storage` and exposes history to `ui`.

## Contract-first development

Schemas in `contracts/json-schemas` are the canonical source for payload validation.

- `upload.request.json`
- `job.status.response.json`
- `processing.result.json`
- `cad.export.request.json`
- `rule.history.response.json`

## Next steps

1. Wire up package managers/workspaces (`pnpm`, `poetry`, `cargo`, etc.) per language choices.
2. Generate server/client types from schemas in `contracts/`.
3. Implement local API with strict schema validation and correlation IDs.
4. Add observability (health checks, metrics, structured logs) and CI.
