from datetime import datetime

from pydantic import BaseModel, ConfigDict


# ============================================================
# MARK ATTENDANCE USING QR
# ============================================================

class AttendanceMarkRequest(BaseModel):
    qr_data: str
    latitude: float | None = None
    longitude: float | None = None


class AttendanceMarkResponse(BaseModel):
    attendance_id: int
    session_id: int
    student_id: int
    subject_id: int
    subject_name: str
    section_id: int
    section_name: str
    classroom_id: int
    marked_at: datetime
    qr_verified: bool
    geofence_verified: bool
    face_verified: bool
    liveness_verified: bool
    attendance_status: str
    rejection_reason: str | None
    next_verification_step: str

    model_config = ConfigDict(from_attributes=True)



# ============================================================
# ACTIVE / RESUMABLE ATTENDANCE ATTEMPT
# ============================================================

class AttendanceActiveAttemptResponse(BaseModel):
    has_active_attempt: bool
    attempt: AttendanceMarkResponse | None = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# GEOFENCE VERIFICATION
# ============================================================

class AttendanceGeofenceRequest(BaseModel):
    latitude: float
    longitude: float


class AttendanceGeofenceResponse(BaseModel):
    attendance_id: int
    session_id: int
    student_id: int

    latitude: float
    longitude: float

    classroom_latitude: float
    classroom_longitude: float
    geofence_radius_meters: float
    distance_from_classroom_meters: float

    qr_verified: bool
    geofence_verified: bool
    face_verified: bool
    liveness_verified: bool

    attendance_status: str
    rejection_reason: str | None
    next_verification_step: str

    model_config = ConfigDict(from_attributes=True)