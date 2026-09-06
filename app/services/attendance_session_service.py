from datetime import datetime, timedelta, timezone
import base64
import io
import json
import secrets

import qrcode
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.faculty_profile import FacultyProfile


# ============================================================
# SESSION SETTINGS
# ============================================================

DEFAULT_QR_EXPIRY_MINUTES = 5
MIN_QR_EXPIRY_MINUTES = 1
MAX_QR_EXPIRY_MINUTES = 15

DEFAULT_GEOFENCE_RADIUS_METERS = 50.0
MIN_GEOFENCE_RADIUS_METERS = 10.0
MAX_GEOFENCE_RADIUS_METERS = 500.0


def _utc_now_naive() -> datetime:
    # Store attendance timestamps as timezone-naive UTC.
    # MySQL DATETIME does not store timezone information.
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ============================================================
# VERIFY FACULTY
# ============================================================

def _verify_faculty(
    current_user: User,
) -> None:

    if current_user.role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User role is not configured.",
        )

    role_name = str(
        current_user.role.role_name
    ).upper()

    if "." in role_name:
        role_name = role_name.split(".")[-1]

    if role_name != "FACULTY":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Faculty access required.",
        )


# ============================================================
# GET FACULTY PROFILE
# ============================================================

def _get_faculty_profile(
    db: Session,
    current_user: User,
) -> FacultyProfile:

    _verify_faculty(current_user)

    faculty_profile = (
        db.query(FacultyProfile)
        .filter(
            FacultyProfile.user_id
            == current_user.user_id
        )
        .first()
    )

    if faculty_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Faculty profile not found.",
        )

    return faculty_profile


# ============================================================
# VERIFY SEMESTER + SUBJECT + SECTION ASSIGNMENT
# ============================================================

def _verify_subject_section_assignment(
    db: Session,
    faculty_id: int,
    semester_id: int,
    subject_id: int,
    section_id: int,
) -> None:
    """
    Verify the complete faculty attendance scope:

        Faculty
            +
        Semester
            +
        Section
            +
        Subject

    The relationship must exist in
    faculty_subject_assignments.

    The selected section must belong to the selected semester,
    and the selected subject must also belong to the selected
    semester.
    """

    result = db.execute(
        text(
            """
            SELECT
                fsa.assignment_id

            FROM faculty_subject_assignments fsa

            INNER JOIN subjects s
                ON s.subject_id = fsa.subject_id

            INNER JOIN sections sec
                ON sec.section_id = fsa.section_id

            WHERE fsa.faculty_id = :faculty_id
              AND fsa.subject_id = :subject_id
              AND fsa.section_id = :section_id

              AND sec.semester_id = :semester_id
              AND s.semester_id = :semester_id

              AND fsa.is_active = 1
              AND s.is_active = 1
              AND sec.is_active = 1

            LIMIT 1
            """
        ),
        {
            "faculty_id": faculty_id,
            "semester_id": semester_id,
            "subject_id": subject_id,
            "section_id": section_id,
        },
    ).first()

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "The selected semester, section and subject "
                "are not valid for this faculty."
            ),
        )


# ============================================================
# VERIFY CLASSROOM
# ============================================================

def _verify_classroom(
    db: Session,
    classroom_id: int,
) -> None:

    result = db.execute(
        text(
            """
            SELECT
                classroom_id
            FROM classrooms
            WHERE classroom_id = :classroom_id
              AND is_active = 1
            LIMIT 1
            """
        ),
        {
            "classroom_id": classroom_id,
        },
    ).first()

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classroom not found or inactive.",
        )


# ============================================================
# VALIDATE SESSION SETTINGS
# ============================================================

def _validate_session_settings(
    qr_validity_minutes: int,
    geofence_radius_meters: float,
) -> None:

    if (
        qr_validity_minutes
        < MIN_QR_EXPIRY_MINUTES
        or qr_validity_minutes
        > MAX_QR_EXPIRY_MINUTES
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "QR validity must be between "
                f"{MIN_QR_EXPIRY_MINUTES} and "
                f"{MAX_QR_EXPIRY_MINUTES} minutes."
            ),
        )

    if (
        geofence_radius_meters
        < MIN_GEOFENCE_RADIUS_METERS
        or geofence_radius_meters
        > MAX_GEOFENCE_RADIUS_METERS
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Geofence radius must be between "
                f"{MIN_GEOFENCE_RADIUS_METERS:.0f} and "
                f"{MAX_GEOFENCE_RADIUS_METERS:.0f} meters."
            ),
        )


# ============================================================
# COMPLETE TIMED-OUT ACTIVE SESSIONS
# ============================================================

def complete_timed_out_attendance_sessions(
    db: Session,
    faculty_id: int | None = None,
) -> int:
    """
    Convert timed-out ACTIVE attendance sessions to COMPLETED.

    This is intentionally server-side. The frontend countdown is only
    a display aid; the database state is reconciled whenever faculty
    session state is read/changed.
    """

    now = _utc_now_naive()

    where_faculty = ""
    params = {
        "now": now,
    }

    if faculty_id is not None:
        where_faculty = " AND faculty_id = :faculty_id"
        params["faculty_id"] = faculty_id

    result = db.execute(
        text(
            f"""
            UPDATE attendance_sessions
            SET
                session_status = 'COMPLETED',
                ended_at = COALESCE(
                    ended_at,
                    qr_expires_at,
                    :now
                )
            WHERE session_status = 'ACTIVE'
              AND qr_expires_at IS NOT NULL
              AND qr_expires_at <= :now
              {where_faculty}
            """
        ),
        params,
    )

    db.commit()

    return int(result.rowcount or 0)


# ============================================================
# CHECK ACTIVE SESSION
# ============================================================

def _check_active_session(
    db: Session,
    faculty_id: int,
    subject_id: int,
    section_id: int,
) -> None:
    """
    Prevent multiple ACTIVE sessions for the same
    faculty + subject + section.

    Timed-out ACTIVE sessions are first converted to COMPLETED.
    """

    complete_timed_out_attendance_sessions(
        db=db,
        faculty_id=faculty_id,
    )

    result = db.execute(
        text(
            """
            SELECT
                session_id
            FROM attendance_sessions
            WHERE faculty_id = :faculty_id
              AND subject_id = :subject_id
              AND section_id = :section_id
              AND session_status = 'ACTIVE'
            ORDER BY session_id DESC
            LIMIT 1
            """
        ),
        {
            "faculty_id": faculty_id,
            "subject_id": subject_id,
            "section_id": section_id,
        },
    ).first()

    if result is None:
        return

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "An active attendance session already "
            "exists for this subject and section."
        ),
    )


# ============================================================
# CREATE ATTENDANCE SESSION
# ============================================================

def create_attendance_session(
    db: Session,
    current_user: User,
    semester_id: int,
    subject_id: int,
    section_id: int,
    classroom_id: int,
    qr_validity_minutes: int = DEFAULT_QR_EXPIRY_MINUTES,
    geofence_radius_meters: float =
        DEFAULT_GEOFENCE_RADIUS_METERS,
) -> dict:
    """
    Create a new attendance session.

    Flow:

        Semester
            ↓
        Section
            ↓
        Faculty Subject Assignment
            ↓
        Classroom
            ↓
        QR + Geofence settings
    """

    # --------------------------------------------------------
    # 1. VALIDATE SESSION SETTINGS
    # --------------------------------------------------------

    _validate_session_settings(
        qr_validity_minutes=qr_validity_minutes,
        geofence_radius_meters=geofence_radius_meters,
    )

    # --------------------------------------------------------
    # 2. GET FACULTY
    # --------------------------------------------------------

    faculty_profile = _get_faculty_profile(
        db=db,
        current_user=current_user,
    )

    faculty_id = faculty_profile.faculty_id

    # --------------------------------------------------------
    # 3. VERIFY SEMESTER + SECTION + SUBJECT
    # --------------------------------------------------------

    _verify_subject_section_assignment(
        db=db,
        faculty_id=faculty_id,
        semester_id=semester_id,
        subject_id=subject_id,
        section_id=section_id,
    )

    # --------------------------------------------------------
    # 4. VERIFY CLASSROOM
    # --------------------------------------------------------

    _verify_classroom(
        db=db,
        classroom_id=classroom_id,
    )

    # --------------------------------------------------------
    # 5. PREVENT DUPLICATE ACTIVE SESSION
    # --------------------------------------------------------

    _check_active_session(
        db=db,
        faculty_id=faculty_id,
        subject_id=subject_id,
        section_id=section_id,
    )

    # --------------------------------------------------------
    # 6. GENERATE SESSION TOKEN
    # --------------------------------------------------------

    session_token = secrets.token_urlsafe(32)

    # --------------------------------------------------------
    # 7. SESSION TIME
    # --------------------------------------------------------

    started_at = _utc_now_naive()

    qr_expires_at = (
        started_at
        + timedelta(
            minutes=qr_validity_minutes
        )
    )

    # --------------------------------------------------------
    # 8. INSERT SESSION
    # --------------------------------------------------------

    insert_query = text(
        """
        INSERT INTO attendance_sessions (
            faculty_id,
            subject_id,
            section_id,
            classroom_id,
            geofence_radius_meters,
            session_token,
            started_at,
            qr_expires_at,
            session_status
        )
        VALUES (
            :faculty_id,
            :subject_id,
            :section_id,
            :classroom_id,
            :geofence_radius_meters,
            :session_token,
            :started_at,
            :qr_expires_at,
            'ACTIVE'
        )
        """
    )

    try:
        result = db.execute(
            insert_query,
            {
                "faculty_id": faculty_id,
                "subject_id": subject_id,
                "section_id": section_id,
                "classroom_id": classroom_id,
                "geofence_radius_meters":
                    geofence_radius_meters,
                "session_token": session_token,
                "started_at": started_at,
                "qr_expires_at": qr_expires_at,
            },
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    session_id = result.lastrowid

    # --------------------------------------------------------
    # 9. RETURN CREATED SESSION
    # --------------------------------------------------------

    return {
        "session_id": session_id,
        "faculty_id": faculty_id,

        "semester_id": semester_id,

        "subject_id": subject_id,
        "section_id": section_id,
        "classroom_id": classroom_id,

        "geofence_radius_meters":
            float(geofence_radius_meters),

        "session_token": session_token,

        "started_at": started_at,
        "ended_at": None,
        "qr_expires_at": qr_expires_at,

        "session_status": "ACTIVE",

        "created_at": started_at,
    }


# ============================================================
# GENERATE ATTENDANCE SESSION QR
# ============================================================

def generate_attendance_session_qr(
    db: Session,
    current_user: User,
    session_id: int,
) -> dict:
    """
    Generate the QR for an existing ACTIVE session.

    The same session token is reused; generating the QR does
    not create another session or another token.
    """

    faculty_profile = _get_faculty_profile(
        db=db,
        current_user=current_user,
    )

    row = db.execute(
        text(
            """
            SELECT
                ats.session_id,
                ats.faculty_id,

                ats.subject_id,
                s.subject_name,

                ats.section_id,
                sec.section_name,
                sec.semester_id,

                ats.classroom_id,
                ats.geofence_radius_meters,

                ats.session_token,
                ats.started_at,
                ats.ended_at,
                ats.qr_expires_at,
                ats.session_status

            FROM attendance_sessions ats

            INNER JOIN subjects s
                ON s.subject_id = ats.subject_id

            INNER JOIN sections sec
                ON sec.section_id = ats.section_id

            WHERE ats.session_id = :session_id
              AND ats.faculty_id = :faculty_id

            LIMIT 1
            """
        ),
        {
            "session_id": session_id,
            "faculty_id":
                faculty_profile.faculty_id,
        },
    ).mappings().first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance session not found.",
        )

    session_status = str(
        row["session_status"]
    ).upper()

    if "." in session_status:
        session_status = session_status.split(".")[-1]

    if session_status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "QR code can only be generated "
                "for an ACTIVE attendance session."
            ),
        )

    # --------------------------------------------------------
    # VERIFY EXPIRY
    # --------------------------------------------------------

    now = _utc_now_naive()

    if (
        row["qr_expires_at"] is not None
        and now >= row["qr_expires_at"]
    ):
        db.execute(
            text(
                """
                UPDATE attendance_sessions
                SET
                    session_status = 'COMPLETED',
                    ended_at = COALESCE(
                        ended_at,
                        :ended_at
                    )
                WHERE session_id = :session_id
                  AND session_status = 'ACTIVE'
                """
            ),
            {
                "session_id": session_id,
                "ended_at": now,
            },
        )

        db.commit()

        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Attendance session has completed because its QR validity ended.",
        )

    # --------------------------------------------------------
    # BUILD QR PAYLOAD
    # --------------------------------------------------------

    qr_payload = {
        "type":
            "SMART_ATTENDANCE_SESSION",

        "session_id":
            row["session_id"],

        "session_token":
            row["session_token"],

        "semester_id":
            row["semester_id"],

        "subject_id":
            row["subject_id"],

        "section_id":
            row["section_id"],

        "classroom_id":
            row["classroom_id"],

        "expires_at":
            row["qr_expires_at"].isoformat(),
    }

    qr_data = json.dumps(
        qr_payload,
        separators=(",", ":"),
    )

    # --------------------------------------------------------
    # GENERATE QR IMAGE
    # --------------------------------------------------------

    qr = qrcode.QRCode(
        version=None,
        error_correction=
            qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )

    qr.add_data(qr_data)
    qr.make(fit=True)

    qr_image = qr.make_image()

    image_buffer = io.BytesIO()

    qr_image.save(
        image_buffer,
        format="PNG",
    )

    qr_base64 = base64.b64encode(
        image_buffer.getvalue()
    ).decode("utf-8")

    # --------------------------------------------------------
    # RETURN QR RESPONSE
    # --------------------------------------------------------

    return {
        "session_id":
            row["session_id"],

        "semester_id":
            row["semester_id"],

        "subject_id":
            row["subject_id"],

        "subject_name":
            row["subject_name"],

        "section_id":
            row["section_id"],

        "section_name":
            row["section_name"],

        "classroom_id":
            row["classroom_id"],

        "geofence_radius_meters": float(
            row["geofence_radius_meters"]
            if row["geofence_radius_meters"]
            is not None
            else DEFAULT_GEOFENCE_RADIUS_METERS
        ),

        "session_status":
            session_status,

        "started_at":
            row["started_at"],

        "qr_expires_at":
            row["qr_expires_at"],

        "qr_data":
            qr_data,

        "qr_code_base64":
            qr_base64,

        "qr_image_data_uri":
            "data:image/png;base64,"
            + qr_base64,
    }


# ============================================================
# GET CURRENT ACTIVE ATTENDANCE SESSION
# ============================================================

def get_active_attendance_session(
    db: Session,
    current_user: User,
) -> dict | None:
    """
    Return the authenticated faculty member's most recent ACTIVE
    attendance session.

    Any timed-out ACTIVE session is converted to COMPLETED first.
    This allows the faculty UI to recover the current QR session
    after navigating back or reopening the attendance page.
    """

    faculty_profile = _get_faculty_profile(
        db=db,
        current_user=current_user,
    )

    faculty_id = faculty_profile.faculty_id

    complete_timed_out_attendance_sessions(
        db=db,
        faculty_id=faculty_id,
    )

    row = db.execute(
        text(
            """
            SELECT
                ats.session_id,
                ats.faculty_id,
                sec.semester_id,
                ats.subject_id,
                s.subject_code,
                s.subject_name,
                ats.section_id,
                sec.section_name,
                ats.classroom_id,
                c.building_name,
                c.room_number,
                ats.geofence_radius_meters,
                ats.session_token,
                ats.started_at,
                ats.ended_at,
                ats.qr_expires_at,
                ats.session_status,
                ats.created_at
            FROM attendance_sessions ats
            INNER JOIN subjects s
                ON s.subject_id = ats.subject_id
            INNER JOIN sections sec
                ON sec.section_id = ats.section_id
            LEFT JOIN classrooms c
                ON c.classroom_id = ats.classroom_id
            WHERE ats.faculty_id = :faculty_id
              AND ats.session_status = 'ACTIVE'
            ORDER BY ats.started_at DESC, ats.session_id DESC
            LIMIT 1
            """
        ),
        {
            "faculty_id": faculty_id,
        },
    ).mappings().first()

    if row is None:
        return None

    return {
        "session_id": int(row["session_id"]),
        "faculty_id": int(row["faculty_id"]),
        "semester_id": int(row["semester_id"]),
        "subject_id": int(row["subject_id"]),
        "subject_code": row["subject_code"],
        "subject_name": row["subject_name"],
        "section_id": int(row["section_id"]),
        "section_name": row["section_name"],
        "classroom_id": int(row["classroom_id"]),
        "building_name": row["building_name"],
        "room_number": row["room_number"],
        "geofence_radius_meters": float(
            row["geofence_radius_meters"]
            if row["geofence_radius_meters"] is not None
            else DEFAULT_GEOFENCE_RADIUS_METERS
        ),
        "session_token": row["session_token"],
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
        "qr_expires_at": row["qr_expires_at"],
        "session_status": "ACTIVE",
        "created_at": row["created_at"],
    }


# ============================================================
# COMPLETE ATTENDANCE SESSION
# ============================================================

def complete_attendance_session(
    db: Session,
    current_user: User,
    session_id: int,
) -> dict:
    """
    Complete a faculty attendance session normally.

    COMPLETED is the normal terminal state. Once completed, the QR
    becomes invalid because student verification accepts ACTIVE
    sessions only.
    """

    faculty_profile = _get_faculty_profile(
        db=db,
        current_user=current_user,
    )

    faculty_id = faculty_profile.faculty_id

    complete_timed_out_attendance_sessions(
        db=db,
        faculty_id=faculty_id,
    )

    row = db.execute(
        text(
            """
            SELECT
                session_id,
                session_status,
                ended_at
            FROM attendance_sessions
            WHERE session_id = :session_id
              AND faculty_id = :faculty_id
            LIMIT 1
            """
        ),
        {
            "session_id": session_id,
            "faculty_id": faculty_id,
        },
    ).mappings().first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance session not found.",
        )

    session_status = str(
        row["session_status"]
    ).upper()

    if "." in session_status:
        session_status = session_status.split(".")[-1]

    if session_status == "COMPLETED":
        return {
            "session_id": session_id,
            "session_status": "COMPLETED",
            "ended_at": row["ended_at"],
            "message": "Attendance session is already completed.",
        }

    if session_status == "EXPIRED":
        ended_at = row["ended_at"] or _utc_now_naive()

        db.execute(
            text(
                """
                UPDATE attendance_sessions
                SET
                    session_status = 'COMPLETED',
                    ended_at = COALESCE(
                        ended_at,
                        :ended_at
                    )
                WHERE session_id = :session_id
                  AND faculty_id = :faculty_id
                  AND session_status = 'EXPIRED'
                """
            ),
            {
                "session_id": session_id,
                "faculty_id": faculty_id,
                "ended_at": ended_at,
            },
        )

        db.commit()

        return {
            "session_id": session_id,
            "session_status": "COMPLETED",
            "ended_at": ended_at,
            "message": "Attendance session completed.",
        }

    if session_status == "CANCELLED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A cancelled attendance session cannot be completed.",
        )

    if session_status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only an ACTIVE attendance session can be completed.",
        )

    ended_at = _utc_now_naive()

    db.execute(
        text(
            """
            UPDATE attendance_sessions
            SET
                session_status = 'COMPLETED',
                ended_at = :ended_at
            WHERE session_id = :session_id
              AND faculty_id = :faculty_id
              AND session_status = 'ACTIVE'
            """
        ),
        {
            "session_id": session_id,
            "faculty_id": faculty_id,
            "ended_at": ended_at,
        },
    )

    db.commit()

    return {
        "session_id": session_id,
        "session_status": "COMPLETED",
        "ended_at": ended_at,
        "message": (
            "Attendance session completed. "
            "The generated QR code is no longer valid."
        ),
    }


# ============================================================
# CANCEL ATTENDANCE SESSION
# ============================================================

def cancel_attendance_session(
    db: Session,
    current_user: User,
    session_id: int,
) -> dict:
    """
    Cancel an ACTIVE attendance session.

    Cancellation immediately invalidates the QR because
    student attendance verification accepts only ACTIVE
    sessions.
    """

    faculty_profile = _get_faculty_profile(
        db=db,
        current_user=current_user,
    )

    complete_timed_out_attendance_sessions(
        db=db,
        faculty_id=faculty_profile.faculty_id,
    )

    row = db.execute(
        text(
            """
            SELECT
                session_id,
                session_status,
                ended_at

            FROM attendance_sessions

            WHERE session_id = :session_id
              AND faculty_id = :faculty_id

            LIMIT 1
            """
        ),
        {
            "session_id": session_id,
            "faculty_id":
                faculty_profile.faculty_id,
        },
    ).mappings().first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance session not found.",
        )

    session_status = str(
        row["session_status"]
    ).upper()

    if "." in session_status:
        session_status = session_status.split(".")[-1]

    if session_status == "CANCELLED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attendance session is already cancelled.",
        )

    if session_status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Only an ACTIVE attendance session "
                "can be cancelled."
            ),
        )

    ended_at = _utc_now_naive()

    db.execute(
        text(
            """
            UPDATE attendance_sessions
            SET
                session_status = 'CANCELLED',
                ended_at = :ended_at

            WHERE session_id = :session_id
              AND faculty_id = :faculty_id
              AND session_status = 'ACTIVE'
            """
        ),
        {
            "session_id": session_id,
            "faculty_id":
                faculty_profile.faculty_id,
            "ended_at": ended_at,
        },
    )

    db.commit()

    return {
        "session_id": session_id,
        "session_status": "CANCELLED",
        "ended_at": ended_at,
        "message": (
            "Attendance session cancelled. "
            "The generated QR code is no longer valid."
        ),
    }