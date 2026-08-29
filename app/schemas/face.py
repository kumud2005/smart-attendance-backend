from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FaceRegistrationRequest(BaseModel):
    face_embedding: list[float] = Field(
        ...,
        min_length=512,
        max_length=512,
    )

    embedding_dimensions: Literal[512]

    model_name: Literal["w600k_r50"]

    @field_validator("face_embedding")
    @classmethod
    def validate_embedding(
        cls,
        value: list[float],
    ) -> list[float]:
        import math

        if not all(
            math.isfinite(item)
            for item in value
        ):
            raise ValueError(
                "Face embedding contains invalid values."
            )

        if not any(
            abs(item) > 1e-12
            for item in value
        ):
            raise ValueError(
                "Face embedding cannot be a zero vector."
            )

        return value


class FaceRegistrationResponse(BaseModel):
    face_profile_id: int
    student_id: int

    is_verified: bool
    is_active: bool

    embedding_dimensions: int

    created_at: datetime
    updated_at: datetime

    message: str

    model_config = ConfigDict(
        from_attributes=True
    )