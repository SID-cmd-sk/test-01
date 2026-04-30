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
# test-01

`test-01` is a **local-only document processing app** that ingests files, lets you correct extracted data, and exports normalized outputs. This README covers setup, startup options, first-run behavior, day-to-day workflow, and troubleshooting.

---

## Prerequisites (exact versions)

Install these versions before running the app:

- **Python**: `3.11.9`
- **pip**: `24.2`
- **Node.js**: `20.11.1`
- **npm**: `10.2.4`
- **SQLite**: `3.45.3`
- **Git**: `2.44.0`

> If your OS ships a newer patch release, pin these exact versions with your package manager or version manager (`pyenv`, `nvm`, etc.) to avoid dependency drift.

---

## Startup

### One-command startup (terminal)

From the project root:

```bash
./start.sh
```

What this should do:

1. Verify runtime versions.
2. Create/activate local environment.
3. Start backend service.
4. Start frontend UI.
5. Open the app at `http://127.0.0.1:8080`.

### Double-click startup (desktop)

Use the launcher script from your file explorer:

- **macOS/Linux**: double-click `Start Test-01.command`
- **Windows**: double-click `Start Test-01.bat`

If prompted by OS security controls, allow local execution for this file.

---

## First-run behavior

On first launch, the app performs initial local setup automatically:

1. **Database initialization**
   - Creates local SQLite DB at `./data/app.db`.
   - Applies schema migrations.
2. **Folder bootstrap**
   - Creates required folders if missing:
     - `./data/inbox/`
     - `./data/processed/`
     - `./data/exports/`
     - `./data/rules/`
     - `./logs/`
3. **Sample processing check**
   - Copies sample files from `./samples/input/` to `./data/inbox/` (if inbox is empty).
   - Runs one sample extraction to validate OCR/parsing pipeline.
   - Writes sample output to `./data/processed/`.

You should see a "Setup complete" status in the UI once this is done.

---

## Core workflow: upload, correct, export

### 1) Upload files

- Use **Upload** in the UI to add PDFs/images/CSVs.
- Or copy files directly into `./data/inbox/` and click **Refresh**.

### 2) Review and correct extraction

- Open a processed record.
- Compare source preview vs extracted fields.
- Edit incorrect fields and click **Save Correction**.
- Corrections are stored locally and linked to the record.

### 3) Export results

- Select one or more corrected records.
- Click **Export** and choose format:
  - `CSV`
  - `JSON`
  - `XLSX`
- Exports are written to `./data/exports/`.

---

## Learning-rule workflow and rule management

Rules let the app learn recurring patterns from your corrections.

### Rule lifecycle

1. **Draft**
   - A new correction can be promoted to a draft rule.
2. **Validate**
   - Run draft rules against recent documents and review hit/miss metrics.
3. **Activate**
   - Enable validated rules for future processing.
4. **Monitor**
   - Track rule precision and false positives.
5. **Retire**
   - Disable outdated rules without deleting historical audit links.

### Rule management actions

From **Settings → Rules**:

- Create rule from correction
- Edit pattern/target field
- Enable/disable rule
- Reorder priority
- Clone rule
- Export/import rules (`.json`) via `./data/rules/`

### Recommended operating pattern

- Promote only repeated corrections to rules.
- Validate on a representative sample before activation.
- Keep high-specificity rules above broad fallback rules.

---

## Sample input/output locations

Use these default local paths:

- **Sample inputs**: `./samples/input/`
- **User uploads (inbox)**: `./data/inbox/`
- **Processed structured outputs**: `./data/processed/`
- **Manual/automated exports**: `./data/exports/`
- **Rule definitions**: `./data/rules/`
- **Logs**: `./logs/`

---

## Local-only architecture and no-cloud guarantees

`test-01` is designed to run completely on your machine/network.

### Architecture notes

- Frontend and backend run on localhost.
- Database is local SQLite (`./data/app.db`).
- Files remain in local project directories.
- Rules, logs, and exports are local filesystem artifacts.

### No-cloud guarantees

- No required cloud API dependencies for standard operation.
- No automatic upload of documents, metadata, or exports.
- No telemetry egress by default.
- Works offline after dependencies are installed.

> Optional enterprise integrations (if manually enabled by administrators) should be treated separately from default local mode.

---

## Troubleshooting matrix

| Symptom | Likely cause | How to diagnose | Resolution |
|---|---|---|---|
| App won’t start | Version mismatch | Run `python --version`, `node --version` | Install exact versions listed above and restart |
| Blank UI page | Frontend dev server not running | Check terminal for frontend process | Restart with `./start.sh`; ensure port `8080` free |
| "Database locked" error | Stale process holding SQLite file | Check running app processes | Stop all app processes, then relaunch |
| Upload fails | Unsupported file type/permissions | Check file extension and permissions | Use supported formats and ensure read access |
| Extraction quality poor | OCR/rule mismatch | Review logs in `./logs/` and sample output | Correct fields, then create/adjust rules |
| Corrections not saved | DB write permission issue | Try creating a test file in `./data/` | Fix directory permissions |
| Export file missing | Export job failed or wrong filter | Check export status and logs | Re-run export with confirmed selection |
| Rules not applied | Rule disabled/low priority | Inspect rule status/order in Rules panel | Enable rule and move higher priority |
| First run hangs | Corrupt prior local state | Review logs and startup output | Backup then remove `./data/app.db`; restart |
| Port already in use | Another service bound to same port | Run `lsof -i :8080` (or OS equivalent) | Stop conflicting process or change app port |

---

## Quick verification checklist

After setup, confirm:

- App opens on `http://127.0.0.1:8080`
- First-run setup completes without error
- A sample file can be processed
- A corrected record can be exported
- Rule creation and activation works

If all checks pass, the local workflow is ready for production-like use.
