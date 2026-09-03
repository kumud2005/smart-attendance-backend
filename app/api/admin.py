"""
Admin Dashboard API
===================

Admin-only endpoints for:

    - Dashboard statistics
    - View all users
    - View pending users
    - View complete user details
    - Activate accounts
    - Suspend accounts
    - Deactivate accounts
    - Reactivate accounts
    - System-wide attendance reports
"""

from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.database import get_db

from app.core.dependencies import require_admin

from app.models.user import User

from app.schemas.admin import (
    AdminDashboardResponse,
    AdminUserListItem,
    AdminUserDetailResponse,
    AdminUserStatusResponse,
    AdminFacultyAssignmentCreate,
    AdminFacultyAssignmentItem,
    AdminFacultyAssignmentMutationResponse,
    AdminFacultyAssignmentOptionsResponse,
    AdminCreateAdminRequest,
    AdminCreateAdminResponse,
    AdminStudentRegistrationDecision,
    AdminStudentRegistrationReviewItem,
    AdminStudentRegistrationDecisionResponse,
    AdminFacultyRegistrationDecision,
    AdminFacultyRegistrationReviewItem,
    AdminFacultyRegistrationDecisionResponse,
    AdminStudentFaceStatusResponse,
    AdminStudentFaceDeleteResponse,
    AdminClassroomCreate,
    AdminClassroomUpdate,
    AdminClassroomItem,
    AdminClassroomMutationResponse,
)

from app.services.admin_report_export_service import (
    build_admin_attendance_excel,
    build_admin_attendance_pdf,
)

from app.services.admin_service import (
    get_dashboard_statistics,
    list_users,
    get_pending_users,
    get_user_details,
    change_account_status,
    get_admin_attendance_report,
    get_faculty_assignment_options,
    list_faculty_assignments,
    create_faculty_assignment,
    deactivate_faculty_assignment,
    create_admin_account,
    list_student_registration_requests,
    approve_student_registration,
    reject_student_registration,
    list_faculty_registration_requests,
    approve_faculty_registration,
    reject_faculty_registration,
    get_student_face_status_for_admin,
    delete_student_face_profile_for_admin,
    list_classrooms,
    create_classroom,
    update_classroom,
    set_classroom_active_status,
    delete_classroom,
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin Dashboard"],
)


# ============================================================
# DASHBOARD STATISTICS
# ============================================================

@router.get(
    "/dashboard",
    response_model=AdminDashboardResponse,
    summary="Get Admin Dashboard Statistics",
)
def dashboard(
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return get_dashboard_statistics(
        db=db
    )







# ============================================================
# CLASSROOM MANAGEMENT
# ============================================================

@router.get(
    "/classrooms",
    response_model=list[AdminClassroomItem],
    summary="List Classrooms",
)
def classrooms(
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return list_classrooms(
        db=db,
        active_only=active_only,
    )


@router.post(
    "/classrooms",
    response_model=AdminClassroomMutationResponse,
    status_code=201,
    summary="Create Classroom",
)
def add_classroom(
    request: AdminClassroomCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return create_classroom(
        db=db,
        data=request,
    )


@router.patch(
    "/classrooms/{classroom_id}",
    response_model=AdminClassroomMutationResponse,
    summary="Update Classroom",
)
def edit_classroom(
    classroom_id: int,
    request: AdminClassroomUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return update_classroom(
        db=db,
        classroom_id=classroom_id,
        data=request,
    )


@router.patch(
    "/classrooms/{classroom_id}/activate",
    response_model=AdminClassroomMutationResponse,
    summary="Activate Classroom",
)
def activate_classroom(
    classroom_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return set_classroom_active_status(
        db=db,
        classroom_id=classroom_id,
        is_active=True,
    )


@router.patch(
    "/classrooms/{classroom_id}/deactivate",
    response_model=AdminClassroomMutationResponse,
    summary="Deactivate Classroom",
)
def deactivate_classroom(
    classroom_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return set_classroom_active_status(
        db=db,
        classroom_id=classroom_id,
        is_active=False,
    )


@router.delete(
    "/classrooms/{classroom_id}",
    response_model=AdminClassroomMutationResponse,
    summary="Delete Unused Classroom",
)
def remove_classroom(
    classroom_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return delete_classroom(
        db=db,
        classroom_id=classroom_id,
    )


# ============================================================
# CREATE ANOTHER ADMIN
# ============================================================

@router.post(
    "/admins",
    response_model=AdminCreateAdminResponse,
    status_code=201,
    summary="Create Another Administrator Account",
)
def create_another_admin(
    request: AdminCreateAdminRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return create_admin_account(
        db=db,
        data=request,
    )


# ============================================================
# STUDENT PUBLIC REGISTRATION REQUESTS
# ============================================================

@router.get(
    "/student-registration-requests",
    response_model=list[AdminStudentRegistrationReviewItem],
    summary="Review Student Registration Requests",
)
def student_registration_requests(
    request_status: str = "PENDING",
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return list_student_registration_requests(
        db=db,
        request_status=request_status,
    )


@router.patch(
    "/student-registration-requests/{user_id}/approve",
    response_model=AdminStudentRegistrationDecisionResponse,
    summary="Approve Student Registration and Assign Section",
)
def approve_student_registration_request(
    user_id: int,
    request: AdminStudentRegistrationDecision,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return approve_student_registration(
        db=db,
        user_id=user_id,
        current_admin=current_admin,
        note=request.note,
    )


@router.patch(
    "/student-registration-requests/{user_id}/reject",
    response_model=AdminStudentRegistrationDecisionResponse,
    summary="Reject Student Registration",
)
def reject_student_registration_request(
    user_id: int,
    request: AdminStudentRegistrationDecision,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return reject_student_registration(
        db=db,
        user_id=user_id,
        current_admin=current_admin,
        note=request.note,
    )


# ============================================================
# FACULTY PUBLIC REGISTRATION REQUESTS
# ============================================================

@router.get(
    "/faculty-registration-requests",
    response_model=list[AdminFacultyRegistrationReviewItem],
    summary="Review Faculty Registration Requests",
)
def faculty_registration_requests(
    request_status: str = "PENDING",
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return list_faculty_registration_requests(
        db=db,
        request_status=request_status,
    )


@router.patch(
    "/faculty-registration-requests/{user_id}/approve",
    response_model=AdminFacultyRegistrationDecisionResponse,
    summary="Approve Faculty Registration and Requested Assignments",
)
def approve_faculty_registration_request(
    user_id: int,
    request: AdminFacultyRegistrationDecision,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return approve_faculty_registration(
        db=db,
        user_id=user_id,
        current_admin=current_admin,
        note=request.note,
    )


@router.patch(
    "/faculty-registration-requests/{user_id}/reject",
    response_model=AdminFacultyRegistrationDecisionResponse,
    summary="Reject Faculty Registration",
)
def reject_faculty_registration_request(
    user_id: int,
    request: AdminFacultyRegistrationDecision,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return reject_faculty_registration(
        db=db,
        user_id=user_id,
        current_admin=current_admin,
        note=request.note,
    )


# ============================================================
# STUDENT FACE PROFILE MANAGEMENT
# ============================================================

@router.get(
    "/students/{student_id}/face-profile",
    response_model=AdminStudentFaceStatusResponse,
    summary="Get Student Face Profile Status",
)
def student_face_profile_status(
    student_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return get_student_face_status_for_admin(
        db=db,
        student_id=student_id,
    )


@router.delete(
    "/students/{student_id}/face-profile",
    response_model=AdminStudentFaceDeleteResponse,
    summary="Delete or Reset Student Face Profile",
)
def delete_student_face_profile(
    student_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return delete_student_face_profile_for_admin(
        db=db,
        student_id=student_id,
    )


# ============================================================
# FACULTY ASSIGNMENT OPTIONS
# ============================================================

@router.get(
    "/faculty-assignments/options",
    response_model=AdminFacultyAssignmentOptionsResponse,
    summary="Get Faculty Assignment Form Options",
)
def faculty_assignment_options(
    semester_id: int | None = None,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return get_faculty_assignment_options(
        db=db,
        semester_id=semester_id,
    )


# ============================================================
# LIST FACULTY ASSIGNMENTS
# ============================================================

@router.get(
    "/faculty-assignments",
    response_model=list[AdminFacultyAssignmentItem],
    summary="List Faculty Academic Assignments",
)
def faculty_assignments(
    faculty_id: int | None = None,
    semester_id: int | None = None,
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return list_faculty_assignments(
        db=db,
        faculty_id=faculty_id,
        semester_id=semester_id,
        active_only=active_only,
    )


# ============================================================
# CREATE / REACTIVATE FACULTY ASSIGNMENT
# ============================================================

@router.post(
    "/faculty-assignments",
    response_model=AdminFacultyAssignmentMutationResponse,
    status_code=201,
    summary="Assign Semester, Section and Subject to Faculty",
)
def assign_faculty_academic_scope(
    request: AdminFacultyAssignmentCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return create_faculty_assignment(
        db=db,
        faculty_id=request.faculty_id,
        semester_id=request.semester_id,
        section_id=request.section_id,
        subject_id=request.subject_id,
    )


# ============================================================
# DEACTIVATE FACULTY ASSIGNMENT
# ============================================================

@router.patch(
    "/faculty-assignments/{assignment_id}/deactivate",
    response_model=AdminFacultyAssignmentMutationResponse,
    summary="Remove Faculty Academic Assignment",
)
def remove_faculty_academic_scope(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return deactivate_faculty_assignment(
        db=db,
        assignment_id=assignment_id,
    )


# ============================================================
# ADMIN ATTENDANCE REPORT
# ============================================================

@router.get(
    "/attendance/report",
    summary="Get System-wide Attendance Report",
)
def attendance_report(
    semester_id: int | None = None,
    section_id: int | None = None,
    subject_id: int | None = None,
    faculty_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return get_admin_attendance_report(
        db=db,
        semester_id=semester_id,
        section_id=section_id,
        subject_id=subject_id,
        faculty_id=faculty_id,
        date_from=date_from,
        date_to=date_to,
    )


# ============================================================
# ADMIN ATTENDANCE REPORT - EXCEL
# ============================================================

@router.get(
    "/attendance/report/excel",
    summary="Download System-wide Attendance Report as Excel",
)
def attendance_report_excel(
    semester_id: int | None = None,
    section_id: int | None = None,
    subject_id: int | None = None,
    faculty_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    report = get_admin_attendance_report(
        db=db,
        semester_id=semester_id,
        section_id=section_id,
        subject_id=subject_id,
        faculty_id=faculty_id,
        date_from=date_from,
        date_to=date_to,
    )

    content = build_admin_attendance_excel(
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
                'attachment; filename="admin_attendance_report.xlsx"'
            ),
        },
    )


# ============================================================
# ADMIN ATTENDANCE REPORT - PDF
# ============================================================

@router.get(
    "/attendance/report/pdf",
    summary="Download System-wide Attendance Report as PDF",
)
def attendance_report_pdf(
    semester_id: int | None = None,
    section_id: int | None = None,
    subject_id: int | None = None,
    faculty_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    report = get_admin_attendance_report(
        db=db,
        semester_id=semester_id,
        section_id=section_id,
        subject_id=subject_id,
        faculty_id=faculty_id,
        date_from=date_from,
        date_to=date_to,
    )

    content = build_admin_attendance_pdf(
        report
    )

    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                'attachment; filename="admin_attendance_report.pdf"'
            ),
        },
    )


# ============================================================
# ALL USERS
# ============================================================

@router.get(
    "/users",
    response_model=list[AdminUserListItem],
    summary="Get All Users",
)
def users(
    role_name: str | None = None,
    account_status: str | None = None,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return list_users(
        db=db,
        role_name=role_name,
        account_status=account_status,
    )


# ============================================================
# PENDING USERS
# ============================================================

@router.get(
    "/users/pending",
    response_model=list[AdminUserListItem],
    summary="Get Pending Users",
)
def pending_users(
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return get_pending_users(
        db=db
    )


# ============================================================
# USER DETAILS
# ============================================================

@router.get(
    "/users/{user_id}",
    response_model=AdminUserDetailResponse,
    summary="Get Complete User Details",
)
def user_details(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return get_user_details(
        db=db,
        user_id=user_id,
    )


# ============================================================
# ACTIVATE USER
# ============================================================

@router.patch(
    "/users/{user_id}/activate",
    response_model=AdminUserStatusResponse,
    summary="Activate User Account",
)
def activate(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return change_account_status(
        db=db,
        target_user_id=user_id,
        new_status="ACTIVE",
        current_admin=current_admin,
    )


# ============================================================
# SUSPEND USER
# ============================================================

@router.patch(
    "/users/{user_id}/suspend",
    response_model=AdminUserStatusResponse,
    summary="Suspend User Account",
)
def suspend(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return change_account_status(
        db=db,
        target_user_id=user_id,
        new_status="SUSPENDED",
        current_admin=current_admin,
    )


# ============================================================
# DEACTIVATE USER
# ============================================================

@router.patch(
    "/users/{user_id}/deactivate",
    response_model=AdminUserStatusResponse,
    summary="Deactivate User Account",
)
def deactivate(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return change_account_status(
        db=db,
        target_user_id=user_id,
        new_status="INACTIVE",
        current_admin=current_admin,
    )


# ============================================================
# REACTIVATE USER
# ============================================================

@router.patch(
    "/users/{user_id}/reactivate",
    response_model=AdminUserStatusResponse,
    summary="Reactivate User Account",
)
def reactivate(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return change_account_status(
        db=db,
        target_user_id=user_id,
        new_status="ACTIVE",
        current_admin=current_admin,
    )