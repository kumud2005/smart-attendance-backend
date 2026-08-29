import math
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)


class FaceEmbeddingRequest(BaseModel):
    embedding: list[float] = Field(
        ...,
        min_length=512,
        max_length=512,
    )

    model_name: Literal["w600k_r50"]

    @field_validator("embedding")
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
                "Face embedding contains "
                "invalid numeric values."
            )

        if not any(
            abs(item) > 1e-12
            for item in value
        ):
            raise ValueError(
                "Face embedding cannot "
                "be a zero vector."
            )

        return value