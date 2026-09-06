from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.database import get_db

from app.schemas.auth import (
    RegisterRequest,
    RegisterResponse,
    RegistrationOptionsResponse,
    LoginRequest,
    LoginResponse,
    PasswordResetConfirmRequest,
    PasswordResetConfirmResponse,
    PasswordResetRequest,
    PasswordResetRequestResponse,
)

from app.services.auth_service import (
    register_user,
    get_registration_options,
    login_user,
    request_password_reset,
    confirm_password_reset,
)


# ============================================================
# AUTHENTICATION ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)


# ============================================================
# PUBLIC REGISTRATION OPTIONS
# ============================================================

@router.get(
    "/registration-options",
    response_model=RegistrationOptionsResponse,
    status_code=status.HTTP_200_OK,
)
def registration_options(
    semester_id: int | None = None,
    db: Session = Depends(get_db),
):
    """
    Public academic options for Student and Faculty registration.

    Students use Semester -> Section. Faculty uses
    Semester -> Section -> Subject.
    """

    return get_registration_options(
        db=db,
        semester_id=semester_id,
    )


# ============================================================
# REGISTER
# ============================================================

@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED
)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Public registration for STUDENT and FACULTY accounts.

    Administrator accounts must be created by an authenticated Admin.
    """

    user = register_user(
        db=db,
        data=data
    )

    return RegisterResponse(
        user_id=user.user_id,
        role_name=user.role.role_name,
        email=user.email,
        full_name=user.full_name,
        account_status=user.account_status,
        message=(
            "Registration successful. "
            "Account is pending administrator approval."
        )
    )


# ============================================================
# LOGIN
# ============================================================

@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK
)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Login for Student, Faculty and Admin users.

    Returns a JWT access token when the account is active.
    """

    result = login_user(
        db=db,
        email=str(data.email),
        password=data.password
    )

    return LoginResponse(
        access_token=result["access_token"],
        token_type=result["token_type"],
        user_id=result["user_id"],
        role_name=result["role_name"],
        email=result["email"],
        full_name=result["full_name"],
        account_status=result["account_status"],
        message=result["message"],
    )


# ============================================================
# PASSWORD RESET - REQUEST
# ============================================================

@router.post(
    "/password-reset/request",
    response_model=PasswordResetRequestResponse,
    status_code=status.HTTP_200_OK,
)
def password_reset_request(
    data: PasswordResetRequest,
    db: Session = Depends(get_db),
):
    """
    Start password reset.

    Local development can explicitly enable a direct test-token bypass.
    Production later will send verification through email/OTP instead.
    """

    return request_password_reset(
        db=db,
        email=str(data.email),
    )


# ============================================================
# PASSWORD RESET - CONFIRM
# ============================================================

@router.post(
    "/password-reset/confirm",
    response_model=PasswordResetConfirmResponse,
    status_code=status.HTTP_200_OK,
)
def password_reset_confirm(
    data: PasswordResetConfirmRequest,
    db: Session = Depends(get_db),
):
    """
    Change the password using a valid short-lived reset token.
    """

    return confirm_password_reset(
        db=db,
        reset_token=data.reset_token,
        new_password=data.new_password,
    )
