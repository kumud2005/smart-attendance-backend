"""
Authentication request and response schemas.
"""

from datetime import date

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


# ============================================================
# REGISTER
# ============================================================

class RegisterRequest(BaseModel):
    """
    Request body used by Admin, Faculty and Student registration.

    Role-specific fields are optional at schema level because
    validation is performed according to role.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    role_name: str = Field(
        ...,
        min_length=1,
        max_length=30
    )

    email: EmailStr

    password: str = Field(
        ...,
        min_length=8,
        max_length=128
    )

    full_name: str = Field(
        ...,
        min_length=2,
        max_length=120
    )

    phone: str | None = Field(
        default=None,
        max_length=20
    )

    # --------------------------------------------------------
    # ADMIN / FACULTY
    # --------------------------------------------------------

    employee_id: str | None = Field(
        default=None,
        max_length=50
    )

    # --------------------------------------------------------
    # FACULTY
    # --------------------------------------------------------

    department: str | None = Field(
        default=None,
        max_length=100
    )

    designation: str | None = Field(
        default=None,
        max_length=100
    )

    # --------------------------------------------------------
    # STUDENT
    # --------------------------------------------------------

    enrollment_number: str | None = Field(
        default=None,
        max_length=50
    )

    roll_number: str | None = Field(
        default=None,
        max_length=50
    )

    date_of_birth: date | None = None

    # --------------------------------------------------------
    # NORMALIZE ROLE
    # --------------------------------------------------------

    @field_validator("role_name")
    @classmethod
    def normalize_role(cls, value: str) -> str:

        return value.strip().upper()

    # --------------------------------------------------------
    # NORMALIZE EMAIL
    # --------------------------------------------------------

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:

        return str(value).strip().lower()


# ============================================================
# REGISTER RESPONSE
# ============================================================

class RegisterResponse(BaseModel):

    user_id: int
    role_name: str
    email: str
    full_name: str
    account_status: str
    message: str


# ============================================================
# LOGIN REQUEST
# ============================================================

class LoginRequest(BaseModel):
    """
    Request body used for Student, Faculty and Admin login.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    email: EmailStr

    password: str = Field(
        ...,
        min_length=1,
        max_length=128
    )

    # --------------------------------------------------------
    # NORMALIZE EMAIL
    # --------------------------------------------------------

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:

        return str(value).strip().lower()


# ============================================================
# LOGIN RESPONSE
# ============================================================

class LoginResponse(BaseModel):

    access_token: str
    token_type: str

    user_id: int
    role_name: str

    email: str
    full_name: str

    account_status: str

    message: str