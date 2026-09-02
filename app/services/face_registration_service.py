from __future__ import annotations

import json
from datetime import datetime

import numpy as np
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.user import User


# ============================================================
# FACE EMBEDDING SETTINGS
# ============================================================

_FACE_MODEL_NAME = "w600k_r50"
_FACE_EMBEDDING_DIMENSIONS = 512


# ============================================================
# NORMALIZE ENUM VALUE
# ============================================================

def _normalize_enum_value(
    value,
) -> str:
    if value is None:
        return ""

    result = str(value).upper()

    if "." in result:
        result = result.split(".")[-1]

    return result


# ============================================================
# VERIFY STUDENT
# ============================================================

def _verify_student(
    current_user: User,
) -> None:
    if current_user.role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User role is not configured.",
        )

    role_name = _normalize_enum_value(
        current_user.role.role_name
    )

    if role_name != "STUDENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student access required.",
        )


# ============================================================
# GET STUDENT ID
# ============================================================

def _get_student_id(
    db: Session,
    current_user: User,
) -> int:
    _verify_student(current_user)

    student_id = db.execute(
        text(
            """
            SELECT
                student_id
            FROM student_profiles
            WHERE user_id = :user_id
            LIMIT 1
            """
        ),
        {
            "user_id": current_user.user_id,
        },
    ).scalar()

    if student_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found.",
        )

    return int(student_id)


# ============================================================
# VALIDATE + NORMALIZE EMBEDDING
# ============================================================

def _prepare_embedding(
    face_embedding: list[float],
    embedding_dimensions: int,
    model_name: str,
) -> np.ndarray:

    clean_model_name = model_name.strip()

    # --------------------------------------------------------
    # MODEL
    # --------------------------------------------------------

    if clean_model_name != _FACE_MODEL_NAME:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Unsupported face embedding model. "
                f"Expected '{_FACE_MODEL_NAME}'."
            ),
        )

    # --------------------------------------------------------
    # DECLARED DIMENSIONS
    # --------------------------------------------------------

    if (
        embedding_dimensions
        != _FACE_EMBEDDING_DIMENSIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Invalid embedding dimensions. "
                f"Expected {_FACE_EMBEDDING_DIMENSIONS}."
            ),
        )

    # --------------------------------------------------------
    # ACTUAL VECTOR LENGTH
    # --------------------------------------------------------

    if (
        len(face_embedding)
        != _FACE_EMBEDDING_DIMENSIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Face embedding must contain exactly "
                f"{_FACE_EMBEDDING_DIMENSIONS} values."
            ),
        )

    # --------------------------------------------------------
    # NUMPY
    # --------------------------------------------------------

    try:
        embedding = np.asarray(
            face_embedding,
            dtype=np.float32,
        ).reshape(-1)

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Face embedding could not be processed: "
                f"{exc}"
            ),
        )

    # --------------------------------------------------------
    # DIMENSION CHECK
    # --------------------------------------------------------

    if (
        embedding.size
        != _FACE_EMBEDDING_DIMENSIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Face embedding has invalid dimensions."
            ),
        )

    # --------------------------------------------------------
    # FINITE VALUES
    # --------------------------------------------------------

    if not np.all(
        np.isfinite(embedding)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Face embedding contains invalid "
                "numeric values."
            ),
        )

    # --------------------------------------------------------
    # L2 NORMALIZE SERVER-SIDE
    # --------------------------------------------------------

    norm = float(
        np.linalg.norm(
            embedding
        )
    )

    if (
        not np.isfinite(norm)
        or norm <= 1e-12
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Face embedding is invalid.",
        )

    return embedding / norm


# ============================================================
# REGISTER STUDENT FACE
# ============================================================

def register_student_face(
    db: Session,
    current_user: User,
    face_embedding: list[float],
    embedding_dimensions: int,
    model_name: str,
) -> dict:
    """
    Register the authenticated student's locally-generated face embedding.

    Existing face profiles cannot be replaced by the Student. An Admin
    must delete/reset the old face profile first.

    No face photograph is uploaded.

    Flutter generates:

        camera frame
            ->
        det_10g.onnx
            ->
        5 face landmarks
            ->
        ArcFace alignment
            ->
        w600k_r50.onnx
            ->
        normalized 512D embedding

    Only the numeric embedding is transmitted.
    """

    # --------------------------------------------------------
    # 1. STUDENT
    # --------------------------------------------------------

    student_id = _get_student_id(
        db=db,
        current_user=current_user,
    )

    # --------------------------------------------------------
    # 2. VALIDATE + NORMALIZE EMBEDDING
    # --------------------------------------------------------

    embedding = _prepare_embedding(
        face_embedding=face_embedding,
        embedding_dimensions=embedding_dimensions,
        model_name=model_name,
    )

    embedding_json = json.dumps(
        [
            float(value)
            for value in embedding
        ]
    )

    now = datetime.now()

    # --------------------------------------------------------
    # 3. CHECK EXISTING PROFILE
    # --------------------------------------------------------

    existing = db.execute(
        text(
            """
            SELECT
                face_profile_id

            FROM student_face_profiles

            WHERE student_id = :student_id

            LIMIT 1
            """
        ),
        {
            "student_id": student_id,
        },
    ).mappings().first()

    # --------------------------------------------------------
    # 4. BLOCK STUDENT-SIDE REPLACEMENT
    # --------------------------------------------------------

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A face profile is already registered for this student. "
                "Contact an administrator to reset/delete the existing "
                "face profile before registering again."
            ),
        )

    # --------------------------------------------------------
    # 5. INSERT NEW FACE PROFILE
    # --------------------------------------------------------

    try:
        result = db.execute(
            text(
                """
                INSERT INTO student_face_profiles (
                    student_id,
                    face_embedding,
                    embedding_model,
                    embedding_dimensions,
                    is_verified,
                    is_active,
                    created_at,
                    updated_at
                )
                VALUES (
                    :student_id,
                    :face_embedding,
                    :embedding_model,
                    :embedding_dimensions,
                    1,
                    1,
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                "student_id": student_id,
                "face_embedding": embedding_json,
                "embedding_model": _FACE_MODEL_NAME,
                "embedding_dimensions": _FACE_EMBEDDING_DIMENSIONS,
                "created_at": now,
                "updated_at": now,
            },
        )

        face_profile_id = int(result.lastrowid)
        db.commit()

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Face profile could not be saved: "
                f"{exc}"
            ),
        )

    # --------------------------------------------------------
    # 6. FETCH SAVED PROFILE
    # --------------------------------------------------------

    row = db.execute(
        text(
            """
            SELECT
                face_profile_id,
                student_id,
                embedding_model,
                embedding_dimensions,
                is_verified,
                is_active,
                created_at,
                updated_at

            FROM student_face_profiles

            WHERE
                face_profile_id =
                    :face_profile_id

                AND student_id =
                    :student_id

            LIMIT 1
            """
        ),
        {
            "face_profile_id":
                face_profile_id,

            "student_id":
                student_id,
        },
    ).mappings().first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Face profile was saved but "
                "could not be retrieved."
            ),
        )

    # --------------------------------------------------------
    # 7. RESPONSE
    # --------------------------------------------------------

    return {
        "face_profile_id":
            int(
                row[
                    "face_profile_id"
                ]
            ),

        "student_id":
            int(
                row[
                    "student_id"
                ]
            ),

        "is_verified":
            bool(
                row[
                    "is_verified"
                ]
            ),

        "is_active":
            bool(
                row[
                    "is_active"
                ]
            ),

        "embedding_dimensions":
            int(
                row[
                    "embedding_dimensions"
                ]
            ),

        "created_at":
            row["created_at"],

        "updated_at":
            row["updated_at"],

        "message":
            (
                "Face embedding registration "
                "completed successfully."
            ),
    }


# ============================================================
# GET STUDENT FACE STATUS
# ============================================================

def get_student_face_status(
    db: Session,
    current_user: User,
) -> dict:
    """
    Return face-profile status and the embedding model
    currently associated with the student.

    No embedding and no photograph is returned.
    """

    student_id = _get_student_id(
        db=db,
        current_user=current_user,
    )

    row = db.execute(
        text(
            """
            SELECT
                face_profile_id,
                embedding_model,
                embedding_dimensions,
                is_verified,
                is_active,
                created_at,
                updated_at

            FROM student_face_profiles

            WHERE student_id = :student_id

            LIMIT 1
            """
        ),
        {
            "student_id":
                student_id,
        },
    ).mappings().first()

    # --------------------------------------------------------
    # NOT REGISTERED
    # --------------------------------------------------------

    if row is None:
        return {
            "registered":
                False,

            "face_profile_id":
                None,

            "student_id":
                student_id,

            "embedding_model":
                None,

            "embedding_dimensions":
                None,

            "is_verified":
                False,

            "is_active":
                False,

            "created_at":
                None,

            "updated_at":
                None,
        }

    # --------------------------------------------------------
    # REGISTERED
    # --------------------------------------------------------

    is_active = bool(
        row[
            "is_active"
        ]
    )

    is_verified = bool(
        row[
            "is_verified"
        ]
    )

    return {
        "registered":
            True,

        "face_profile_id":
            int(
                row[
                    "face_profile_id"
                ]
            ),

        "student_id":
            student_id,

        "embedding_model":
            row[
                "embedding_model"
            ],

        "embedding_dimensions": (
            int(
                row[
                    "embedding_dimensions"
                ]
            )
            if row[
                "embedding_dimensions"
            ] is not None
            else None
        ),

        "is_verified":
            is_verified,

        "is_active":
            is_active,

        "created_at":
            row[
                "created_at"
            ],

        "updated_at":
            row[
                "updated_at"
            ],
    }