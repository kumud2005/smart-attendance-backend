from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.user import User


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

    role_name = str(
        current_user.role.role_name
    ).upper()

    if "." in role_name:
        role_name = role_name.split(".")[-1]

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
):
    _verify_student(current_user)

    profile = db.execute(
        text(
            """
            SELECT
                student_id,
                user_id,
                enrollment_number,
                roll_number,
                date_of_birth,
                created_at
            FROM student_profiles
            WHERE user_id = :user_id
            LIMIT 1
            """
        ),
        {
            "user_id": current_user.user_id,
        },
    ).mappings().first()

    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found.",
        )

    return profile


# ============================================================
# GET CURRENT SECTION
# ============================================================

def _get_student_section(
    db: Session,
    student_id: int,
):
    return db.execute(
        text(
            """
            SELECT
                sec.section_id,
                sec.section_name,
                sec.program_id,
                sec.branch_id,
                sec.academic_year_id,
                sec.semester_id,

                sem.semester_number,
                sem.semester_name

            FROM student_section_assignments ssa

            INNER JOIN sections sec
                ON sec.section_id = ssa.section_id

            LEFT JOIN semesters sem
                ON sem.semester_id = sec.semester_id

            WHERE ssa.student_id = :student_id
              AND ssa.is_active = 1
              AND sec.is_active = 1

            ORDER BY ssa.section_id DESC

            LIMIT 1
            """
        ),
        {
            "student_id": student_id,
        },
    ).mappings().first()


# ============================================================
# GET SUBJECT COUNT
# ============================================================

def _get_subject_count(
    db: Session,
    section_id: int | None,
) -> int:
    if section_id is None:
        return 0

    result = db.execute(
        text(
            """
            SELECT COUNT(
                DISTINCT fsa.subject_id
            )

            FROM faculty_subject_assignments fsa

            INNER JOIN subjects s
                ON s.subject_id = fsa.subject_id

            WHERE fsa.section_id = :section_id
              AND fsa.is_active = 1
              AND s.is_active = 1
            """
        ),
        {
            "section_id": section_id,
        },
    ).scalar()

    return int(result or 0)


# ============================================================
# GET CLASS / SESSION COUNT
# ============================================================

def _get_class_count(
    db: Session,
    section_id: int | None,
) -> int:
    if section_id is None:
        return 0

    result = db.execute(
        text(
            """
            SELECT COUNT(
                DISTINCT session_id
            )

            FROM attendance_sessions

            WHERE section_id = :section_id
              AND session_status <> 'CANCELLED'
            """
        ),
        {
            "section_id": section_id,
        },
    ).scalar()

    return int(result or 0)


# ============================================================
# GET ATTENDANCE STATISTICS
# ============================================================

def _get_attendance_statistics(
    db: Session,
    student_id: int,
) -> dict:
    row = db.execute(
        text(
            """
            SELECT
                COUNT(
                    attendance_id
                ) AS attendance_count,

                SUM(
                    CASE
                        WHEN attendance_status = 'PRESENT'
                        THEN 1
                        ELSE 0
                    END
                ) AS present_count,

                SUM(
                    CASE
                        WHEN attendance_status = 'PENDING'
                        THEN 1
                        ELSE 0
                    END
                ) AS pending_count,

                SUM(
                    CASE
                        WHEN attendance_status = 'REJECTED'
                        THEN 1
                        ELSE 0
                    END
                ) AS rejected_count

            FROM attendance_records

            WHERE student_id = :student_id
            """
        ),
        {
            "student_id": student_id,
        },
    ).mappings().first()

    if row is None:
        return {
            "attendance_count": 0,
            "present_count": 0,
            "pending_count": 0,
            "rejected_count": 0,
        }

    return {
        "attendance_count": int(
            row["attendance_count"] or 0
        ),
        "present_count": int(
            row["present_count"] or 0
        ),
        "pending_count": int(
            row["pending_count"] or 0
        ),
        "rejected_count": int(
            row["rejected_count"] or 0
        ),
    }


# ============================================================
# GET RECENT ATTENDANCE
# ============================================================

def _get_recent_attendance(
    db: Session,
    student_id: int,
) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT
                ar.attendance_id,
                ar.session_id,

                ats.subject_id,
                s.subject_code,
                s.subject_name,

                ats.section_id,
                sec.section_name,

                ar.qr_verified,
                ar.geofence_verified,
                ar.face_verified,
                ar.liveness_verified,

                ar.attendance_status,
                ar.rejection_reason,

                ats.started_at,
                ats.ended_at

            FROM attendance_records ar

            INNER JOIN attendance_sessions ats
                ON ats.session_id = ar.session_id

            INNER JOIN subjects s
                ON s.subject_id = ats.subject_id

            INNER JOIN sections sec
                ON sec.section_id = ats.section_id

            WHERE ar.student_id = :student_id

            ORDER BY ar.attendance_id DESC

            LIMIT 10
            """
        ),
        {
            "student_id": student_id,
        },
    ).mappings().all()

    return [
        {
            "attendance_id":
                int(row["attendance_id"]),

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

            "qr_verified":
                bool(row["qr_verified"]),

            "geofence_verified":
                bool(row["geofence_verified"]),

            "face_verified":
                bool(row["face_verified"]),

            "liveness_verified":
                bool(row["liveness_verified"]),

            "attendance_status":
                str(row["attendance_status"]),

            "rejection_reason":
                row["rejection_reason"],

            "started_at":
                row["started_at"],

            "ended_at":
                row["ended_at"],
        }
        for row in rows
    ]


# ============================================================
# BUILD STUDENT DASHBOARD
# ============================================================

def get_student_dashboard(
    db: Session,
    current_user: User,
) -> dict:
    profile = _get_student_profile(
        db=db,
        current_user=current_user,
    )

    student_id = int(
        profile["student_id"]
    )

    # --------------------------------------------------------
    # CURRENT SECTION / SEMESTER
    # --------------------------------------------------------

    section = _get_student_section(
        db=db,
        student_id=student_id,
    )

    section_id = (
        int(section["section_id"])
        if section is not None
        else None
    )

    # --------------------------------------------------------
    # STATISTICS
    # --------------------------------------------------------

    subject_count = _get_subject_count(
        db=db,
        section_id=section_id,
    )

    class_count = _get_class_count(
        db=db,
        section_id=section_id,
    )

    attendance_stats = (
        _get_attendance_statistics(
            db=db,
            student_id=student_id,
        )
    )

    present_count = attendance_stats[
        "present_count"
    ]

    attendance_percentage = 0.0

    if class_count > 0:
        attendance_percentage = round(
            (
                present_count
                / class_count
            )
            * 100,
            2,
        )

    # --------------------------------------------------------
    # RECENT ATTENDANCE
    # --------------------------------------------------------

    recent_attendance = (
        _get_recent_attendance(
            db=db,
            student_id=student_id,
        )
    )

    # --------------------------------------------------------
    # ROLE
    # --------------------------------------------------------

    role_name = ""

    if current_user.role is not None:
        role_name = str(
            current_user.role.role_name
        )

        if "." in role_name:
            role_name = (
                role_name
                .split(".")[-1]
            )

    # --------------------------------------------------------
    # FINAL RESPONSE
    # --------------------------------------------------------

    return {
        # ----------------------------------------------------
        # USER
        # ----------------------------------------------------

        "user_id":
            current_user.user_id,

        "student_id":
            student_id,

        "full_name":
            current_user.full_name,

        "email":
            current_user.email,

        "phone":
            current_user.phone,

        "role_name":
            role_name,

        "account_status":
            str(
                current_user.account_status
            ),

        # ----------------------------------------------------
        # STUDENT PROFILE
        # ----------------------------------------------------

        "enrollment_number":
            profile[
                "enrollment_number"
            ],

        "roll_number":
            profile["roll_number"],

        "date_of_birth":
            profile["date_of_birth"],

        # ----------------------------------------------------
        # SECTION / SEMESTER
        # ----------------------------------------------------

        "section_id": (
            int(section["section_id"])
            if section is not None
            else None
        ),

        "section_name": (
            section["section_name"]
            if section is not None
            else None
        ),

        "semester_id": (
            int(section["semester_id"])
            if section is not None
            and section["semester_id"]
            is not None
            else None
        ),

        "semester_number": (
            int(
                section[
                    "semester_number"
                ]
            )
            if section is not None
            and section[
                "semester_number"
            ] is not None
            else None
        ),

        "semester_name": (
            section["semester_name"]
            if section is not None
            else None
        ),

        "program_id": (
            int(section["program_id"])
            if section is not None
            and section["program_id"]
            is not None
            else None
        ),

        "branch_id": (
            int(section["branch_id"])
            if section is not None
            and section["branch_id"]
            is not None
            else None
        ),

        "academic_year_id": (
            int(
                section[
                    "academic_year_id"
                ]
            )
            if section is not None
            and section[
                "academic_year_id"
            ] is not None
            else None
        ),

        # ----------------------------------------------------
        # STATISTICS
        # ----------------------------------------------------

        "subject_count":
            subject_count,

        "class_count":
            class_count,

        "attendance_count":
            attendance_stats[
                "attendance_count"
            ],

        "present_count":
            present_count,

        "pending_count":
            attendance_stats[
                "pending_count"
            ],

        "rejected_count":
            attendance_stats[
                "rejected_count"
            ],

        "attendance_percentage":
            attendance_percentage,

        # ----------------------------------------------------
        # RECENT ATTENDANCE
        # ----------------------------------------------------

        "recent_attendance":
            recent_attendance,
    }


# ============================================================
# ATTENDANCE REPORT HELPERS
# ============================================================

def _attendance_percentage(
    present_count: int,
    total_classes: int,
) -> float:
    if total_classes <= 0:
        return 0.0

    return round(
        (
            present_count
            / total_classes
        )
        * 100,
        2,
    )


# ============================================================
# GET REPORT SUMMARY
# ============================================================

def _get_attendance_report_summary(
    db: Session,
    student_id: int,
    section_id: int,
) -> dict:
    row = db.execute(
        text(
            """
            SELECT
                COUNT(
                    ats.session_id
                ) AS total_classes,

                SUM(
                    CASE
                        WHEN ar.attendance_id IS NOT NULL
                        THEN 1
                        ELSE 0
                    END
                ) AS attendance_records,

                SUM(
                    CASE
                        WHEN ar.attendance_status = 'PRESENT'
                        THEN 1
                        ELSE 0
                    END
                ) AS present_count,

                SUM(
                    CASE
                        WHEN ar.attendance_status = 'PENDING'
                        THEN 1
                        ELSE 0
                    END
                ) AS pending_count,

                SUM(
                    CASE
                        WHEN ar.attendance_status = 'REJECTED'
                        THEN 1
                        ELSE 0
                    END
                ) AS rejected_count,

                SUM(
                    CASE
                        WHEN ar.attendance_id IS NULL
                        THEN 1
                        ELSE 0
                    END
                ) AS not_marked_count

            FROM attendance_sessions ats

            LEFT JOIN attendance_records ar
                ON ar.session_id = ats.session_id
               AND ar.student_id = :student_id

            WHERE ats.section_id = :section_id
              AND ats.session_status <> 'CANCELLED'
            """
        ),
        {
            "student_id": student_id,
            "section_id": section_id,
        },
    ).mappings().first()

    if row is None:
        return {
            "total_classes": 0,
            "attendance_records": 0,
            "present": 0,
            "pending": 0,
            "rejected": 0,
            "not_marked": 0,
            "attendance_percentage": 0.0,
        }

    total_classes = int(
        row["total_classes"] or 0
    )

    present_count = int(
        row["present_count"] or 0
    )

    return {
        "total_classes":
            total_classes,

        "attendance_records":
            int(
                row[
                    "attendance_records"
                ]
                or 0
            ),

        "present":
            present_count,

        "pending":
            int(
                row["pending_count"]
                or 0
            ),

        "rejected":
            int(
                row["rejected_count"]
                or 0
            ),

        "not_marked":
            int(
                row["not_marked_count"]
                or 0
            ),

        "attendance_percentage":
            _attendance_percentage(
                present_count=
                    present_count,
                total_classes=
                    total_classes,
            ),
    }


# ============================================================
# GET SUBJECT-WISE REPORT
# ============================================================

def _get_subject_wise_attendance_report(
    db: Session,
    student_id: int,
    section_id: int,
) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT
                ats.subject_id,
                s.subject_code,
                s.subject_name,

                COUNT(
                    ats.session_id
                ) AS total_classes,

                SUM(
                    CASE
                        WHEN ar.attendance_status = 'PRESENT'
                        THEN 1
                        ELSE 0
                    END
                ) AS present_count,

                SUM(
                    CASE
                        WHEN ar.attendance_status = 'PENDING'
                        THEN 1
                        ELSE 0
                    END
                ) AS pending_count,

                SUM(
                    CASE
                        WHEN ar.attendance_status = 'REJECTED'
                        THEN 1
                        ELSE 0
                    END
                ) AS rejected_count,

                SUM(
                    CASE
                        WHEN ar.attendance_id IS NULL
                        THEN 1
                        ELSE 0
                    END
                ) AS not_marked_count

            FROM attendance_sessions ats

            INNER JOIN subjects s
                ON s.subject_id = ats.subject_id

            LEFT JOIN attendance_records ar
                ON ar.session_id = ats.session_id
               AND ar.student_id = :student_id

            WHERE ats.section_id = :section_id
              AND ats.session_status <> 'CANCELLED'

            GROUP BY
                ats.subject_id,
                s.subject_code,
                s.subject_name

            ORDER BY
                s.subject_code ASC,
                s.subject_name ASC
            """
        ),
        {
            "student_id": student_id,
            "section_id": section_id,
        },
    ).mappings().all()

    result: list[dict] = []

    for row in rows:
        total_classes = int(
            row["total_classes"] or 0
        )

        present_count = int(
            row["present_count"] or 0
        )

        result.append(
            {
                "subject_id":
                    int(
                        row["subject_id"]
                    ),

                "subject_code":
                    row["subject_code"],

                "subject_name":
                    row["subject_name"],

                "total_classes":
                    total_classes,

                "present":
                    present_count,

                "pending":
                    int(
                        row[
                            "pending_count"
                        ]
                        or 0
                    ),

                "rejected":
                    int(
                        row[
                            "rejected_count"
                        ]
                        or 0
                    ),

                "not_marked":
                    int(
                        row[
                            "not_marked_count"
                        ]
                        or 0
                    ),

                "attendance_percentage":
                    _attendance_percentage(
                        present_count=
                            present_count,
                        total_classes=
                            total_classes,
                    ),
            }
        )

    return result


# ============================================================
# GET DAY-WISE REPORT
# ============================================================

def _get_day_wise_attendance_report(
    db: Session,
    student_id: int,
    section_id: int,
) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT
                DATE(
                    ats.started_at
                ) AS attendance_date,

                COUNT(
                    ats.session_id
                ) AS total_classes,

                SUM(
                    CASE
                        WHEN ar.attendance_status = 'PRESENT'
                        THEN 1
                        ELSE 0
                    END
                ) AS present_count,

                SUM(
                    CASE
                        WHEN ar.attendance_status = 'PENDING'
                        THEN 1
                        ELSE 0
                    END
                ) AS pending_count,

                SUM(
                    CASE
                        WHEN ar.attendance_status = 'REJECTED'
                        THEN 1
                        ELSE 0
                    END
                ) AS rejected_count,

                SUM(
                    CASE
                        WHEN ar.attendance_id IS NULL
                        THEN 1
                        ELSE 0
                    END
                ) AS not_marked_count

            FROM attendance_sessions ats

            LEFT JOIN attendance_records ar
                ON ar.session_id = ats.session_id
               AND ar.student_id = :student_id

            WHERE ats.section_id = :section_id
              AND ats.session_status <> 'CANCELLED'

            GROUP BY
                DATE(
                    ats.started_at
                )

            ORDER BY
                DATE(
                    ats.started_at
                ) DESC
            """
        ),
        {
            "student_id": student_id,
            "section_id": section_id,
        },
    ).mappings().all()

    result: list[dict] = []

    for row in rows:
        total_classes = int(
            row["total_classes"] or 0
        )

        present_count = int(
            row["present_count"] or 0
        )

        attendance_date = (
            row["attendance_date"]
        )

        result.append(
            {
                "date": (
                    attendance_date.isoformat()
                    if attendance_date
                    is not None
                    else None
                ),

                "total_classes":
                    total_classes,

                "present":
                    present_count,

                "pending":
                    int(
                        row[
                            "pending_count"
                        ]
                        or 0
                    ),

                "rejected":
                    int(
                        row[
                            "rejected_count"
                        ]
                        or 0
                    ),

                "not_marked":
                    int(
                        row[
                            "not_marked_count"
                        ]
                        or 0
                    ),

                "attendance_percentage":
                    _attendance_percentage(
                        present_count=
                            present_count,
                        total_classes=
                            total_classes,
                    ),
            }
        )

    return result


# ============================================================
# GET DETAILED ATTENDANCE RECORDS
# ============================================================

def _get_detailed_attendance_records(
    db: Session,
    student_id: int,
    section_id: int,
) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT
                ats.session_id,
                ats.subject_id,

                s.subject_code,
                s.subject_name,

                ats.section_id,
                sec.section_name,

                ats.started_at,
                ats.ended_at,
                ats.session_status,

                ar.attendance_id,
                ar.marked_at,

                ar.qr_verified,
                ar.geofence_verified,
                ar.face_verified,
                ar.liveness_verified,

                ar.attendance_status,
                ar.rejection_reason,

                ar.distance_from_classroom_meters

            FROM attendance_sessions ats

            INNER JOIN subjects s
                ON s.subject_id = ats.subject_id

            INNER JOIN sections sec
                ON sec.section_id = ats.section_id

            LEFT JOIN attendance_records ar
                ON ar.session_id = ats.session_id
               AND ar.student_id = :student_id

            WHERE ats.section_id = :section_id
              AND ats.session_status <> 'CANCELLED'

            ORDER BY
                ats.started_at DESC,
                ats.session_id DESC
            """
        ),
        {
            "student_id": student_id,
            "section_id": section_id,
        },
    ).mappings().all()

    records: list[dict] = []

    for row in rows:
        attendance_id = (
            int(
                row["attendance_id"]
            )
            if row["attendance_id"]
            is not None
            else None
        )

        started_at = (
            row["started_at"]
        )

        ended_at = (
            row["ended_at"]
        )

        marked_at = (
            row["marked_at"]
        )

        distance = (
            float(
                row[
                    "distance_from_classroom_meters"
                ]
            )
            if row[
                "distance_from_classroom_meters"
            ] is not None
            else None
        )

        attendance_status = (
            str(
                row[
                    "attendance_status"
                ]
            )
            if row[
                "attendance_status"
            ] is not None
            else "NOT_MARKED"
        )

        records.append(
            {
                "attendance_id":
                    attendance_id,

                "session_id":
                    int(
                        row["session_id"]
                    ),

                "subject_id":
                    int(
                        row["subject_id"]
                    ),

                "subject_code":
                    row["subject_code"],

                "subject_name":
                    row["subject_name"],

                "section_id":
                    int(
                        row["section_id"]
                    ),

                "section_name":
                    row["section_name"],

                "date": (
                    started_at
                    .date()
                    .isoformat()
                    if started_at
                    is not None
                    else None
                ),

                "started_at": (
                    started_at
                    .isoformat()
                    if started_at
                    is not None
                    else None
                ),

                "ended_at": (
                    ended_at
                    .isoformat()
                    if ended_at
                    is not None
                    else None
                ),

                "marked_at": (
                    marked_at
                    .isoformat()
                    if marked_at
                    is not None
                    else None
                ),

                "session_status":
                    str(
                        row[
                            "session_status"
                        ]
                    ),

                "attendance_status":
                    attendance_status,

                "qr_verified": (
                    bool(
                        row[
                            "qr_verified"
                        ]
                    )
                    if attendance_id
                    is not None
                    else False
                ),

                "geofence_verified": (
                    bool(
                        row[
                            "geofence_verified"
                        ]
                    )
                    if attendance_id
                    is not None
                    else False
                ),

                "face_verified": (
                    bool(
                        row[
                            "face_verified"
                        ]
                    )
                    if attendance_id
                    is not None
                    else False
                ),

                "liveness_verified": (
                    bool(
                        row[
                            "liveness_verified"
                        ]
                    )
                    if attendance_id
                    is not None
                    else False
                ),

                "rejection_reason":
                    row[
                        "rejection_reason"
                    ],

                "distance_from_classroom_meters":
                    distance,
            }
        )

    return records


# ============================================================
# BUILD COMPLETE STUDENT ATTENDANCE REPORT
# ============================================================

def get_student_attendance_report(
    db: Session,
    current_user: User,
) -> dict:
    profile = _get_student_profile(
        db=db,
        current_user=current_user,
    )

    student_id = int(
        profile["student_id"]
    )

    section = _get_student_section(
        db=db,
        student_id=student_id,
    )

    # --------------------------------------------------------
    # NO ACTIVE SECTION
    # --------------------------------------------------------

    if section is None:
        return {
            "student": {
                "student_id":
                    student_id,

                "full_name":
                    current_user.full_name,

                "enrollment_number":
                    profile[
                        "enrollment_number"
                    ],

                "roll_number":
                    profile[
                        "roll_number"
                    ],

                "section_id":
                    None,

                "section_name":
                    None,

                "semester_id":
                    None,

                "semester_name":
                    None,
            },

            "summary": {
                "total_classes": 0,
                "attendance_records": 0,
                "present": 0,
                "pending": 0,
                "rejected": 0,
                "not_marked": 0,
                "attendance_percentage": 0.0,
            },

            "subject_wise": [],
            "day_wise": [],
            "records": [],
        }

    section_id = int(
        section["section_id"]
    )

    summary = (
        _get_attendance_report_summary(
            db=db,
            student_id=student_id,
            section_id=section_id,
        )
    )

    subject_wise = (
        _get_subject_wise_attendance_report(
            db=db,
            student_id=student_id,
            section_id=section_id,
        )
    )

    day_wise = (
        _get_day_wise_attendance_report(
            db=db,
            student_id=student_id,
            section_id=section_id,
        )
    )

    records = (
        _get_detailed_attendance_records(
            db=db,
            student_id=student_id,
            section_id=section_id,
        )
    )

    return {
        "student": {
            "student_id":
                student_id,

            "full_name":
                current_user.full_name,

            "enrollment_number":
                profile[
                    "enrollment_number"
                ],

            "roll_number":
                profile[
                    "roll_number"
                ],

            "section_id":
                section_id,

            "section_name":
                section[
                    "section_name"
                ],

            "semester_id": (
                int(
                    section[
                        "semester_id"
                    ]
                )
                if section[
                    "semester_id"
                ] is not None
                else None
            ),

            "semester_name":
                section[
                    "semester_name"
                ],
        },

        "summary":
            summary,

        "subject_wise":
            subject_wise,

        "day_wise":
            day_wise,

        "records":
            records,
    }