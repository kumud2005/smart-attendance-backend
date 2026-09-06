"""
Authentication request and response schemas.
"""

from datetime import date
import re

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
    # ACADEMIC IDENTITY (STUDENT + FACULTY)
    # --------------------------------------------------------

    # Both values are required by the registration service for new public
    # registrations. Program is submitted so the backend can verify that
    # the selected branch actually belongs to it. Only branch_id is stored
    # in the profile because branches.program_id already defines the program.
    program_id: int | None = Field(default=None, gt=0)
    branch_id: int | None = Field(default=None, gt=0)

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

    abc_id: str | None = Field(
        default=None,
        max_length=20
    )

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

    # --------------------------------------------------------
    # NORMALIZE FULL NAME
    # --------------------------------------------------------

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        return " ".join(value.strip().split()).title()

    # --------------------------------------------------------
    # PASSWORD STRENGTH
    # --------------------------------------------------------

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if not re.search(r"[A-Z]", value):
            raise ValueError(
                "Password must contain at least 1 uppercase letter."
            )

        if not re.search(r"[a-z]", value):
            raise ValueError(
                "Password must contain at least 1 lowercase letter."
            )

        if not re.search(r"[0-9]", value):
            raise ValueError(
                "Password must contain at least 1 number."
            )

        if not re.search(r"[^A-Za-z0-9]", value):
            raise ValueError(
                "Password must contain at least 1 special character."
            )

        return value


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
    programs: list[dict]
    branches: list[dict]
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


# ============================================================
# PASSWORD RESET - REQUEST
# ============================================================

class PasswordResetRequest(BaseModel):
    """
    Start a password-reset flow.

    Current local-test mode:
        registered email -> short-lived reset token

    Future production mode:
        registered email -> email/OTP verification -> reset token
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(
        cls,
        value: EmailStr,
    ) -> str:
        return str(value).strip().lower()


class PasswordResetRequestResponse(BaseModel):
    message: str

    # Returned ONLY while the explicit local test bypass is enabled.
    test_reset_token: str | None = None

    expires_in_minutes: int | None = None

    test_mode: bool = False


# ============================================================
# PASSWORD RESET - CONFIRM
# ============================================================

class PasswordResetConfirmRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    reset_token: str = Field(
        ...,
        min_length=1,
    )

    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
    )

    @field_validator("new_password")
    @classmethod
    def validate_new_password_strength(
        cls,
        value: str,
    ) -> str:
        if not re.search(r"[A-Z]", value):
            raise ValueError(
                "Password must contain at least 1 uppercase letter."
            )

        if not re.search(r"[a-z]", value):
            raise ValueError(
                "Password must contain at least 1 lowercase letter."
            )

        if not re.search(r"[0-9]", value):
            raise ValueError(
                "Password must contain at least 1 number."
            )

        if not re.search(r"[^A-Za-z0-9]", value):
            raise ValueError(
                "Password must contain at least 1 special character."
            )

        return value


class PasswordResetConfirmResponse(BaseModel):
    message: str
