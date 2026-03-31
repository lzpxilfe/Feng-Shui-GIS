# -*- coding: utf-8 -*-
"""Structured error types for plugin and service boundaries."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class FengShuiErrorCode(str, Enum):
    INPUT_VALIDATION = "input_validation"
    SERVICE_UNAVAILABLE = "service_unavailable"
    ANALYSIS_FAILURE = "analysis_failure"
    COMPARISON_FAILURE = "comparison_failure"
    CALIBRATION_FAILURE = "calibration_failure"
    TERM_EXTRACTION_FAILURE = "term_extraction_failure"
    OUTPUT_GENERATION_FAILURE = "output_generation_failure"
    IO_FAILURE = "io_failure"
    CONFIGURATION_ERROR = "configuration_error"
    UNEXPECTED = "unexpected"


@dataclass(frozen=True)
class FengShuiError(Exception):
    """Domain-aware exception raised from orchestration/service boundaries."""

    code: FengShuiErrorCode
    message: str
    details: Optional[str] = None
    user_message: Optional[str] = None

    def __str__(self) -> str:
        if self.details:
            return f"{self.code.value}: {self.message} ({self.details})"
        return f"{self.code.value}: {self.message}"
