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
# FACULTY REGISTRATION ASSIGNMENT REQUEST
# ============================================================

class FacultyRegistrationAssignmentRequest(BaseModel):
    """
    One Semester + Section + Subject combination requested by
    a Faculty member during public registration.

    This is only a request. It does not become an active teaching
    assignment until an administrator approves the registration.
    """

    model_config = ConfigDict(extra="forbid")

    semester_id: int = Field(..., gt=0)
    section_id: int = Field(..., gt=0)
    subject_id: int = Field(..., gt=0)


# ============================================================
# REGISTER
# ============================================================

class RegisterRequest(BaseModel):
    """
    Public registration request.

    Public registration supports only STUDENT and FACULTY.
    Administrator accounts are created by an authenticated Admin.
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
    # FACULTY
    # --------------------------------------------------------

    employee_id: str | None = Field(
        default=None,
        max_length=50
    )

    department: str | None = Field(
        default=None,
        max_length=100
    )

    designation: str | None = Field(
        default=None,
        max_length=100
    )

    faculty_assignments: list[
        FacultyRegistrationAssignmentRequest
    ] = Field(default_factory=list)

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

    # Student selects the requested Section during registration.
    # Semester is derived from the selected Section and is shown in
    # the registration UI through /api/auth/registration-options.
    student_section_id: int | None = Field(default=None, gt=0)

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
# REGISTRATION OPTIONS
# ============================================================

class RegistrationOptionsResponse(BaseModel):
    semesters: list[dict]
    sections: list[dict]
    subjects: list[dict]


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
