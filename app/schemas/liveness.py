import math
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)


# ============================================================
# LIVENESS FRAME EVIDENCE
# ============================================================

class LivenessFrameEvidenceRequest(BaseModel):
    embedding: list[float] = Field(
        ...,
        min_length=512,
        max_length=512,
    )

    left_eye_open_probability: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    right_eye_open_probability: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    head_yaw: float
    head_pitch: float
    head_roll: float

    detection_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
    )

    @field_validator(
        "embedding",
    )
    @classmethod
    def validate_embedding(
        cls,
        value: list[float],
    ) -> list[float]:

        if not all(
            math.isfinite(item)
            for item in value
        ):
            raise ValueError(
                "Liveness embedding contains "
                "invalid numeric values."
            )

        if not any(
            abs(item) > 1e-12
            for item in value
        ):
            raise ValueError(
                "Liveness embedding cannot "
                "be a zero vector."
            )

        return value

    @field_validator(
        "head_yaw",
        "head_pitch",
        "head_roll",
        "detection_score",
    )
    @classmethod
    def validate_finite_number(
        cls,
        value: float,
    ) -> float:

        if not math.isfinite(value):
            raise ValueError(
                "Liveness evidence contains "
                "an invalid numeric value."
            )

        return value

    @field_validator(
        "left_eye_open_probability",
        "right_eye_open_probability",
    )
    @classmethod
    def validate_optional_probability(
        cls,
        value: float | None,
    ) -> float | None:

        if value is None:
            return None

        if not math.isfinite(value):
            raise ValueError(
                "Eye-open probability is invalid."
            )

        return value


# ============================================================
# LIVENESS REQUEST
# ============================================================

class LivenessVerificationRequest(BaseModel):
    model_name: Literal["w600k_r50"]

    embedding_dimensions: Literal[512]

    neutral: LivenessFrameEvidenceRequest
    blink: LivenessFrameEvidenceRequest
    turn: LivenessFrameEvidenceRequest


# ============================================================
# LIVENESS RESPONSE
# ============================================================

class LivenessVerificationResponse(BaseModel):
    attendance_id: int
    session_id: int
    student_id: int

    liveness_verified: bool

    neutral_face_detected: bool
    blink_detected: bool
    head_turn_detected: bool

    attendance_status: str

    rejection_reason: str | None = None
    next_verification_step: str | None = None