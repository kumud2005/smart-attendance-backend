"""
Admin Dashboard Service
=======================

Contains all business logic used by the Admin Dashboard.

The service is intentionally separate from the API router so that
the same functionality can later be reused by other interfaces.
"""

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, joinedload

from app.models.user import User
from app.models.role import Role


# ============================================================
# HELPER: NORMALIZE ACCOUNT STATUS
# ============================================================

def _normalize_status(value) -> str:
    """
    Convert account status values/enums into plain uppercase strings.
    """

    if value is None:
        return ""

    value = str(value)

    if "." in value:
        value = value.split(".")[-1]

    return value.upper()


# ============================================================
# HELPER: USER LIST RESPONSE
# ============================================================

def _user_to_list_item(user: User) -> dict:
    """
    Convert a User SQLAlchemy object into the structure expected
    by AdminUserListItem.
    """

    role_name = None

    if user.role is not None:
        role_name = str(user.role.role_name)

        if "." in role_name:
            role_name = role_name.split(".")[-1]

        role_name = role_name.upper()

    return {
        "user_id": user.user_id,
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,
        "role_name": role_name or "",
        "account_status": _normalize_status(user.account_status),
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_login_at": user.last_login_at,
    }


# ============================================================
# HELPER: PROFILE RESPONSE
# ============================================================

def _user_to_detail(user: User) -> dict:
    """
    Convert a User SQLAlchemy object into the structure expected
    by AdminUserDetailResponse.
    """

    role_name = None

    if user.role is not None:
        role_name = str(user.role.role_name)

        if "." in role_name:
            role_name = role_name.split(".")[-1]

        role_name = role_name.upper()

    student_profile = None

    if user.student_profile is not None:
        profile = user.student_profile

        student_profile = {
            "student_id": profile.student_id,
            "enrollment_number": profile.enrollment_number,
            "roll_number": profile.roll_number,
            "date_of_birth": profile.date_of_birth,
        }

    faculty_profile = None

    if user.faculty_profile is not None:
        profile = user.faculty_profile

        faculty_profile = {
            "faculty_id": profile.faculty_id,
            "employee_id": profile.employee_id,
            "department": profile.department,
            "designation": profile.designation,
        }

    admin_profile = None

    if user.admin_profile is not None:
        profile = user.admin_profile

        admin_profile = {
            "admin_id": profile.admin_id,
            "employee_id": profile.employee_id,
            "designation": profile.designation,
        }

    return {
        "user_id": user.user_id,

        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,

        "role_name": role_name or "",

        "account_status": _normalize_status(
            user.account_status
        ),

        "created_at": user.created_at,
        "updated_at": user.updated_at,

        "last_login_at": user.last_login_at,

        "student_profile": student_profile,
        "faculty_profile": faculty_profile,
        "admin_profile": admin_profile,
    }


# ============================================================
# DASHBOARD STATISTICS
# ============================================================

def get_dashboard_statistics(
    db: Session,
) -> dict:
    """
    Return summary statistics for the Admin Dashboard.
    """

    # --------------------------------------------------------
    # TOTAL USERS
    # --------------------------------------------------------

    total_users = db.scalar(
        select(func.count(User.user_id))
    ) or 0

    # --------------------------------------------------------
    # STATUS COUNTS
    # --------------------------------------------------------

    pending_users = db.scalar(
        select(func.count(User.user_id))
        .where(User.account_status == "PENDING")
    ) or 0

    active_users = db.scalar(
        select(func.count(User.user_id))
        .where(User.account_status == "ACTIVE")
    ) or 0

    suspended_users = db.scalar(
        select(func.count(User.user_id))
        .where(User.account_status == "SUSPENDED")
    ) or 0

    inactive_users = db.scalar(
        select(func.count(User.user_id))
        .where(User.account_status == "INACTIVE")
    ) or 0

    # --------------------------------------------------------
    # ROLE COUNTS
    # --------------------------------------------------------

    total_students = db.scalar(
        select(func.count(User.user_id))
        .join(Role)
        .where(Role.role_name == "STUDENT")
    ) or 0

    total_faculty = db.scalar(
        select(func.count(User.user_id))
        .join(Role)
        .where(Role.role_name == "FACULTY")
    ) or 0

    total_admins = db.scalar(
        select(func.count(User.user_id))
        .join(Role)
        .where(Role.role_name == "ADMIN")
    ) or 0

    return {
        "total_users": total_users,

        "pending_users": pending_users,
        "active_users": active_users,
        "suspended_users": suspended_users,
        "inactive_users": inactive_users,

        "total_students": total_students,
        "total_faculty": total_faculty,
        "total_admins": total_admins,
    }


# ============================================================
# LIST USERS
# ============================================================

def list_users(
    db: Session,
    role_name: str | None = None,
    account_status: str | None = None,
):
    """
    Return users for the Admin Dashboard.

    Optional filters:

        role_name
        account_status
    """

    statement = (
        select(User)
        .options(
            joinedload(User.role)
        )
        .join(User.role)
    )

    # --------------------------------------------------------
    # ROLE FILTER
    # --------------------------------------------------------

    if role_name:

        normalized_role = role_name.strip().upper()

        allowed_roles = {
            "ADMIN",
            "FACULTY",
            "STUDENT",
        }

        if normalized_role not in allowed_roles:

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Invalid role filter. "
                    "Allowed values: ADMIN, FACULTY, STUDENT."
                ),
            )

        statement = statement.where(
            Role.role_name == normalized_role
        )

    # --------------------------------------------------------
    # STATUS FILTER
    # --------------------------------------------------------

    if account_status:

        normalized_status = (
            account_status.strip().upper()
        )

        allowed_statuses = {
            "PENDING",
            "ACTIVE",
            "SUSPENDED",
            "INACTIVE",
        }

        if normalized_status not in allowed_statuses:

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Invalid account status filter. "
                    "Allowed values: "
                    "PENDING, ACTIVE, SUSPENDED, INACTIVE."
                ),
            )

        statement = statement.where(
            User.account_status == normalized_status
        )

    statement = statement.order_by(
        User.created_at.desc()
    )

    users = db.scalars(
        statement
    ).unique().all()

    return [
        _user_to_list_item(user)
        for user in users
    ]


# ============================================================
# PENDING USERS
# ============================================================

def get_pending_users(
    db: Session,
):
    """
    Return all accounts waiting for activation.
    """

    return list_users(
        db=db,
        account_status="PENDING",
    )


# ============================================================
# GET USER DETAILS
# ============================================================

def get_user_details(
    db: Session,
    user_id: int,
):
    """
    Return complete details of one user.
    """

    user = db.scalar(
        select(User)
        .options(
            joinedload(User.role),
            joinedload(User.student_profile),
            joinedload(User.faculty_profile),
            joinedload(User.admin_profile),
        )
        .where(User.user_id == user_id)
    )

    if user is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )

    return _user_to_detail(user)


# ============================================================
# CHANGE ACCOUNT STATUS
# ============================================================

def change_account_status(
    db: Session,
    target_user_id: int,
    new_status: str,
    current_admin: User,
):
    """
    Change the account status of another user.

    The Admin cannot change their own account status.
    """

    normalized_status = new_status.strip().upper()

    allowed_statuses = {
        "PENDING",
        "ACTIVE",
        "SUSPENDED",
        "INACTIVE",
    }

    if normalized_status not in allowed_statuses:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid account status.",
        )

    # --------------------------------------------------------
    # PREVENT SELF STATUS CHANGE
    # --------------------------------------------------------

    if target_user_id == current_admin.user_id:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "An administrator cannot change "
                "their own account status."
            ),
        )

    # --------------------------------------------------------
    # FIND TARGET USER
    # --------------------------------------------------------

    user = db.scalar(
        select(User)
        .options(
            joinedload(User.role)
        )
        .where(User.user_id == target_user_id)
    )

    if user is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )

    previous_status = _normalize_status(
        user.account_status
    )

    # --------------------------------------------------------
    # NO-OP CHECK
    # --------------------------------------------------------

    if previous_status == normalized_status:

        role_name = ""

        if user.role is not None:
            role_name = str(user.role.role_name)

            if "." in role_name:
                role_name = role_name.split(".")[-1]

            role_name = role_name.upper()

        return {
            "user_id": user.user_id,
            "email": user.email,
            "full_name": user.full_name,
            "role_name": role_name,
            "previous_status": previous_status,
            "account_status": normalized_status,
            "message": (
                f"Account is already {normalized_status}."
            ),
        }

    # --------------------------------------------------------
    # UPDATE STATUS
    # --------------------------------------------------------

    user.account_status = normalized_status

    try:

        db.commit()

        db.refresh(user)

    except Exception as exc:

        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Unable to update account status.",
                "error": str(exc),
            },
        )

    # --------------------------------------------------------
    # ROLE
    # --------------------------------------------------------

    role_name = ""

    if user.role is not None:
        role_name = str(user.role.role_name)

        if "." in role_name:
            role_name = role_name.split(".")[-1]

        role_name = role_name.upper()

    # --------------------------------------------------------
    # SUCCESS MESSAGE
    # --------------------------------------------------------

    messages = {
        "ACTIVE": "Account activated successfully.",
        "SUSPENDED": "Account suspended successfully.",
        "INACTIVE": "Account deactivated successfully.",
        "PENDING": "Account moved back to pending status.",
    }

    return {
        "user_id": user.user_id,
        "email": user.email,
        "full_name": user.full_name,
        "role_name": role_name,
        "previous_status": previous_status,
        "account_status": normalized_status,
        "message": messages[normalized_status],
    }
# ============================================================
# ADMIN ATTENDANCE REPORT HELPERS
# ============================================================

def _attendance_percentage(
    present: int,
    total: int,
) -> float:
    if total <= 0:
        return 0.0

    return round(
        (present / total) * 100,
        2,
    )


def _normalize_report_status(
    value,
) -> str:
    if value is None:
        return "NOT_MARKED"

    normalized = str(value).upper()

    if "." in normalized:
        normalized = normalized.split(".")[-1]

    return normalized


def _build_admin_report_filters(
    semester_id: int | None,
    section_id: int | None,
    subject_id: int | None,
    faculty_id: int | None,
    date_from,
    date_to,
) -> tuple[str, dict]:
    conditions = [
        "ats.session_status <> 'CANCELLED'",
    ]

    params: dict = {}

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

    if faculty_id is not None:
        conditions.append(
            "ats.faculty_id = :faculty_id"
        )
        params["faculty_id"] = faculty_id

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
        "\n              AND ".join(
            conditions
        ),
        params,
    )


def _get_admin_report_rows(
    db: Session,
    semester_id: int | None = None,
    section_id: int | None = None,
    subject_id: int | None = None,
    faculty_id: int | None = None,
    date_from=None,
    date_to=None,
) -> list[dict]:
    where_sql, params = (
        _build_admin_report_filters(
            semester_id=semester_id,
            section_id=section_id,
            subject_id=subject_id,
            faculty_id=faculty_id,
            date_from=date_from,
            date_to=date_to,
        )
    )

    rows = db.execute(
        text(
            f"""
            SELECT
                ats.session_id,

                ats.faculty_id,
                fp.employee_id AS faculty_employee_id,
                fu.full_name AS faculty_name,
                fu.email AS faculty_email,
                fp.department AS faculty_department,
                fp.designation AS faculty_designation,

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
                su.full_name AS student_name,
                su.email AS student_email,

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

            INNER JOIN faculty_profiles fp
                ON fp.faculty_id = ats.faculty_id

            INNER JOIN users fu
                ON fu.user_id = fp.user_id

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

            INNER JOIN users su
                ON su.user_id = sp.user_id

            LEFT JOIN attendance_records ar
                ON ar.session_id = ats.session_id
               AND ar.student_id = sp.student_id

            WHERE {where_sql}

            ORDER BY
                ats.started_at DESC,
                ats.session_id DESC,
                sp.roll_number,
                su.full_name
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

        attendance_status = (
            _normalize_report_status(
                row["attendance_status"]
            )
        )

        session_status = (
            _normalize_report_status(
                row["session_status"]
            )
        )

        result.append(
            {
                "session_id":
                    int(row["session_id"]),

                "faculty_id":
                    int(row["faculty_id"]),

                "faculty_employee_id":
                    row["faculty_employee_id"],

                "faculty_name":
                    row["faculty_name"],

                "faculty_email":
                    row["faculty_email"],

                "faculty_department":
                    row["faculty_department"],

                "faculty_designation":
                    row["faculty_designation"],

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


def _admin_report_summary(
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

    faculty_ids = {
        row["faculty_id"]
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
        "total_sessions": len(session_ids),
        "total_students": len(student_ids),
        "total_faculty": len(faculty_ids),
        "attendance_opportunities":
            total_opportunities,
        "attendance_records":
            attendance_records,
        "present": present,
        "pending": pending,
        "rejected": rejected,
        "not_marked": not_marked,
        "attendance_percentage":
            _attendance_percentage(
                present=present,
                total=total_opportunities,
            ),
    }


def _group_admin_report_rows(
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
                    "session_ids": set(),
                    "student_ids": set(),
                    "attendance_records": 0,
                    "present": 0,
                    "pending": 0,
                    "rejected": 0,
                    "not_marked": 0,
                }
            )

            groups[key] = group

        group["session_ids"].add(
            row["session_id"]
        )

        group["student_ids"].add(
            row["student_id"]
        )

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

    result: list[dict] = []

    for group in groups.values():
        total = (
            group["present"]
            + group["pending"]
            + group["rejected"]
            + group["not_marked"]
        )

        # Count unique sessions and unique students for this
        # exact report group. Keep this explicit because these values
        # are displayed directly in the Admin grouped-report tables.
        session_ids = group.pop("session_ids")
        student_ids = group.pop("student_ids")

        group["session_count"] = len(
            {
                session_id
                for session_id in session_ids
                if session_id is not None
            }
        )

        group["student_count"] = len(
            {
                student_id
                for student_id in student_ids
                if student_id is not None
            }
        )

        group["attendance_opportunities"] = (
            total
        )

        group["attendance_percentage"] = (
            _attendance_percentage(
                present=group["present"],
                total=total,
            )
        )

        result.append(group)

    return result


def _admin_faculty_wise_report(
    rows: list[dict],
) -> list[dict]:
    result = _group_admin_report_rows(
        rows=rows,
        key_fields=(
            "faculty_id",
            "faculty_employee_id",
            "faculty_name",
            "faculty_department",
            "faculty_designation",
        ),
    )

    result.sort(
        key=lambda item: (
            str(item["faculty_name"] or ""),
            str(
                item["faculty_employee_id"]
                or ""
            ),
        )
    )

    return result


def _admin_subject_wise_report(
    rows: list[dict],
) -> list[dict]:
    result = _group_admin_report_rows(
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


def _admin_section_wise_report(
    rows: list[dict],
) -> list[dict]:
    result = _group_admin_report_rows(
        rows=rows,
        key_fields=(
            "semester_id",
            "section_id",
            "section_name",
        ),
    )

    result.sort(
        key=lambda item: (
            int(item["semester_id"] or 0),
            str(item["section_name"] or ""),
        )
    )

    return result


def _admin_day_wise_report(
    rows: list[dict],
) -> list[dict]:
    result = _group_admin_report_rows(
        rows=rows,
        key_fields=(
            "date",
        ),
    )

    result.sort(
        key=lambda item: (
            item["date"] or ""
        ),
        reverse=True,
    )

    return result


def _admin_session_wise_report(
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

                "faculty_id":
                    row["faculty_id"],

                "faculty_employee_id":
                    row["faculty_employee_id"],

                "faculty_name":
                    row["faculty_name"],

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
# BUILD COMPLETE ADMIN ATTENDANCE REPORT
# ============================================================

def get_admin_attendance_report(
    db: Session,
    semester_id: int | None = None,
    section_id: int | None = None,
    subject_id: int | None = None,
    faculty_id: int | None = None,
    date_from=None,
    date_to=None,
) -> dict:
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

    rows = _get_admin_report_rows(
        db=db,
        semester_id=semester_id,
        section_id=section_id,
        subject_id=subject_id,
        faculty_id=faculty_id,
        date_from=date_from,
        date_to=date_to,
    )

    return {
        "filters": {
            "semester_id": semester_id,
            "section_id": section_id,
            "subject_id": subject_id,
            "faculty_id": faculty_id,
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
            _admin_report_summary(
                rows
            ),

        "faculty_wise":
            _admin_faculty_wise_report(
                rows
            ),

        "subject_wise":
            _admin_subject_wise_report(
                rows
            ),

        "section_wise":
            _admin_section_wise_report(
                rows
            ),

        "day_wise":
            _admin_day_wise_report(
                rows
            ),

        "session_wise":
            _admin_session_wise_report(
                rows
            ),

        "records":
            rows,
    }