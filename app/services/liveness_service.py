from __future__ import annotations

import json

import numpy as np
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.liveness import (
    LivenessFrameEvidenceRequest,
    LivenessVerificationRequest,
)


# ============================================================
# LIVENESS SETTINGS
# ============================================================

FACE_MODEL_NAME = "w600k_r50"
FACE_EMBEDDING_DIMENSIONS = 512

# Embedding similarity.
FACE_MATCH_THRESHOLD = 0.45

# Require the same identity across all challenge frames.
FRAME_IDENTITY_THRESHOLD = 0.45

# Local detector already uses 0.60.
MIN_DETECTION_SCORE = 0.60

# Neutral/open-eyes requirement.
NEUTRAL_EYE_OPEN_THRESHOLD = 0.55

# Blink:
#
# blink average eye-open probability
# ----------------------------------
# neutral average eye-open probability
#
# must be <= this ratio.
BLINK_RATIO_THRESHOLD = 0.75

# Turned yaw must move by at least this many degrees
# relative to the neutral frame.
HEAD_TURN_YAW_THRESHOLD = 12.0


# ============================================================
# HELPERS
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
    _verify_student(
        current_user
    )

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

    return int(
        student_id
    )


# ============================================================
# VERIFY ACTIVE SESSION
# ============================================================

def _verify_active_session(
    attendance,
) -> None:
    session_status = _normalize_enum_value(
        attendance[
            "session_status"
        ]
    )

    if (
        session_status != "ACTIVE"
        or attendance["ended_at"] is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This attendance session "
                "is no longer active."
            ),
        )


# ============================================================
# NORMALIZE EMBEDDING
# ============================================================

def _normalize_embedding(
    values: list[float],
) -> np.ndarray:
    if (
        len(values)
        != FACE_EMBEDDING_DIMENSIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Liveness face embedding must contain "
                f"exactly {FACE_EMBEDDING_DIMENSIONS} values."
            ),
        )

    try:
        vector = np.asarray(
            values,
            dtype=np.float32,
        ).reshape(-1)

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Liveness face embedding could "
                f"not be processed: {exc}"
            ),
        )

    if (
        vector.size
        != FACE_EMBEDDING_DIMENSIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Invalid liveness embedding dimensions."
            ),
        )

    if not np.all(
        np.isfinite(vector)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Liveness face embedding contains "
                "invalid numeric values."
            ),
        )

    norm = float(
        np.linalg.norm(
            vector
        )
    )

    if (
        not np.isfinite(norm)
        or norm <= 1e-12
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Liveness face embedding "
                "has invalid magnitude."
            ),
        )

    return vector / norm


# ============================================================
# COSINE SIMILARITY
# ============================================================

def _cosine_similarity(
    first: np.ndarray,
    second: np.ndarray,
) -> float:
    if (
        first.shape
        != second.shape
    ):
        return -1.0

    value = float(
        np.dot(
            first,
            second,
        )
    )

    if not np.isfinite(
        value
    ):
        return -1.0

    return max(
        -1.0,
        min(
            1.0,
            value,
        ),
    )


# ============================================================
# LOAD REGISTERED FACE PROFILE
# ============================================================

def _load_registered_embedding(
    db: Session,
    student_id: int,
) -> np.ndarray:
    registered = db.execute(
        text(
            """
            SELECT
                face_embedding,
                embedding_model,
                embedding_dimensions,
                is_verified,
                is_active

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

    if registered is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Face profile is not registered."
            ),
        )

    if not bool(
        registered[
            "is_active"
        ]
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Face profile is inactive."
            ),
        )

    if not bool(
        registered[
            "is_verified"
        ]
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Registered face profile "
                "is not verified."
            ),
        )

    stored_model = (
        registered[
            "embedding_model"
        ]
        or ""
    )

    if (
        stored_model
        != FACE_MODEL_NAME
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Face profile uses a different "
                "embedding model. Register again."
            ),
        )

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
                "are incompatible. Register again."
            ),
        )

    try:
        values = json.loads(
            registered[
                "face_embedding"
            ]
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Stored face embedding is invalid."
            ),
        )

    return _normalize_embedding(
        values
    )


# ============================================================
# EYE PROBABILITY
# ============================================================

def _average_eye_open_probability(
    frame: LivenessFrameEvidenceRequest,
    *,
    required: bool,
) -> float | None:
    left = frame.left_eye_open_probability
    right = frame.right_eye_open_probability

    if (
        left is None
        or right is None
    ):
        if required:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Eye-open probabilities are required "
                    "for this liveness challenge."
                ),
            )

        return None

    return (
        float(left)
        + float(right)
    ) / 2.0


# ============================================================
# DETECTION QUALITY
# ============================================================

def _verify_detection_score(
    frame_name: str,
    frame: LivenessFrameEvidenceRequest,
) -> None:
    score = float(
        frame.detection_score
    )

    if (
        not np.isfinite(score)
        or score < MIN_DETECTION_SCORE
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"{frame_name} face detection "
                "quality is too low."
            ),
        )


# ============================================================
# REJECT ATTENDANCE
# ============================================================

def _reject_liveness(
    db: Session,
    attendance_id: int,
    student_id: int,
    rejection_reason: str,
) -> None:
    result = db.execute(
        text(
            """
            UPDATE attendance_records ar

            SET
                ar.liveness_verified = 0,
                ar.attendance_status = 'REJECTED',
                ar.rejection_reason = :rejection_reason

            WHERE
                ar.attendance_id = :attendance_id

                AND ar.student_id = :student_id

                AND ar.attendance_status = 'PENDING'

                AND ar.qr_verified = 1

                AND ar.geofence_verified = 1

                AND ar.face_verified = 1

                AND ar.liveness_verified = 0

                AND EXISTS (
                    SELECT 1

                    FROM attendance_sessions ats

                    WHERE
                        ats.session_id =
                            ar.session_id

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

            "rejection_reason":
                rejection_reason,
        },
    )

    if result.rowcount != 1:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Liveness result could not be saved "
                "because the attendance or session "
                "state changed."
            ),
        )

    db.commit()


# ============================================================
# VERIFY LIVENESS
# ============================================================

def verify_liveness(
    db: Session,
    current_user: User,
    attendance_id: int,
    request: LivenessVerificationRequest,
) -> dict:
    # --------------------------------------------------------
    # 1. STUDENT
    # --------------------------------------------------------

    student_id = _get_student_id(
        db=db,
        current_user=current_user,
    )

    # --------------------------------------------------------
    # 2. MODEL CONTRACT
    # --------------------------------------------------------

    if (
        request.model_name
        != FACE_MODEL_NAME
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Unsupported liveness embedding model."
            ),
        )

    if (
        request.embedding_dimensions
        != FACE_EMBEDDING_DIMENSIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Invalid liveness embedding dimensions."
            ),
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

                ats.session_status,
                ats.ended_at

            FROM attendance_records ar

            INNER JOIN attendance_sessions ats
                ON ats.session_id =
                    ar.session_id

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
    # 4. SESSION + ATTENDANCE STATE
    # --------------------------------------------------------

    _verify_active_session(
        attendance
    )

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
                "state for liveness verification."
            ),
        )

    if not bool(
        attendance[
            "qr_verified"
        ]
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "QR verification must "
                "be completed first."
            ),
        )

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

    if not bool(
        attendance[
            "face_verified"
        ]
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Face verification must "
                "be completed first."
            ),
        )

    if bool(
        attendance[
            "liveness_verified"
        ]
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Liveness verification "
                "is already complete."
            ),
        )

    # --------------------------------------------------------
    # 5. DETECTION QUALITY
    # --------------------------------------------------------

    _verify_detection_score(
        "Neutral",
        request.neutral,
    )

    _verify_detection_score(
        "Blink",
        request.blink,
    )

    _verify_detection_score(
        "Head-turn",
        request.turn,
    )

    # --------------------------------------------------------
    # 6. NORMALIZE THREE EMBEDDINGS
    # --------------------------------------------------------

    neutral_embedding = _normalize_embedding(
        request.neutral.embedding
    )

    blink_embedding = _normalize_embedding(
        request.blink.embedding
    )

    turn_embedding = _normalize_embedding(
        request.turn.embedding
    )

    # --------------------------------------------------------
    # 7. REGISTERED IDENTITY
    # --------------------------------------------------------

    registered_embedding = (
        _load_registered_embedding(
            db=db,
            student_id=student_id,
        )
    )

    neutral_registered_similarity = (
        _cosine_similarity(
            registered_embedding,
            neutral_embedding,
        )
    )

    blink_registered_similarity = (
        _cosine_similarity(
            registered_embedding,
            blink_embedding,
        )
    )

    turn_registered_similarity = (
        _cosine_similarity(
            registered_embedding,
            turn_embedding,
        )
    )

    identity_matches_registered = all(
        similarity
        >= FACE_MATCH_THRESHOLD

        for similarity in (
            neutral_registered_similarity,
            blink_registered_similarity,
            turn_registered_similarity,
        )
    )

    # --------------------------------------------------------
    # 8. SAME PERSON ACROSS FRAMES
    # --------------------------------------------------------

    neutral_blink_similarity = (
        _cosine_similarity(
            neutral_embedding,
            blink_embedding,
        )
    )

    neutral_turn_similarity = (
        _cosine_similarity(
            neutral_embedding,
            turn_embedding,
        )
    )

    same_person_across_frames = (
        neutral_blink_similarity
        >= FRAME_IDENTITY_THRESHOLD

        and neutral_turn_similarity
        >= FRAME_IDENTITY_THRESHOLD
    )

    # --------------------------------------------------------
    # 9. BLINK
    # --------------------------------------------------------

    neutral_eye_open = (
        _average_eye_open_probability(
            request.neutral,
            required=True,
        )
    )

    blink_eye_open = (
        _average_eye_open_probability(
            request.blink,
            required=True,
        )
    )

    assert neutral_eye_open is not None
    assert blink_eye_open is not None

    neutral_eyes_open = (
        neutral_eye_open
        >= NEUTRAL_EYE_OPEN_THRESHOLD
    )

    blink_ratio = (
        blink_eye_open
        / max(
            neutral_eye_open,
            1e-6,
        )
    )

    blink_detected = (
        neutral_eyes_open

        and blink_ratio
        <= BLINK_RATIO_THRESHOLD
    )

    # --------------------------------------------------------
    # 10. HEAD TURN
    # --------------------------------------------------------

    neutral_yaw = float(
        request.neutral.head_yaw
    )

    turned_yaw = float(
        request.turn.head_yaw
    )

    yaw_change = abs(
        turned_yaw
        - neutral_yaw
    )

    head_turn_detected = (
        yaw_change
        >= HEAD_TURN_YAW_THRESHOLD
    )

    # --------------------------------------------------------
    # 11. FINAL LIVENESS RESULT
    # --------------------------------------------------------

    liveness_verified = (
        identity_matches_registered
        and same_person_across_frames
        and blink_detected
        and head_turn_detected
    )

    if not liveness_verified:
        reasons: list[str] = []

        if not identity_matches_registered:
            reasons.append(
                "challenge face did not match "
                "the registered student"
            )

        if not same_person_across_frames:
            reasons.append(
                "different identities were detected "
                "between challenge captures"
            )

        if not blink_detected:
            reasons.append(
                "blink challenge was not detected"
            )

        if not head_turn_detected:
            reasons.append(
                "head-turn challenge was not detected"
            )

        rejection_reason = (
            "Liveness verification failed: "
            + ", ".join(
                reasons
            )
            + "."
        )

        _reject_liveness(
            db=db,

            attendance_id=
                attendance_id,

            student_id=
                student_id,

            rejection_reason=
                rejection_reason,
        )

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

            "liveness_verified":
                False,

            "neutral_face_detected":
                True,

            "blink_detected":
                bool(
                    blink_detected
                ),

            "head_turn_detected":
                bool(
                    head_turn_detected
                ),

            "attendance_status":
                "REJECTED",

            "rejection_reason":
                rejection_reason,

            "next_verification_step":
                None,
        }

    # --------------------------------------------------------
    # 12. SUCCESS -> PRESENT
    # --------------------------------------------------------

    result = db.execute(
        text(
            """
            UPDATE attendance_records ar

            SET
                ar.liveness_verified = 1,
                ar.attendance_status = 'PRESENT',
                ar.rejection_reason = NULL

            WHERE
                ar.attendance_id = :attendance_id

                AND ar.student_id = :student_id

                AND ar.qr_verified = 1

                AND ar.geofence_verified = 1

                AND ar.face_verified = 1

                AND ar.liveness_verified = 0

                AND ar.attendance_status = 'PENDING'

                AND EXISTS (
                    SELECT 1

                    FROM attendance_sessions ats

                    WHERE
                        ats.session_id =
                            ar.session_id

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
                "Attendance could not be finalized "
                "because the session or verification "
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

        "liveness_verified":
            True,

        "neutral_face_detected":
            True,

        "blink_detected":
            True,

        "head_turn_detected":
            True,

        "attendance_status":
            "PRESENT",

        "rejection_reason":
            None,

        "next_verification_step":
            None,
    }