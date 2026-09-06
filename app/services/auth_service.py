"""
Authentication and Registration Service
========================================

Public registration supports STUDENT and FACULTY accounts.
Administrator accounts are created only by an authenticated Admin.

Student public registration stores the requested Section in
student_section_registration_requests. Faculty public registration
stores requested Semester + Section + Subject combinations in
faculty_assignment_requests. All requests remain PENDING until an
administrator approves them.
"""

import bcrypt

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    decode_password_reset_token,
    password_hash_fingerprint,
)

from app.models.branch import Branch  # noqa: F401 - registers branches table in ORM metadata
from app.models.role import Role
from app.models.user import User
from app.models.faculty_profile import FacultyProfile
from app.models.student_profile import StudentProfile


# ============================================================
# PASSWORD FUNCTIONS
# ============================================================

def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt."""

    password_bytes = password.encode("utf-8")

    if len(password_bytes) > 72:
        raise ValueError(
            "Password cannot be longer than 72 bytes."
        )

    hashed_password = bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt()
    )

    return hashed_password.decode("utf-8")


# ============================================================
# VERIFY PASSWORD
# ============================================================

def verify_password(
    password: str,
    password_hash: str
) -> bool:
    """Verify a plain-text password against a bcrypt hash."""

    try:
        password_bytes = password.encode("utf-8")
        hash_bytes = password_hash.encode("utf-8")

        if len(password_bytes) > 72:
            return False

        return bcrypt.checkpw(
            password_bytes,
            hash_bytes
        )

    except (ValueError, TypeError):
        return False


# ============================================================
# REGISTRATION OPTIONS
# ============================================================

def get_registration_options(
    db: Session,
    semester_id: int | None = None,
) -> dict:
    """
    Public academic options used by the Faculty registration form.

    No user or faculty information is exposed here.
    """

    programs = db.execute(
        text(
            """
            SELECT
                program_id,
                program_name,
                program_code,
                default_semesters
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
                branch_name,
                branch_code,
                total_semesters
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

    section_where = "sec.is_active = 1"
    subject_where = "s.is_active = 1"
    params: dict = {}

    if semester_id is not None:
        section_where += " AND sec.semester_id = :semester_id"
        subject_where += " AND s.semester_id = :semester_id"
        params["semester_id"] = semester_id

    sections = db.execute(
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
        params,
    ).mappings().all()

    subjects = db.execute(
        text(
            f"""
            SELECT
                s.subject_id,
                s.program_id,
                s.branch_id,
                s.subject_code,
                s.subject_name,
                s.semester_id
            FROM subjects s
            WHERE {subject_where}
            ORDER BY s.semester_id, s.subject_code, s.subject_name
            """
        ),
        params,
    ).mappings().all()

    return {
        "programs": [
            {
                "program_id": int(row["program_id"]),
                "program_name": row["program_name"],
                "program_code": row["program_code"],
                "default_semesters": int(row["default_semesters"]),
            }
            for row in programs
        ],
        "branches": [
            {
                "branch_id": int(row["branch_id"]),
                "program_id": int(row["program_id"]),
                "branch_name": row["branch_name"],
                "branch_code": row["branch_code"],
                "total_semesters": int(row["total_semesters"]),
            }
            for row in branches
        ],
        "semesters": [
            {
                "semester_id": int(row["semester_id"]),
                "semester_number": row["semester_number"],
                "semester_name": row["semester_name"],
            }
            for row in semesters
        ],
        "sections": [
            {
                "section_id": int(row["section_id"]),
                "section_name": row["section_name"],
                "semester_id": int(row["semester_id"]),
            }
            for row in sections
        ],
        "subjects": [
            {
                "subject_id": int(row["subject_id"]),
                "program_id": int(row["program_id"]),
                "branch_id": int(row["branch_id"]),
                "subject_code": row["subject_code"],
                "subject_name": row["subject_name"],
                "semester_id": int(row["semester_id"]),
            }
            for row in subjects
        ],
    }


# ============================================================
# VALIDATE PROGRAM + BRANCH
# ============================================================

def _get_registration_branch(
    db: Session,
    program_id: int,
    branch_id: int,
):
    """Validate an active Program -> Branch selection and return its row."""

    row = db.execute(
        text(
            """
            SELECT
                b.branch_id,
                b.branch_name,
                b.branch_code,
                b.program_id,
                b.total_semesters,
                b.is_active AS branch_is_active,
                p.program_name,
                p.program_code,
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

    if row is None:
        raise HTTPException(
            status_code=400,
            detail="Selected department/branch does not exist.",
        )

    if int(row["program_id"]) != program_id:
        raise HTTPException(
            status_code=400,
            detail="Selected department does not belong to the selected program.",
        )

    if not bool(row["program_is_active"]):
        raise HTTPException(
            status_code=409,
            detail="Selected program is inactive.",
        )

    if not bool(row["branch_is_active"]):
        raise HTTPException(
            status_code=409,
            detail="Selected department is inactive.",
        )

    return row


# ============================================================
# VALIDATE FACULTY REQUESTED ASSIGNMENT
# ============================================================

def _validate_faculty_requested_assignment(
    db: Session,
    program_id: int,
    branch_id: int,
    max_semesters: int,
    semester_id: int,
    section_id: int,
    subject_id: int,
) -> None:
    semester = db.execute(
        text(
            """
            SELECT
                semester_id,
                semester_number
            FROM semesters
            WHERE semester_id = :semester_id
            LIMIT 1
            """
        ),
        {"semester_id": semester_id},
    ).mappings().first()

    if semester is None:
        raise HTTPException(
            status_code=400,
            detail="Selected semester does not exist.",
        )

    semester_number = int(semester["semester_number"])

    if semester_number > max_semesters:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Selected department/branch has only {max_semesters} semester(s). "
                f"Semester {semester_number} is outside its configured duration."
            ),
        )

    section = db.execute(
        text(
            """
            SELECT
                sec.section_id,
                sec.semester_id,
                sec.is_active,
                sem.semester_number
            FROM sections sec
            INNER JOIN semesters sem
                ON sem.semester_id = sec.semester_id
            WHERE sec.section_id = :section_id
            LIMIT 1
            """
        ),
        {"section_id": section_id},
    ).mappings().first()

    if section is None:
        raise HTTPException(
            status_code=400,
            detail="Selected section does not exist.",
        )

    if not bool(section["is_active"]):
        raise HTTPException(
            status_code=409,
            detail="Selected section is inactive.",
        )

    if int(section["semester_id"]) != semester_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "Selected section does not belong to "
                "the selected semester."
            ),
        )

    subject = db.execute(
        text(
            """
            SELECT
                subject_id,
                program_id,
                branch_id,
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
            status_code=400,
            detail="Selected subject does not exist.",
        )

    if not bool(subject["is_active"]):
        raise HTTPException(
            status_code=409,
            detail="Selected subject is inactive.",
        )

    if int(subject["program_id"]) != program_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "Selected subject does not belong to "
                "the selected program."
            ),
        )

    if int(subject["branch_id"]) != branch_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "Selected subject does not belong to "
                "the selected department/branch."
            ),
        )

    if int(subject["semester_id"]) != semester_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "Selected subject does not belong to "
                "the selected semester."
            ),
        )


# ============================================================
# VALIDATE STUDENT REQUESTED SECTION
# ============================================================

def _validate_student_requested_section(
    db: Session,
    section_id: int,
    max_semesters: int,
) -> None:
    section = db.execute(
        text(
            """
            SELECT
                section_id,
                semester_id,
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
            status_code=400,
            detail="Selected section does not exist.",
        )

    if not bool(section["is_active"]):
        raise HTTPException(
            status_code=409,
            detail="Selected section is inactive.",
        )

    if section["semester_id"] is None:
        raise HTTPException(
            status_code=409,
            detail="Selected section has no semester configured.",
        )

    semester_number = int(section["semester_number"])

    if semester_number > max_semesters:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Selected department/branch has only {max_semesters} semester(s). "
                f"Semester {semester_number} is outside its configured duration."
            ),
        )


# ============================================================
# REGISTRATION SERVICE
# ============================================================

def register_user(
    db: Session,
    data
):
    """
    Register a new STUDENT or FACULTY account.

    New accounts always start as PENDING.
    """

    role_name = data.role_name.strip().upper()

    if role_name == "ADMIN":
        raise HTTPException(
            status_code=403,
            detail=(
                "Administrator accounts cannot be created through "
                "public registration. An existing administrator must "
                "create the account."
            ),
        )

    allowed_roles = {
        "FACULTY",
        "STUDENT",
    }

    if role_name not in allowed_roles:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid role. Allowed public registration roles: "
                "FACULTY, STUDENT."
            ),
        )

    role = db.scalar(
        select(Role).where(
            Role.role_name == role_name
        )
    )

    if role is None:
        raise HTTPException(
            status_code=400,
            detail=f"Role '{role_name}' does not exist."
        )

    email = data.email.strip().lower()
    full_name = " ".join(data.full_name.strip().split()).title()

    existing_user = db.scalar(
        select(User).where(
            User.email == email
        )
    )

    if existing_user is not None:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists.",
        )

    if data.program_id is None:
        raise HTTPException(
            status_code=400,
            detail="program_id is required for registration.",
        )

    if data.branch_id is None:
        raise HTTPException(
            status_code=400,
            detail="branch_id is required for registration.",
        )

    academic_branch = _get_registration_branch(
        db=db,
        program_id=int(data.program_id),
        branch_id=int(data.branch_id),
    )

    # Validate Faculty requests before creating any user/profile row.
    faculty_requests = list(
        getattr(data, "faculty_assignments", []) or []
    )

    if role_name == "FACULTY":
        if not data.employee_id:
            raise HTTPException(
                status_code=400,
                detail="employee_id is required for FACULTY registration.",
            )

        if not faculty_requests:
            raise HTTPException(
                status_code=400,
                detail=(
                    "At least one Semester, Section and Subject "
                    "assignment request is required for Faculty registration."
                ),
            )

        seen: set[tuple[int, int, int]] = set()

        for item in faculty_requests:
            key = (
                int(item.semester_id),
                int(item.section_id),
                int(item.subject_id),
            )

            if key in seen:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Duplicate Faculty assignment request detected."
                    ),
                )

            seen.add(key)

            _validate_faculty_requested_assignment(
                db=db,
                program_id=int(data.program_id),
                branch_id=int(data.branch_id),
                max_semesters=int(academic_branch["total_semesters"]),
                semester_id=key[0],
                section_id=key[1],
                subject_id=key[2],
            )

    if role_name == "STUDENT":
        if not data.enrollment_number:
            raise HTTPException(
                status_code=400,
                detail=(
                    "enrollment_number is required for STUDENT registration."
                ),
            )

        if not data.abc_id or not data.abc_id.strip():
            raise HTTPException(
                status_code=400,
                detail="abc_id is required for STUDENT registration.",
            )

        abc_id = data.abc_id.strip()

        existing_abc_id = db.scalar(
            select(StudentProfile.student_id).where(
                StudentProfile.abc_id == abc_id
            )
        )

        if existing_abc_id is not None:
            raise HTTPException(
                status_code=409,
                detail="This ABC ID is already registered.",
            )

        if data.student_section_id is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "student_section_id is required for STUDENT registration."
                ),
            )

        _validate_student_requested_section(
            db=db,
            section_id=int(data.student_section_id),
            max_semesters=int(academic_branch["total_semesters"]),
        )

    try:
        password_hash = hash_password(
            data.password
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    user = User(
        role_id=role.role_id,
        email=email,
        password_hash=password_hash,
        full_name=full_name,
        phone=(
            data.phone.strip()
            if data.phone
            else None
        ),
        account_status="PENDING"
    )

    try:
        db.add(user)
        db.flush()

        if role_name == "FACULTY":
            profile = FacultyProfile(
                user_id=user.user_id,
                employee_id=data.employee_id.strip(),
                # Keep legacy department text synchronized for existing
                # reports/screens while branch_id is the authoritative link.
                department=str(academic_branch["branch_name"]).strip(),
                branch_id=int(academic_branch["branch_id"]),
                designation=(
                    data.designation.strip()
                    if data.designation
                    else None
                )
            )

            db.add(profile)
            db.flush()

            for item in faculty_requests:
                db.execute(
                    text(
                        """
                        INSERT INTO faculty_assignment_requests (
                            faculty_id,
                            semester_id,
                            section_id,
                            subject_id,
                            request_status
                        )
                        VALUES (
                            :faculty_id,
                            :semester_id,
                            :section_id,
                            :subject_id,
                            'PENDING'
                        )
                        """
                    ),
                    {
                        "faculty_id": int(profile.faculty_id),
                        "semester_id": int(item.semester_id),
                        "section_id": int(item.section_id),
                        "subject_id": int(item.subject_id),
                    },
                )

        elif role_name == "STUDENT":
            profile = StudentProfile(
                user_id=user.user_id,
                enrollment_number=data.enrollment_number.strip(),
                roll_number=(
                    data.roll_number.strip()
                    if data.roll_number
                    else None
                ),
                date_of_birth=data.date_of_birth,
                branch_id=int(academic_branch["branch_id"]),
                abc_id=abc_id,
            )

            db.add(profile)
            db.flush()

            db.execute(
                text(
                    """
                    INSERT INTO student_section_registration_requests (
                        student_id,
                        section_id,
                        request_status
                    )
                    VALUES (
                        :student_id,
                        :section_id,
                        'PENDING'
                    )
                    """
                ),
                {
                    "student_id": int(profile.student_id),
                    "section_id": int(data.student_section_id),
                },
            )

        db.commit()
        db.refresh(user)

    except HTTPException:
        db.rollback()
        raise

    except Exception as exc:
        db.rollback()

        error_message = str(exc)

        if "Duplicate entry" in error_message:
            raise HTTPException(
                status_code=409,
                detail=(
                    "A record with the supplied unique value already exists."
                ),
            )

        if (
            "faculty_assignment_requests" in error_message
            or "student_section_registration_requests" in error_message
        ) and (
            "doesn't exist" in error_message
            or "does not exist" in error_message
        ):
            raise HTTPException(
                status_code=500,
                detail=(
                    "Registration request storage is not installed. "
                    "Run the supplied database migration first."
                ),
            )

        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": "Registration failed.",
                "error": error_message,
            },
        )

    return user


# ============================================================
# LOGIN SERVICE
# ============================================================

def login_user(
    db: Session,
    email: str,
    password: str
):
    """
    Authenticate a user using email and password.

    Login flow:

        Email + Password
              ↓
        Find user
              ↓
        Verify password
              ↓
        Check account status
              ↓
        Create JWT
              ↓
        Update last_login_at
              ↓
        Return token
    """

    # --------------------------------------------------------
    # 1. NORMALIZE EMAIL
    # --------------------------------------------------------

    email = email.strip().lower()

    # --------------------------------------------------------
    # 2. FIND USER
    # --------------------------------------------------------

    user = db.scalar(
        select(User).where(
            User.email == email
        )
    )

    # --------------------------------------------------------
    # 3. USER NOT FOUND
    #
    # Use the same message as an incorrect password so that
    # the API does not reveal whether an email exists.
    # --------------------------------------------------------

    if user is None:

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password."
        )

    # --------------------------------------------------------
    # 4. VERIFY PASSWORD
    # --------------------------------------------------------

    password_is_valid = verify_password(
        password,
        user.password_hash
    )

    if not password_is_valid:

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password."
        )

    # --------------------------------------------------------
    # 5. CHECK ACCOUNT STATUS
    # --------------------------------------------------------

    if user.account_status == "PENDING":

        raise HTTPException(
            status_code=403,
            detail=(
                "Account is pending activation. "
                "Please wait for an administrator to activate "
                "your account."
            )
        )

    if user.account_status == "SUSPENDED":

        raise HTTPException(
            status_code=403,
            detail=(
                "Your account has been suspended. "
                "Please contact an administrator."
            )
        )

    if user.account_status == "INACTIVE":

        raise HTTPException(
            status_code=403,
            detail=(
                "Your account is inactive. "
                "Please contact an administrator."
            )
        )

    # --------------------------------------------------------
    # 6. MAKE SURE ROLE EXISTS
    # --------------------------------------------------------

    if user.role is None:

        raise HTTPException(
            status_code=500,
            detail=(
                "User account has no valid role assigned."
            )
        )

    role_name = user.role.role_name

    # --------------------------------------------------------
    # 7. CREATE JWT ACCESS TOKEN
    # --------------------------------------------------------

    access_token = create_access_token(
        user_id=user.user_id,
        email=user.email,
        role_name=role_name,
    )

    # --------------------------------------------------------
    # 8. UPDATE LAST LOGIN
    # --------------------------------------------------------

    from datetime import datetime

    user.last_login_at = datetime.utcnow()

    try:

        db.commit()

        db.refresh(user)

    except Exception as exc:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": "Unable to update login information.",
                "error": str(exc)
            }
        )

    # --------------------------------------------------------
    # 9. RETURN LOGIN INFORMATION
    # --------------------------------------------------------

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.user_id,
        "role_name": role_name,
        "email": user.email,
        "full_name": user.full_name,
        "account_status": user.account_status,
        "message": "Login successful."
    }


# ============================================================
# PASSWORD RESET - REQUEST
# ============================================================

def request_password_reset(
    db: Session,
    email: str,
) -> dict:
    """
    Start password reset.

    LOCAL TEST MODE:
        If ALLOW_TEST_PASSWORD_RESET=True, a short-lived reset token
        is returned directly for a registered email.

    PRODUCTION LATER:
        This same function becomes the place that creates/sends an OTP
        or email link. The final password-confirm endpoint does not need
        to be redesigned.
    """

    clean_email = email.strip().lower()

    user = db.scalar(
        select(User).where(
            User.email == clean_email
        )
    )

    generic_message = (
        "If an account with this email exists, "
        "password reset instructions are available."
    )

    # --------------------------------------------------------
    # PRODUCTION-SAFE DEFAULT
    # --------------------------------------------------------

    if not settings.ALLOW_TEST_PASSWORD_RESET:
        return {
            "message": generic_message,
            "test_reset_token": None,
            "expires_in_minutes": None,
            "test_mode": False,
        }

    # --------------------------------------------------------
    # LOCAL TEST BYPASS
    # --------------------------------------------------------

    if user is None:
        return {
            "message": generic_message,
            "test_reset_token": None,
            "expires_in_minutes":
                settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES,
            "test_mode": True,
        }

    reset_token = create_password_reset_token(
        user_id=user.user_id,
        email=user.email,
        password_hash=user.password_hash,
    )

    return {
        "message": generic_message,
        "test_reset_token": reset_token,
        "expires_in_minutes":
            settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES,
        "test_mode": True,
    }


# ============================================================
# PASSWORD RESET - CONFIRM
# ============================================================

def confirm_password_reset(
    db: Session,
    reset_token: str,
    new_password: str,
) -> dict:
    """
    Change the password after a valid short-lived reset token.

    The token carries a fingerprint of the OLD password hash. Once the
    password is changed, that fingerprint no longer matches, so the same
    token cannot be reused.
    """

    try:
        payload = decode_password_reset_token(
            reset_token
        )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=(
                "Password reset session is invalid or expired. "
                "Please start again."
            ),
        )

    try:
        user_id = int(
            payload["sub"]
        )
    except (TypeError, ValueError, KeyError):
        raise HTTPException(
            status_code=400,
            detail=(
                "Password reset session is invalid or expired. "
                "Please start again."
            ),
        )

    token_email = str(
        payload.get("email", "")
    ).strip().lower()

    token_password_fingerprint = str(
        payload.get("pwd", "")
    ).strip()

    user = db.scalar(
        select(User).where(
            User.user_id == user_id,
            User.email == token_email,
        )
    )

    if user is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Password reset session is invalid or expired. "
                "Please start again."
            ),
        )

    current_fingerprint = password_hash_fingerprint(
        user.password_hash
    )

    if (
        not token_password_fingerprint
        or token_password_fingerprint
        != current_fingerprint
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "This password reset session has already been used "
                "or is no longer valid."
            ),
        )

    if verify_password(
        new_password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "New password must be different from "
                "your current password."
            ),
        )

    try:
        new_password_hash = hash_password(
            new_password
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    user.password_hash = new_password_hash

    try:
        db.commit()
        db.refresh(user)

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": "Unable to reset password.",
                "error": str(exc),
            },
        )

    return {
        "message": (
            "Password changed successfully. "
            "You can now sign in with your new password."
        ),
    }
