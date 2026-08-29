from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.faculty_profile import FacultyProfile


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

def get_faculty_profile(
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
# GET ALL SEMESTERS
# ============================================================

def get_faculty_semesters(
    db: Session,
    current_user: User,
) -> list[dict]:
    """
    Return all semesters available in the system.

    Semester selection is the first step of the
    faculty attendance-session creation flow.
    """

    _verify_faculty(current_user)

    rows = db.execute(
        text(
            """
            SELECT
                semester_id,
                semester_number,
                semester_name
            FROM semesters
            ORDER BY semester_number
            """
        )
    ).mappings().all()

    return [
        {
            "semester_id": row["semester_id"],
            "semester_number": row["semester_number"],
            "semester_name": row["semester_name"],
        }
        for row in rows
    ]


# ============================================================
# GET SECTIONS FOR SELECTED SEMESTER
# ============================================================

def get_faculty_sections_for_semester(
    db: Session,
    current_user: User,
    semester_id: int,
) -> list[dict]:
    """
    Return active sections belonging to the selected semester.
    """

    _verify_faculty(current_user)

    rows = db.execute(
        text(
            """
            SELECT
                sec.section_id,
                sec.section_name,
                sec.semester_id,

                COUNT(
                    DISTINCT ssa.student_id
                ) AS student_count

            FROM sections sec

            LEFT JOIN student_section_assignments ssa
                ON ssa.section_id = sec.section_id
               AND ssa.is_active = 1

            WHERE sec.semester_id = :semester_id
              AND sec.is_active = 1

            GROUP BY
                sec.section_id,
                sec.section_name,
                sec.semester_id

            ORDER BY sec.section_name
            """
        ),
        {
            "semester_id": semester_id,
        },
    ).mappings().all()

    return [
        {
            "section_id": row["section_id"],
            "section_name": row["section_name"],
            "semester_id": row["semester_id"],
            "student_count": int(
                row["student_count"] or 0
            ),
        }
        for row in rows
    ]


# ============================================================
# GET FACULTY SUBJECTS FOR SEMESTER + SECTION
# ============================================================

def get_faculty_subjects_for_section(
    db: Session,
    current_user: User,
    semester_id: int,
    section_id: int,
) -> list[dict]:
    """
    Return only subjects that:

        1. belong to the selected semester
        2. belong to the selected section
        3. are assigned to the logged-in faculty
        4. are active
    """

    faculty_profile = get_faculty_profile(
        db=db,
        current_user=current_user,
    )

    rows = db.execute(
        text(
            """
            SELECT DISTINCT
                s.subject_id,
                s.subject_code,
                s.subject_name,
                s.credits,
                s.semester_id

            FROM faculty_subject_assignments fsa

            INNER JOIN sections sec
                ON sec.section_id = fsa.section_id

            INNER JOIN subjects s
                ON s.subject_id = fsa.subject_id

            WHERE fsa.faculty_id = :faculty_id
              AND fsa.section_id = :section_id

              AND sec.semester_id = :semester_id
              AND s.semester_id = :semester_id

              AND fsa.is_active = 1
              AND sec.is_active = 1
              AND s.is_active = 1

            ORDER BY s.subject_name
            """
        ),
        {
            "faculty_id": faculty_profile.faculty_id,
            "semester_id": semester_id,
            "section_id": section_id,
        },
    ).mappings().all()

    return [
        {
            "subject_id": row["subject_id"],
            "subject_code": row["subject_code"],
            "subject_name": row["subject_name"],
            "credits": (
                float(row["credits"])
                if row["credits"] is not None
                else None
            ),
            "semester_id": row["semester_id"],
            "section_id": section_id,
        }
        for row in rows
    ]


# ============================================================
# GET ASSIGNED SUBJECTS
# ============================================================

def _get_subjects(
    db: Session,
    faculty_id: int,
) -> list[dict]:

    query = text(
        """
        SELECT DISTINCT
            s.subject_id,
            s.subject_code,
            s.subject_name,
            s.credits
        FROM faculty_subject_assignments fsa
        INNER JOIN subjects s
            ON s.subject_id = fsa.subject_id
        WHERE fsa.faculty_id = :faculty_id
          AND fsa.is_active = 1
          AND s.is_active = 1
        ORDER BY s.subject_name
        """
    )

    rows = db.execute(
        query,
        {
            "faculty_id": faculty_id,
        },
    ).mappings().all()

    return [
        {
            "subject_id": row["subject_id"],
            "subject_code": row["subject_code"],
            "subject_name": row["subject_name"],
            "credits": (
                float(row["credits"])
                if row["credits"] is not None
                else None
            ),
        }
        for row in rows
    ]


# ============================================================
# GET ASSIGNED SECTIONS
# ============================================================

def _get_sections(
    db: Session,
    faculty_id: int,
) -> list[dict]:

    query = text(
        """
        SELECT
            s.section_id,
            s.section_name,

            COUNT(
                DISTINCT ssa.student_id
            ) AS student_count

        FROM faculty_subject_assignments fsa

        INNER JOIN sections s
            ON s.section_id = fsa.section_id

        LEFT JOIN student_section_assignments ssa
            ON ssa.section_id = s.section_id
           AND ssa.is_active = 1

        WHERE fsa.faculty_id = :faculty_id
          AND fsa.is_active = 1
          AND s.is_active = 1

        GROUP BY
            s.section_id,
            s.section_name

        ORDER BY s.section_name
        """
    )

    rows = db.execute(
        query,
        {
            "faculty_id": faculty_id,
        },
    ).mappings().all()

    return [
        {
            "section_id": row["section_id"],
            "section_name": row["section_name"],
            "student_count": int(
                row["student_count"] or 0
            ),
        }
        for row in rows
    ]


# ============================================================
# GET STUDENT COUNT
# ============================================================

def _get_student_count(
    db: Session,
    faculty_id: int,
) -> int:

    query = text(
        """
        SELECT COUNT(DISTINCT ssa.student_id)

        FROM faculty_subject_assignments fsa

        INNER JOIN student_section_assignments ssa
            ON ssa.section_id = fsa.section_id

        WHERE fsa.faculty_id = :faculty_id
          AND fsa.is_active = 1
          AND ssa.is_active = 1
        """
    )

    result = db.execute(
        query,
        {
            "faculty_id": faculty_id,
        },
    ).scalar()

    return int(result or 0)


# ============================================================
# GET ATTENDANCE COUNT
# ============================================================

def _get_attendance_count(
    db: Session,
    faculty_id: int,
) -> int:

    query = text(
        """
        SELECT COUNT(ar.attendance_id)

        FROM attendance_records ar

        INNER JOIN attendance_sessions ats
            ON ats.session_id = ar.session_id

        WHERE ats.faculty_id = :faculty_id
        """
    )

    result = db.execute(
        query,
        {
            "faculty_id": faculty_id,
        },
    ).scalar()

    return int(result or 0)


# ============================================================
# GET RECENT ATTENDANCE SESSIONS
# ============================================================

def _get_recent_sessions(
    db: Session,
    faculty_id: int,
) -> list[dict]:

    query = text(
        """
        SELECT
            ats.session_id,

            ats.subject_id,
            s.subject_name,

            ats.section_id,
            sec.section_name,

            ats.classroom_id,

            ats.session_status,
            ats.started_at,
            ats.ended_at,
            ats.qr_expires_at,

            COUNT(
                ar.attendance_id
            ) AS attendance_count

        FROM attendance_sessions ats

        INNER JOIN subjects s
            ON s.subject_id = ats.subject_id

        INNER JOIN sections sec
            ON sec.section_id = ats.section_id

        LEFT JOIN attendance_records ar
            ON ar.session_id = ats.session_id

        WHERE ats.faculty_id = :faculty_id

        GROUP BY
            ats.session_id,
            ats.subject_id,
            s.subject_name,
            ats.section_id,
            sec.section_name,
            ats.classroom_id,
            ats.session_status,
            ats.started_at,
            ats.ended_at,
            ats.qr_expires_at

        ORDER BY ats.started_at DESC

        LIMIT 10
        """
    )

    rows = db.execute(
        query,
        {
            "faculty_id": faculty_id,
        },
    ).mappings().all()

    return [
        {
            "session_id":
                row["session_id"],

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

            "session_status":
                str(row["session_status"]),

            "started_at":
                row["started_at"],

            "ended_at":
                row["ended_at"],

            "qr_expires_at":
                row["qr_expires_at"],

            "attendance_count":
                int(
                    row["attendance_count"] or 0
                ),
        }
        for row in rows
    ]


# ============================================================
# GET FACULTY CLASSROOMS
# ============================================================

def get_faculty_classrooms(
    db: Session,
    current_user: User,
) -> list[dict]:
    """
    Return active classrooms available for
    attendance-session creation.
    """

    _verify_faculty(current_user)

    rows = db.execute(
        text(
            """
            SELECT
                classroom_id,
                building_name,
                room_number,
                latitude,
                longitude,
                geofence_radius_meters,
                is_active

            FROM classrooms

            WHERE is_active = 1

            ORDER BY
                building_name,
                room_number
            """
        )
    ).mappings().all()

    return [
        {
            "classroom_id":
                row["classroom_id"],

            "building_name":
                row["building_name"],

            "room_number":
                row["room_number"],

            "latitude": (
                float(row["latitude"])
                if row["latitude"] is not None
                else None
            ),

            "longitude": (
                float(row["longitude"])
                if row["longitude"] is not None
                else None
            ),

            "geofence_radius_meters": (
                float(
                    row["geofence_radius_meters"]
                )
                if row["geofence_radius_meters"]
                is not None
                else None
            ),

            "is_active":
                bool(row["is_active"]),
        }
        for row in rows
    ]


# ============================================================
# GET FACULTY STUDENTS
# ============================================================

def get_faculty_students(
    db: Session,
    current_user: User,
) -> list[dict]:
    """
    Return active students belonging to sections
    assigned to the authenticated faculty.
    """

    faculty_profile = get_faculty_profile(
        db=db,
        current_user=current_user,
    )

    rows = db.execute(
        text(
            """
            SELECT DISTINCT

                sp.student_id,
                sp.enrollment_number,
                sp.roll_number,

                u.full_name,
                u.email,

                sec.section_id,
                sec.section_name

            FROM faculty_subject_assignments fsa

            INNER JOIN sections sec
                ON sec.section_id = fsa.section_id

            INNER JOIN student_section_assignments ssa
                ON ssa.section_id = sec.section_id
               AND ssa.is_active = 1

            INNER JOIN student_profiles sp
                ON sp.student_id = ssa.student_id

            INNER JOIN users u
                ON u.user_id = sp.user_id

            WHERE fsa.faculty_id = :faculty_id
              AND fsa.is_active = 1
              AND sec.is_active = 1

            ORDER BY
                sec.section_name,
                sp.roll_number,
                u.full_name
            """
        ),
        {
            "faculty_id":
                faculty_profile.faculty_id,
        },
    ).mappings().all()

    return [
        {
            "student_id":
                row["student_id"],

            "enrollment_number":
                row["enrollment_number"],

            "roll_number":
                row["roll_number"],

            "full_name":
                row["full_name"],

            "email":
                row["email"],

            "section_id":
                row["section_id"],

            "section_name":
                row["section_name"],
        }
        for row in rows
    ]


# ============================================================
# BUILD FACULTY DASHBOARD
# ============================================================

def get_faculty_dashboard(
    db: Session,
    current_user: User,
) -> dict:

    faculty_profile = get_faculty_profile(
        db=db,
        current_user=current_user,
    )

    role_name = ""

    if current_user.role is not None:
        role_name = str(
            current_user.role.role_name
        )

    # --------------------------------------------------------
    # ASSIGNED SUBJECTS
    # --------------------------------------------------------

    subjects = _get_subjects(
        db=db,
        faculty_id=faculty_profile.faculty_id,
    )

    # --------------------------------------------------------
    # ASSIGNED SECTIONS
    # --------------------------------------------------------

    sections = _get_sections(
        db=db,
        faculty_id=faculty_profile.faculty_id,
    )

    # --------------------------------------------------------
    # STUDENTS
    # --------------------------------------------------------

    student_count = _get_student_count(
        db=db,
        faculty_id=faculty_profile.faculty_id,
    )

    # --------------------------------------------------------
    # ATTENDANCE
    # --------------------------------------------------------

    attendance_count = _get_attendance_count(
        db=db,
        faculty_id=faculty_profile.faculty_id,
    )

    # --------------------------------------------------------
    # RECENT SESSIONS
    # --------------------------------------------------------

    recent_sessions = _get_recent_sessions(
        db=db,
        faculty_id=faculty_profile.faculty_id,
    )

    # --------------------------------------------------------
    # FINAL RESPONSE
    # --------------------------------------------------------

    return {
        "user_id":
            current_user.user_id,

        "faculty_id":
            faculty_profile.faculty_id,

        "employee_id":
            faculty_profile.employee_id,

        "full_name":
            current_user.full_name,

        "email":
            current_user.email,

        "phone":
            current_user.phone,

        "department":
            faculty_profile.department,

        "designation":
            faculty_profile.designation,

        "role_name":
            role_name,

        "account_status":
            str(current_user.account_status),

        "created_at":
            current_user.created_at,

        "updated_at":
            current_user.updated_at,

        "last_login_at":
            current_user.last_login_at,

        # ----------------------------------------------------
        # STATISTICS
        # ----------------------------------------------------

        "subject_count":
            len(subjects),

        "section_count":
            len(sections),

        "student_count":
            student_count,

        "attendance_count":
            attendance_count,

        # ----------------------------------------------------
        # ASSIGNED DATA
        # ----------------------------------------------------

        "subjects":
            subjects,

        "sections":
            sections,

        # ----------------------------------------------------
        # RECENT SESSIONS
        # ----------------------------------------------------

        "recent_sessions":
            recent_sessions,
    }

# ============================================================
# FACULTY ATTENDANCE REPORT HELPERS
# ============================================================

def _attendance_percentage(
    present: int,
    total: int,
) -> float:
    if total <= 0:
        return 0.0

    return round(
        (present / total) * 100.0,
        2,
    )


def _normalize_status(
    value,
) -> str:
    if value is None:
        return "NOT_MARKED"

    normalized = str(value).upper()

    if "." in normalized:
        normalized = normalized.split(".")[-1]

    return normalized


def _build_faculty_report_filters(
    faculty_id: int,
    semester_id: int | None,
    section_id: int | None,
    subject_id: int | None,
    date_from,
    date_to,
) -> tuple[str, dict]:
    conditions = [
        "ats.faculty_id = :faculty_id",
        "ats.session_status <> 'CANCELLED'",
    ]

    params = {
        "faculty_id": faculty_id,
    }

    if semester_id is not None:
        conditions.append(
            "sec.semester_id = :semester_id"
        )
        params["semester_id"] = semester_id

    if section_id is not None:
        conditions.append(
            "ats.section_id = :section_id"
        )
        params["section_id"] = section_id

    if subject_id is not None:
        conditions.append(
            "ats.subject_id = :subject_id"
        )
        params["subject_id"] = subject_id

    if date_from is not None:
        conditions.append(
            "DATE(ats.started_at) >= :date_from"
        )
        params["date_from"] = date_from

    if date_to is not None:
        conditions.append(
            "DATE(ats.started_at) <= :date_to"
        )
        params["date_to"] = date_to

    return (
        "\n              AND ".join(conditions),
        params,
    )


def _get_faculty_report_rows(
    db: Session,
    faculty_id: int,
    semester_id: int | None = None,
    section_id: int | None = None,
    subject_id: int | None = None,
    date_from=None,
    date_to=None,
) -> list[dict]:
    where_sql, params = (
        _build_faculty_report_filters(
            faculty_id=faculty_id,
            semester_id=semester_id,
            section_id=section_id,
            subject_id=subject_id,
            date_from=date_from,
            date_to=date_to,
        )
    )

    rows = db.execute(
        text(
            f"""
            SELECT
                ats.session_id,
                ats.subject_id,
                s.subject_code,
                s.subject_name,

                ats.section_id,
                sec.section_name,
                sec.semester_id,

                ats.classroom_id,
                c.building_name,
                c.room_number,

                ats.started_at,
                ats.ended_at,
                ats.session_status,

                sp.student_id,
                sp.enrollment_number,
                sp.roll_number,
                u.full_name AS student_name,
                u.email AS student_email,

                ar.attendance_id,
                ar.marked_at,
                ar.distance_from_classroom_meters,
                ar.qr_verified,
                ar.geofence_verified,
                ar.face_verified,
                ar.liveness_verified,
                ar.attendance_status,
                ar.rejection_reason

            FROM attendance_sessions ats

            INNER JOIN subjects s
                ON s.subject_id = ats.subject_id

            INNER JOIN sections sec
                ON sec.section_id = ats.section_id

            LEFT JOIN classrooms c
                ON c.classroom_id = ats.classroom_id

            INNER JOIN student_section_assignments ssa
                ON ssa.section_id = ats.section_id
               AND ssa.is_active = 1

            INNER JOIN student_profiles sp
                ON sp.student_id = ssa.student_id

            INNER JOIN users u
                ON u.user_id = sp.user_id

            LEFT JOIN attendance_records ar
                ON ar.session_id = ats.session_id
               AND ar.student_id = sp.student_id

            WHERE {where_sql}

            ORDER BY
                ats.started_at DESC,
                ats.session_id DESC,
                sp.roll_number,
                u.full_name
            """
        ),
        params,
    ).mappings().all()

    result: list[dict] = []

    for row in rows:
        attendance_id = (
            int(row["attendance_id"])
            if row["attendance_id"] is not None
            else None
        )

        started_at = row["started_at"]
        ended_at = row["ended_at"]
        marked_at = row["marked_at"]

        attendance_status = _normalize_status(
            row["attendance_status"]
        )

        session_status = _normalize_status(
            row["session_status"]
        )

        result.append(
            {
                "session_id":
                    int(row["session_id"]),

                "subject_id":
                    int(row["subject_id"]),

                "subject_code":
                    row["subject_code"],

                "subject_name":
                    row["subject_name"],

                "section_id":
                    int(row["section_id"]),

                "section_name":
                    row["section_name"],

                "semester_id":
                    int(row["semester_id"]),

                "classroom_id": (
                    int(row["classroom_id"])
                    if row["classroom_id"] is not None
                    else None
                ),

                "building_name":
                    row["building_name"],

                "room_number":
                    row["room_number"],

                "date": (
                    started_at.date().isoformat()
                    if started_at is not None
                    else None
                ),

                "started_at": (
                    started_at.isoformat()
                    if started_at is not None
                    else None
                ),

                "ended_at": (
                    ended_at.isoformat()
                    if ended_at is not None
                    else None
                ),

                "session_status":
                    session_status,

                "student_id":
                    int(row["student_id"]),

                "enrollment_number":
                    row["enrollment_number"],

                "roll_number":
                    row["roll_number"],

                "student_name":
                    row["student_name"],

                "student_email":
                    row["student_email"],

                "attendance_id":
                    attendance_id,

                "marked_at": (
                    marked_at.isoformat()
                    if marked_at is not None
                    else None
                ),

                "attendance_status":
                    attendance_status,

                "qr_verified": (
                    bool(row["qr_verified"])
                    if attendance_id is not None
                    else False
                ),

                "geofence_verified": (
                    bool(row["geofence_verified"])
                    if attendance_id is not None
                    else False
                ),

                "face_verified": (
                    bool(row["face_verified"])
                    if attendance_id is not None
                    else False
                ),

                "liveness_verified": (
                    bool(row["liveness_verified"])
                    if attendance_id is not None
                    else False
                ),

                "distance_from_classroom_meters": (
                    float(
                        row[
                            "distance_from_classroom_meters"
                        ]
                    )
                    if row[
                        "distance_from_classroom_meters"
                    ] is not None
                    else None
                ),

                "rejection_reason":
                    row["rejection_reason"],
            }
        )

    return result


def _faculty_report_summary(
    rows: list[dict],
) -> dict:
    session_ids = {
        row["session_id"]
        for row in rows
    }

    student_ids = {
        row["student_id"]
        for row in rows
    }

    total_opportunities = len(rows)

    attendance_records = sum(
        1
        for row in rows
        if row["attendance_id"] is not None
    )

    present = sum(
        1
        for row in rows
        if row["attendance_status"] == "PRESENT"
    )

    pending = sum(
        1
        for row in rows
        if row["attendance_status"] == "PENDING"
    )

    rejected = sum(
        1
        for row in rows
        if row["attendance_status"] == "REJECTED"
    )

    not_marked = sum(
        1
        for row in rows
        if row["attendance_status"] == "NOT_MARKED"
    )

    return {
        "total_sessions":
            len(session_ids),

        "total_students":
            len(student_ids),

        "attendance_opportunities":
            total_opportunities,

        "attendance_records":
            attendance_records,

        "present":
            present,

        "pending":
            pending,

        "rejected":
            rejected,

        "not_marked":
            not_marked,

        "attendance_percentage":
            _attendance_percentage(
                present=present,
                total=total_opportunities,
            ),
    }


def _group_faculty_report_rows(
    rows: list[dict],
    key_fields: tuple[str, ...],
) -> list[dict]:
    groups: dict[tuple, dict] = {}

    for row in rows:
        key = tuple(
            row[field]
            for field in key_fields
        )

        group = groups.get(key)

        if group is None:
            group = {
                field: row[field]
                for field in key_fields
            }

            group.update(
                {
                    "_session_ids": set(),
                    "attendance_opportunities": 0,
                    "attendance_records": 0,
                    "present": 0,
                    "pending": 0,
                    "rejected": 0,
                    "not_marked": 0,
                }
            )

            groups[key] = group

        group["_session_ids"].add(
            row["session_id"]
        )

        group[
            "attendance_opportunities"
        ] += 1

        if row["attendance_id"] is not None:
            group["attendance_records"] += 1

        attendance_status = (
            row["attendance_status"]
        )

        if attendance_status == "PRESENT":
            group["present"] += 1
        elif attendance_status == "PENDING":
            group["pending"] += 1
        elif attendance_status == "REJECTED":
            group["rejected"] += 1
        else:
            group["not_marked"] += 1

    result: list[dict] = []

    for group in groups.values():
        session_count = len(
            group.pop("_session_ids")
        )

        group["session_count"] = (
            session_count
        )

        group["attendance_percentage"] = (
            _attendance_percentage(
                present=group["present"],
                total=group[
                    "attendance_opportunities"
                ],
            )
        )

        result.append(group)

    return result


def _faculty_subject_wise_report(
    rows: list[dict],
) -> list[dict]:
    result = _group_faculty_report_rows(
        rows=rows,
        key_fields=(
            "subject_id",
            "subject_code",
            "subject_name",
        ),
    )

    result.sort(
        key=lambda item: (
            str(item["subject_code"] or ""),
            str(item["subject_name"] or ""),
        )
    )

    return result


def _faculty_section_wise_report(
    rows: list[dict],
) -> list[dict]:
    result = _group_faculty_report_rows(
        rows=rows,
        key_fields=(
            "section_id",
            "section_name",
            "semester_id",
        ),
    )

    result.sort(
        key=lambda item: (
            int(item["semester_id"]),
            str(item["section_name"] or ""),
        )
    )

    return result


def _faculty_day_wise_report(
    rows: list[dict],
) -> list[dict]:
    result = _group_faculty_report_rows(
        rows=rows,
        key_fields=("date",),
    )

    result.sort(
        key=lambda item: (
            item["date"] or ""
        ),
        reverse=True,
    )

    return result


def _faculty_session_wise_report(
    rows: list[dict],
) -> list[dict]:
    groups: dict[int, dict] = {}

    for row in rows:
        session_id = row["session_id"]

        group = groups.get(session_id)

        if group is None:
            group = {
                "session_id":
                    session_id,

                "date":
                    row["date"],

                "started_at":
                    row["started_at"],

                "ended_at":
                    row["ended_at"],

                "session_status":
                    row["session_status"],

                "subject_id":
                    row["subject_id"],

                "subject_code":
                    row["subject_code"],

                "subject_name":
                    row["subject_name"],

                "section_id":
                    row["section_id"],

                "section_name":
                    row["section_name"],

                "semester_id":
                    row["semester_id"],

                "classroom_id":
                    row["classroom_id"],

                "building_name":
                    row["building_name"],

                "room_number":
                    row["room_number"],

                "expected_students": 0,
                "attendance_records": 0,
                "present": 0,
                "pending": 0,
                "rejected": 0,
                "not_marked": 0,
            }

            groups[session_id] = group

        group["expected_students"] += 1

        if row["attendance_id"] is not None:
            group["attendance_records"] += 1

        status_name = row["attendance_status"]

        if status_name == "PRESENT":
            group["present"] += 1
        elif status_name == "PENDING":
            group["pending"] += 1
        elif status_name == "REJECTED":
            group["rejected"] += 1
        else:
            group["not_marked"] += 1

    result = list(groups.values())

    for group in result:
        group["attendance_percentage"] = (
            _attendance_percentage(
                present=group["present"],
                total=group[
                    "expected_students"
                ],
            )
        )

    result.sort(
        key=lambda item: (
            item["started_at"] or ""
        ),
        reverse=True,
    )

    return result


# ============================================================
# BUILD COMPLETE FACULTY ATTENDANCE REPORT
# ============================================================

def get_faculty_attendance_report(
    db: Session,
    current_user: User,
    semester_id: int | None = None,
    section_id: int | None = None,
    subject_id: int | None = None,
    date_from=None,
    date_to=None,
) -> dict:
    faculty_profile = get_faculty_profile(
        db=db,
        current_user=current_user,
    )

    if (
        date_from is not None
        and date_to is not None
        and date_from > date_to
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "date_from cannot be later than date_to."
            ),
        )

    rows = _get_faculty_report_rows(
        db=db,
        faculty_id=faculty_profile.faculty_id,
        semester_id=semester_id,
        section_id=section_id,
        subject_id=subject_id,
        date_from=date_from,
        date_to=date_to,
    )

    return {
        "faculty": {
            "faculty_id":
                faculty_profile.faculty_id,

            "employee_id":
                faculty_profile.employee_id,

            "full_name":
                current_user.full_name,

            "email":
                current_user.email,

            "department":
                faculty_profile.department,

            "designation":
                faculty_profile.designation,
        },

        "filters": {
            "semester_id":
                semester_id,

            "section_id":
                section_id,

            "subject_id":
                subject_id,

            "date_from": (
                date_from.isoformat()
                if date_from is not None
                else None
            ),

            "date_to": (
                date_to.isoformat()
                if date_to is not None
                else None
            ),
        },

        "summary":
            _faculty_report_summary(
                rows
            ),

        "subject_wise":
            _faculty_subject_wise_report(
                rows
            ),

        "section_wise":
            _faculty_section_wise_report(
                rows
            ),

        "day_wise":
            _faculty_day_wise_report(
                rows
            ),

        "session_wise":
            _faculty_session_wise_report(
                rows
            ),

        "records":
            rows,
    }