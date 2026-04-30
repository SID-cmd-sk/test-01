# Contracts

Shared, versioned interfaces across UI, backend, and pipeline modules.

## Contents

- `json-schemas/`: Runtime validation schemas for request/response DTOs.
- `openapi.yaml`: API surface for localhost backend service.

## Versioning policy

- Backward-compatible changes: additive fields only.
- Breaking changes: bump major contract version and keep compatibility shim.
