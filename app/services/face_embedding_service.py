from __future__ import annotations

import json

import numpy as np
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.user import User


# ============================================================
# FACE EMBEDDING SETTINGS
# ============================================================

FACE_MODEL_NAME = "w600k_r50"
FACE_EMBEDDING_DIMENSIONS = 512

# InsightFace / ArcFace starting threshold.
#
# This matches the threshold previously used by the
# server-side InsightFace verification implementation.
#
# Calibrate using real student data later if necessary.
FACE_MATCH_THRESHOLD = 0.45


# ============================================================
# NORMALIZE ENUM
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
            "user_id":
                current_user.user_id,
        },
    ).scalar()

    if student_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found.",
        )

    return int(student_id)


# ============================================================
# NORMALIZE RECEIVED EMBEDDING
# ============================================================

def _normalize_embedding(
    embedding: list[float],
    model_name: str,
) -> np.ndarray:

    clean_model_name = (
        model_name.strip()
    )

    # --------------------------------------------------------
    # VERIFY MODEL
    # --------------------------------------------------------

    if clean_model_name != FACE_MODEL_NAME:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Unsupported face embedding model. "
                f"Expected '{FACE_MODEL_NAME}'."
            ),
        )

    # --------------------------------------------------------
    # VERIFY LENGTH
    # --------------------------------------------------------

    if len(embedding) != FACE_EMBEDDING_DIMENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Invalid face embedding dimensions. "
                f"Expected {FACE_EMBEDDING_DIMENSIONS}, "
                f"received {len(embedding)}."
            ),
        )

    # --------------------------------------------------------
    # CONVERT TO NUMPY
    # --------------------------------------------------------

    try:
        vector = np.asarray(
            embedding,
            dtype=np.float32,
        ).reshape(-1)

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Face embedding could not "
                f"be processed: {exc}"
            ),
        )

    # --------------------------------------------------------
    # VERIFY DIMENSIONS AGAIN
    # --------------------------------------------------------

    if vector.size != FACE_EMBEDDING_DIMENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Invalid face embedding dimensions. "
                f"Expected {FACE_EMBEDDING_DIMENSIONS}."
            ),
        )

    # --------------------------------------------------------
    # FINITE VALUES
    # --------------------------------------------------------

    if not np.all(
        np.isfinite(vector)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Face embedding contains "
                "invalid numeric values."
            ),
        )

    # --------------------------------------------------------
    # L2 NORMALIZE
    # --------------------------------------------------------

    norm = float(
        np.linalg.norm(vector)
    )

    if (
        not np.isfinite(norm)
        or norm <= 1e-12
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Face embedding has "
                "invalid magnitude."
            ),
        )

    return vector / norm


# ============================================================
# VERIFY ACTIVE SESSION
# ============================================================

def _verify_active_session(
    attendance,
) -> None:

    session_status = _normalize_enum_value(
        attendance["session_status"]
    )

    if session_status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Attendance session "
                "is no longer active."
            ),
        )

    if attendance["ended_at"] is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Attendance session "
                "has already ended."
            ),
        )


# ============================================================
# LOAD STORED FACE EMBEDDING
# ============================================================

def _load_registered_embedding(
    registered,
) -> np.ndarray:

    # --------------------------------------------------------
    # MODEL
    # --------------------------------------------------------

    stored_model = (
        registered["embedding_model"]
        or ""
    )

    if stored_model != FACE_MODEL_NAME:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Your face profile was created "
                "using a different face model. "
                "Please register your face again."
            ),
        )

    # --------------------------------------------------------
    # DIMENSIONS
    # --------------------------------------------------------

    stored_dimensions = (
        int(
            registered[
                "embedding_dimensions"
            ]
        )
        if registered[
            "embedding_dimensions"
        ] is not None
        else 0
    )

    if (
        stored_dimensions
        != FACE_EMBEDDING_DIMENSIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Stored face embedding dimensions "
                "are incompatible. "
                "Please register your face again."
            ),
        )

    # --------------------------------------------------------
    # JSON -> NUMPY
    # --------------------------------------------------------

    try:
        raw_embedding = json.loads(
            registered[
                "face_embedding"
            ]
        )

        vector = np.asarray(
            raw_embedding,
            dtype=np.float32,
        ).reshape(-1)

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Stored face embedding "
                "is invalid."
            ),
        )

    # --------------------------------------------------------
    # VERIFY SIZE
    # --------------------------------------------------------

    if (
        vector.size
        != FACE_EMBEDDING_DIMENSIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Stored face embedding "
                "dimensions are invalid."
            ),
        )

    # --------------------------------------------------------
    # VERIFY FINITE
    # --------------------------------------------------------

    if not np.all(
        np.isfinite(vector)
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Stored face embedding contains "
                "invalid numeric values."
            ),
        )

    # --------------------------------------------------------
    # NORMALIZE AGAIN
    # --------------------------------------------------------

    norm = float(
        np.linalg.norm(vector)
    )

    if (
        not np.isfinite(norm)
        or norm <= 1e-12
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Stored face embedding "
                "has invalid magnitude."
            ),
        )

    return vector / norm


# ============================================================
# VERIFY ATTENDANCE FACE EMBEDDING
# ============================================================

def verify_student_face_embedding(
    db: Session,
    current_user: User,
    attendance_id: int,
    embedding: list[float],
    model_name: str,
) -> dict:

    # --------------------------------------------------------
    # 1. STUDENT
    # --------------------------------------------------------

    student_id = _get_student_id(
        db=db,
        current_user=current_user,
    )

    # --------------------------------------------------------
    # 2. CURRENT EMBEDDING
    # --------------------------------------------------------

    current_embedding = _normalize_embedding(
        embedding=embedding,
        model_name=model_name,
    )

    # --------------------------------------------------------
    # 3. ATTENDANCE RECORD
    # --------------------------------------------------------

    attendance = db.execute(
        text(
            """
            SELECT
                ar.attendance_id,
                ar.session_id,
                ar.student_id,

                ar.qr_verified,
                ar.geofence_verified,
                ar.face_verified,
                ar.liveness_verified,

                ar.attendance_status,

                ats.subject_id,
                ats.section_id,
                ats.classroom_id,

                ats.session_status,
                ats.ended_at,

                s.subject_name,
                sec.section_name

            FROM attendance_records ar

            INNER JOIN attendance_sessions ats
                ON ats.session_id =
                    ar.session_id

            INNER JOIN subjects s
                ON s.subject_id =
                    ats.subject_id

            INNER JOIN sections sec
                ON sec.section_id =
                    ats.section_id

            WHERE
                ar.attendance_id =
                    :attendance_id

                AND ar.student_id =
                    :student_id

            LIMIT 1
            """
        ),
        {
            "attendance_id":
                attendance_id,

            "student_id":
                student_id,
        },
    ).mappings().first()

    if attendance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance record not found.",
        )

    # --------------------------------------------------------
    # 4. SESSION
    # --------------------------------------------------------

    _verify_active_session(
        attendance
    )

    # --------------------------------------------------------
    # 5. ATTENDANCE STATE
    # --------------------------------------------------------

    attendance_status = _normalize_enum_value(
        attendance[
            "attendance_status"
        ]
    )

    if attendance_status == "REJECTED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This attendance attempt "
                "has already been rejected."
            ),
        )

    if attendance_status == "PRESENT":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Attendance has already "
                "been marked present."
            ),
        )

    if attendance_status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Attendance is not in a valid "
                "state for face verification."
            ),
        )

    # --------------------------------------------------------
    # QR
    # --------------------------------------------------------

    if not bool(
        attendance["qr_verified"]
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "QR verification must "
                "be completed first."
            ),
        )

    # --------------------------------------------------------
    # GEOFENCE
    # --------------------------------------------------------

    if not bool(
        attendance[
            "geofence_verified"
        ]
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Geofence verification must "
                "be completed first."
            ),
        )

    # --------------------------------------------------------
    # FACE ALREADY VERIFIED
    # --------------------------------------------------------

    if bool(
        attendance["face_verified"]
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Face verification has "
                "already been completed."
            ),
        )

    # --------------------------------------------------------
    # 6. REGISTERED FACE PROFILE
    # --------------------------------------------------------

    registered = db.execute(
        text(
            """
            SELECT
                face_profile_id,
                face_embedding,
                embedding_model,
                embedding_dimensions,
                is_verified,
                is_active

            FROM student_face_profiles

            WHERE student_id =
                :student_id

            LIMIT 1
            """
        ),
        {
            "student_id":
                student_id,
        },
    ).mappings().first()

    if registered is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Face profile is not registered. "
                "Please register your face first."
            ),
        )

    if not bool(
        registered["is_active"]
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Your face profile is inactive."
            ),
        )

    if not bool(
        registered["is_verified"]
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Registered face profile "
                "is not verified."
            ),
        )

    # --------------------------------------------------------
    # 7. LOAD REGISTERED EMBEDDING
    # --------------------------------------------------------

    registered_embedding = (
        _load_registered_embedding(
            registered
        )
    )

    # --------------------------------------------------------
    # 8. COSINE SIMILARITY
    #
    # Both embeddings are already L2-normalized,
    # therefore dot product == cosine similarity.
    # --------------------------------------------------------

    similarity = float(
        np.dot(
            registered_embedding,
            current_embedding,
        )
    )

    if not np.isfinite(similarity):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Face similarity calculation "
                "produced an invalid result."
            ),
        )

    # Floating-point rounding can theoretically
    # produce tiny values outside [-1, 1].
    similarity = max(
        -1.0,
        min(
            1.0,
            similarity,
        ),
    )

    matched = (
        similarity
        >= FACE_MATCH_THRESHOLD
    )

    # --------------------------------------------------------
    # 9. FACE FAILED
    # --------------------------------------------------------

    if not matched:

        result = db.execute(
            text(
                """
                UPDATE attendance_records

                SET
                    face_verified = 0,

                    attendance_status =
                        'REJECTED',

                    rejection_reason =
                        'Face verification failed.'

                WHERE
                    attendance_id =
                        :attendance_id

                    AND student_id =
                        :student_id

                    AND attendance_status =
                        'PENDING'

                    AND face_verified = 0

                    AND EXISTS (
                        SELECT 1

                        FROM attendance_sessions ats

                        WHERE
                            ats.session_id =
                                attendance_records.session_id

                            AND ats.session_status =
                                'ACTIVE'

                            AND ats.ended_at IS NULL
                    )
                """
            ),
            {
                "attendance_id":
                    attendance_id,

                "student_id":
                    student_id,
            },
        )

        if result.rowcount != 1:
            db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Face verification could not "
                    "be saved because the attendance "
                    "state changed."
                ),
            )

        db.commit()

        return {
            "attendance_id":
                attendance_id,

            "session_id":
                int(
                    attendance[
                        "session_id"
                    ]
                ),

            "student_id":
                student_id,

            "subject_id":
                int(
                    attendance[
                        "subject_id"
                    ]
                ),

            "subject_name":
                attendance[
                    "subject_name"
                ],

            "section_id":
                int(
                    attendance[
                        "section_id"
                    ]
                ),

            "section_name":
                attendance[
                    "section_name"
                ],

            "classroom_id":
                int(
                    attendance[
                        "classroom_id"
                    ]
                ),

            "face_verified":
                False,

            "face_similarity":
                round(
                    similarity,
                    4,
                ),

            "attendance_status":
                "REJECTED",

            "rejection_reason":
                "Face verification failed.",

            "next_verification_step":
                None,
        }

    # --------------------------------------------------------
    # 10. FACE SUCCESS
    # --------------------------------------------------------

    result = db.execute(
        text(
            """
            UPDATE attendance_records

            SET
                face_verified = 1,
                rejection_reason = NULL

            WHERE
                attendance_id =
                    :attendance_id

                AND student_id =
                    :student_id

                AND attendance_status =
                    'PENDING'

                AND qr_verified = 1

                AND geofence_verified = 1

                AND face_verified = 0

                AND EXISTS (
                    SELECT 1

                    FROM attendance_sessions ats

                    WHERE
                        ats.session_id =
                            attendance_records.session_id

                        AND ats.session_status =
                            'ACTIVE'

                        AND ats.ended_at IS NULL
                )
            """
        ),
        {
            "attendance_id":
                attendance_id,

            "student_id":
                student_id,
        },
    )

    if result.rowcount != 1:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Face verification could not "
                "be saved because the attendance "
                "state changed."
            ),
        )

    db.commit()

    # --------------------------------------------------------
    # 11. RESPONSE
    # --------------------------------------------------------

    return {
        "attendance_id":
            attendance_id,

        "session_id":
            int(
                attendance[
                    "session_id"
                ]
            ),

        "student_id":
            student_id,

        "subject_id":
            int(
                attendance[
                    "subject_id"
                ]
            ),

        "subject_name":
            attendance[
                "subject_name"
            ],

        "section_id":
            int(
                attendance[
                    "section_id"
                ]
            ),

        "section_name":
            attendance[
                "section_name"
            ],

        "classroom_id":
            int(
                attendance[
                    "classroom_id"
                ]
            ),

        "face_verified":
            True,

        "face_similarity":
            round(
                similarity,
                4,
            ),

        "attendance_status":
            "PENDING",

        "rejection_reason":
            None,

        "next_verification_step":
            "LIVENESS",
    }