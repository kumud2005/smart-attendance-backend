from pydantic import BaseModel


class FaceVerificationResponse(BaseModel):
    attendance_id: int
    session_id: int
    student_id: int
    subject_id: int
    subject_name: str
    section_id: int
    section_name: str
    classroom_id: int
    face_verified: bool
    face_similarity: float
    attendance_status: str
    rejection_reason: str | None = None
    next_verification_step: str | None = None