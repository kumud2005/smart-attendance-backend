from datetime import datetime

from pydantic import BaseModel, ConfigDict


# ============================================================
# FACULTY PROFILE RESPONSE
# ============================================================

class FacultyProfileResponse(BaseModel):
    user_id: int
    faculty_id: int
    employee_id: str

    email: str
    full_name: str
    phone: str | None

    role_name: str
    account_status: str

    department: str | None
    designation: str | None

    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None

    model_config = ConfigDict(
        from_attributes=True
    )


# ============================================================
# FACULTY SUBJECT
# ============================================================

class FacultySubjectResponse(BaseModel):
    subject_id: int
    subject_code: str
    subject_name: str
    credits: float | None = None

    model_config = ConfigDict(
        from_attributes=True
    )


# ============================================================
# FACULTY SECTION
# ============================================================

class FacultySectionResponse(BaseModel):
    section_id: int
    section_name: str
    student_count: int = 0

    model_config = ConfigDict(
        from_attributes=True
    )


# ============================================================
# RECENT ATTENDANCE SESSION
# ============================================================

class FacultyAttendanceSessionResponse(BaseModel):
    session_id: int

    subject_id: int
    subject_name: str

    section_id: int
    section_name: str

    classroom_id: int

    session_status: str
    started_at: datetime
    ended_at: datetime | None
    qr_expires_at: datetime

    attendance_count: int = 0

    model_config = ConfigDict(
        from_attributes=True
    )


# ============================================================
# FACULTY DASHBOARD RESPONSE
# ============================================================

class FacultyDashboardResponse(BaseModel):
    user_id: int
    faculty_id: int
    employee_id: str

    full_name: str
    email: str
    phone: str | None

    department: str | None
    designation: str | None

    role_name: str
    account_status: str

    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None

    # ----------------------------------------------------------
    # DASHBOARD STATISTICS
    # ----------------------------------------------------------

    subject_count: int = 0
    section_count: int = 0
    student_count: int = 0
    attendance_count: int = 0

    # ----------------------------------------------------------
    # ASSIGNED DATA
    # ----------------------------------------------------------

    subjects: list[FacultySubjectResponse] = []
    sections: list[FacultySectionResponse] = []

    # ----------------------------------------------------------
    # RECENT SESSIONS
    # ----------------------------------------------------------

    recent_sessions: list[
        FacultyAttendanceSessionResponse
    ] = []

    model_config = ConfigDict(
        from_attributes=True
    )