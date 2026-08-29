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