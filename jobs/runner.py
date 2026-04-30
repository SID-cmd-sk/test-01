from __future__ import annotations

from pathlib import Path
from typing import Callable

from backend.errors import AppError, ErrorCode, RecoverableStageError
from backend.ingestion import parse_pdf_pages, validate_input_file
from backend.logging_utils import configure_structured_logging, log_event
from jobs.state import JobStage, JobState, StateStore


def run_job(
    job_id: str,
    source_file: Path,
    total_pages: int,
    extracted_pages: int,
    plugin: Callable[[], None] | None = None,
    retry_from_stage: JobStage | None = None,
) -> JobState:
    logger = configure_structured_logging()
    store = StateStore()
    state = store.load(job_id)

    if retry_from_stage:
        state.current_stage = retry_from_stage

    stages = [JobStage.INGEST, JobStage.EXTRACT, JobStage.OCR_FALLBACK, JobStage.TRANSFORM]
    start_index = stages.index(state.current_stage)

    for stage in stages[start_index:]:
        state.current_stage = stage
        store.save(state)
        log_event(logger, "stage_start", job_id=job_id, stage=stage.value)
        try:
            if stage == JobStage.INGEST:
                validate_input_file(source_file)
            elif stage == JobStage.EXTRACT:
                parse_pdf_pages(total_pages, extracted_pages)
            elif stage == JobStage.OCR_FALLBACK and extracted_pages == 0:
                state.artifacts.append(f"logs/{job_id}_ocr_fallback.txt")
            elif stage == JobStage.TRANSFORM and plugin:
                plugin()

            state.completed_stages.append(stage.value)
            store.save(state)
            log_event(logger, "stage_success", job_id=job_id, stage=stage.value)

        except RecoverableStageError as err:
            state.errors.append(err.to_status_payload())
            state.artifacts.append(f"logs/{job_id}_{stage.value}_partial.json")
            store.save(state)
            log_event(
                logger,
                "stage_recoverable_error",
                job_id=job_id,
                stage=stage.value,
                error=err.to_status_payload(),
            )
            if stage == JobStage.EXTRACT:
                continue

        except Exception as err:
            app_error = (
                err
                if isinstance(err, AppError)
                else AppError(
                    code=ErrorCode.PLUGIN_FAILURE,
                    user_message="A processing component failed. Please retry.",
                    technical_message=str(err),
                    stage=stage.value,
                    retryable=True,
                )
            )
            state.errors.append(app_error.to_status_payload())
            state.artifacts.append(f"logs/{job_id}_{stage.value}_crash.json")
            store.save(state)
            log_event(
                logger,
                "stage_crash",
                job_id=job_id,
                stage=stage.value,
                error=app_error.to_status_payload(),
            )
            break

    if len(state.completed_stages) == len(stages):
        state.current_stage = JobStage.COMPLETE
        store.save(state)
        log_event(logger, "job_complete", job_id=job_id)
    return state


def build_status_panel(state: JobState) -> dict:
    return {
        "job_id": state.job_id,
        "current_stage": state.current_stage.value,
        "completed_stages": state.completed_stages,
        "errors": state.errors,
        "artifacts": state.artifacts,
        "user_message": "Processing completed." if not state.errors else "Completed with warnings/errors. See details.",
    }
