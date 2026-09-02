from fastapi import (
    APIRouter,
    Depends,
)
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.database import get_db
from app.models.user import User


# ============================================================
# SCHEMAS
# ============================================================

from app.schemas.attendance import (
    AttendanceGeofenceRequest,
    AttendanceGeofenceResponse,
    AttendanceMarkRequest,
    AttendanceMarkResponse,
)

from app.schemas.face import (
    FaceRegistrationRequest,
    FaceRegistrationResponse,
)

from app.schemas.face_embedding import (
    FaceEmbeddingRequest,
)

from app.schemas.face_verification import (
    FaceVerificationResponse,
)

from app.schemas.liveness import (
    LivenessVerificationRequest,
    LivenessVerificationResponse,
)


# ============================================================
# SERVICES
# ============================================================

from app.services.attendance_service import (
    mark_attendance_with_qr,
    verify_attendance_geofence,
)

from app.services.face_registration_service import (
    get_student_face_status,
    register_student_face,
)

from app.services.face_embedding_service import (
    verify_student_face_embedding,
)

from app.services.liveness_service import (
    verify_liveness,
)

from app.services.student_service import (
    get_student_attendance_report,
    get_student_dashboard,
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/student",
    tags=["Student"],
)


# ============================================================
# STUDENT DASHBOARD
# ============================================================

@router.get(
    "/dashboard",
)
def student_dashboard(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(
        get_db
    ),
):
    return get_student_dashboard(
        db=db,
        current_user=current_user,
    )


# ============================================================
# STUDENT ATTENDANCE REPORT
# ============================================================

@router.get(
    "/attendance/report",
)
def student_attendance_report(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(
        get_db
    ),
):
    """
    Complete read-only student attendance report.

    Returns:

        - overall summary
        - subject-wise attendance
        - day-wise attendance
        - detailed session records

    Student Web:
        Reports only.

    Student Mobile:
        Reports + attendance verification flow.
    """

    return get_student_attendance_report(
        db=db,
        current_user=current_user,
    )


# ============================================================
# MARK ATTENDANCE USING QR
# ============================================================

@router.post(
    "/attendance/mark",
    response_model=AttendanceMarkResponse,
    status_code=201,
)
def mark_attendance(
    request: AttendanceMarkRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(
        get_db
    ),
):
    """
    Attendance Step 1.

    QR
        ↓
    Attendance record created as PENDING
        ↓
    Next verification step: GEOFENCE
    """

    return mark_attendance_with_qr(
        db=db,
        current_user=current_user,
        qr_data=request.qr_data,
        latitude=request.latitude,
        longitude=request.longitude,
    )


# ============================================================
# VERIFY GEOFENCE
# ============================================================

@router.post(
    "/attendance/{attendance_id}/geofence",
    response_model=AttendanceGeofenceResponse,
)
def verify_geofence(
    attendance_id: int,
    request: AttendanceGeofenceRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(
        get_db
    ),
):
    """
    Attendance Step 2.

    QR VERIFIED
        ↓
    GEOFENCE
        ↓
    Next verification step: FACE
    """

    return verify_attendance_geofence(
        db=db,
        current_user=current_user,
        attendance_id=attendance_id,
        latitude=request.latitude,
        longitude=request.longitude,
    )


# ============================================================
# FACE PROFILE STATUS
# ============================================================

@router.get(
    "/face/status",
)
def face_registration_status(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(
        get_db
    ),
):
    """
    Return the authenticated student's
    face-registration status.

    No biometric photograph is returned.
    """

    return get_student_face_status(
        db=db,
        current_user=current_user,
    )


# ============================================================
# REGISTER FACE EMBEDDING
# ============================================================

@router.post(
    "/face/register",
    response_model=FaceRegistrationResponse,
    status_code=201,
)
def register_face(
    request: FaceRegistrationRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(
        get_db
    ),
):
    """
    Register the student's face embedding when no face profile exists.

    Flutter performs locally:

        Camera
            ↓
        OpenCV quality validation
            ↓
        det_10g.onnx
            ↓
        5 facial landmarks
            ↓
        ArcFace 112x112 alignment
            ↓
        w600k_r50.onnx
            ↓
        normalized 512D embedding

    Only the normalized embedding is sent.

    No face photograph is uploaded.
    """

    return register_student_face(
        db=db,
        current_user=current_user,

        face_embedding=
            request.face_embedding,

        embedding_dimensions=
            request.embedding_dimensions,

        model_name=
            request.model_name,
    )


# ============================================================
# VERIFY FACE USING LOCAL EMBEDDING
# ============================================================

@router.post(
    "/attendance/{attendance_id}/face-embedding",
    response_model=FaceVerificationResponse,
)
def verify_face_embedding(
    attendance_id: int,
    request: FaceEmbeddingRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(
        get_db
    ),
):
    """
    Attendance Step 3.

    Flutter:

        Camera
            ↓
        Local OpenCV preprocessing
            ↓
        Local SCRFD face detection
            ↓
        Local ArcFace alignment
            ↓
        Local w600k_r50 embedding
            ↓
        normalized 512D embedding

    Backend:

        registered embedding
                VS
        current embedding
                ↓
        cosine similarity
                ↓
        FACE VERIFIED
                ↓
        next step: LIVENESS

    No face photograph is uploaded.
    """

    return verify_student_face_embedding(
        db=db,
        current_user=current_user,
        attendance_id=attendance_id,
        embedding=request.embedding,
        model_name=request.model_name,
    )


# ============================================================
# VERIFY LIVENESS USING LOCAL NUMERIC EVIDENCE
# ============================================================

@router.post(
    "/attendance/{attendance_id}/liveness",
    response_model=LivenessVerificationResponse,
)
def verify_attendance_liveness(
    attendance_id: int,
    request: LivenessVerificationRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(
        get_db
    ),
):
    """
    Attendance Step 4.

    The phone processes all three
    liveness captures locally.

    FastAPI receives only numeric evidence:

        - three normalized 512D embeddings
        - eye-open probabilities
        - head-pose values
        - local detection confidence

    No liveness photograph is uploaded.

    Successful flow:

        QR
            ↓
        GEOFENCE
            ↓
        FACE
            ↓
        LIVENESS
            ↓
        PRESENT
    """

    return verify_liveness(
        db=db,
        current_user=current_user,
        attendance_id=attendance_id,
        request=request,
    )