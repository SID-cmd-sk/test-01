from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    EMPTY_FILE = "EMPTY_FILE"
    MALFORMED_FILE = "MALFORMED_FILE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    MULTIPAGE_PARTIAL_EXTRACTION = "MULTIPAGE_PARTIAL_EXTRACTION"
    LOW_QUALITY_SCAN = "LOW_QUALITY_SCAN"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    PLUGIN_FAILURE = "PLUGIN_FAILURE"
    STAGE_CRASH = "STAGE_CRASH"
    UNKNOWN = "UNKNOWN"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(slots=True)
class AppError(Exception):
    code: ErrorCode
    user_message: str
    technical_message: str
    severity: Severity = Severity.ERROR
    retryable: bool = False
    stage: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_status_payload(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "severity": self.severity.value,
            "retryable": self.retryable,
            "stage": self.stage,
            "message": self.user_message,
            "details": self.details,
        }


class RecoverableStageError(AppError):
    def __init__(self, **kwargs: Any):
        super().__init__(retryable=True, **kwargs)
