# processing

PDF analysis pipeline.

## Responsibilities
- Ingest PDF bytes from storage path.
- Detect raster/vector/hybrid composition.
- Preprocess pages (deskew, denoise, vector normalize).
- Extract geometry + text into canonical `processing.result.json`.

## Output contract
- Must emit payload conforming to `../contracts/json-schemas/processing.result.json`.
