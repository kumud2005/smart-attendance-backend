"""
Admin Dashboard Schemas
=======================

Pydantic schemas used by the Admin Dashboard API.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ============================================================
# DASHBOARD STATISTICS
# ============================================================

class AdminDashboardResponse(BaseModel):

    total_users: int

    pending_users: int
    active_users: int
    suspended_users: int
    inactive_users: int

    total_students: int
    total_faculty: int
    total_admins: int


# ============================================================
# USER LIST ITEM
# ============================================================

class AdminUserListItem(BaseModel):

    model_config = ConfigDict(
        from_attributes=True
    )

    user_id: int
    email: str
    full_name: str
    phone: str | None

    role_name: str

    account_status: str

    created_at: datetime
    updated_at: datetime

    last_login_at: datetime | None


# ============================================================
# PROFILE DETAILS
# ============================================================

class StudentProfileDetails(BaseModel):

    student_id: int
    enrollment_number: str
    roll_number: str | None
    date_of_birth: date | None


class FacultyProfileDetails(BaseModel):

    faculty_id: int
    employee_id: str
    department: str | None
    designation: str | None


class AdminProfileDetails(BaseModel):

    admin_id: int
    employee_id: str
    designation: str | None


# ============================================================
# COMPLETE USER DETAILS
# ============================================================

class AdminUserDetailResponse(BaseModel):

    user_id: int

    email: str
    full_name: str
    phone: str | None

    role_name: str

    account_status: str

    created_at: datetime
    updated_at: datetime

    last_login_at: datetime | None

    student_profile: StudentProfileDetails | None = None

    faculty_profile: FacultyProfileDetails | None = None

    admin_profile: AdminProfileDetails | None = None


# ============================================================
# STATUS UPDATE RESPONSE
# ============================================================

class AdminUserStatusResponse(BaseModel):

    user_id: int

    email: str

    full_name: str

    role_name: str

    previous_status: str

    account_status: str

    message: str

# ============================================================
# ACADEMIC PROGRAM / COURSE-BRANCH MANAGEMENT
# ============================================================

class AdminProgramCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    program_code: str = Field(..., min_length=1, max_length=30)
    program_name: str = Field(..., min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=255)


class AdminProgramItem(BaseModel):
    program_id: int
    program_code: str
    program_name: str
    description: str | None = None
    is_active: bool


class AdminProgramMutationResponse(AdminProgramItem):
    message: str


class AdminBranchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    program_id: int = Field(..., gt=0)
    branch_code: str = Field(..., min_length=1, max_length=30)
    branch_name: str = Field(..., min_length=2, max_length=100)


class AdminBranchItem(BaseModel):
    branch_id: int
    program_id: int
    program_code: str
    program_name: str
    branch_code: str
    branch_name: str
    is_active: bool


class AdminBranchMutationResponse(AdminBranchItem):
    message: str


# ============================================================
# ACADEMIC SUBJECT MANAGEMENT
# ============================================================

class AdminSubjectCreate(BaseModel):
    """Create one subject inside Program -> Branch -> Semester."""

    model_config = ConfigDict(extra="forbid")

    program_id: int = Field(..., gt=0)
    branch_id: int = Field(..., gt=0)
    semester_id: int = Field(..., gt=0)

    subject_code: str = Field(..., min_length=1, max_length=30)
    subject_name: str = Field(..., min_length=2, max_length=150)
    credits: float | None = Field(default=None, ge=0, le=30)


class AdminSubjectItem(BaseModel):
    subject_id: int

    program_id: int
    program_code: str
    program_name: str

    branch_id: int
    branch_code: str
    branch_name: str

    semester_id: int
    semester_number: int | None = None
    semester_name: str | None = None

    subject_code: str
    subject_name: str
    credits: float | None = None
    is_active: bool


class AdminSubjectMutationResponse(AdminSubjectItem):
    message: str


class AdminSubjectOptionsResponse(BaseModel):
    programs: list[dict]
    branches: list[dict]
    semesters: list[dict]


# ============================================================
# FACULTY ASSIGNMENT MANAGEMENT
# ============================================================

class AdminFacultyAssignmentCreate(BaseModel):
    faculty_id: int = Field(..., gt=0)
    semester_id: int = Field(..., gt=0)
    section_id: int = Field(..., gt=0)
    subject_id: int = Field(..., gt=0)


class AdminFacultyAssignmentItem(BaseModel):
    assignment_id: int

    faculty_id: int
    faculty_name: str
    employee_id: str

    semester_id: int
    semester_number: int | None = None
    semester_name: str | None = None

    section_id: int
    section_name: str

    subject_id: int
    subject_code: str
    subject_name: str

    is_active: bool


class AdminFacultyAssignmentMutationResponse(
    AdminFacultyAssignmentItem
):
    message: str


class AdminFacultyAssignmentOptionsResponse(BaseModel):
    faculties: list[dict]
    semesters: list[dict]
    sections: list[dict]
    subjects: list[dict]




# ============================================================
# ADMIN-CREATED ADMIN ACCOUNT
# ============================================================

class AdminCreateAdminRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    employee_id: str = Field(..., min_length=1, max_length=50)
    designation: str | None = Field(default=None, max_length=100)


class AdminCreateAdminResponse(BaseModel):
    user_id: int
    admin_id: int
    email: str
    full_name: str
    employee_id: str
    account_status: str
    message: str


# ============================================================
# STUDENT REGISTRATION REVIEW
# ============================================================

class AdminStudentRegistrationDecision(BaseModel):
    note: str | None = Field(default=None, max_length=255)


class AdminStudentRegistrationReviewItem(BaseModel):
    request_id: int
    user_id: int
    student_id: int
    email: str
    full_name: str
    phone: str | None
    enrollment_number: str
    roll_number: str | None
    date_of_birth: date | None
    account_status: str
    created_at: datetime
    section_id: int
    section_name: str
    semester_id: int
    semester_number: int | None = None
    semester_name: str | None = None
    request_status: str
    requested_at: datetime
    reviewed_at: datetime | None = None
    reviewed_by_user_id: int | None = None
    review_note: str | None = None


class AdminStudentRegistrationDecisionResponse(BaseModel):
    user_id: int
    student_id: int
    email: str
    full_name: str
    account_status: str
    section_id: int
    section_name: str
    message: str


# ============================================================
# FACULTY REGISTRATION REVIEW
# ============================================================

class AdminFacultyRegistrationDecision(BaseModel):
    note: str | None = Field(default=None, max_length=255)


class AdminFacultyRegistrationAssignmentItem(BaseModel):
    request_id: int
    semester_id: int
    semester_number: int | None = None
    semester_name: str | None = None
    section_id: int
    section_name: str
    subject_id: int
    subject_code: str
    subject_name: str
    request_status: str
    requested_at: datetime
    reviewed_at: datetime | None = None
    reviewed_by_user_id: int | None = None
    review_note: str | None = None


class AdminFacultyRegistrationReviewItem(BaseModel):
    user_id: int
    faculty_id: int
    email: str
    full_name: str
    phone: str | None
    employee_id: str
    department: str | None
    designation: str | None
    account_status: str
    created_at: datetime
    assignments: list[AdminFacultyRegistrationAssignmentItem]


class AdminFacultyRegistrationDecisionResponse(BaseModel):
    user_id: int
    faculty_id: int
    email: str
    full_name: str
    account_status: str
    processed_assignments: int
    message: str


# ============================================================
# ADMIN STUDENT FACE MANAGEMENT
# ============================================================

class AdminStudentFaceStatusResponse(BaseModel):
    user_id: int
    student_id: int
    full_name: str
    enrollment_number: str
    registered: bool
    face_profile_id: int | None = None
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
    is_verified: bool = False
    is_active: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AdminStudentFaceDeleteResponse(BaseModel):
    student_id: int
    deleted_face_profile_id: int
    registered: bool
    message: str


# ============================================================
# CLASSROOM MANAGEMENT
# ============================================================

class AdminClassroomCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    building_name: str = Field(..., min_length=1, max_length=100)
    room_number: str = Field(..., min_length=1, max_length=50)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    geofence_radius_meters: float = Field(default=50.0, ge=10, le=500)
    is_active: bool = True


class AdminClassroomUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    building_name: str | None = Field(default=None, min_length=1, max_length=100)
    room_number: str | None = Field(default=None, min_length=1, max_length=50)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    geofence_radius_meters: float | None = Field(default=None, ge=10, le=500)


class AdminClassroomItem(BaseModel):
    classroom_id: int
    building_name: str
    room_number: str
    latitude: float
    longitude: float
    geofence_radius_meters: float
    is_active: bool
    created_at: datetime


class AdminClassroomMutationResponse(AdminClassroomItem):
    message: str
