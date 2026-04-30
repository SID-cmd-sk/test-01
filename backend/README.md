# backend

Local API service on localhost for orchestration.

## Responsibilities
- Validate incoming DTOs against JSON schemas.
- Manage job lifecycle: queue -> run -> complete/fail/cancel.
- Coordinate processing, learning, and cad modules.
- Persist status/errors and artifact metadata in SQLite.

## Interfaces
- Public REST API defined in `../contracts/openapi.yaml`.
- Internal interfaces: `ProcessingService`, `CadService`, `LearningService`, `StorageRepository`.
