from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# CREATE ATTENDANCE SESSION
# ============================================================

class AttendanceSessionCreate(BaseModel):
    semester_id: int
    section_id: int
    subject_id: int
    classroom_id: int

    qr_validity_minutes: int = Field(
        default=5,
        ge=1,
        le=15,
    )

    geofence_radius_meters: float = Field(
        default=50.0,
        ge=10.0,
        le=500.0,
    )


# ============================================================
# ATTENDANCE SESSION RESPONSE
# ============================================================

class AttendanceSessionResponse(BaseModel):
    session_id: int
    faculty_id: int

    semester_id: int
    section_id: int
    subject_id: int
    classroom_id: int

    geofence_radius_meters: float

    session_token: str

    started_at: datetime
    ended_at: datetime | None

    qr_expires_at: datetime

    session_status: str

    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


# ============================================================
# ATTENDANCE SESSION QR RESPONSE
# ============================================================

class AttendanceSessionQRResponse(BaseModel):
    session_id: int

    semester_id: int

    subject_id: int
    subject_name: str

    section_id: int
    section_name: str

    classroom_id: int

    geofence_radius_meters: float

    session_status: str

    started_at: datetime
    qr_expires_at: datetime

    qr_data: str
    qr_code_base64: str
    qr_image_data_uri: str

    model_config = ConfigDict(
        from_attributes=True
    )


# ============================================================
# CANCEL SESSION
# ============================================================

class AttendanceSessionCancelResponse(BaseModel):
    session_id: int
    session_status: str
    ended_at: datetime
    message: str