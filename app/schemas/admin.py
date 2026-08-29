"""
Admin Dashboard Schemas
=======================

Pydantic schemas used by the Admin Dashboard API.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


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