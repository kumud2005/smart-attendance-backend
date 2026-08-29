"""
Authentication and Registration Service
========================================

This module handles:

1. Password hashing
2. Password verification
3. User registration
4. User login
5. JWT access-token generation
6. Role validation
7. Duplicate email checking
8. Role-specific profile creation

Supported roles:

    ADMIN
    FACULTY
    STUDENT

Password hashing uses bcrypt directly.
"""

import bcrypt

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token

from app.models.role import Role
from app.models.user import User
from app.models.admin_profile import AdminProfile
from app.models.faculty_profile import FacultyProfile
from app.models.student_profile import StudentProfile


# ============================================================
# PASSWORD FUNCTIONS
# ============================================================

def hash_password(password: str) -> str:
    """
    Hash a plain-text password using bcrypt.

    bcrypt has a maximum password size of 72 bytes.
    """

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
    """
    Verify a plain-text password against a bcrypt hash.
    """

    try:

        password_bytes = password.encode("utf-8")
        hash_bytes = password_hash.encode("utf-8")

        # bcrypt cannot process passwords over 72 bytes
        if len(password_bytes) > 72:
            return False

        return bcrypt.checkpw(
            password_bytes,
            hash_bytes
        )

    except (ValueError, TypeError):

        return False


# ============================================================
# REGISTRATION SERVICE
# ============================================================

def register_user(
    db: Session,
    data
):
    """
    Register a new ADMIN, FACULTY, or STUDENT.
    """

    # --------------------------------------------------------
    # 1. NORMALIZE ROLE
    # --------------------------------------------------------

    role_name = data.role_name.strip().upper()

    allowed_roles = {
        "ADMIN",
        "FACULTY",
        "STUDENT"
    }

    if role_name not in allowed_roles:

        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid role. "
                "Allowed roles: ADMIN, FACULTY, STUDENT"
            )
        )

    # --------------------------------------------------------
    # 2. FIND ROLE
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # 3. CHECK DUPLICATE EMAIL
    # --------------------------------------------------------

    email = data.email.strip().lower()

    existing_user = db.scalar(
        select(User).where(
            User.email == email
        )
    )

    if existing_user is not None:

        raise HTTPException(
            status_code=409,
            detail=(
                "An account with this email already exists."
            )
        )

    # --------------------------------------------------------
    # 4. HASH PASSWORD
    # --------------------------------------------------------

    try:

        password_hash = hash_password(
            data.password
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    # --------------------------------------------------------
    # 5. CREATE USER
    # --------------------------------------------------------

    user = User(
        role_id=role.role_id,
        email=email,
        password_hash=password_hash,
        full_name=data.full_name.strip(),
        phone=(
            data.phone.strip()
            if data.phone
            else None
        ),
        account_status="PENDING"
    )

    db.add(user)

    # Generate user_id before creating profile.
    db.flush()

    # --------------------------------------------------------
    # 6. CREATE ADMIN PROFILE
    # --------------------------------------------------------

    if role_name == "ADMIN":

        if not data.employee_id:

            db.rollback()

            raise HTTPException(
                status_code=400,
                detail=(
                    "employee_id is required "
                    "for ADMIN registration."
                )
            )

        profile = AdminProfile(
            user_id=user.user_id,
            employee_id=data.employee_id.strip(),
            designation=(
                data.designation.strip()
                if data.designation
                else None
            )
        )

        db.add(profile)

    # --------------------------------------------------------
    # 7. CREATE FACULTY PROFILE
    # --------------------------------------------------------

    elif role_name == "FACULTY":

        if not data.employee_id:

            db.rollback()

            raise HTTPException(
                status_code=400,
                detail=(
                    "employee_id is required "
                    "for FACULTY registration."
                )
            )

        profile = FacultyProfile(
            user_id=user.user_id,
            employee_id=data.employee_id.strip(),
            department=(
                data.department.strip()
                if data.department
                else None
            ),
            designation=(
                data.designation.strip()
                if data.designation
                else None
            )
        )

        db.add(profile)

    # --------------------------------------------------------
    # 8. CREATE STUDENT PROFILE
    # --------------------------------------------------------

    elif role_name == "STUDENT":

        if not data.enrollment_number:

            db.rollback()

            raise HTTPException(
                status_code=400,
                detail=(
                    "enrollment_number is required "
                    "for STUDENT registration."
                )
            )

        profile = StudentProfile(
            user_id=user.user_id,
            enrollment_number=data.enrollment_number.strip(),
            roll_number=(
                data.roll_number.strip()
                if data.roll_number
                else None
            ),
            date_of_birth=data.date_of_birth
        )

        db.add(profile)

    # --------------------------------------------------------
    # 9. COMMIT REGISTRATION
    # --------------------------------------------------------

    try:

        db.commit()

        db.refresh(user)

    except Exception as exc:

        db.rollback()

        error_message = str(exc)

        if (
            "Duplicate entry" in error_message
            or "uq_users_email" in error_message
        ):

            raise HTTPException(
                status_code=409,
                detail=(
                    "A record with the supplied "
                    "unique value already exists."
                )
            )

        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": "Registration failed.",
                "error": error_message
            }
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
