from __future__ import annotations

import json
from datetime import datetime
from math import atan2, cos, radians, sin, sqrt

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User


# ============================================================
# GEOLOCATION SETTINGS
# ============================================================

EARTH_RADIUS_METERS = 6_371_000.0


# ============================================================
# ENUM NORMALIZATION
# ============================================================

def _normalize_enum_value(value) -> str:
    if value is None:
        return ""

    result = str(value).upper()

    if "." in result:
        result = result.split(".")[-1]

    return result


# ============================================================
# ATTENDANCE RESUME STATE
# ============================================================

def _next_verification_step(
    *,
    attendance_status: str,
    qr_verified: bool,
    geofence_verified: bool,
    face_verified: bool,
    liveness_verified: bool,
) -> str | None:
    """Derive the next step from the authoritative database state."""

    if _normalize_enum_value(
        attendance_status
    ) != "PENDING":
        return None

    if not qr_verified:
        return "QR"

    if not geofence_verified:
        return "GEOFENCE"

    if not face_verified:
        return "FACE"

    if not liveness_verified:
        return "LIVENESS"

    return None


def get_active_attendance_attempt(
    db: Session,
    current_user: User,
) -> dict:
    """Return the student's currently resumable PENDING attempt."""

    student_id = _get_student_profile(
        db=db,
        current_user=current_user,
    )

    now = datetime.now()

    attempt = db.execute(
        text(
            """
            SELECT
                ar.attendance_id,
                ar.session_id,
                ar.student_id,
                ar.marked_at,

                ar.qr_verified,
                ar.geofence_verified,
                ar.face_verified,
                ar.liveness_verified,

                ar.attendance_status,
                ar.rejection_reason,

                ats.subject_id,
                ats.section_id,
                ats.classroom_id,

                s.subject_name,
                sec.section_name

            FROM attendance_records ar

            INNER JOIN attendance_sessions ats
                ON ats.session_id = ar.session_id

            INNER JOIN subjects s
                ON s.subject_id = ats.subject_id

            INNER JOIN sections sec
                ON sec.section_id = ats.section_id

            WHERE ar.student_id = :student_id
              AND ar.attendance_status = 'PENDING'
              AND ats.session_status = 'ACTIVE'
              AND ats.ended_at IS NULL
              AND ats.qr_expires_at > :now

            ORDER BY ar.attendance_id DESC

            LIMIT 1
            """
        ),
        {
            "student_id": student_id,
            "now": now,
        },
    ).mappings().first()

    if attempt is None:
        return {
            "has_active_attempt": False,
            "attempt": None,
        }

    next_step = _next_verification_step(
        attendance_status=attempt[
            "attendance_status"
        ],
        qr_verified=bool(
            attempt["qr_verified"]
        ),
        geofence_verified=bool(
            attempt["geofence_verified"]
        ),
        face_verified=bool(
            attempt["face_verified"]
        ),
        liveness_verified=bool(
            attempt["liveness_verified"]
        ),
    )

    if next_step is None:
        return {
            "has_active_attempt": False,
            "attempt": None,
        }

    return {
        "has_active_attempt": True,
        "attempt": {
            "attendance_id":
                int(attempt["attendance_id"]),

            "session_id":
                int(attempt["session_id"]),

            "student_id":
                int(attempt["student_id"]),

            "subject_id":
                int(attempt["subject_id"]),

            "subject_name":
                attempt["subject_name"],

            "section_id":
                int(attempt["section_id"]),

            "section_name":
                attempt["section_name"],

            "classroom_id":
                int(attempt["classroom_id"]),

            "marked_at":
                attempt["marked_at"],

            "qr_verified":
                bool(attempt["qr_verified"]),

            "geofence_verified":
                bool(attempt["geofence_verified"]),

            "face_verified":
                bool(attempt["face_verified"]),

            "liveness_verified":
                bool(attempt["liveness_verified"]),

            "attendance_status":
                _normalize_enum_value(
                    attempt["attendance_status"]
                ),

            "rejection_reason":
                attempt["rejection_reason"],

            "next_verification_step":
                next_step,
        },
    }


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
# GET STUDENT PROFILE
# ============================================================

def _get_student_profile(
    db: Session,
    current_user: User,
) -> int:
    """
    Return student_id belonging to the authenticated user.
    """

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

    return int(student_id)


# ============================================================
# PARSE QR DATA
# ============================================================

def _extract_session_token(
    qr_data: str,
) -> str:
    """
    Extract the attendance session token from QR data.

    Accepted formats:

    1. Smart Attendance JSON payload
    2. Raw session token
    """

    if qr_data is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="QR data is required.",
        )

    value = qr_data.strip()

    if not value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="QR data cannot be empty.",
        )

    # --------------------------------------------------------
    # JSON QR PAYLOAD
    # --------------------------------------------------------

    if value.startswith("{"):
        try:
            payload = json.loads(
                value
            )

        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid QR payload.",
            )

        if not isinstance(
            payload,
            dict,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid QR payload.",
            )

        if (
            payload.get("type")
            != "SMART_ATTENDANCE_SESSION"
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Invalid Smart Attendance "
                    "QR code."
                ),
            )

        session_token = payload.get(
            "session_token"
        )

        if not session_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "QR payload does not contain "
                    "a session token."
                ),
            )

        token = str(
            session_token
        ).strip()

        if not token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "QR session token is empty."
                ),
            )

        return token

    # --------------------------------------------------------
    # RAW TOKEN
    # --------------------------------------------------------

    return value


# ============================================================
# MARK ATTENDANCE USING QR
# ============================================================

def mark_attendance_with_qr(
    db: Session,
    current_user: User,
    qr_data: str,
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict:
    """
    Start an attendance attempt after successful QR validation.

    Pipeline:

        QR
        ↓
        GEOFENCE
        ↓
        FACE
        ↓
        LIVENESS
        ↓
        PRESENT

    QR verification creates a PENDING attendance record.
    """

    # ========================================================
    # 1. AUTHENTICATED STUDENT
    # ========================================================

    student_id = _get_student_profile(
        db=db,
        current_user=current_user,
    )

    # ========================================================
    # 2. EXTRACT SESSION TOKEN
    # ========================================================

    session_token = (
        _extract_session_token(
            qr_data
        )
    )

    # ========================================================
    # 3. FIND SESSION
    # ========================================================

    row = db.execute(
        text(
            """
            SELECT
                ats.session_id,
                ats.faculty_id,
                ats.subject_id,
                ats.section_id,
                ats.classroom_id,

                ats.session_token,

                ats.started_at,
                ats.ended_at,
                ats.qr_expires_at,

                ats.session_status,
                ats.geofence_radius_meters,

                s.subject_name,
                sec.section_name

            FROM attendance_sessions ats

            INNER JOIN subjects s
                ON s.subject_id =
                   ats.subject_id

            INNER JOIN sections sec
                ON sec.section_id =
                   ats.section_id

            WHERE ats.session_token =
                :session_token

            LIMIT 1
            """
        ),
        {
            "session_token":
                session_token,
        },
    ).mappings().first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Attendance session not found. "
                "The QR code may be invalid."
            ),
        )

    # ========================================================
    # 4. VERIFY SESSION ACTIVE
    # ========================================================

    session_status = (
        _normalize_enum_value(
            row["session_status"]
        )
    )

    if (
        session_status != "ACTIVE"
        or row["ended_at"] is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This attendance session "
                "is no longer active."
            ),
        )

    # ========================================================
    # 5. VERIFY QR EXPIRY
    # ========================================================

    now = datetime.now()

    if (
        row["qr_expires_at"] is not None
        and now >= row["qr_expires_at"]
    ):
        db.execute(
            text(
                """
                UPDATE attendance_sessions

                SET
                    session_status = 'EXPIRED',
                    ended_at = COALESCE(
                        ended_at,
                        :ended_at
                    )

                WHERE session_id =
                    :session_id

                  AND session_status =
                    'ACTIVE'
                """
            ),
            {
                "session_id":
                    row["session_id"],

                "ended_at":
                    now,
            },
        )

        db.commit()

        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=(
                "This attendance QR code "
                "has expired."
            ),
        )

    # ========================================================
    # 6. VERIFY GEOFENCE CONFIGURATION
    # ========================================================

    radius = row[
        "geofence_radius_meters"
    ]

    if radius is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Attendance session geofence "
                "radius is not configured."
            ),
        )

    if float(radius) <= 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Attendance session geofence "
                "radius is invalid."
            ),
        )

    # ========================================================
    # 7. VERIFY STUDENT SECTION
    # ========================================================

    assignment_exists = db.execute(
        text(
            """
            SELECT
                assignment_id

            FROM student_section_assignments

            WHERE student_id =
                :student_id

              AND section_id =
                :section_id

              AND is_active = 1

            LIMIT 1
            """
        ),
        {
            "student_id":
                student_id,

            "section_id":
                row["section_id"],
        },
    ).first()

    if assignment_exists is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You are not assigned to the "
                "section for this attendance "
                "session."
            ),
        )

    # ========================================================
    # 8. RESUME EXISTING ATTEMPT / PREVENT DUPLICATE
    # ========================================================

    existing = db.execute(
        text(
            """
            SELECT
                attendance_id,
                session_id,
                student_id,
                marked_at,

                qr_verified,
                geofence_verified,
                face_verified,
                liveness_verified,

                attendance_status,
                rejection_reason

            FROM attendance_records

            WHERE session_id =
                :session_id

              AND student_id =
                :student_id

            LIMIT 1
            """
        ),
        {
            "session_id":
                row["session_id"],

            "student_id":
                student_id,
        },
    ).mappings().first()

    if existing is not None:
        existing_status = _normalize_enum_value(
            existing["attendance_status"]
        )

        if existing_status == "PENDING":
            next_step = _next_verification_step(
                attendance_status=existing_status,
                qr_verified=bool(
                    existing["qr_verified"]
                ),
                geofence_verified=bool(
                    existing["geofence_verified"]
                ),
                face_verified=bool(
                    existing["face_verified"]
                ),
                liveness_verified=bool(
                    existing["liveness_verified"]
                ),
            )

            if next_step is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "The existing attendance attempt "
                        "has an inconsistent verification state."
                    ),
                )

            return {
                "attendance_id":
                    int(existing["attendance_id"]),

                "session_id":
                    int(existing["session_id"]),

                "student_id":
                    int(existing["student_id"]),

                "subject_id":
                    int(row["subject_id"]),

                "subject_name":
                    row["subject_name"],

                "section_id":
                    int(row["section_id"]),

                "section_name":
                    row["section_name"],

                "classroom_id":
                    int(row["classroom_id"]),

                "marked_at":
                    existing["marked_at"],

                "qr_verified":
                    bool(existing["qr_verified"]),

                "geofence_verified":
                    bool(
                        existing["geofence_verified"]
                    ),

                "face_verified":
                    bool(existing["face_verified"]),

                "liveness_verified":
                    bool(
                        existing["liveness_verified"]
                    ),

                "attendance_status":
                    existing_status,

                "rejection_reason":
                    existing["rejection_reason"],

                "next_verification_step":
                    next_step,
            }

        if existing_status == "PRESENT":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Attendance has already been "
                    "marked present for this session."
                ),
            )

        if existing_status == "REJECTED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The attendance attempt for this "
                    "session has already been rejected."
                ),
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Attendance has already been "
                "started for this session."
            ),
        )

    # ========================================================
    # 9. CREATE PENDING ATTENDANCE
    # ========================================================

    try:
        result = db.execute(
            text(
                """
                INSERT INTO attendance_records (
                    session_id,
                    student_id,

                    latitude,
                    longitude,

                    qr_verified,
                    geofence_verified,
                    face_verified,
                    liveness_verified,

                    attendance_status,
                    rejection_reason
                )
                VALUES (
                    :session_id,
                    :student_id,

                    :latitude,
                    :longitude,

                    1,
                    0,
                    0,
                    0,

                    'PENDING',
                    NULL
                )
                """
            ),
            {
                "session_id":
                    row["session_id"],

                "student_id":
                    student_id,

                "latitude":
                    latitude,

                "longitude":
                    longitude,
            },
        )

        attendance_id = int(
            result.lastrowid
        )

        db.commit()

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Attendance has already been "
                "started for this session."
            ),
        )

    except Exception:
        db.rollback()
        raise

    # ========================================================
    # 10. FETCH CREATED ATTENDANCE
    # ========================================================

    attendance_row = db.execute(
        text(
            """
            SELECT
                attendance_id,
                session_id,
                student_id,
                marked_at,

                qr_verified,
                geofence_verified,
                face_verified,
                liveness_verified,

                attendance_status,
                rejection_reason

            FROM attendance_records

            WHERE attendance_id =
                :attendance_id

            LIMIT 1
            """
        ),
        {
            "attendance_id":
                attendance_id,
        },
    ).mappings().first()

    if attendance_row is None:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Attendance was created but "
                "could not be retrieved."
            ),
        )

    # ========================================================
    # 11. RESPONSE
    # ========================================================

    return {
        "attendance_id":
            int(
                attendance_row[
                    "attendance_id"
                ]
            ),

        "session_id":
            int(
                attendance_row[
                    "session_id"
                ]
            ),

        "student_id":
            int(
                attendance_row[
                    "student_id"
                ]
            ),

        "subject_id":
            int(
                row["subject_id"]
            ),

        "subject_name":
            row["subject_name"],

        "section_id":
            int(
                row["section_id"]
            ),

        "section_name":
            row["section_name"],

        "classroom_id":
            int(
                row["classroom_id"]
            ),

        "marked_at":
            attendance_row[
                "marked_at"
            ],

        "qr_verified":
            bool(
                attendance_row[
                    "qr_verified"
                ]
            ),

        "geofence_verified":
            bool(
                attendance_row[
                    "geofence_verified"
                ]
            ),

        "face_verified":
            bool(
                attendance_row[
                    "face_verified"
                ]
            ),

        "liveness_verified":
            bool(
                attendance_row[
                    "liveness_verified"
                ]
            ),

        "attendance_status":
            _normalize_enum_value(
                attendance_row[
                    "attendance_status"
                ]
            ),

        "rejection_reason":
            attendance_row[
                "rejection_reason"
            ],

        "next_verification_step":
            "GEOFENCE",
    }


# ============================================================
# BACKWARD-COMPATIBLE QR ALIAS
# ============================================================

def mark_attendance_by_qr(
    db: Session,
    current_user: User,
    qr_data: str,
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict:
    """
    Compatibility wrapper for older API imports.
    """

    return mark_attendance_with_qr(
        db=db,
        current_user=current_user,
        qr_data=qr_data,
        latitude=latitude,
        longitude=longitude,
    )


# ============================================================
# HAVERSINE DISTANCE
# ============================================================

def _calculate_distance_meters(
    latitude1: float,
    longitude1: float,
    latitude2: float,
    longitude2: float,
) -> float:
    """
    Calculate straight-line geographic distance
    between two GPS coordinates.
    """

    lat1 = radians(
        latitude1
    )

    lon1 = radians(
        longitude1
    )

    lat2 = radians(
        latitude2
    )

    lon2 = radians(
        longitude2
    )

    delta_latitude = (
        lat2 - lat1
    )

    delta_longitude = (
        lon2 - lon1
    )

    a = (
        sin(
            delta_latitude / 2
        ) ** 2
        +
        cos(lat1)
        * cos(lat2)
        * sin(
            delta_longitude / 2
        ) ** 2
    )

    # Protect against tiny floating-point overshoot.
    a = min(
        1.0,
        max(
            0.0,
            a,
        ),
    )

    c = 2 * atan2(
        sqrt(a),
        sqrt(1 - a),
    )

    return (
        EARTH_RADIUS_METERS
        * c
    )


# ============================================================
# VALIDATE GPS COORDINATES
# ============================================================

def _validate_coordinates(
    latitude: float,
    longitude: float,
) -> None:
    if not (
        -90.0
        <= latitude
        <= 90.0
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Latitude must be between "
                "-90 and 90."
            ),
        )

    if not (
        -180.0
        <= longitude
        <= 180.0
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Longitude must be between "
                "-180 and 180."
            ),
        )


# ============================================================
# GET STUDENT ATTENDANCE RECORD
# ============================================================

def _get_student_attendance_record(
    db: Session,
    attendance_id: int,
    student_id: int,
):
    """
    Return the student's attendance attempt together
    with the session-specific verification settings.
    """

    return db.execute(
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
                ar.rejection_reason,

                ats.classroom_id,

                ats.session_status,
                ats.qr_expires_at,
                ats.ended_at,

                ats.geofence_radius_meters

            FROM attendance_records ar

            INNER JOIN attendance_sessions ats
                ON ats.session_id =
                   ar.session_id

            WHERE ar.attendance_id =
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


# ============================================================
# VERIFY GEOFENCE
# ============================================================

def verify_attendance_geofence(
    db: Session,
    current_user: User,
    attendance_id: int,
    latitude: float,
    longitude: float,
) -> dict:
    """
    Verify the student's GPS location against the
    radius configured for this attendance session.

    Pipeline:

        QR VERIFIED
            ↓
        GEOFENCE VERIFIED
            ↓
        FACE
            ↓
        LIVENESS
            ↓
        PRESENT
    """

    # ========================================================
    # 1. AUTHENTICATED STUDENT
    # ========================================================

    student_id = _get_student_profile(
        db=db,
        current_user=current_user,
    )

    # ========================================================
    # 2. VALIDATE STUDENT GPS
    # ========================================================

    _validate_coordinates(
        latitude=latitude,
        longitude=longitude,
    )

    # ========================================================
    # 3. GET ATTENDANCE + SESSION
    # ========================================================

    record = (
        _get_student_attendance_record(
            db=db,
            attendance_id=attendance_id,
            student_id=student_id,
        )
    )

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance record not found.",
        )

    # ========================================================
    # 4. ATTENDANCE STATUS
    # ========================================================

    attendance_status = (
        _normalize_enum_value(
            record[
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
                "state for geofence verification."
            ),
        )

    # ========================================================
    # 5. QR MUST BE VERIFIED
    # ========================================================

    if not bool(
        record["qr_verified"]
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "QR verification must be "
                "completed first."
            ),
        )

    # ========================================================
    # 6. PREVENT OUT-OF-ORDER / DUPLICATE STEPS
    # ========================================================

    if bool(
        record[
            "geofence_verified"
        ]
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Geofence verification has "
                "already been completed."
            ),
        )

    if bool(
        record["face_verified"]
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Face verification has already "
                "been completed."
            ),
        )

    if bool(
        record[
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
    # 7. SESSION MUST STILL BE ACTIVE
    # ========================================================

    session_status = (
        _normalize_enum_value(
            record[
                "session_status"
            ]
        )
    )

    if (
        session_status != "ACTIVE"
        or record["ended_at"] is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Attendance session is "
                "no longer active."
            ),
        )

    # ========================================================
    # 8. VERIFY SESSION EXPIRY
    # ========================================================

    now = datetime.now()

    if (
        record[
            "qr_expires_at"
        ] is not None
        and now
        >= record[
            "qr_expires_at"
        ]
    ):
        db.execute(
            text(
                """
                UPDATE attendance_sessions

                SET
                    session_status = 'EXPIRED',

                    ended_at = COALESCE(
                        ended_at,
                        :ended_at
                    )

                WHERE session_id =
                    :session_id

                  AND session_status =
                    'ACTIVE'
                """
            ),
            {
                "session_id":
                    record[
                        "session_id"
                    ],

                "ended_at":
                    now,
            },
        )

        db.commit()

        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=(
                "Attendance session "
                "has expired."
            ),
        )

    # ========================================================
    # 9. SESSION GEOFENCE RADIUS
    # ========================================================

    radius = record[
        "geofence_radius_meters"
    ]

    if radius is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Attendance session geofence "
                "radius is not configured."
            ),
        )

    radius = float(
        radius
    )

    if radius <= 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Attendance session geofence "
                "radius is invalid."
            ),
        )

    # ========================================================
    # 10. GET CLASSROOM GPS
    # ========================================================

    classroom = db.execute(
        text(
            """
            SELECT
                classroom_id,
                latitude,
                longitude,
                is_active

            FROM classrooms

            WHERE classroom_id =
                :classroom_id

            LIMIT 1
            """
        ),
        {
            "classroom_id":
                record[
                    "classroom_id"
                ],
        },
    ).mappings().first()

    if classroom is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classroom not found.",
        )

    if not bool(
        classroom["is_active"]
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Classroom is inactive.",
        )

    classroom_latitude = (
        classroom["latitude"]
    )

    classroom_longitude = (
        classroom["longitude"]
    )

    if (
        classroom_latitude is None
        or classroom_longitude is None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Classroom GPS coordinates "
                "are not configured."
            ),
        )

    # ========================================================
    # 11. CALCULATE DISTANCE
    # ========================================================

    distance = (
        _calculate_distance_meters(
            latitude1=latitude,
            longitude1=longitude,

            latitude2=float(
                classroom_latitude
            ),

            longitude2=float(
                classroom_longitude
            ),
        )
    )

    distance = round(
        distance,
        2,
    )

    # ========================================================
    # 12. INSIDE GEOFENCE
    # ========================================================

    if distance <= radius:
        result = db.execute(
            text(
                """
                UPDATE attendance_records ar

                SET
                    ar.latitude =
                        :latitude,

                    ar.longitude =
                        :longitude,

                    ar.distance_from_classroom_meters =
                        :distance,

                    ar.geofence_verified =
                        1,

                    ar.rejection_reason =
                        NULL

                WHERE ar.attendance_id =
                    :attendance_id

                  AND ar.student_id =
                    :student_id

                  AND ar.attendance_status =
                    'PENDING'

                  AND ar.qr_verified =
                    1

                  AND ar.geofence_verified =
                    0

                  AND ar.face_verified =
                    0

                  AND ar.liveness_verified =
                    0

                  AND EXISTS (
                      SELECT 1

                      FROM attendance_sessions ats

                      WHERE ats.session_id =
                          ar.session_id

                        AND ats.session_status =
                            'ACTIVE'

                        AND ats.ended_at
                            IS NULL
                  )
                """
            ),
            {
                "latitude":
                    latitude,

                "longitude":
                    longitude,

                "distance":
                    distance,

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
                    "Geofence verification could "
                    "not be saved because the "
                    "session or attendance state "
                    "changed."
                ),
            )

        db.commit()

        return {
            "attendance_id":
                attendance_id,

            "session_id":
                int(
                    record[
                        "session_id"
                    ]
                ),

            "student_id":
                student_id,

            "latitude":
                latitude,

            "longitude":
                longitude,

            "classroom_latitude":
                float(
                    classroom_latitude
                ),

            "classroom_longitude":
                float(
                    classroom_longitude
                ),

            "geofence_radius_meters":
                radius,

            "distance_from_classroom_meters":
                distance,

            "qr_verified":
                True,

            "geofence_verified":
                True,

            "face_verified":
                False,

            "liveness_verified":
                False,

            "attendance_status":
                "PENDING",

            "rejection_reason":
                None,

            "next_verification_step":
                "FACE",
        }

    # ========================================================
    # 13. OUTSIDE GEOFENCE
    # ========================================================

    rejection_reason = (
        "Student is outside the attendance "
        "session geofence. "
        f"Distance from classroom: "
        f"{distance:.2f} meters. "
        f"Allowed radius: "
        f"{radius:.2f} meters."
    )

    result = db.execute(
        text(
            """
            UPDATE attendance_records ar

            SET
                ar.latitude =
                    :latitude,

                ar.longitude =
                    :longitude,

                ar.distance_from_classroom_meters =
                    :distance,

                ar.geofence_verified =
                    0,

                ar.attendance_status =
                    'REJECTED',

                ar.rejection_reason =
                    :rejection_reason

            WHERE ar.attendance_id =
                :attendance_id

              AND ar.student_id =
                :student_id

              AND ar.attendance_status =
                'PENDING'

              AND ar.qr_verified =
                1

              AND ar.geofence_verified =
                0

              AND ar.face_verified =
                0

              AND ar.liveness_verified =
                0

              AND EXISTS (
                  SELECT 1

                  FROM attendance_sessions ats

                  WHERE ats.session_id =
                      ar.session_id

                    AND ats.session_status =
                        'ACTIVE'

                    AND ats.ended_at
                        IS NULL
              )
            """
        ),
        {
            "latitude":
                latitude,

            "longitude":
                longitude,

            "distance":
                distance,

            "rejection_reason":
                rejection_reason,

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
                "Geofence rejection could not "
                "be saved because the session "
                "or attendance state changed."
            ),
        )

    db.commit()

    return {
        "attendance_id":
            attendance_id,

        "session_id":
            int(
                record[
                    "session_id"
                ]
            ),

        "student_id":
            student_id,

        "latitude":
            latitude,

        "longitude":
            longitude,

        "classroom_latitude":
            float(
                classroom_latitude
            ),

        "classroom_longitude":
            float(
                classroom_longitude
            ),

        "geofence_radius_meters":
            radius,

        "distance_from_classroom_meters":
            distance,

        "qr_verified":
            True,

        "geofence_verified":
            False,

        "face_verified":
            False,

        "liveness_verified":
            False,

        "attendance_status":
            "REJECTED",

        "rejection_reason":
            rejection_reason,

        "next_verification_step":
            None,
    }