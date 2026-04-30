from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Stage(str, Enum):
    INGEST = "ingest"
    PREPROCESS = "preprocess"
    GEOMETRY = "geometry_detection"
    OCR = "ocr_dimension_parsing"
    RECONSTRUCT = "vector_reconstruction"
    EXPORT = "export"


STAGE_ORDER = [
    Stage.INGEST,
    Stage.PREPROCESS,
    Stage.GEOMETRY,
    Stage.OCR,
    Stage.RECONSTRUCT,
    Stage.EXPORT,
]


@dataclass(frozen=True)
class JobConfig:
    input_pdf: str
    output_dir: str
    dpi: int = 300
    denoise_strength: int = 2
    adaptive_threshold_block: int = 31
    adaptive_threshold_bias: int = 7
    snap_tolerance: float = 1.25
    collinearity_angle_tolerance: float = 1.0
    random_seed: int = 42


@dataclass
class StageResult:
    stage: Stage
    payload: dict[str, Any]


@dataclass
class JobState:
    config_hash: str
    completed_stages: list[str] = field(default_factory=list)


class ProcessingPipeline:
    def __init__(self, config: JobConfig):
        self.config = config
        self.out_dir = Path(config.output_dir)
        self.state_file = self.out_dir / "state.json"
        self.stage_dir = self.out_dir / "stages"

    def run(self) -> None:
        self._prepare_dirs()
        state = self._load_state()

        for stage in STAGE_ORDER:
            if stage.value in state.completed_stages:
                continue

            result = self._run_stage(stage)
            self._save_stage_result(result)
            state.completed_stages.append(stage.value)
            self._save_state(state)

    def _prepare_dirs(self) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.stage_dir.mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> JobState:
        expected_hash = self._config_hash()
        if not self.state_file.exists():
            return JobState(config_hash=expected_hash)

        state_data = json.loads(self.state_file.read_text())
        if state_data.get("config_hash") != expected_hash:
            return JobState(config_hash=expected_hash)

        return JobState(**state_data)

    def _save_state(self, state: JobState) -> None:
        self.state_file.write_text(json.dumps(asdict(state), indent=2, sort_keys=True))

    def _config_hash(self) -> str:
        encoded = json.dumps(asdict(self.config), sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _run_stage(self, stage: Stage) -> StageResult:
        if stage == Stage.INGEST:
            return StageResult(stage=stage, payload=self._run_ingest())
        if stage == Stage.PREPROCESS:
            return StageResult(stage=stage, payload=self._run_preprocess())
        if stage == Stage.GEOMETRY:
            return StageResult(stage=stage, payload=self._run_geometry_detection())
        if stage == Stage.OCR:
            return StageResult(stage=stage, payload=self._run_ocr_dimension_parsing())
        if stage == Stage.RECONSTRUCT:
            return StageResult(stage=stage, payload=self._run_vector_reconstruction())
        if stage == Stage.EXPORT:
            return StageResult(stage=stage, payload=self._run_export())
        raise ValueError(f"Unsupported stage: {stage}")

    def _save_stage_result(self, stage_result: StageResult) -> None:
        stage_file = self.stage_dir / f"{stage_result.stage.value}.json"
        stage_file.write_text(json.dumps(stage_result.payload, indent=2, sort_keys=True))

    def _read_stage_payload(self, stage: Stage) -> dict[str, Any]:
        return json.loads((self.stage_dir / f"{stage.value}.json").read_text())

    def _run_ingest(self) -> dict[str, Any]:
        """Ingest stage.

        Performs page splitting metadata, vector-vs-scanned heuristics, and
        rasterization fallback planning.
        """
        pdf_path = Path(self.config.input_pdf)
        pages = [{"page_index": 0, "source": str(pdf_path)}]

        page_assets = []
        for page in pages:
            # Deterministic, side-effect free heuristic placeholder.
            is_vector = pdf_path.suffix.lower() == ".pdf" and pdf_path.stat().st_size % 2 == 0
            asset = {
                "page_index": page["page_index"],
                "is_vector": is_vector,
                "vector_parse": "planned" if is_vector else "skipped",
                "rasterize_fallback": {
                    "enabled": not is_vector,
                    "dpi": self.config.dpi,
                    "output": f"ingest/page_{page['page_index']:04d}.png",
                },
            }
            page_assets.append(asset)

        return {
            "input_pdf": str(pdf_path),
            "pages": pages,
            "assets": page_assets,
        }

    def _run_preprocess(self) -> dict[str, Any]:
        ingest = self._read_stage_payload(Stage.INGEST)
        operations = []
        for asset in ingest["assets"]:
            operations.append(
                {
                    "page_index": asset["page_index"],
                    "operations": [
                        "grayscale",
                        f"denoise:{self.config.denoise_strength}",
                        (
                            "adaptive_threshold:"
                            f"block={self.config.adaptive_threshold_block},"
                            f"bias={self.config.adaptive_threshold_bias}"
                        ),
                        "deskew_rotation_correction",
                        "artifact_suppression",
                    ],
                    "estimated_skew_degrees": 0.0,
                }
            )

        return {"preprocess": operations}

    def _run_geometry_detection(self) -> dict[str, Any]:
        preprocess = self._read_stage_payload(Stage.PREPROCESS)
        detections = []
        for page in preprocess["preprocess"]:
            detections.append(
                {
                    "page_index": page["page_index"],
                    "entities": {
                        "lines": [{"id": "L1", "confidence": 0.90}],
                        "circles": [{"id": "C1", "confidence": 0.87}],
                        "arcs": [{"id": "A1", "confidence": 0.83}],
                        "polylines": [{"id": "P1", "confidence": 0.88}],
                        "contours": [{"id": "K1", "confidence": 0.76}],
                    },
                }
            )

        return {"geometry_detection": detections}

    def _run_ocr_dimension_parsing(self) -> dict[str, Any]:
        geometry = self._read_stage_payload(Stage.GEOMETRY)
        pages = []
        for page in geometry["geometry_detection"]:
            pages.append(
                {
                    "page_index": page["page_index"],
                    "ocr_engine": "local",
                    "recognized": [
                        {"text": "R10", "class": "dimension", "leader": True},
                        {"text": "NOTE A", "class": "text", "leader": False},
                    ],
                }
            )

        return {"ocr_dimension_parsing": pages}

    def _run_vector_reconstruction(self) -> dict[str, Any]:
        geometry = self._read_stage_payload(Stage.GEOMETRY)
        reconstructed = []
        for page in geometry["geometry_detection"]:
            reconstructed.append(
                {
                    "page_index": page["page_index"],
                    "steps": [
                        f"snapping:{self.config.snap_tolerance}",
                        f"collinearity_merge:{self.config.collinearity_angle_tolerance}",
                        "arc_circle_fitting",
                        "topology_cleanup",
                    ],
                    "uncertain_entities": ["K1"],
                }
            )

        return {"vector_reconstruction": reconstructed}

    def _run_export(self) -> dict[str, Any]:
        output_dxf = self.out_dir / "output.dxf"
        output_dxf.write_text(
            "\n".join(
                [
                    "0", "SECTION", "2", "TABLES", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES", "0", "ENDSEC", "0", "EOF"
                ]
            )
        )

        return {
            "dxf": str(output_dxf),
            "layers": ["GEOMETRY", "TEXT", "DIMENSIONS", "UNCERTAIN"],
        }
