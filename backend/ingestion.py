from __future__ import annotations

from pathlib import Path

from backend.errors import AppError, ErrorCode, RecoverableStageError, Severity

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024


def validate_input_file(path: Path) -> None:
    if not path.exists() or path.stat().st_size == 0:
        raise AppError(
            code=ErrorCode.EMPTY_FILE,
            user_message="The uploaded file is empty. Please upload a non-empty file.",
            technical_message=f"file missing or zero-size: {path}",
            severity=Severity.ERROR,
            stage="ingest",
        )

    if path.stat().st_size > MAX_FILE_SIZE_BYTES:
        raise AppError(
            code=ErrorCode.FILE_TOO_LARGE,
            user_message="The file is too large to process. Please upload a smaller file.",
            technical_message=f"file exceeds limit: {path}",
            severity=Severity.ERROR,
            stage="ingest",
        )

    if path.suffix.lower() not in {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        raise AppError(
            code=ErrorCode.MALFORMED_FILE,
            user_message="Unsupported or malformed file format.",
            technical_message=f"unsupported extension: {path.suffix}",
            severity=Severity.ERROR,
            stage="ingest",
        )


def parse_pdf_pages(total_pages: int, extracted_pages: int) -> None:
    if extracted_pages == 0:
        raise RecoverableStageError(
            code=ErrorCode.LOW_QUALITY_SCAN,
            user_message="We could not read this scan clearly. Trying fallback OCR.",
            technical_message="0 pages extracted from scan",
            severity=Severity.WARNING,
            stage="extract",
            details={"total_pages": total_pages},
        )
    if extracted_pages < total_pages:
        raise RecoverableStageError(
            code=ErrorCode.MULTIPAGE_PARTIAL_EXTRACTION,
            user_message="Some pages could not be extracted. Continuing with partial results.",
            technical_message="partial extraction",
            severity=Severity.WARNING,
            stage="extract",
            details={"total_pages": total_pages, "extracted_pages": extracted_pages},
        )
