from __future__ import annotations

import json
from threading import Lock

import cv2
import numpy as np
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.user import User


_FACE_MODEL_NAME = "buffalo_l"
_FACE_DET_SIZE = (640, 640)
_FACE_MATCH_THRESHOLD = 0.45

_face_app = None
_face_lock = Lock()


# ============================================================
# HELPERS
# ============================================================

def _normalize_enum_value(value) -> str:
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
            SELECT student_id
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
# LOAD FACE MODEL
# ============================================================

def _get_face_app():
    global _face_app

    if _face_app is not None:
        return _face_app

    with _face_lock:
        if _face_app is not None:
            return _face_app

        try:
            from insightface.app import FaceAnalysis

            app = FaceAnalysis(
                name=_FACE_MODEL_NAME,
                providers=[
                    "CPUExecutionProvider",
                ],
            )

            app.prepare(
                ctx_id=0,
                det_size=_FACE_DET_SIZE,
            )

            _face_app = app

            return _face_app

        except Exception as exc:
            raise HTTPException(
                status_code=(
                    status.HTTP_503_SERVICE_UNAVAILABLE
                ),
                detail=(
                    "Face recognition model could not "
                    f"be initialized: {exc}"
                ),
            )


# ============================================================
# READ FACE IMAGE
# ============================================================

async def _read_face_image(
    file: UploadFile,
) -> np.ndarray:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Face image is required.",
        )

    allowed_types = {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
    }

    if (
        file.content_type
        and file.content_type.lower()
        not in allowed_types
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
            ),
            detail=(
                "Unsupported image format. "
                "Use JPEG, PNG, or WebP."
            ),
        )

    data = await file.read()

    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded face image is empty.",
        )

    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            ),
            detail=(
                "Face image is too large. "
                "Maximum size is 10 MB."
            ),
        )

    image = cv2.imdecode(
        np.frombuffer(
            data,
            dtype=np.uint8,
        ),
        cv2.IMREAD_COLOR,
    )

    if image is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The uploaded file is not "
                "a valid image."
            ),
        )

    height, width = image.shape[:2]

    if width < 160 or height < 160:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Face image is too small.",
        )

    return image


# ============================================================
# GENERATE FACE EMBEDDING
# ============================================================

def _generate_embedding(
    image: np.ndarray,
) -> np.ndarray:
    try:
        faces = _get_face_app().get(
            image
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Unable to process face image: "
                f"{exc}"
            ),
        )

    if not faces:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "No face detected. Make sure your "
                "full face is visible and well lit."
            ),
        )

    if len(faces) > 1:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Multiple faces detected. Show "
                "only the student's face."
            ),
        )

    embedding = getattr(
        faces[0],
        "normed_embedding",
        None,
    )

    if embedding is None:
        embedding = getattr(
            faces[0],
            "embedding",
            None,
        )

    if embedding is None:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Face embedding could not "
                "be generated."
            ),
        )

    embedding = np.asarray(
        embedding,
        dtype=np.float32,
    ).reshape(-1)

    norm = float(
        np.linalg.norm(
            embedding
        )
    )

    if embedding.size == 0 or norm <= 0:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Generated face embedding "
                "is invalid."
            ),
        )

    return embedding / norm


# ============================================================
# COSINE SIMILARITY
# ============================================================

def _cosine_similarity(
    registered_embedding: np.ndarray,
    current_embedding: np.ndarray,
) -> float:
    registered_norm = float(
        np.linalg.norm(
            registered_embedding
        )
    )

    current_norm = float(
        np.linalg.norm(
            current_embedding
        )
    )

    if (
        registered_norm <= 0
        or current_norm <= 0
    ):
        return 0.0

    return float(
        np.dot(
            registered_embedding
            / registered_norm,
            current_embedding
            / current_norm,
        )
    )


# ============================================================
# VERIFY SESSION IS ACTIVE
# ============================================================

def _verify_active_session(
    attendance,
) -> None:
    session_status = _normalize_enum_value(
        attendance["session_status"]
    )

    if (
        session_status != "ACTIVE"
        or attendance["ended_at"] is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This attendance session is no "
                "longer active."
            ),
        )


# ============================================================
# VERIFY STUDENT FACE
# ============================================================

async def verify_student_face(
    db: Session,
    current_user: User,
    attendance_id: int,
    file: UploadFile,
) -> dict:
    student_id = _get_student_id(
        db=db,
        current_user=current_user,
    )

    # ========================================================
    # 1. GET ATTENDANCE + SESSION
    # ========================================================

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
                ON ats.session_id = ar.session_id

            INNER JOIN subjects s
                ON s.subject_id = ats.subject_id

            INNER JOIN sections sec
                ON sec.section_id = ats.section_id

            WHERE ar.attendance_id = :attendance_id
              AND ar.student_id = :student_id

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

    # ========================================================
    # 2. VERIFY SESSION
    # ========================================================

    _verify_active_session(
        attendance
    )

    # ========================================================
    # 3. VERIFY ATTENDANCE STATE
    # ========================================================

    attendance_status = (
        _normalize_enum_value(
            attendance[
                "attendance_status"
            ]
        )
    )

    if attendance_status == "REJECTED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This attendance attempt has "
                "already been rejected."
            ),
        )

    if attendance_status == "PRESENT":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Attendance has already been "
                "marked present."
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

    # ========================================================
    # 4. VERIFY PREVIOUS STEPS
    # ========================================================

    if not bool(
        attendance["qr_verified"]
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "QR verification must be "
                "completed first."
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

    if bool(
        attendance[
            "face_verified"
        ]
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Face verification has already "
                "been completed."
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
                "Attendance verification has "
                "already been finalized."
            ),
        )

    # ========================================================
    # 5. GET REGISTERED FACE
    # ========================================================

    registered = db.execute(
        text(
            """
            SELECT
                face_profile_id,
                face_embedding,
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

    if (
        registered is None
        or not bool(
            registered["is_active"]
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Face is not registered. "
                "Complete face registration first."
            ),
        )

    if not bool(
        registered["is_verified"]
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Registered face is not verified."
            ),
        )

    # ========================================================
    # 6. LOAD STORED EMBEDDING
    # ========================================================

    try:
        registered_embedding = (
            np.asarray(
                json.loads(
                    registered[
                        "face_embedding"
                    ]
                ),
                dtype=np.float32,
            ).reshape(-1)
        )

    except Exception:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Stored face embedding is invalid."
            ),
        )

    if registered_embedding.size == 0:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Stored face embedding is empty."
            ),
        )

    # ========================================================
    # 7. PROCESS CURRENT IMAGE
    # ========================================================

    image = await _read_face_image(
        file
    )

    current_embedding = (
        _generate_embedding(
            image
        )
    )

    if (
        registered_embedding.shape
        != current_embedding.shape
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Face embedding dimensions "
                "do not match."
            ),
        )

    similarity = _cosine_similarity(
        registered_embedding,
        current_embedding,
    )

    matched = (
        similarity
        >= _FACE_MATCH_THRESHOLD
    )

    # ========================================================
    # 8. FACE FAILED
    # ========================================================

    if not matched:
        result = db.execute(
            text(
                """
                UPDATE attendance_records ar

                SET
                    ar.face_verified = 0,
                    ar.attendance_status = 'REJECTED',
                    ar.rejection_reason = :reason

                WHERE ar.attendance_id = :attendance_id
                  AND ar.student_id = :student_id
                  AND ar.attendance_status = 'PENDING'

                  AND EXISTS (
                      SELECT 1
                      FROM attendance_sessions ats
                      WHERE ats.session_id = ar.session_id
                        AND ats.session_status = 'ACTIVE'
                        AND ats.ended_at IS NULL
                  )
                """
            ),
            {
                "attendance_id":
                    attendance_id,
                "student_id":
                    student_id,
                "reason":
                    "Face verification failed.",
            },
        )

        if result.rowcount != 1:
            db.rollback()

            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "Face verification could not "
                    "be saved because the session "
                    "or attendance state changed."
                ),
            )

        db.commit()

        return {
            "attendance_id":
                int(
                    attendance[
                        "attendance_id"
                    ]
                ),

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

    # ========================================================
    # 9. FACE SUCCESS
    # ========================================================

    result = db.execute(
        text(
            """
            UPDATE attendance_records ar

            SET
                ar.face_verified = 1,
                ar.rejection_reason = NULL

            WHERE ar.attendance_id = :attendance_id
              AND ar.student_id = :student_id
              AND ar.attendance_status = 'PENDING'
              AND ar.qr_verified = 1
              AND ar.geofence_verified = 1
              AND ar.face_verified = 0

              AND EXISTS (
                  SELECT 1
                  FROM attendance_sessions ats
                  WHERE ats.session_id = ar.session_id
                    AND ats.session_status = 'ACTIVE'
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
                "Face verification could not be "
                "saved because the session or "
                "attendance state changed."
            ),
        )

    db.commit()

    return {
        "attendance_id":
            int(
                attendance[
                    "attendance_id"
                ]
            ),

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