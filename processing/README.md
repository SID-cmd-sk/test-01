# processing

PDF analysis pipeline.

## Responsibilities
- Ingest PDF bytes from storage path.
- Detect raster/vector/hybrid composition.
- Preprocess pages (deskew, denoise, vector normalize).
- Extract geometry + text into canonical `processing.result.json`.

## Output contract
- Must emit payload conforming to `../contracts/json-schemas/processing.result.json`.
# Processing Pipeline

Implements staged processing with deterministic resume points:

1. `ingest`: page split metadata, vector/scanned detection, raster fallback plan.
2. `preprocess`: grayscale, denoise, adaptive threshold, deskew/rotation correction, artifact suppression.
3. `geometry_detection`: line/circle/arc/polyline/contour detection with confidence.
4. `ocr_dimension_parsing`: local OCR + text/dimension/leader classification.
5. `vector_reconstruction`: snapping, collinearity merge, arc/circle fitting, topology cleanup.
6. `export`: DXF export with `GEOMETRY`, `TEXT`, `DIMENSIONS`, `UNCERTAIN` layers.

## Resume behavior

- Job state is persisted in `output_dir/state.json`.
- Stage payloads are persisted in `output_dir/stages/<stage>.json`.
- Re-running with the same config hash resumes from the first incomplete stage.
- If config changes, the job restarts from stage 1.
