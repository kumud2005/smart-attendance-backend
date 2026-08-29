from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.database import get_db

from app.schemas.auth import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    LoginResponse,
)

from app.services.auth_service import (
    register_user,
    login_user,
)


# ============================================================
# AUTHENTICATION ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
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
    Register a new Student, Faculty or Admin account.
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
            "Account is pending activation."
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