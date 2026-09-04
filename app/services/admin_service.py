"""
Admin Dashboard Service
=======================

Contains all business logic used by the Admin Dashboard.

The service is intentionally separate from the API router so that
the same functionality can later be reused by other interfaces.
"""

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.user import User
from app.models.role import Role
from app.models.admin_profile import AdminProfile
from app.services.auth_service import hash_password


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

    # Faculty public registrations must be approved through the
    # dedicated Faculty-registration workflow so that requested
    # Semester + Section + Subject combinations are verified and
    # activated atomically with the account.
    target_role_name = ""

    if user.role is not None:
        target_role_name = str(user.role.role_name)

        if "." in target_role_name:
            target_role_name = target_role_name.split(".")[-1]

        target_role_name = target_role_name.upper()

    if (
        normalized_status == "ACTIVE"
        and previous_status == "PENDING"
        and target_role_name == "FACULTY"
    ):
        pending_faculty_request = db.execute(
            text(
                """
                SELECT far.request_id
                FROM faculty_assignment_requests far
                INNER JOIN faculty_profiles fp
                    ON fp.faculty_id = far.faculty_id
                WHERE fp.user_id = :user_id
                  AND far.request_status = 'PENDING'
                LIMIT 1
                """
            ),
            {"user_id": target_user_id},
        ).scalar()

        if pending_faculty_request is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Pending Faculty registrations must be approved "
                    "through the Faculty registration review endpoint so "
                    "their requested academic assignments are verified."
                ),
            )

    if (
        normalized_status == "ACTIVE"
        and previous_status == "PENDING"
        and target_role_name == "STUDENT"
    ):
        pending_student_request = db.execute(
            text(
                """
                SELECT ssrr.request_id
                FROM student_section_registration_requests ssrr
                INNER JOIN student_profiles sp
                    ON sp.student_id = ssrr.student_id
                WHERE sp.user_id = :user_id
                  AND ssrr.request_status = 'PENDING'
                LIMIT 1
                """
            ),
            {"user_id": target_user_id},
        ).scalar()

        if pending_student_request is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Pending Student registrations must be approved "
                    "through the Student registration review endpoint so "
                    "the requested Section is verified and assigned."
                ),
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
# ACADEMIC PROGRAM / COURSE-BRANCH MANAGEMENT
# ============================================================

def _program_row_to_dict(row, message: str | None = None) -> dict:
    result = {
        "program_id": int(row["program_id"]),
        "program_code": row["program_code"],
        "program_name": row["program_name"],
        "description": row["description"],
        "is_active": bool(row["is_active"]),
    }
    if message is not None:
        result["message"] = message
    return result


def _get_program_row(db: Session, program_id: int):
    row = db.execute(
        text(
            """
            SELECT program_id, program_code, program_name, description, is_active
            FROM degree_programs
            WHERE program_id = :program_id
            LIMIT 1
            """
        ),
        {"program_id": program_id},
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Program not found.")
    return row


def list_programs(db: Session, active_only: bool = False) -> list[dict]:
    where_sql = " WHERE is_active = 1" if active_only else ""
    rows = db.execute(
        text(
            """
            SELECT program_id, program_code, program_name, description, is_active
            FROM degree_programs
            """ + where_sql + " ORDER BY program_name, program_id"
        )
    ).mappings().all()
    return [_program_row_to_dict(row) for row in rows]


def create_program(
    db: Session,
    program_code: str,
    program_name: str,
    description: str | None = None,
) -> dict:
    code = program_code.strip().upper()
    name = " ".join(program_name.strip().split())
    desc = description.strip() if description and description.strip() else None

    duplicate = db.execute(
        text(
            """
            SELECT program_id
            FROM degree_programs
            WHERE UPPER(program_code) = :code
               OR UPPER(program_name) = UPPER(:name)
            LIMIT 1
            """
        ),
        {"code": code, "name": name},
    ).scalar()
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="A program with this code or name already exists.")

    try:
        result = db.execute(
            text(
                """
                INSERT INTO degree_programs (
                    program_name, program_code, description, is_active
                ) VALUES (
                    :name, :code, :description, 1
                )
                """
            ),
            {"name": name, "code": code, "description": desc},
        )
        program_id = int(result.lastrowid)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Program could not be created because the code or name already exists.") from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unable to create program: {exc}") from exc

    return _program_row_to_dict(
        _get_program_row(db, program_id),
        message="Program added successfully.",
    )


def set_program_active_status(db: Session, program_id: int, is_active: bool) -> dict:
    current = _get_program_row(db, program_id)
    desired = bool(is_active)

    if bool(current["is_active"]) == desired:
        return _program_row_to_dict(
            current,
            message="Program is already active." if desired else "Program is already inactive.",
        )

    if not desired:
        active_branch = db.execute(
            text("SELECT branch_id FROM branches WHERE program_id = :program_id AND is_active = 1 LIMIT 1"),
            {"program_id": program_id},
        ).scalar()
        active_subject = db.execute(
            text("SELECT subject_id FROM subjects WHERE program_id = :program_id AND is_active = 1 LIMIT 1"),
            {"program_id": program_id},
        ).scalar()
        if active_branch is not None or active_subject is not None:
            raise HTTPException(
                status_code=409,
                detail="Deactivate this program's active courses/branches and subjects first.",
            )

    db.execute(
        text("UPDATE degree_programs SET is_active = :active WHERE program_id = :program_id"),
        {"active": 1 if desired else 0, "program_id": program_id},
    )
    db.commit()
    return _program_row_to_dict(
        _get_program_row(db, program_id),
        message="Program activated successfully." if desired else "Program deactivated successfully.",
    )


def delete_program(db: Session, program_id: int) -> dict:
    current = _get_program_row(db, program_id)
    branch_count = int(db.execute(text("SELECT COUNT(*) FROM branches WHERE program_id = :program_id"), {"program_id": program_id}).scalar() or 0)
    subject_count = int(db.execute(text("SELECT COUNT(*) FROM subjects WHERE program_id = :program_id"), {"program_id": program_id}).scalar() or 0)
    if branch_count or subject_count:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Program cannot be permanently deleted because it is linked to "
                f"{branch_count} course/branch record(s) and {subject_count} subject record(s). "
                "Deactivate it instead."
            ),
        )
    try:
        db.execute(text("DELETE FROM degree_programs WHERE program_id = :program_id"), {"program_id": program_id})
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Program is referenced by existing academic records. Deactivate it instead.") from exc
    result = _program_row_to_dict(current)
    result["message"] = "Program deleted permanently."
    return result


def _branch_row_to_dict(row, message: str | None = None) -> dict:
    result = {
        "branch_id": int(row["branch_id"]),
        "program_id": int(row["program_id"]),
        "program_code": row["program_code"],
        "program_name": row["program_name"],
        "branch_code": row["branch_code"],
        "branch_name": row["branch_name"],
        "is_active": bool(row["is_active"]),
    }
    if message is not None:
        result["message"] = message
    return result


def _get_branch_row(db: Session, branch_id: int):
    row = db.execute(
        text(
            """
            SELECT b.branch_id, b.program_id, b.branch_code, b.branch_name, b.is_active,
                   p.program_code, p.program_name
            FROM branches b
            INNER JOIN degree_programs p ON p.program_id = b.program_id
            WHERE b.branch_id = :branch_id
            LIMIT 1
            """
        ),
        {"branch_id": branch_id},
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Course/branch not found.")
    return row


def list_branches(
    db: Session,
    program_id: int | None = None,
    active_only: bool = False,
) -> list[dict]:
    conditions = []
    params = {}
    if program_id is not None:
        conditions.append("b.program_id = :program_id")
        params["program_id"] = program_id
    if active_only:
        conditions.append("b.is_active = 1")
    where_sql = " WHERE " + " AND ".join(conditions) if conditions else ""
    rows = db.execute(
        text(
            """
            SELECT b.branch_id, b.program_id, b.branch_code, b.branch_name, b.is_active,
                   p.program_code, p.program_name
            FROM branches b
            INNER JOIN degree_programs p ON p.program_id = b.program_id
            """ + where_sql + " ORDER BY p.program_name, b.branch_name, b.branch_id"
        ),
        params,
    ).mappings().all()
    return [_branch_row_to_dict(row) for row in rows]


def create_branch(
    db: Session,
    program_id: int,
    branch_code: str,
    branch_name: str,
) -> dict:
    program = _get_program_row(db, program_id)
    if not bool(program["is_active"]):
        raise HTTPException(status_code=409, detail="Selected program is inactive.")

    code = branch_code.strip().upper()
    name = " ".join(branch_name.strip().split())
    duplicate = db.execute(
        text(
            """
            SELECT branch_id
            FROM branches
            WHERE program_id = :program_id
              AND (UPPER(branch_code) = :code OR UPPER(branch_name) = UPPER(:name))
            LIMIT 1
            """
        ),
        {"program_id": program_id, "code": code, "name": name},
    ).scalar()
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="This program already has a course/branch with the same code or name.")

    try:
        result = db.execute(
            text(
                """
                INSERT INTO branches (program_id, branch_name, branch_code, is_active)
                VALUES (:program_id, :name, :code, 1)
                """
            ),
            {"program_id": program_id, "name": name, "code": code},
        )
        branch_id = int(result.lastrowid)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Course/branch could not be created because a duplicate value already exists.") from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unable to create course/branch: {exc}") from exc

    return _branch_row_to_dict(
        _get_branch_row(db, branch_id),
        message="Course/branch added successfully.",
    )


def set_branch_active_status(db: Session, branch_id: int, is_active: bool) -> dict:
    current = _get_branch_row(db, branch_id)
    desired = bool(is_active)
    if bool(current["is_active"]) == desired:
        return _branch_row_to_dict(
            current,
            message="Course/branch is already active." if desired else "Course/branch is already inactive.",
        )

    if desired:
        program = _get_program_row(db, int(current["program_id"]))
        if not bool(program["is_active"]):
            raise HTTPException(status_code=409, detail="Activate the parent program first.")
    else:
        active_subject = db.execute(
            text("SELECT subject_id FROM subjects WHERE branch_id = :branch_id AND is_active = 1 LIMIT 1"),
            {"branch_id": branch_id},
        ).scalar()
        if active_subject is not None:
            raise HTTPException(status_code=409, detail="Deactivate this course/branch's active subjects first.")

    db.execute(
        text("UPDATE branches SET is_active = :active WHERE branch_id = :branch_id"),
        {"active": 1 if desired else 0, "branch_id": branch_id},
    )
    db.commit()
    return _branch_row_to_dict(
        _get_branch_row(db, branch_id),
        message="Course/branch activated successfully." if desired else "Course/branch deactivated successfully.",
    )


def _column_exists(db: Session, table_name: str, column_name: str) -> bool:
    value = db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :table_name
              AND COLUMN_NAME = :column_name
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    ).scalar()
    return bool(value)


def _reference_count(db: Session, table_name: str, column_name: str, value: int) -> int:
    if not _column_exists(db, table_name, column_name):
        return 0
    # table/column names below are internal constants, not user input.
    return int(db.execute(text(f"SELECT COUNT(*) FROM {table_name} WHERE {column_name} = :value"), {"value": value}).scalar() or 0)


def delete_branch(db: Session, branch_id: int) -> dict:
    current = _get_branch_row(db, branch_id)
    dependencies = {
        "subjects": _reference_count(db, "subjects", "branch_id", branch_id),
        "students": _reference_count(db, "student_profiles", "branch_id", branch_id),
        "faculty": _reference_count(db, "faculty_profiles", "branch_id", branch_id),
        "sections": _reference_count(db, "sections", "branch_id", branch_id),
    }
    total = sum(dependencies.values())
    if total:
        details = ", ".join(f"{count} {name}" for name, count in dependencies.items() if count)
        raise HTTPException(
            status_code=409,
            detail=f"Course/branch cannot be permanently deleted because it is referenced by {details}. Deactivate it instead.",
        )
    try:
        db.execute(text("DELETE FROM branches WHERE branch_id = :branch_id"), {"branch_id": branch_id})
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Course/branch is referenced by existing academic records. Deactivate it instead.") from exc
    result = _branch_row_to_dict(current)
    result["message"] = "Course/branch deleted permanently."
    return result


# ============================================================
# ACADEMIC SUBJECT MANAGEMENT
# ============================================================

def get_subject_management_options(db: Session) -> dict:
    """Return active Program -> Branch and Semester choices for Admin."""

    programs = db.execute(
        text(
            """
            SELECT
                program_id,
                program_code,
                program_name
            FROM degree_programs
            WHERE is_active = 1
            ORDER BY program_name, program_id
            """
        )
    ).mappings().all()

    branches = db.execute(
        text(
            """
            SELECT
                branch_id,
                program_id,
                branch_code,
                branch_name
            FROM branches
            WHERE is_active = 1
            ORDER BY program_id, branch_name, branch_id
            """
        )
    ).mappings().all()

    semesters = db.execute(
        text(
            """
            SELECT
                semester_id,
                semester_number,
                semester_name
            FROM semesters
            ORDER BY semester_number, semester_id
            """
        )
    ).mappings().all()

    return {
        "programs": [dict(row) for row in programs],
        "branches": [dict(row) for row in branches],
        "semesters": [dict(row) for row in semesters],
    }


def _subject_select_sql() -> str:
    return """
        SELECT
            s.subject_id,
            s.subject_code,
            s.subject_name,
            s.credits,
            s.semester_id,
            s.branch_id,
            s.is_active,

            sem.semester_number,
            sem.semester_name,

            b.branch_code,
            b.branch_name,
            s.program_id,

            p.program_code,
            p.program_name

        FROM subjects s
        INNER JOIN semesters sem
            ON sem.semester_id = s.semester_id
        INNER JOIN branches b
            ON b.branch_id = s.branch_id
        INNER JOIN degree_programs p
            ON p.program_id = s.program_id
    """


def _subject_row_to_dict(row, message: str | None = None) -> dict:
    result = {
        "subject_id": int(row["subject_id"]),
        "program_id": int(row["program_id"]),
        "program_code": row["program_code"],
        "program_name": row["program_name"],
        "branch_id": int(row["branch_id"]),
        "branch_code": row["branch_code"],
        "branch_name": row["branch_name"],
        "semester_id": int(row["semester_id"]),
        "semester_number": row["semester_number"],
        "semester_name": row["semester_name"],
        "subject_code": row["subject_code"],
        "subject_name": row["subject_name"],
        "credits": (
            float(row["credits"])
            if row["credits"] is not None
            else None
        ),
        "is_active": bool(row["is_active"]),
    }

    if message is not None:
        result["message"] = message

    return result


def _get_subject_row(
    db: Session,
    subject_id: int,
):
    row = db.execute(
        text(
            _subject_select_sql()
            + " WHERE s.subject_id = :subject_id LIMIT 1"
        ),
        {"subject_id": subject_id},
    ).mappings().first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found.",
        )

    return row


def list_subjects(
    db: Session,
    program_id: int | None = None,
    branch_id: int | None = None,
    semester_id: int | None = None,
    active_only: bool = False,
) -> list[dict]:
    conditions: list[str] = []
    params: dict = {}

    if program_id is not None:
        conditions.append("s.program_id = :program_id")
        params["program_id"] = program_id

    if branch_id is not None:
        conditions.append("s.branch_id = :branch_id")
        params["branch_id"] = branch_id

    if semester_id is not None:
        conditions.append("s.semester_id = :semester_id")
        params["semester_id"] = semester_id

    if active_only:
        conditions.append("s.is_active = 1")

    where_sql = ""
    if conditions:
        where_sql = " WHERE " + " AND ".join(conditions)

    rows = db.execute(
        text(
            _subject_select_sql()
            + where_sql
            + """
              ORDER BY
                p.program_name,
                b.branch_name,
                sem.semester_number,
                s.subject_code,
                s.subject_name
            """
        ),
        params,
    ).mappings().all()

    return [_subject_row_to_dict(row) for row in rows]


def create_subject(
    db: Session,
    program_id: int,
    branch_id: int,
    semester_id: int,
    subject_code: str,
    subject_name: str,
    credits: float | None = None,
) -> dict:
    """Create one active subject in Program -> Branch -> Semester."""

    academic_scope = db.execute(
        text(
            """
            SELECT
                b.branch_id,
                b.branch_code,
                b.branch_name,
                b.program_id,
                b.is_active AS branch_is_active,
                p.program_code,
                p.program_name,
                p.is_active AS program_is_active
            FROM branches b
            INNER JOIN degree_programs p
                ON p.program_id = b.program_id
            WHERE b.branch_id = :branch_id
            LIMIT 1
            """
        ),
        {"branch_id": branch_id},
    ).mappings().first()

    if academic_scope is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Selected branch/department does not exist.",
        )

    if int(academic_scope["program_id"]) != program_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected branch does not belong to the selected program.",
        )

    if not bool(academic_scope["program_is_active"]):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Selected program is inactive.",
        )

    if not bool(academic_scope["branch_is_active"]):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Selected branch/department is inactive.",
        )

    semester = db.execute(
        text(
            """
            SELECT
                semester_id,
                semester_number,
                semester_name
            FROM semesters
            WHERE semester_id = :semester_id
            LIMIT 1
            """
        ),
        {"semester_id": semester_id},
    ).mappings().first()

    if semester is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Selected semester does not exist.",
        )

    normalized_code = subject_code.strip().upper()
    normalized_name = " ".join(subject_name.strip().split())

    if not normalized_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subject code is required.",
        )

    if not normalized_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subject name is required.",
        )

    duplicate = db.execute(
        text(
            """
            SELECT subject_id
            FROM subjects
            WHERE UPPER(subject_code) = :subject_code
            LIMIT 1
            """
        ),
        {"subject_code": normalized_code},
    ).scalar()

    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A subject with this subject code already exists.",
        )

    try:
        result = db.execute(
            text(
                """
                INSERT INTO subjects (
                    program_id,
                    branch_id,
                    semester_id,
                    subject_code,
                    subject_name,
                    credits,
                    is_active
                )
                VALUES (
                    :program_id,
                    :branch_id,
                    :semester_id,
                    :subject_code,
                    :subject_name,
                    :credits,
                    1
                )
                """
            ),
            {
                "program_id": program_id,
                "branch_id": branch_id,
                "semester_id": semester_id,
                "subject_code": normalized_code,
                "subject_name": normalized_name,
                "credits": credits,
            },
        )

        subject_id = int(result.lastrowid)
        db.commit()

    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Subject could not be created because a unique academic value already exists.",
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to create subject: {exc}",
        ) from exc

    row = _get_subject_row(
        db=db,
        subject_id=subject_id,
    )

    return _subject_row_to_dict(
        row,
        message="Subject added successfully.",
    )


def set_subject_active_status(
    db: Session,
    subject_id: int,
    is_active: bool,
) -> dict:
    """
    Activate or deactivate one subject without removing academic history.

    Deactivation is blocked while an ACTIVE attendance session is using
    the subject. Historical sessions and assignments remain intact.
    """

    current = _get_subject_row(
        db=db,
        subject_id=subject_id,
    )

    desired = bool(is_active)

    if bool(current["is_active"]) == desired:
        return _subject_row_to_dict(
            current,
            message=(
                "Subject is already active."
                if desired
                else "Subject is already inactive."
            ),
        )

    if not desired:
        active_session = db.execute(
            text(
                """
                SELECT session_id
                FROM attendance_sessions
                WHERE subject_id = :subject_id
                  AND session_status = 'ACTIVE'
                LIMIT 1
                """
            ),
            {"subject_id": subject_id},
        ).scalar()

        if active_session is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This subject is currently being used by an ACTIVE "
                    "attendance session. Complete or cancel that session "
                    "before deactivating the subject."
                ),
            )

    try:
        db.execute(
            text(
                """
                UPDATE subjects
                SET is_active = :is_active
                WHERE subject_id = :subject_id
                """
            ),
            {
                "subject_id": subject_id,
                "is_active": 1 if desired else 0,
            },
        )
        db.commit()

    except Exception:
        db.rollback()
        raise

    updated = _get_subject_row(
        db=db,
        subject_id=subject_id,
    )

    return _subject_row_to_dict(
        updated,
        message=(
            "Subject activated successfully."
            if desired
            else "Subject deactivated successfully."
        ),
    )


def delete_subject(
    db: Session,
    subject_id: int,
) -> dict:
    """
    Permanently delete only a subject that has never been referenced.

    Any subject used by faculty assignments, faculty registration
    assignment requests, or attendance sessions is preserved so academic
    and attendance history remains valid. Such a subject should be
    deactivated instead.
    """

    current = _get_subject_row(
        db=db,
        subject_id=subject_id,
    )

    reference_checks = (
        (
            "faculty_subject_assignments",
            "assignment_id",
            "faculty assignment",
        ),
        (
            "faculty_assignment_requests",
            "request_id",
            "faculty registration/assignment request",
        ),
        (
            "attendance_sessions",
            "session_id",
            "attendance session/history",
        ),
    )

    for table_name, id_column, label in reference_checks:
        reference = db.execute(
            text(
                f"""
                SELECT {id_column}
                FROM {table_name}
                WHERE subject_id = :subject_id
                LIMIT 1
                """
            ),
            {"subject_id": subject_id},
        ).scalar()

        if reference is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"This subject is referenced by an existing {label} "
                    "and cannot be permanently deleted. "
                    "Deactivate the subject instead."
                ),
            )

    try:
        db.execute(
            text(
                """
                DELETE FROM subjects
                WHERE subject_id = :subject_id
                """
            ),
            {"subject_id": subject_id},
        )
        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This subject is referenced by existing system records "
                "and cannot be permanently deleted. "
                "Deactivate the subject instead."
            ),
        )
    except Exception:
        db.rollback()
        raise

    return _subject_row_to_dict(
        current,
        message="Subject deleted successfully.",
    )


# ============================================================
# FACULTY ASSIGNMENT MANAGEMENT
# ============================================================

def get_faculty_assignment_options(
    db: Session,
    semester_id: int | None = None,
) -> dict:
    """
    Return values used by the Admin Faculty Assignment form.

    Sections and subjects are optionally limited to one semester so
    the Flutter form can use dependent Semester -> Section/Subject
    dropdowns without hard-coded academic data.
    """

    faculty_rows = db.execute(
        text(
            """
            SELECT
                fp.faculty_id,
                fp.employee_id,
                fp.department,
                fp.designation,
                u.full_name,
                u.email,
                u.account_status
            FROM faculty_profiles fp
            INNER JOIN users u
                ON u.user_id = fp.user_id
            INNER JOIN roles r
                ON r.role_id = u.role_id
            WHERE r.role_name = 'FACULTY'
              AND u.account_status = 'ACTIVE'
            ORDER BY u.full_name, fp.employee_id
            """
        )
    ).mappings().all()

    semester_rows = db.execute(
        text(
            """
            SELECT
                semester_id,
                semester_number,
                semester_name
            FROM semesters
            ORDER BY semester_number, semester_id
            """
        )
    ).mappings().all()

    section_params: dict = {}
    section_where = "sec.is_active = 1"

    subject_params: dict = {}
    subject_where = "s.is_active = 1"

    if semester_id is not None:
        section_where += " AND sec.semester_id = :semester_id"
        subject_where += " AND s.semester_id = :semester_id"

        section_params["semester_id"] = semester_id
        subject_params["semester_id"] = semester_id

    section_rows = db.execute(
        text(
            f"""
            SELECT
                sec.section_id,
                sec.section_name,
                sec.semester_id
            FROM sections sec
            WHERE {section_where}
            ORDER BY sec.semester_id, sec.section_name
            """
        ),
        section_params,
    ).mappings().all()

    subject_rows = db.execute(
        text(
            f"""
            SELECT
                s.subject_id,
                s.subject_code,
                s.subject_name,
                s.credits,
                s.semester_id
            FROM subjects s
            WHERE {subject_where}
            ORDER BY s.semester_id, s.subject_code, s.subject_name
            """
        ),
        subject_params,
    ).mappings().all()

    return {
        "faculties": [
            {
                "faculty_id": int(row["faculty_id"]),
                "employee_id": row["employee_id"],
                "full_name": row["full_name"],
                "email": row["email"],
                "department": row["department"],
                "designation": row["designation"],
                "account_status": _normalize_status(
                    row["account_status"]
                ),
            }
            for row in faculty_rows
        ],
        "semesters": [
            {
                "semester_id": int(row["semester_id"]),
                "semester_number": row["semester_number"],
                "semester_name": row["semester_name"],
            }
            for row in semester_rows
        ],
        "sections": [
            {
                "section_id": int(row["section_id"]),
                "section_name": row["section_name"],
                "semester_id": int(row["semester_id"]),
            }
            for row in section_rows
        ],
        "subjects": [
            {
                "subject_id": int(row["subject_id"]),
                "subject_code": row["subject_code"],
                "subject_name": row["subject_name"],
                "credits": (
                    float(row["credits"])
                    if row["credits"] is not None
                    else None
                ),
                "semester_id": int(row["semester_id"]),
            }
            for row in subject_rows
        ],
    }


def _faculty_assignment_select_sql() -> str:
    return """
        SELECT
            fsa.assignment_id,

            fp.faculty_id,
            fp.employee_id,
            fu.full_name AS faculty_name,

            sem.semester_id,
            sem.semester_number,
            sem.semester_name,

            sec.section_id,
            sec.section_name,

            s.subject_id,
            s.subject_code,
            s.subject_name,

            fsa.is_active

        FROM faculty_subject_assignments fsa

        INNER JOIN faculty_profiles fp
            ON fp.faculty_id = fsa.faculty_id

        INNER JOIN users fu
            ON fu.user_id = fp.user_id

        INNER JOIN sections sec
            ON sec.section_id = fsa.section_id

        INNER JOIN semesters sem
            ON sem.semester_id = sec.semester_id

        INNER JOIN subjects s
            ON s.subject_id = fsa.subject_id
    """


def _faculty_assignment_row_to_dict(
    row,
    message: str | None = None,
) -> dict:
    result = {
        "assignment_id": int(row["assignment_id"]),

        "faculty_id": int(row["faculty_id"]),
        "faculty_name": row["faculty_name"],
        "employee_id": row["employee_id"],

        "semester_id": int(row["semester_id"]),
        "semester_number": row["semester_number"],
        "semester_name": row["semester_name"],

        "section_id": int(row["section_id"]),
        "section_name": row["section_name"],

        "subject_id": int(row["subject_id"]),
        "subject_code": row["subject_code"],
        "subject_name": row["subject_name"],

        "is_active": bool(row["is_active"]),
    }

    if message is not None:
        result["message"] = message

    return result


def list_faculty_assignments(
    db: Session,
    faculty_id: int | None = None,
    semester_id: int | None = None,
    active_only: bool = False,
) -> list[dict]:
    conditions: list[str] = []
    params: dict = {}

    if faculty_id is not None:
        conditions.append(
            "fsa.faculty_id = :faculty_id"
        )
        params["faculty_id"] = faculty_id

    if semester_id is not None:
        conditions.append(
            "sec.semester_id = :semester_id"
        )
        params["semester_id"] = semester_id

    if active_only:
        conditions.append(
            "fsa.is_active = 1"
        )

    where_sql = ""

    if conditions:
        where_sql = (
            " WHERE "
            + " AND ".join(conditions)
        )

    rows = db.execute(
        text(
            _faculty_assignment_select_sql()
            + where_sql
            + """
              ORDER BY
                fu.full_name,
                sem.semester_number,
                sec.section_name,
                s.subject_code,
                fsa.assignment_id
            """
        ),
        params,
    ).mappings().all()

    return [
        _faculty_assignment_row_to_dict(row)
        for row in rows
    ]


def create_faculty_assignment(
    db: Session,
    faculty_id: int,
    semester_id: int,
    section_id: int,
    subject_id: int,
) -> dict:
    """
    Assign one active Semester + Section + Subject combination
    to one active Faculty member.

    Semester is validated through both the section and subject.
    The existing faculty_subject_assignments table remains the
    source of truth, so no attendance-history table is changed.
    """

    faculty = db.execute(
        text(
            """
            SELECT
                fp.faculty_id,
                fp.employee_id,
                u.full_name,
                u.account_status,
                r.role_name
            FROM faculty_profiles fp
            INNER JOIN users u
                ON u.user_id = fp.user_id
            INNER JOIN roles r
                ON r.role_id = u.role_id
            WHERE fp.faculty_id = :faculty_id
            LIMIT 1
            """
        ),
        {
            "faculty_id": faculty_id,
        },
    ).mappings().first()

    if faculty is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Faculty profile not found.",
        )

    if str(faculty["role_name"]).upper() != "FACULTY":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected user is not a faculty member.",
        )

    if _normalize_status(
        faculty["account_status"]
    ) != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Faculty account must be ACTIVE before "
                "academic assignments can be created."
            ),
        )

    section = db.execute(
        text(
            """
            SELECT
                section_id,
                section_name,
                semester_id,
                academic_year_id,
                is_active
            FROM sections
            WHERE section_id = :section_id
            LIMIT 1
            """
        ),
        {
            "section_id": section_id,
        },
    ).mappings().first()

    if section is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Section not found.",
        )

    if not bool(section["is_active"]):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Selected section is inactive.",
        )

    if int(section["semester_id"]) != semester_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Selected section does not belong to "
                "the selected semester."
            ),
        )

    if section["academic_year_id"] is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Selected section does not have an academic year "
                "configured."
            ),
        )

    academic_year_id = int(
        section["academic_year_id"]
    )

    subject = db.execute(
        text(
            """
            SELECT
                subject_id,
                subject_code,
                subject_name,
                semester_id,
                is_active
            FROM subjects
            WHERE subject_id = :subject_id
            LIMIT 1
            """
        ),
        {
            "subject_id": subject_id,
        },
    ).mappings().first()

    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found.",
        )

    if not bool(subject["is_active"]):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Selected subject is inactive.",
        )

    if int(subject["semester_id"]) != semester_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Selected subject does not belong to "
                "the selected semester."
            ),
        )

    semester_exists = db.execute(
        text(
            """
            SELECT semester_id
            FROM semesters
            WHERE semester_id = :semester_id
            LIMIT 1
            """
        ),
        {
            "semester_id": semester_id,
        },
    ).scalar()

    if semester_exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Semester not found.",
        )

    existing = db.execute(
        text(
            """
            SELECT
                assignment_id,
                is_active
            FROM faculty_subject_assignments
            WHERE faculty_id = :faculty_id
              AND subject_id = :subject_id
              AND section_id = :section_id
              AND academic_year_id = :academic_year_id
            ORDER BY assignment_id DESC
            LIMIT 1
            """
        ),
        {
            "faculty_id": faculty_id,
            "subject_id": subject_id,
            "section_id": section_id,
            "academic_year_id": academic_year_id,
        },
    ).mappings().first()

    if (
        existing is not None
        and bool(existing["is_active"])
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This faculty already has the selected "
                "semester, section and subject assignment."
            ),
        )

    try:
        if existing is not None:
            assignment_id = int(
                existing["assignment_id"]
            )

            db.execute(
                text(
                    """
                    UPDATE faculty_subject_assignments
                    SET is_active = 1
                    WHERE assignment_id = :assignment_id
                    """
                ),
                {
                    "assignment_id": assignment_id,
                },
            )

            action_message = (
                "Faculty assignment reactivated successfully."
            )
        else:
            result = db.execute(
                text(
                    """
                    INSERT INTO faculty_subject_assignments (
                        faculty_id,
                        subject_id,
                        section_id,
                        academic_year_id,
                        is_active
                    )
                    VALUES (
                        :faculty_id,
                        :subject_id,
                        :section_id,
                        :academic_year_id,
                        1
                    )
                    """
                ),
                {
                    "faculty_id": faculty_id,
                    "subject_id": subject_id,
                    "section_id": section_id,
                    "academic_year_id": academic_year_id,
                },
            )

            assignment_id = int(
                result.lastrowid
            )

            action_message = (
                "Faculty assignment created successfully."
            )

        db.commit()

    except Exception:
        db.rollback()
        raise

    row = db.execute(
        text(
            _faculty_assignment_select_sql()
            + """
              WHERE fsa.assignment_id = :assignment_id
              LIMIT 1
            """
        ),
        {
            "assignment_id": assignment_id,
        },
    ).mappings().first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Faculty assignment was saved but "
                "could not be retrieved."
            ),
        )

    return _faculty_assignment_row_to_dict(
        row,
        message=action_message,
    )


def deactivate_faculty_assignment(
    db: Session,
    assignment_id: int,
) -> dict:
    row = db.execute(
        text(
            _faculty_assignment_select_sql()
            + """
              WHERE fsa.assignment_id = :assignment_id
              LIMIT 1
            """
        ),
        {
            "assignment_id": assignment_id,
        },
    ).mappings().first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Faculty assignment not found.",
        )

    if not bool(row["is_active"]):
        return _faculty_assignment_row_to_dict(
            row,
            message="Faculty assignment is already inactive.",
        )

    active_session = db.execute(
        text(
            """
            SELECT session_id
            FROM attendance_sessions
            WHERE faculty_id = :faculty_id
              AND subject_id = :subject_id
              AND section_id = :section_id
              AND session_status = 'ACTIVE'
            LIMIT 1
            """
        ),
        {
            "faculty_id": int(row["faculty_id"]),
            "subject_id": int(row["subject_id"]),
            "section_id": int(row["section_id"]),
        },
    ).scalar()

    if active_session is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This assignment has an ACTIVE attendance "
                "session. Complete or cancel that session "
                "before removing the assignment."
            ),
        )

    try:
        db.execute(
            text(
                """
                UPDATE faculty_subject_assignments
                SET is_active = 0
                WHERE assignment_id = :assignment_id
                """
            ),
            {
                "assignment_id": assignment_id,
            },
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    updated = db.execute(
        text(
            _faculty_assignment_select_sql()
            + """
              WHERE fsa.assignment_id = :assignment_id
              LIMIT 1
            """
        ),
        {
            "assignment_id": assignment_id,
        },
    ).mappings().first()

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Faculty assignment was updated but "
                "could not be retrieved."
            ),
        )

    return _faculty_assignment_row_to_dict(
        updated,
        message="Faculty assignment removed successfully.",
    )





# ============================================================
# CLASSROOM MANAGEMENT
# ============================================================

def _classroom_row_to_dict(
    row,
    message: str | None = None,
) -> dict:
    result = {
        "classroom_id": int(row["classroom_id"]),
        "building_name": row["building_name"],
        "room_number": row["room_number"],
        "latitude": float(row["latitude"]),
        "longitude": float(row["longitude"]),
        "geofence_radius_meters": float(
            row["geofence_radius_meters"]
        ),
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
    }

    if message is not None:
        result["message"] = message

    return result


def _get_classroom_row(
    db: Session,
    classroom_id: int,
):
    row = db.execute(
        text(
            """
            SELECT
                classroom_id,
                building_name,
                room_number,
                latitude,
                longitude,
                geofence_radius_meters,
                is_active,
                created_at
            FROM classrooms
            WHERE classroom_id = :classroom_id
            LIMIT 1
            """
        ),
        {"classroom_id": classroom_id},
    ).mappings().first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classroom not found.",
        )

    return row


def list_classrooms(
    db: Session,
    active_only: bool = False,
) -> list[dict]:
    where_sql = "WHERE is_active = 1" if active_only else ""

    rows = db.execute(
        text(
            f"""
            SELECT
                classroom_id,
                building_name,
                room_number,
                latitude,
                longitude,
                geofence_radius_meters,
                is_active,
                created_at
            FROM classrooms
            {where_sql}
            ORDER BY building_name, room_number, classroom_id
            """
        )
    ).mappings().all()

    return [
        _classroom_row_to_dict(row)
        for row in rows
    ]


def create_classroom(
    db: Session,
    data,
) -> dict:
    building_name = data.building_name.strip()
    room_number = data.room_number.strip()

    existing = db.execute(
        text(
            """
            SELECT classroom_id
            FROM classrooms
            WHERE building_name = :building_name
              AND room_number = :room_number
            LIMIT 1
            """
        ),
        {
            "building_name": building_name,
            "room_number": room_number,
        },
    ).scalar()

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A classroom with this building name and "
                "room number already exists."
            ),
        )

    try:
        result = db.execute(
            text(
                """
                INSERT INTO classrooms (
                    building_name,
                    room_number,
                    latitude,
                    longitude,
                    geofence_radius_meters,
                    is_active
                )
                VALUES (
                    :building_name,
                    :room_number,
                    :latitude,
                    :longitude,
                    :geofence_radius_meters,
                    :is_active
                )
                """
            ),
            {
                "building_name": building_name,
                "room_number": room_number,
                "latitude": data.latitude,
                "longitude": data.longitude,
                "geofence_radius_meters": data.geofence_radius_meters,
                "is_active": 1 if data.is_active else 0,
            },
        )

        classroom_id = int(result.lastrowid)
        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A classroom with this building name and "
                "room number already exists."
            ),
        )
    except Exception:
        db.rollback()
        raise

    row = _get_classroom_row(
        db=db,
        classroom_id=classroom_id,
    )

    return _classroom_row_to_dict(
        row,
        message="Classroom created successfully.",
    )


def update_classroom(
    db: Session,
    classroom_id: int,
    data,
) -> dict:
    current = _get_classroom_row(
        db=db,
        classroom_id=classroom_id,
    )

    values = data.model_dump(exclude_unset=True)

    if not values:
        return _classroom_row_to_dict(
            current,
            message="No classroom changes were provided.",
        )

    if "building_name" in values:
        values["building_name"] = values["building_name"].strip()

    if "room_number" in values:
        values["room_number"] = values["room_number"].strip()

    building_name = values.get(
        "building_name",
        current["building_name"],
    )
    room_number = values.get(
        "room_number",
        current["room_number"],
    )

    duplicate = db.execute(
        text(
            """
            SELECT classroom_id
            FROM classrooms
            WHERE building_name = :building_name
              AND room_number = :room_number
              AND classroom_id <> :classroom_id
            LIMIT 1
            """
        ),
        {
            "building_name": building_name,
            "room_number": room_number,
            "classroom_id": classroom_id,
        },
    ).scalar()

    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Another classroom already uses this building "
                "name and room number."
            ),
        )

    allowed_fields = {
        "building_name",
        "room_number",
        "latitude",
        "longitude",
        "geofence_radius_meters",
    }

    assignments = []
    params = {"classroom_id": classroom_id}

    for key, value in values.items():
        if key not in allowed_fields:
            continue
        assignments.append(f"{key} = :{key}")
        params[key] = value

    if not assignments:
        return _classroom_row_to_dict(
            current,
            message="No classroom changes were provided.",
        )

    try:
        db.execute(
            text(
                "UPDATE classrooms SET "
                + ", ".join(assignments)
                + " WHERE classroom_id = :classroom_id"
            ),
            params,
        )
        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Another classroom already uses this building "
                "name and room number."
            ),
        )
    except Exception:
        db.rollback()
        raise

    updated = _get_classroom_row(
        db=db,
        classroom_id=classroom_id,
    )

    return _classroom_row_to_dict(
        updated,
        message="Classroom updated successfully.",
    )


def set_classroom_active_status(
    db: Session,
    classroom_id: int,
    is_active: bool,
) -> dict:
    current = _get_classroom_row(
        db=db,
        classroom_id=classroom_id,
    )

    desired = bool(is_active)

    if bool(current["is_active"]) == desired:
        return _classroom_row_to_dict(
            current,
            message=(
                "Classroom is already active."
                if desired
                else "Classroom is already inactive."
            ),
        )

    if not desired:
        active_session = db.execute(
            text(
                """
                SELECT session_id
                FROM attendance_sessions
                WHERE classroom_id = :classroom_id
                  AND session_status = 'ACTIVE'
                LIMIT 1
                """
            ),
            {"classroom_id": classroom_id},
        ).scalar()

        if active_session is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This classroom has an ACTIVE attendance session. "
                    "Complete or cancel that session before "
                    "deactivating the classroom."
                ),
            )

    try:
        db.execute(
            text(
                """
                UPDATE classrooms
                SET is_active = :is_active
                WHERE classroom_id = :classroom_id
                """
            ),
            {
                "is_active": 1 if desired else 0,
                "classroom_id": classroom_id,
            },
        )
        db.commit()

    except Exception:
        db.rollback()
        raise

    updated = _get_classroom_row(
        db=db,
        classroom_id=classroom_id,
    )

    return _classroom_row_to_dict(
        updated,
        message=(
            "Classroom activated successfully."
            if desired
            else "Classroom deactivated successfully."
        ),
    )


def delete_classroom(
    db: Session,
    classroom_id: int,
) -> dict:
    """
    Permanently delete only a classroom that has never been used.

    Any classroom referenced by attendance_sessions is preserved so
    historical attendance and audit records remain intact. In that
    situation the Admin should deactivate the classroom instead.
    """
    current = _get_classroom_row(
        db=db,
        classroom_id=classroom_id,
    )

    attendance_reference = db.execute(
        text(
            """
            SELECT session_id
            FROM attendance_sessions
            WHERE classroom_id = :classroom_id
            LIMIT 1
            """
        ),
        {"classroom_id": classroom_id},
    ).scalar()

    if attendance_reference is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This classroom has attendance history or an attendance "
                "session and cannot be permanently deleted. "
                "Deactivate the classroom instead."
            ),
        )

    try:
        db.execute(
            text(
                """
                DELETE FROM classrooms
                WHERE classroom_id = :classroom_id
                """
            ),
            {"classroom_id": classroom_id},
        )
        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This classroom is referenced by existing system records "
                "and cannot be permanently deleted. "
                "Deactivate the classroom instead."
            ),
        )
    except Exception:
        db.rollback()
        raise

    return _classroom_row_to_dict(
        current,
        message="Classroom deleted successfully.",
    )


# ============================================================
# CREATE ANOTHER ADMIN ACCOUNT
# ============================================================

def create_admin_account(
    db: Session,
    data,
) -> dict:
    """Create an ACTIVE administrator account from an Admin-only API."""

    email = str(data.email).strip().lower()
    employee_id = data.employee_id.strip()

    existing_email = db.scalar(
        select(User).where(User.email == email)
    )

    if existing_email is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    existing_employee_id = db.execute(
        text(
            """
            SELECT admin_id
            FROM admin_profiles
            WHERE employee_id = :employee_id
            LIMIT 1
            """
        ),
        {"employee_id": employee_id},
    ).scalar()

    if existing_employee_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An Admin with this employee_id already exists.",
        )

    admin_role = db.scalar(
        select(Role).where(Role.role_name == "ADMIN")
    )

    if admin_role is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADMIN role is not configured.",
        )

    try:
        password_hash = hash_password(data.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    user = User(
        role_id=admin_role.role_id,
        email=email,
        password_hash=password_hash,
        full_name=data.full_name.strip(),
        phone=(data.phone.strip() if data.phone else None),
        account_status="ACTIVE",
    )

    try:
        db.add(user)
        db.flush()

        profile = AdminProfile(
            user_id=user.user_id,
            employee_id=employee_id,
            designation=(
                data.designation.strip()
                if data.designation
                else None
            ),
        )

        db.add(profile)
        db.commit()
        db.refresh(user)
        db.refresh(profile)

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to create Admin account: {exc}",
        )

    return {
        "user_id": int(user.user_id),
        "admin_id": int(profile.admin_id),
        "email": user.email,
        "full_name": user.full_name,
        "employee_id": profile.employee_id,
        "account_status": _normalize_status(user.account_status),
        "message": "Administrator account created successfully.",
    }


# ============================================================
# STUDENT REGISTRATION REVIEW
# ============================================================

def _validate_student_registration_section(
    db: Session,
    section_id: int,
) -> dict:
    section = db.execute(
        text(
            """
            SELECT
                sec.section_id,
                sec.section_name,
                sec.semester_id,
                sec.is_active,
                sem.semester_number,
                sem.semester_name
            FROM sections sec
            LEFT JOIN semesters sem
                ON sem.semester_id = sec.semester_id
            WHERE sec.section_id = :section_id
            LIMIT 1
            """
        ),
        {"section_id": section_id},
    ).mappings().first()

    if section is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Requested Student section no longer exists.",
        )

    if not bool(section["is_active"]):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Requested Student section is inactive.",
        )

    if section["semester_id"] is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Requested Student section has no semester configured.",
        )

    return dict(section)


def list_student_registration_requests(
    db: Session,
    request_status: str = "PENDING",
) -> list[dict]:
    normalized = request_status.strip().upper()

    if normalized not in {"PENDING", "APPROVED", "REJECTED", "ALL"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "request_status must be PENDING, APPROVED, REJECTED or ALL."
            ),
        )

    where_request = ""
    params: dict = {}

    if normalized != "ALL":
        where_request = " AND ssrr.request_status = :request_status"
        params["request_status"] = normalized

    rows = db.execute(
        text(
            f"""
            SELECT
                ssrr.request_id,
                u.user_id,
                sp.student_id,
                u.email,
                u.full_name,
                u.phone,
                sp.enrollment_number,
                sp.roll_number,
                sp.date_of_birth,
                u.account_status,
                u.created_at,

                ssrr.section_id,
                sec.section_name,
                sec.semester_id,
                sem.semester_number,
                sem.semester_name,

                ssrr.request_status,
                ssrr.requested_at,
                ssrr.reviewed_at,
                ssrr.reviewed_by_user_id,
                ssrr.review_note

            FROM student_section_registration_requests ssrr
            INNER JOIN student_profiles sp
                ON sp.student_id = ssrr.student_id
            INNER JOIN users u
                ON u.user_id = sp.user_id
            INNER JOIN roles r
                ON r.role_id = u.role_id
            INNER JOIN sections sec
                ON sec.section_id = ssrr.section_id
            LEFT JOIN semesters sem
                ON sem.semester_id = sec.semester_id

            WHERE r.role_name = 'STUDENT'
              {where_request}

            ORDER BY u.created_at DESC, ssrr.request_id DESC
            """
        ),
        params,
    ).mappings().all()

    return [
        {
            "request_id": int(row["request_id"]),
            "user_id": int(row["user_id"]),
            "student_id": int(row["student_id"]),
            "email": row["email"],
            "full_name": row["full_name"],
            "phone": row["phone"],
            "enrollment_number": row["enrollment_number"],
            "roll_number": row["roll_number"],
            "date_of_birth": row["date_of_birth"],
            "account_status": _normalize_status(row["account_status"]),
            "created_at": row["created_at"],
            "section_id": int(row["section_id"]),
            "section_name": row["section_name"],
            "semester_id": int(row["semester_id"]),
            "semester_number": row["semester_number"],
            "semester_name": row["semester_name"],
            "request_status": str(row["request_status"]).upper(),
            "requested_at": row["requested_at"],
            "reviewed_at": row["reviewed_at"],
            "reviewed_by_user_id": row["reviewed_by_user_id"],
            "review_note": row["review_note"],
        }
        for row in rows
    ]


def approve_student_registration(
    db: Session,
    user_id: int,
    current_admin: User,
    note: str | None = None,
) -> dict:
    student = db.execute(
        text(
            """
            SELECT
                u.user_id,
                u.email,
                u.full_name,
                u.account_status,
                r.role_name,
                sp.student_id,
                ssrr.request_id,
                ssrr.section_id,
                ssrr.request_status
            FROM users u
            INNER JOIN roles r
                ON r.role_id = u.role_id
            INNER JOIN student_profiles sp
                ON sp.user_id = u.user_id
            INNER JOIN student_section_registration_requests ssrr
                ON ssrr.student_id = sp.student_id
            WHERE u.user_id = :user_id
            LIMIT 1
            """
        ),
        {"user_id": user_id},
    ).mappings().first()

    if student is None or str(student["role_name"]).upper() != "STUDENT":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending Student registration not found.",
        )

    if _normalize_status(student["account_status"]) != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a PENDING Student registration can be approved.",
        )

    if str(student["request_status"]).upper() != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student Section request is not PENDING.",
        )

    student_id = int(student["student_id"])
    section_id = int(student["section_id"])
    section = _validate_student_registration_section(
        db=db,
        section_id=section_id,
    )

    try:
        # A student should have only one active current Section.
        db.execute(
            text(
                """
                UPDATE student_section_assignments
                SET is_active = 0
                WHERE student_id = :student_id
                  AND is_active = 1
                """
            ),
            {"student_id": student_id},
        )

        existing_assignment = db.execute(
            text(
                """
                SELECT assignment_id
                FROM student_section_assignments
                WHERE student_id = :student_id
                  AND section_id = :section_id
                LIMIT 1
                """
            ),
            {
                "student_id": student_id,
                "section_id": section_id,
            },
        ).scalar()

        if existing_assignment is None:
            db.execute(
                text(
                    """
                    INSERT INTO student_section_assignments (
                        student_id,
                        section_id,
                        is_active
                    )
                    VALUES (
                        :student_id,
                        :section_id,
                        1
                    )
                    """
                ),
                {
                    "student_id": student_id,
                    "section_id": section_id,
                },
            )
        else:
            db.execute(
                text(
                    """
                    UPDATE student_section_assignments
                    SET is_active = 1,
                        assigned_at = CURRENT_TIMESTAMP
                    WHERE assignment_id = :assignment_id
                    """
                ),
                {"assignment_id": int(existing_assignment)},
            )

        db.execute(
            text(
                """
                UPDATE student_section_registration_requests
                SET
                    request_status = 'APPROVED',
                    reviewed_at = CURRENT_TIMESTAMP,
                    reviewed_by_user_id = :reviewed_by_user_id,
                    review_note = :review_note
                WHERE request_id = :request_id
                  AND request_status = 'PENDING'
                """
            ),
            {
                "request_id": int(student["request_id"]),
                "reviewed_by_user_id": current_admin.user_id,
                "review_note": note.strip() if note else None,
            },
        )

        db.execute(
            text(
                """
                UPDATE users
                SET account_status = 'ACTIVE'
                WHERE user_id = :user_id
                """
            ),
            {"user_id": user_id},
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "user_id": int(student["user_id"]),
        "student_id": student_id,
        "email": student["email"],
        "full_name": student["full_name"],
        "account_status": "ACTIVE",
        "section_id": section_id,
        "section_name": section["section_name"],
        "message": (
            "Student registration approved and Section assigned successfully."
        ),
    }


def reject_student_registration(
    db: Session,
    user_id: int,
    current_admin: User,
    note: str | None = None,
) -> dict:
    student = db.execute(
        text(
            """
            SELECT
                u.user_id,
                u.email,
                u.full_name,
                u.account_status,
                r.role_name,
                sp.student_id,
                ssrr.request_id,
                ssrr.section_id,
                ssrr.request_status,
                sec.section_name
            FROM users u
            INNER JOIN roles r
                ON r.role_id = u.role_id
            INNER JOIN student_profiles sp
                ON sp.user_id = u.user_id
            INNER JOIN student_section_registration_requests ssrr
                ON ssrr.student_id = sp.student_id
            INNER JOIN sections sec
                ON sec.section_id = ssrr.section_id
            WHERE u.user_id = :user_id
            LIMIT 1
            """
        ),
        {"user_id": user_id},
    ).mappings().first()

    if student is None or str(student["role_name"]).upper() != "STUDENT":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending Student registration not found.",
        )

    if _normalize_status(student["account_status"]) != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a PENDING Student registration can be rejected.",
        )

    if str(student["request_status"]).upper() != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student Section request is not PENDING.",
        )

    try:
        db.execute(
            text(
                """
                UPDATE student_section_registration_requests
                SET
                    request_status = 'REJECTED',
                    reviewed_at = CURRENT_TIMESTAMP,
                    reviewed_by_user_id = :reviewed_by_user_id,
                    review_note = :review_note
                WHERE request_id = :request_id
                  AND request_status = 'PENDING'
                """
            ),
            {
                "request_id": int(student["request_id"]),
                "reviewed_by_user_id": current_admin.user_id,
                "review_note": note.strip() if note else None,
            },
        )

        db.execute(
            text(
                """
                UPDATE users
                SET account_status = 'INACTIVE'
                WHERE user_id = :user_id
                """
            ),
            {"user_id": user_id},
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "user_id": int(student["user_id"]),
        "student_id": int(student["student_id"]),
        "email": student["email"],
        "full_name": student["full_name"],
        "account_status": "INACTIVE",
        "section_id": int(student["section_id"]),
        "section_name": student["section_name"],
        "message": "Student registration rejected.",
    }


# ============================================================
# FACULTY REGISTRATION REVIEW HELPERS
# ============================================================

def _validate_faculty_registration_request_scope(
    db: Session,
    semester_id: int,
    section_id: int,
    subject_id: int,
) -> int:
    """Validate one requested scope and return its academic_year_id."""

    section = db.execute(
        text(
            """
            SELECT
                section_id,
                semester_id,
                academic_year_id,
                is_active
            FROM sections
            WHERE section_id = :section_id
            LIMIT 1
            """
        ),
        {"section_id": section_id},
    ).mappings().first()

    if section is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A requested section no longer exists.",
        )

    if not bool(section["is_active"]):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A requested section is inactive.",
        )

    if int(section["semester_id"]) != semester_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A requested section no longer belongs to the "
                "requested semester."
            ),
        )

    if section["academic_year_id"] is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A requested section has no academic year configured.",
        )

    subject = db.execute(
        text(
            """
            SELECT
                subject_id,
                semester_id,
                is_active
            FROM subjects
            WHERE subject_id = :subject_id
            LIMIT 1
            """
        ),
        {"subject_id": subject_id},
    ).mappings().first()

    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A requested subject no longer exists.",
        )

    if not bool(subject["is_active"]):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A requested subject is inactive.",
        )

    if int(subject["semester_id"]) != semester_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A requested subject no longer belongs to the "
                "requested semester."
            ),
        )

    return int(section["academic_year_id"])


def list_faculty_registration_requests(
    db: Session,
    request_status: str = "PENDING",
) -> list[dict]:
    """Return Faculty registrations and their requested assignments."""

    normalized = request_status.strip().upper()

    if normalized not in {"PENDING", "APPROVED", "REJECTED", "ALL"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "request_status must be PENDING, APPROVED, REJECTED or ALL."
            ),
        )

    where_request = ""
    params: dict = {}

    if normalized != "ALL":
        where_request = " AND far.request_status = :request_status"
        params["request_status"] = normalized

    rows = db.execute(
        text(
            f"""
            SELECT
                u.user_id,
                u.email,
                u.full_name,
                u.phone,
                u.account_status,
                u.created_at,

                fp.faculty_id,
                fp.employee_id,
                fp.department,
                fp.designation,

                far.request_id,
                far.semester_id,
                sem.semester_number,
                sem.semester_name,
                far.section_id,
                sec.section_name,
                far.subject_id,
                s.subject_code,
                s.subject_name,
                far.request_status,
                far.requested_at,
                far.reviewed_at,
                far.reviewed_by_user_id,
                far.review_note

            FROM users u
            INNER JOIN roles r
                ON r.role_id = u.role_id
            INNER JOIN faculty_profiles fp
                ON fp.user_id = u.user_id
            INNER JOIN faculty_assignment_requests far
                ON far.faculty_id = fp.faculty_id
            INNER JOIN semesters sem
                ON sem.semester_id = far.semester_id
            INNER JOIN sections sec
                ON sec.section_id = far.section_id
            INNER JOIN subjects s
                ON s.subject_id = far.subject_id

            WHERE r.role_name = 'FACULTY'
              {where_request}

            ORDER BY
                u.created_at DESC,
                u.user_id DESC,
                far.request_id ASC
            """
        ),
        params,
    ).mappings().all()

    grouped: dict[int, dict] = {}

    for row in rows:
        user_id = int(row["user_id"])

        item = grouped.get(user_id)
        if item is None:
            item = {
                "user_id": user_id,
                "faculty_id": int(row["faculty_id"]),
                "email": row["email"],
                "full_name": row["full_name"],
                "phone": row["phone"],
                "employee_id": row["employee_id"],
                "department": row["department"],
                "designation": row["designation"],
                "account_status": _normalize_status(row["account_status"]),
                "created_at": row["created_at"],
                "assignments": [],
            }
            grouped[user_id] = item

        item["assignments"].append(
            {
                "request_id": int(row["request_id"]),
                "semester_id": int(row["semester_id"]),
                "semester_number": row["semester_number"],
                "semester_name": row["semester_name"],
                "section_id": int(row["section_id"]),
                "section_name": row["section_name"],
                "subject_id": int(row["subject_id"]),
                "subject_code": row["subject_code"],
                "subject_name": row["subject_name"],
                "request_status": str(row["request_status"]),
                "requested_at": row["requested_at"],
                "reviewed_at": row["reviewed_at"],
                "reviewed_by_user_id": (
                    int(row["reviewed_by_user_id"])
                    if row["reviewed_by_user_id"] is not None
                    else None
                ),
                "review_note": row["review_note"],
            }
        )

    return list(grouped.values())


def approve_faculty_registration(
    db: Session,
    user_id: int,
    current_admin: User,
    note: str | None = None,
) -> dict:
    """
    Activate a pending Faculty account and atomically convert every
    PENDING registration assignment request into an active assignment.
    """

    faculty = db.execute(
        text(
            """
            SELECT
                u.user_id,
                u.email,
                u.full_name,
                u.account_status,
                r.role_name,
                fp.faculty_id
            FROM users u
            INNER JOIN roles r
                ON r.role_id = u.role_id
            INNER JOIN faculty_profiles fp
                ON fp.user_id = u.user_id
            WHERE u.user_id = :user_id
            LIMIT 1
            """
        ),
        {"user_id": user_id},
    ).mappings().first()

    if faculty is None or str(faculty["role_name"]).upper() != "FACULTY":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending Faculty registration not found.",
        )

    if _normalize_status(faculty["account_status"]) != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a PENDING Faculty registration can be approved.",
        )

    faculty_id = int(faculty["faculty_id"])

    requests = db.execute(
        text(
            """
            SELECT
                request_id,
                semester_id,
                section_id,
                subject_id
            FROM faculty_assignment_requests
            WHERE faculty_id = :faculty_id
              AND request_status = 'PENDING'
            ORDER BY request_id
            """
        ),
        {"faculty_id": faculty_id},
    ).mappings().all()

    if not requests:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This Faculty registration has no pending academic "
                "assignment requests to approve."
            ),
        )

    validated: list[tuple[dict, int]] = []

    # Validate every request before changing any database row.
    for request in requests:
        academic_year_id = _validate_faculty_registration_request_scope(
            db=db,
            semester_id=int(request["semester_id"]),
            section_id=int(request["section_id"]),
            subject_id=int(request["subject_id"]),
        )
        validated.append((request, academic_year_id))

    try:
        for request, academic_year_id in validated:
            existing = db.execute(
                text(
                    """
                    SELECT assignment_id
                    FROM faculty_subject_assignments
                    WHERE faculty_id = :faculty_id
                      AND subject_id = :subject_id
                      AND section_id = :section_id
                      AND academic_year_id = :academic_year_id
                    ORDER BY assignment_id DESC
                    LIMIT 1
                    """
                ),
                {
                    "faculty_id": faculty_id,
                    "subject_id": int(request["subject_id"]),
                    "section_id": int(request["section_id"]),
                    "academic_year_id": academic_year_id,
                },
            ).scalar()

            if existing is None:
                db.execute(
                    text(
                        """
                        INSERT INTO faculty_subject_assignments (
                            faculty_id,
                            subject_id,
                            section_id,
                            academic_year_id,
                            is_active
                        )
                        VALUES (
                            :faculty_id,
                            :subject_id,
                            :section_id,
                            :academic_year_id,
                            1
                        )
                        """
                    ),
                    {
                        "faculty_id": faculty_id,
                        "subject_id": int(request["subject_id"]),
                        "section_id": int(request["section_id"]),
                        "academic_year_id": academic_year_id,
                    },
                )
            else:
                db.execute(
                    text(
                        """
                        UPDATE faculty_subject_assignments
                        SET is_active = 1
                        WHERE assignment_id = :assignment_id
                        """
                    ),
                    {"assignment_id": int(existing)},
                )

        db.execute(
            text(
                """
                UPDATE faculty_assignment_requests
                SET
                    request_status = 'APPROVED',
                    reviewed_at = CURRENT_TIMESTAMP,
                    reviewed_by_user_id = :reviewed_by_user_id,
                    review_note = :review_note
                WHERE faculty_id = :faculty_id
                  AND request_status = 'PENDING'
                """
            ),
            {
                "faculty_id": faculty_id,
                "reviewed_by_user_id": current_admin.user_id,
                "review_note": note.strip() if note else None,
            },
        )

        db.execute(
            text(
                """
                UPDATE users
                SET account_status = 'ACTIVE'
                WHERE user_id = :user_id
                """
            ),
            {"user_id": user_id},
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "user_id": int(faculty["user_id"]),
        "faculty_id": faculty_id,
        "email": faculty["email"],
        "full_name": faculty["full_name"],
        "account_status": "ACTIVE",
        "processed_assignments": len(validated),
        "message": (
            "Faculty registration approved and academic assignments "
            "activated successfully."
        ),
    }


def reject_faculty_registration(
    db: Session,
    user_id: int,
    current_admin: User,
    note: str | None = None,
) -> dict:
    """Reject a pending Faculty registration without deleting history."""

    faculty = db.execute(
        text(
            """
            SELECT
                u.user_id,
                u.email,
                u.full_name,
                u.account_status,
                r.role_name,
                fp.faculty_id
            FROM users u
            INNER JOIN roles r
                ON r.role_id = u.role_id
            INNER JOIN faculty_profiles fp
                ON fp.user_id = u.user_id
            WHERE u.user_id = :user_id
            LIMIT 1
            """
        ),
        {"user_id": user_id},
    ).mappings().first()

    if faculty is None or str(faculty["role_name"]).upper() != "FACULTY":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending Faculty registration not found.",
        )

    if _normalize_status(faculty["account_status"]) != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a PENDING Faculty registration can be rejected.",
        )

    faculty_id = int(faculty["faculty_id"])

    try:
        result = db.execute(
            text(
                """
                UPDATE faculty_assignment_requests
                SET
                    request_status = 'REJECTED',
                    reviewed_at = CURRENT_TIMESTAMP,
                    reviewed_by_user_id = :reviewed_by_user_id,
                    review_note = :review_note
                WHERE faculty_id = :faculty_id
                  AND request_status = 'PENDING'
                """
            ),
            {
                "faculty_id": faculty_id,
                "reviewed_by_user_id": current_admin.user_id,
                "review_note": note.strip() if note else None,
            },
        )

        db.execute(
            text(
                """
                UPDATE users
                SET account_status = 'INACTIVE'
                WHERE user_id = :user_id
                """
            ),
            {"user_id": user_id},
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "user_id": int(faculty["user_id"]),
        "faculty_id": faculty_id,
        "email": faculty["email"],
        "full_name": faculty["full_name"],
        "account_status": "INACTIVE",
        "processed_assignments": int(result.rowcount or 0),
        "message": "Faculty registration rejected.",
    }


# ============================================================
# ADMIN STUDENT FACE MANAGEMENT
# ============================================================

def get_student_face_status_for_admin(
    db: Session,
    student_id: int,
) -> dict:
    """Return face metadata only. Never return the biometric embedding."""

    row = db.execute(
        text(
            """
            SELECT
                u.user_id,
                u.full_name,
                sp.student_id,
                sp.enrollment_number,

                sfp.face_profile_id,
                sfp.embedding_model,
                sfp.embedding_dimensions,
                sfp.is_verified,
                sfp.is_active,
                sfp.created_at AS face_created_at,
                sfp.updated_at AS face_updated_at

            FROM student_profiles sp
            INNER JOIN users u
                ON u.user_id = sp.user_id
            LEFT JOIN student_face_profiles sfp
                ON sfp.student_id = sp.student_id
            WHERE sp.student_id = :student_id
            LIMIT 1
            """
        ),
        {"student_id": student_id},
    ).mappings().first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found.",
        )

    registered = row["face_profile_id"] is not None

    return {
        "user_id": int(row["user_id"]),
        "student_id": int(row["student_id"]),
        "full_name": row["full_name"],
        "enrollment_number": row["enrollment_number"],
        "registered": registered,
        "face_profile_id": (
            int(row["face_profile_id"])
            if row["face_profile_id"] is not None
            else None
        ),
        "embedding_model": row["embedding_model"],
        "embedding_dimensions": (
            int(row["embedding_dimensions"])
            if row["embedding_dimensions"] is not None
            else None
        ),
        "is_verified": bool(row["is_verified"]) if registered else False,
        "is_active": bool(row["is_active"]) if registered else False,
        "created_at": row["face_created_at"],
        "updated_at": row["face_updated_at"],
    }


def delete_student_face_profile_for_admin(
    db: Session,
    student_id: int,
) -> dict:
    """
    Permanently remove only the student's biometric face profile.

    Student account, student profile and attendance history are untouched.
    """

    student_exists = db.execute(
        text(
            """
            SELECT student_id
            FROM student_profiles
            WHERE student_id = :student_id
            LIMIT 1
            """
        ),
        {"student_id": student_id},
    ).scalar()

    if student_exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found.",
        )

    face_profile_id = db.execute(
        text(
            """
            SELECT face_profile_id
            FROM student_face_profiles
            WHERE student_id = :student_id
            LIMIT 1
            """
        ),
        {"student_id": student_id},
    ).scalar()

    if face_profile_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student face profile is not registered.",
        )

    try:
        db.execute(
            text(
                """
                DELETE FROM student_face_profiles
                WHERE student_id = :student_id
                  AND face_profile_id = :face_profile_id
                """
            ),
            {
                "student_id": student_id,
                "face_profile_id": int(face_profile_id),
            },
        )
        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "student_id": student_id,
        "deleted_face_profile_id": int(face_profile_id),
        "registered": False,
        "message": (
            "Student face profile deleted successfully. "
            "The student may register a new face profile."
        ),
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