from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.database import get_db
from app.models.user import User

from app.schemas.attendance_session import (
    AttendanceSessionCancelResponse,
    AttendanceSessionCreate,
    AttendanceSessionQRResponse,
    AttendanceSessionResponse,
)

from app.schemas.faculty import (
    FacultyDashboardResponse,
    FacultyProfileResponse,
)

from app.services.attendance_session_service import (
    cancel_attendance_session,
    complete_attendance_session,
    create_attendance_session,
    generate_attendance_session_qr,
    get_active_attendance_session,
)

from app.services.faculty_report_export_service import (
    build_faculty_attendance_excel,
    build_faculty_attendance_pdf,
)

from app.services.faculty_service import (
    get_faculty_attendance_report,
    get_faculty_classrooms,
    get_faculty_dashboard,
    get_faculty_profile,
    get_faculty_sections_for_semester,
    get_faculty_semesters,
    get_faculty_students,
    get_faculty_subjects_for_section,
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/faculty",
    tags=["Faculty"],
)


# ============================================================
# FACULTY PROFILE
# ============================================================

@router.get(
    "/profile",
    response_model=FacultyProfileResponse,
)
def faculty_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    faculty_profile_data = get_faculty_profile(
        db=db,
        current_user=current_user,
    )

    role_name = ""

    if current_user.role is not None:
        role_name = str(
            current_user.role.role_name
        )

    return {
        "user_id": current_user.user_id,
        "faculty_id": faculty_profile_data.faculty_id,
        "employee_id": faculty_profile_data.employee_id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "phone": current_user.phone,
        "role_name": role_name,
        "account_status": str(
            current_user.account_status
        ),
        "department": faculty_profile_data.department,
        "designation": faculty_profile_data.designation,
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at,
        "last_login_at": current_user.last_login_at,
    }


# ============================================================
# FACULTY DASHBOARD
# ============================================================

@router.get(
    "/dashboard",
    response_model=FacultyDashboardResponse,
)
def faculty_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Reconcile any timed-out ACTIVE session before building
    # dashboard statistics/current-session data.
    get_active_attendance_session(
        db=db,
        current_user=current_user,
    )

    return get_faculty_dashboard(
        db=db,
        current_user=current_user,
    )


# ============================================================
# FACULTY ATTENDANCE REPORT
# ============================================================

@router.get(
    "/attendance/report",
)
def faculty_attendance_report(
    semester_id: int | None = None,
    section_id: int | None = None,
    subject_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_faculty_attendance_report(
        db=db,
        current_user=current_user,
        semester_id=semester_id,
        section_id=section_id,
        subject_id=subject_id,
        date_from=date_from,
        date_to=date_to,
    )


# ============================================================
# FACULTY ATTENDANCE REPORT - EXCEL
# ============================================================

@router.get(
    "/attendance/report/excel",
)
def faculty_attendance_report_excel(
    semester_id: int | None = None,
    section_id: int | None = None,
    subject_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = get_faculty_attendance_report(
        db=db,
        current_user=current_user,
        semester_id=semester_id,
        section_id=section_id,
        subject_id=subject_id,
        date_from=date_from,
        date_to=date_to,
    )

    content = build_faculty_attendance_excel(
        report
    )

    return Response(
        content=content,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": (
                'attachment; filename="faculty_attendance_report.xlsx"'
            ),
        },
    )


# ============================================================
# FACULTY ATTENDANCE REPORT - PDF
# ============================================================

@router.get(
    "/attendance/report/pdf",
)
def faculty_attendance_report_pdf(
    semester_id: int | None = None,
    section_id: int | None = None,
    subject_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = get_faculty_attendance_report(
        db=db,
        current_user=current_user,
        semester_id=semester_id,
        section_id=section_id,
        subject_id=subject_id,
        date_from=date_from,
        date_to=date_to,
    )

    content = build_faculty_attendance_pdf(
        report
    )

    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                'attachment; filename="faculty_attendance_report.pdf"'
            ),
        },
    )


# ============================================================
# FACULTY SEMESTERS
# ============================================================

@router.get(
    "/semesters",
)
def faculty_semesters(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_faculty_semesters(
        db=db,
        current_user=current_user,
    )


# ============================================================
# FACULTY SECTIONS FOR SELECTED SEMESTER
# ============================================================

@router.get(
    "/sections",
)
def faculty_sections(
    semester_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_faculty_sections_for_semester(
        db=db,
        current_user=current_user,
        semester_id=semester_id,
    )


# ============================================================
# FACULTY SUBJECTS FOR SELECTED SEMESTER + SECTION
# ============================================================

@router.get(
    "/subjects",
)
def faculty_subjects(
    semester_id: int,
    section_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_faculty_subjects_for_section(
        db=db,
        current_user=current_user,
        semester_id=semester_id,
        section_id=section_id,
    )


# ============================================================
# FACULTY CLASSROOMS
# ============================================================

@router.get(
    "/classrooms",
)
def faculty_classrooms(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_faculty_classrooms(
        db=db,
        current_user=current_user,
    )


# ============================================================
# FACULTY STUDENTS
# ============================================================

@router.get(
    "/students",
)
def faculty_students(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_faculty_students(
        db=db,
        current_user=current_user,
    )


# ============================================================
# CURRENT ACTIVE ATTENDANCE SESSION
# ============================================================

@router.get(
    "/attendance/session/active",
)
def current_active_attendance_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_active_attendance_session(
        db=db,
        current_user=current_user,
    )


# ============================================================
# START ATTENDANCE SESSION
# ============================================================

@router.post(
    "/attendance/session",
    response_model=AttendanceSessionResponse,
    status_code=201,
)
def start_attendance_session(
    request: AttendanceSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return create_attendance_session(
        db=db,
        current_user=current_user,
        semester_id=request.semester_id,
        subject_id=request.subject_id,
        section_id=request.section_id,
        classroom_id=request.classroom_id,
        qr_validity_minutes=request.qr_validity_minutes,
        geofence_radius_meters=request.geofence_radius_meters,
    )


# ============================================================
# GENERATE ATTENDANCE QR
# ============================================================

@router.post(
    "/attendance/session/{session_id}/qr",
    response_model=AttendanceSessionQRResponse,
)
def attendance_session_qr(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return generate_attendance_session_qr(
        db=db,
        current_user=current_user,
        session_id=session_id,
    )


# ============================================================
# COMPLETE ATTENDANCE SESSION
# ============================================================

@router.post(
    "/attendance/session/{session_id}/complete",
)
def complete_attendance_session_endpoint(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return complete_attendance_session(
        db=db,
        current_user=current_user,
        session_id=session_id,
    )


# ============================================================
# CANCEL ATTENDANCE SESSION
# ============================================================

@router.post(
    "/attendance/session/{session_id}/cancel",
    response_model=AttendanceSessionCancelResponse,
)
def cancel_attendance_session_endpoint(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return cancel_attendance_session(
        db=db,
        current_user=current_user,
        session_id=session_id,
    )
