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
    AdminProgramCreate,
    AdminProgramUpdate,
    AdminProgramItem,
    AdminProgramMutationResponse,
    AdminBranchCreate,
    AdminBranchUpdate,
    AdminBranchItem,
    AdminBranchMutationResponse,
    AdminSubjectCreate,
    AdminSubjectUpdate,
    AdminSubjectItem,
    AdminSubjectMutationResponse,
    AdminSubjectOptionsResponse,
    AdminSubjectImportRequest,
    AdminSubjectImportResponse,
    AdminFacultyAssignmentCreate,
    AdminFacultyAssignmentSectionCreate,
    AdminFacultyAssignmentSectionResponse,
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

from app.services.subject_catalog_export_service import (
    build_subject_catalog_csv,
    build_subject_catalog_excel,
    build_subject_catalog_pdf,
    filter_subject_export_rows,
)

from app.services.admin_service import (
    get_dashboard_statistics,
    list_users,
    get_pending_users,
    get_user_details,
    change_account_status,
    get_admin_attendance_report,
    list_programs,
    create_program,
    update_program,
    set_program_active_status,
    delete_program,
    list_branches,
    create_branch,
    update_branch,
    set_branch_active_status,
    delete_branch,
    get_subject_management_options,
    list_subjects,
    create_subject,
    update_subject,
    set_subject_active_status,
    delete_subject,
    import_subject_catalog,
    get_faculty_assignment_options,
    list_faculty_assignments,
    create_faculty_assignment,
    create_faculty_assignment_section,
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
# ACADEMIC PROGRAM MANAGEMENT
# ============================================================

@router.get("/programs", response_model=list[AdminProgramItem], summary="List Academic Programs")
def academic_programs(
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return list_programs(db=db, active_only=active_only)


@router.post("/programs", response_model=AdminProgramMutationResponse, status_code=201, summary="Create Academic Program")
def add_academic_program(
    request: AdminProgramCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return create_program(
        db=db,
        program_code=request.program_code,
        program_name=request.program_name,
        description=request.description,
        default_semesters=request.default_semesters,
    )



@router.patch(
    "/programs/{program_id}",
    response_model=AdminProgramMutationResponse,
    summary="Edit Academic Program",
)
def edit_academic_program(
    program_id: int,
    request: AdminProgramUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return update_program(
        db=db,
        program_id=program_id,
        program_code=request.program_code,
        program_name=request.program_name,
        description=request.description,
        default_semesters=request.default_semesters,
    )


@router.patch("/programs/{program_id}/activate", response_model=AdminProgramMutationResponse, summary="Activate Academic Program")
def activate_academic_program(program_id: int, db: Session = Depends(get_db), current_admin: User = Depends(require_admin)):
    return set_program_active_status(db=db, program_id=program_id, is_active=True)


@router.patch("/programs/{program_id}/deactivate", response_model=AdminProgramMutationResponse, summary="Deactivate Academic Program")
def deactivate_academic_program(program_id: int, db: Session = Depends(get_db), current_admin: User = Depends(require_admin)):
    return set_program_active_status(db=db, program_id=program_id, is_active=False)


@router.delete("/programs/{program_id}", response_model=AdminProgramMutationResponse, summary="Safely Delete Unused Academic Program")
def remove_academic_program(program_id: int, db: Session = Depends(get_db), current_admin: User = Depends(require_admin)):
    return delete_program(db=db, program_id=program_id)


# ============================================================
# COURSE / BRANCH MANAGEMENT
# ============================================================

@router.get("/branches", response_model=list[AdminBranchItem], summary="List Courses / Branches")
def academic_branches(
    program_id: int | None = None,
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return list_branches(db=db, program_id=program_id, active_only=active_only)


@router.post("/branches", response_model=AdminBranchMutationResponse, status_code=201, summary="Create Course / Branch")
def add_academic_branch(
    request: AdminBranchCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return create_branch(
        db=db,
        program_id=request.program_id,
        branch_code=request.branch_code,
        branch_name=request.branch_name,
        total_semesters=request.total_semesters,
    )



@router.patch(
    "/branches/{branch_id}",
    response_model=AdminBranchMutationResponse,
    summary="Edit Course / Branch",
)
def edit_academic_branch(
    branch_id: int,
    request: AdminBranchUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return update_branch(
        db=db,
        branch_id=branch_id,
        program_id=request.program_id,
        branch_code=request.branch_code,
        branch_name=request.branch_name,
        total_semesters=request.total_semesters,
    )


@router.patch("/branches/{branch_id}/activate", response_model=AdminBranchMutationResponse, summary="Activate Course / Branch")
def activate_academic_branch(branch_id: int, db: Session = Depends(get_db), current_admin: User = Depends(require_admin)):
    return set_branch_active_status(db=db, branch_id=branch_id, is_active=True)


@router.patch("/branches/{branch_id}/deactivate", response_model=AdminBranchMutationResponse, summary="Deactivate Course / Branch")
def deactivate_academic_branch(branch_id: int, db: Session = Depends(get_db), current_admin: User = Depends(require_admin)):
    return set_branch_active_status(db=db, branch_id=branch_id, is_active=False)


@router.delete("/branches/{branch_id}", response_model=AdminBranchMutationResponse, summary="Safely Delete Unused Course / Branch")
def remove_academic_branch(branch_id: int, db: Session = Depends(get_db), current_admin: User = Depends(require_admin)):
    return delete_branch(db=db, branch_id=branch_id)


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
# ACADEMIC SUBJECT MANAGEMENT
# ============================================================

@router.get(
    "/subjects/options",
    response_model=AdminSubjectOptionsResponse,
    summary="Get Subject Management Form Options",
)
def subject_management_options(
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return get_subject_management_options(db=db)


@router.post(
    "/subjects/import",
    response_model=AdminSubjectImportResponse,
    summary="Preview or Import Subjects from CSV, XLSX or PDF",
)
def import_subjects_from_file(
    request: AdminSubjectImportRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return import_subject_catalog(
        db=db,
        file_name=request.file_name,
        content_base64=request.content_base64,
        dry_run=request.dry_run,
    )



def _subject_export_scope_label(
    *,
    program_id: int | None,
    branch_id: int | None,
    semester_id: int | None,
    status_filter: str,
    search: str | None,
) -> str:
    parts: list[str] = []

    if program_id is not None:
        parts.append(f"Program ID {program_id}")

    if branch_id is not None:
        parts.append(f"Branch ID {branch_id}")

    if semester_id is not None:
        parts.append(f"Semester ID {semester_id}")

    if status_filter and status_filter.upper() != "ALL":
        parts.append(status_filter.upper())

    if search and search.strip():
        parts.append(f'Search: "{search.strip()}"')

    return " • ".join(parts) if parts else "All Subjects"


def _subject_export_rows(
    *,
    db: Session,
    program_id: int | None,
    branch_id: int | None,
    semester_id: int | None,
    status_filter: str,
    search: str | None,
) -> list[dict]:
    rows = list_subjects(
        db=db,
        program_id=program_id,
        branch_id=branch_id,
        semester_id=semester_id,
        active_only=False,
    )

    return filter_subject_export_rows(
        rows,
        status_filter=status_filter,
        search=search,
    )


@router.get(
    "/subjects/export/csv",
    summary="Export Subject Catalog as CSV",
)
def export_subjects_csv(
    program_id: int | None = None,
    branch_id: int | None = None,
    semester_id: int | None = None,
    status_filter: str = "ALL",
    search: str | None = None,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    rows = _subject_export_rows(
        db=db,
        program_id=program_id,
        branch_id=branch_id,
        semester_id=semester_id,
        status_filter=status_filter,
        search=search,
    )

    return Response(
        content=build_subject_catalog_csv(rows),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                'attachment; filename="subject_catalog.csv"'
            ),
        },
    )


@router.get(
    "/subjects/export/excel",
    summary="Export Subject Catalog as Excel",
)
def export_subjects_excel(
    program_id: int | None = None,
    branch_id: int | None = None,
    semester_id: int | None = None,
    status_filter: str = "ALL",
    search: str | None = None,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    rows = _subject_export_rows(
        db=db,
        program_id=program_id,
        branch_id=branch_id,
        semester_id=semester_id,
        status_filter=status_filter,
        search=search,
    )

    return Response(
        content=build_subject_catalog_excel(rows),
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": (
                'attachment; filename="subject_catalog.xlsx"'
            ),
        },
    )


@router.get(
    "/subjects/export/pdf",
    summary="Export Subject Catalog as PDF",
)
def export_subjects_pdf(
    program_id: int | None = None,
    branch_id: int | None = None,
    semester_id: int | None = None,
    status_filter: str = "ALL",
    search: str | None = None,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    rows = _subject_export_rows(
        db=db,
        program_id=program_id,
        branch_id=branch_id,
        semester_id=semester_id,
        status_filter=status_filter,
        search=search,
    )

    scope_label = _subject_export_scope_label(
        program_id=program_id,
        branch_id=branch_id,
        semester_id=semester_id,
        status_filter=status_filter,
        search=search,
    )

    return Response(
        content=build_subject_catalog_pdf(
            rows,
            scope_label=scope_label,
        ),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                'attachment; filename="subject_catalog.pdf"'
            ),
        },
    )


@router.get(
    "/subjects",
    response_model=list[AdminSubjectItem],
    summary="List Subjects by Academic Scope",
)
def subjects(
    program_id: int | None = None,
    branch_id: int | None = None,
    semester_id: int | None = None,
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return list_subjects(
        db=db,
        program_id=program_id,
        branch_id=branch_id,
        semester_id=semester_id,
        active_only=active_only,
    )


@router.post(
    "/subjects",
    response_model=AdminSubjectMutationResponse,
    status_code=201,
    summary="Add Subject to Program, Branch and Semester",
)
def add_subject(
    request: AdminSubjectCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return create_subject(
        db=db,
        program_id=request.program_id,
        branch_id=request.branch_id,
        semester_id=request.semester_id,
        subject_code=request.subject_code,
        subject_name=request.subject_name,
        credits=request.credits,
    )



@router.patch(
    "/subjects/{subject_id}",
    response_model=AdminSubjectMutationResponse,
    summary="Edit Subject Details",
)
def edit_subject(
    subject_id: int,
    request: AdminSubjectUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return update_subject(
        db=db,
        subject_id=subject_id,
        program_id=request.program_id,
        branch_id=request.branch_id,
        semester_id=request.semester_id,
        subject_code=request.subject_code,
        subject_name=request.subject_name,
        credits=request.credits,
    )


@router.patch(
    "/subjects/{subject_id}/activate",
    response_model=AdminSubjectMutationResponse,
    summary="Activate Subject",
)
def activate_subject(
    subject_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return set_subject_active_status(
        db=db,
        subject_id=subject_id,
        is_active=True,
    )


@router.patch(
    "/subjects/{subject_id}/deactivate",
    response_model=AdminSubjectMutationResponse,
    summary="Deactivate Subject",
)
def deactivate_subject(
    subject_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return set_subject_active_status(
        db=db,
        subject_id=subject_id,
        is_active=False,
    )


@router.delete(
    "/subjects/{subject_id}",
    response_model=AdminSubjectMutationResponse,
    summary="Safely Delete Unused Subject",
)
def remove_subject(
    subject_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return delete_subject(
        db=db,
        subject_id=subject_id,
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
# ADD ANOTHER SECTION FOR AN EXISTING ACADEMIC SCOPE
# ============================================================

@router.post(
    "/faculty-assignments/sections",
    response_model=AdminFacultyAssignmentSectionResponse,
    status_code=201,
    summary="Add Section for Faculty Assignment Scope",
)
def add_faculty_assignment_section(
    request: AdminFacultyAssignmentSectionCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return create_faculty_assignment_section(
        db=db,
        source_section_id=request.source_section_id,
        section_name=request.section_name,
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
# ACTIVATE FACULTY ASSIGNMENT
# ============================================================

@router.patch(
    "/faculty-assignments/{assignment_id}/activate",
    response_model=AdminFacultyAssignmentMutationResponse,
    summary="Activate Faculty Academic Assignment",
)
def activate_faculty_academic_scope(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return activate_faculty_assignment(
        db=db,
        assignment_id=assignment_id,
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
# DELETE UNUSED FACULTY ASSIGNMENT
# ============================================================

@router.delete(
    "/faculty-assignments/{assignment_id}",
    response_model=AdminFacultyAssignmentMutationResponse,
    summary="Safely Delete Unused Faculty Assignment",
)
def delete_faculty_academic_scope(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return delete_faculty_assignment(
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