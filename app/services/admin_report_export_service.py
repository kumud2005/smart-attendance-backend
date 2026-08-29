from __future__ import annotations

from html import escape
from io import BytesIO
from typing import Any

import xlsxwriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _safe(value: Any) -> str:
    return escape(_text(value), quote=False)


def _yes_no(value: Any) -> str:
    return "YES" if bool(value) else "NO"


def _percentage(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _result_explanation(row: dict) -> str:
    attendance = _text(
        row.get("attendance_status")
    ).upper()

    qr_status = _text(
        row.get("qr_status")
        or row.get("session_status")
    ).upper()

    rejection = _text(
        row.get("rejection_reason")
    ).strip()

    if qr_status == "CANCELLED":
        return (
            "QR/session was cancelled by faculty. "
            "This row is audit-only and does not reduce attendance."
        )

    if attendance == "PRESENT":
        return (
            "Attendance accepted after QR, geofence, face "
            "and liveness verification passed."
        )

    if attendance == "REJECTED":
        if rejection:
            return rejection

        if not bool(row.get("qr_verified")):
            return "Attendance rejected because QR verification failed."

        if not bool(row.get("geofence_verified")):
            return "Attendance rejected because geofence verification failed."

        if not bool(row.get("face_verified")):
            return "Attendance rejected because face verification failed."

        if not bool(row.get("liveness_verified")):
            return "Attendance rejected because liveness verification failed."

        return "Attendance attempt was rejected by the verification workflow."

    if attendance == "PENDING":
        if not bool(row.get("qr_verified")):
            return "Attendance verification is pending at the QR step."

        if not bool(row.get("geofence_verified")):
            return "QR passed; geofence verification is pending."

        if not bool(row.get("face_verified")):
            return "QR and geofence passed; face verification is pending."

        if not bool(row.get("liveness_verified")):
            return (
                "QR, geofence and face passed; "
                "liveness verification is pending."
            )

        return "Attendance verification is still in progress."

    if attendance == "NOT_MARKED":
        if qr_status == "COMPLETED":
            return (
                "QR/session completed before this student "
                "successfully marked attendance."
            )

        if qr_status == "ACTIVE":
            return (
                "QR/session is still active and attendance "
                "has not been marked yet."
            )

        return "No successful attendance attempt was recorded."

    return "Attendance result recorded by the system."


# ============================================================
# EXCEL
# ============================================================

def build_admin_attendance_excel(
    report: dict,
) -> bytes:
    output = BytesIO()

    workbook = xlsxwriter.Workbook(
        output,
        {
            "in_memory": True,
            "constant_memory": False,
        },
    )

    workbook.set_properties(
        {
            "title": "Admin Attendance Report",
            "subject": "Smart Anti-Proxy Attendance System",
            "author": "Smart Anti-Proxy Attendance System",
            "company": "Smart Anti-Proxy Attendance System",
        }
    )

    title_fmt = workbook.add_format(
        {
            "bold": True,
            "font_size": 16,
        }
    )
    section_fmt = workbook.add_format(
        {
            "bold": True,
            "bg_color": "#E9EEF7",
            "border": 1,
        }
    )
    label_fmt = workbook.add_format(
        {
            "bold": True,
            "bg_color": "#F5F7FB",
            "border": 1,
        }
    )
    value_fmt = workbook.add_format(
        {
            "border": 1,
        }
    )
    header_fmt = workbook.add_format(
        {
            "bold": True,
            "bg_color": "#19295C",
            "font_color": "#FFFFFF",
            "border": 1,
            "align": "center",
            "valign": "vcenter",
            "text_wrap": True,
        }
    )
    cell_fmt = workbook.add_format(
        {
            "border": 1,
            "valign": "top",
        }
    )
    wrap_fmt = workbook.add_format(
        {
            "border": 1,
            "valign": "top",
            "text_wrap": True,
        }
    )
    center_fmt = workbook.add_format(
        {
            "border": 1,
            "align": "center",
            "valign": "top",
        }
    )
    percent_fmt = workbook.add_format(
        {
            "border": 1,
            "num_format": "0.00%",
            "align": "center",
        }
    )

    status_green = workbook.add_format(
        {
            "border": 1,
            "bg_color": "#E8F5E9",
            "font_color": "#1B5E20",
            "align": "center",
        }
    )
    status_orange = workbook.add_format(
        {
            "border": 1,
            "bg_color": "#FFF8E1",
            "font_color": "#8D6E00",
            "align": "center",
        }
    )
    status_red = workbook.add_format(
        {
            "border": 1,
            "bg_color": "#FFEBEE",
            "font_color": "#B71C1C",
            "align": "center",
        }
    )
    status_grey = workbook.add_format(
        {
            "border": 1,
            "bg_color": "#ECEFF1",
            "font_color": "#37474F",
            "align": "center",
        }
    )

    def status_format(value: Any):
        status = _text(value).upper()

        if status in {"PRESENT", "COMPLETED"}:
            return status_green

        if status in {"PENDING", "ACTIVE"}:
            return status_orange

        if status in {"REJECTED", "CANCELLED"}:
            return status_red

        if status == "NOT_MARKED":
            return status_grey

        return center_fmt

    filters = report.get("filters") or {}
    summary = report.get("summary") or {}

    ws = workbook.add_worksheet("Summary")
    ws.hide_gridlines(2)
    ws.set_column("A:A", 30)
    ws.set_column("B:B", 32)
    ws.set_column("C:H", 16)

    ws.merge_range(
        "A1:H1",
        "Smart Anti-Proxy Attendance System - Admin Attendance Report",
        title_fmt,
    )

    row_index = 2

    ws.write(
        row_index,
        0,
        "Applied Filters",
        section_fmt,
    )
    ws.merge_range(
        row_index,
        1,
        row_index,
        7,
        "",
        section_fmt,
    )
    row_index += 1

    for label, value in (
        ("Semester ID", filters.get("semester_id")),
        ("Section ID", filters.get("section_id")),
        ("Subject ID", filters.get("subject_id")),
        ("Faculty ID", filters.get("faculty_id")),
        ("Date From", filters.get("date_from")),
        ("Date To", filters.get("date_to")),
    ):
        ws.write(
            row_index,
            0,
            label,
            label_fmt,
        )
        ws.write(
            row_index,
            1,
            _text(value)
            if value is not None
            else "All",
            value_fmt,
        )
        row_index += 1

    row_index += 1

    ws.write(
        row_index,
        0,
        "Summary",
        section_fmt,
    )
    ws.merge_range(
        row_index,
        1,
        row_index,
        7,
        "",
        section_fmt,
    )
    row_index += 1

    summary_rows = [
        ("Total Sessions", summary.get("total_sessions")),
        ("Active QR Sessions", summary.get("active_sessions")),
        ("Completed QR Sessions", summary.get("completed_sessions")),
        ("Cancelled QR Sessions", summary.get("cancelled_sessions")),
        ("Total Students", summary.get("total_students")),
        ("Total Faculty", summary.get("total_faculty")),
        (
            "Attendance Opportunities",
            summary.get("attendance_opportunities"),
        ),
        (
            "Attendance Records",
            summary.get("attendance_records"),
        ),
        ("Present", summary.get("present")),
        ("Pending", summary.get("pending")),
        ("Rejected", summary.get("rejected")),
        ("Not Marked", summary.get("not_marked")),
    ]

    for label, value in summary_rows:
        ws.write(
            row_index,
            0,
            label,
            label_fmt,
        )
        ws.write_number(
            row_index,
            1,
            float(value or 0),
            value_fmt,
        )
        row_index += 1

    ws.write(
        row_index,
        0,
        "Attendance Percentage",
        label_fmt,
    )
    ws.write_number(
        row_index,
        1,
        _percentage(
            summary.get("attendance_percentage")
        ) / 100.0,
        percent_fmt,
    )

    def write_table_sheet(
        name: str,
        rows: list[dict],
        columns: list[tuple[str, str]],
        widths: list[float],
        *,
        percent_keys: set[str] | None = None,
        status_keys: set[str] | None = None,
    ) -> None:
        sheet = workbook.add_worksheet(name)
        sheet.hide_gridlines(2)
        sheet.freeze_panes(1, 0)

        for col, width in enumerate(widths):
            sheet.set_column(
                col,
                col,
                width,
            )

        for col, (_, label) in enumerate(columns):
            sheet.write(
                0,
                col,
                label,
                header_fmt,
            )

        for row_number, row_data in enumerate(
            rows,
            start=1,
        ):
            for col, (key, _) in enumerate(columns):
                if key == "result_explanation":
                    value = _result_explanation(
                        row_data
                    )
                else:
                    value = row_data.get(key)

                if percent_keys and key in percent_keys:
                    sheet.write_number(
                        row_number,
                        col,
                        _percentage(value) / 100.0,
                        percent_fmt,
                    )
                    continue

                if status_keys and key in status_keys:
                    sheet.write(
                        row_number,
                        col,
                        _text(value),
                        status_format(value),
                    )
                    continue

                if isinstance(value, bool):
                    sheet.write(
                        row_number,
                        col,
                        _yes_no(value),
                        center_fmt,
                    )
                    continue

                if (
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                ):
                    sheet.write_number(
                        row_number,
                        col,
                        float(value),
                        cell_fmt,
                    )
                    continue

                sheet.write(
                    row_number,
                    col,
                    _text(value),
                    wrap_fmt,
                )

        if rows:
            sheet.autofilter(
                0,
                0,
                len(rows),
                len(columns) - 1,
            )

    metric_columns = [
        ("session_count", "Sessions"),
        ("student_count", "Students"),
        (
            "attendance_opportunities",
            "Opportunities",
        ),
        ("attendance_records", "Records"),
        ("present", "Present"),
        ("pending", "Pending"),
        ("rejected", "Rejected"),
        ("not_marked", "Not Marked"),
        (
            "attendance_percentage",
            "Attendance %",
        ),
    ]

    write_table_sheet(
        "Faculty Wise",
        report.get("faculty_wise") or [],
        [
            (
                "faculty_employee_id",
                "Employee ID",
            ),
            ("faculty_name", "Faculty"),
            (
                "faculty_department",
                "Department",
            ),
            (
                "faculty_designation",
                "Designation",
            ),
            *metric_columns,
        ],
        [
            16, 28, 22, 22,
            12, 12, 16, 12, 11, 11, 11, 14, 15,
        ],
        percent_keys={"attendance_percentage"},
    )

    write_table_sheet(
        "Subject Wise",
        report.get("subject_wise") or [],
        [
            ("subject_code", "Subject Code"),
            ("subject_name", "Subject Name"),
            *metric_columns,
        ],
        [
            16, 34,
            12, 12, 16, 12, 11, 11, 11, 14, 15,
        ],
        percent_keys={"attendance_percentage"},
    )

    write_table_sheet(
        "Section Wise",
        report.get("section_wise") or [],
        [
            ("semester_id", "Semester"),
            ("section_name", "Section"),
            *metric_columns,
        ],
        [
            14, 18,
            12, 12, 16, 12, 11, 11, 11, 14, 15,
        ],
        percent_keys={"attendance_percentage"},
    )

    write_table_sheet(
        "Day Wise",
        report.get("day_wise") or [],
        [
            ("date", "Date"),
            *metric_columns,
        ],
        [
            16,
            12, 12, 16, 12, 11, 11, 11, 14, 15,
        ],
        percent_keys={"attendance_percentage"},
    )

    write_table_sheet(
        "Session Wise",
        report.get("session_wise") or [],
        [
            ("date", "Date"),
            ("session_id", "Session ID"),
            ("faculty_name", "Faculty"),
            ("subject_code", "Subject Code"),
            ("subject_name", "Subject Name"),
            ("section_name", "Section"),
            ("qr_status", "QR Status"),
            (
                "attendance_opportunities",
                "Opportunities",
            ),
            ("expected_students", "Assigned Students"),
            ("attendance_records", "Records"),
            ("present", "Present"),
            ("pending", "Pending"),
            ("rejected", "Rejected"),
            ("not_marked", "Not Marked"),
            (
                "attendance_percentage",
                "Attendance %",
            ),
        ],
        [
            14, 12, 28, 15, 30, 16, 16,
            15, 16, 12, 11, 11, 11, 14, 15,
        ],
        percent_keys={"attendance_percentage"},
        status_keys={"qr_status"},
    )

    write_table_sheet(
        "Detailed Records",
        report.get("records") or [],
        [
            ("date", "Date"),
            ("session_id", "Session ID"),
            ("faculty_name", "Faculty"),
            (
                "faculty_employee_id",
                "Faculty Employee ID",
            ),
            ("subject_code", "Subject Code"),
            ("subject_name", "Subject"),
            ("semester_id", "Semester"),
            ("section_name", "Section"),
            ("student_name", "Student"),
            (
                "enrollment_number",
                "Enrollment Number",
            ),
            ("roll_number", "Roll Number"),
            ("qr_status", "QR Status"),
            (
                "attendance_status",
                "Attendance Status",
            ),
            ("qr_verified", "QR Verified"),
            (
                "geofence_verified",
                "Geofence Verified",
            ),
            ("face_verified", "Face Verified"),
            (
                "liveness_verified",
                "Liveness Verified",
            ),
            (
                "distance_from_classroom_meters",
                "Distance (m)",
            ),
            ("marked_at", "Marked At"),
            (
                "rejection_reason",
                "Rejection Reason",
            ),
            (
                "result_explanation",
                "Result Explanation",
            ),
        ],
        [
            14, 12, 26, 18, 15, 30, 12, 16, 26, 20, 14,
            16, 18, 12, 14, 12, 14, 14, 20, 34, 48,
        ],
        status_keys={
            "qr_status",
            "attendance_status",
        },
    )

    workbook.close()
    return output.getvalue()


# ============================================================
# PDF
# ============================================================

def _pdf_cell(
    value: Any,
    style: ParagraphStyle,
) -> Paragraph:
    return Paragraph(
        _safe(value),
        style,
    )


def _pdf_table_style(
    font_size: float = 6.5,
) -> TableStyle:
    return TableStyle(
        [
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP",
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.25,
                colors.grey,
            ),
            (
                "FONTNAME",
                (0, 0),
                (-1, -1),
                "Helvetica",
            ),
            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                font_size,
            ),
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#E9EEF7"),
            ),
            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Helvetica-Bold",
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                2,
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                2,
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                3,
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                3,
            ),
        ]
    )


def _group_table(
    rows: list[dict],
    columns: list[tuple[str, str]],
    widths: list[float],
    cell_style: ParagraphStyle,
) -> LongTable:
    data = [
        [
            _pdf_cell(
                label,
                cell_style,
            )
            for _, label in columns
        ]
    ]

    for row in rows:
        rendered = []

        for key, _ in columns:
            if key == "attendance_percentage":
                value = (
                    f"{_percentage(row.get(key)):.2f}%"
                )
            elif key == "result_explanation":
                value = _result_explanation(row)
            elif key in {
                "qr_verified",
                "geofence_verified",
                "face_verified",
                "liveness_verified",
            }:
                value = _yes_no(
                    row.get(key)
                )
            else:
                value = row.get(key)

            rendered.append(
                _pdf_cell(
                    value,
                    cell_style,
                )
            )

        data.append(rendered)

    table = LongTable(
        data,
        colWidths=widths,
        repeatRows=1,
        splitByRow=1,
    )
    table.setStyle(
        _pdf_table_style()
    )
    return table


def _page_number(
    canvas,
    document,
) -> None:
    canvas.saveState()
    canvas.setFont(
        "Helvetica",
        7,
    )
    canvas.setFillColor(
        colors.grey
    )
    canvas.drawRightString(
        landscape(A4)[0] - 10 * mm,
        6 * mm,
        f"Page {document.page}",
    )
    canvas.restoreState()


def build_admin_attendance_pdf(
    report: dict,
) -> bytes:
    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=8 * mm,
        leftMargin=8 * mm,
        topMargin=9 * mm,
        bottomMargin=12 * mm,
        title="Admin Attendance Report",
        author="Smart Anti-Proxy Attendance System",
    )

    styles = getSampleStyleSheet()

    title_style = styles["Title"]
    heading_style = styles["Heading2"]
    body_style = styles["BodyText"]

    cell_style = ParagraphStyle(
        "AdminReportCell",
        parent=body_style,
        fontName="Helvetica",
        fontSize=5.5,
        leading=6.8,
        spaceAfter=0,
        spaceBefore=0,
    )

    story = []

    filters = report.get("filters") or {}
    summary = report.get("summary") or {}

    story.append(
        Paragraph(
            (
                "Smart Anti-Proxy Attendance System "
                "- Admin Attendance Report"
            ),
            title_style,
        )
    )
    story.append(
        Spacer(
            1,
            4 * mm,
        )
    )

    filter_parts = []

    for key, label in (
        ("semester_id", "Semester"),
        ("section_id", "Section"),
        ("subject_id", "Subject"),
        ("faculty_id", "Faculty"),
        ("date_from", "Date From"),
        ("date_to", "Date To"),
    ):
        value = filters.get(key)

        if value is not None:
            filter_parts.append(
                f"{label}: {_safe(value)}"
            )

    story.append(
        Paragraph(
            "<b>Filters:</b> "
            + (
                " | ".join(filter_parts)
                if filter_parts
                else "None"
            ),
            body_style,
        )
    )
    story.append(
        Spacer(
            1,
            4 * mm,
        )
    )

    summary_data = [
        [
            _pdf_cell(
                "Metric",
                cell_style,
            ),
            _pdf_cell(
                "Value",
                cell_style,
            ),
        ]
    ]

    for label, key in (
        ("Total Sessions", "total_sessions"),
        ("Active QR Sessions", "active_sessions"),
        (
            "Completed QR Sessions",
            "completed_sessions",
        ),
        (
            "Cancelled QR Sessions",
            "cancelled_sessions",
        ),
        ("Total Students", "total_students"),
        ("Total Faculty", "total_faculty"),
        (
            "Attendance Opportunities",
            "attendance_opportunities",
        ),
        (
            "Attendance Records",
            "attendance_records",
        ),
        ("Present", "present"),
        ("Pending", "pending"),
        ("Rejected", "rejected"),
        ("Not Marked", "not_marked"),
    ):
        summary_data.append(
            [
                _pdf_cell(
                    label,
                    cell_style,
                ),
                _pdf_cell(
                    summary.get(key),
                    cell_style,
                ),
            ]
        )

    summary_data.append(
        [
            _pdf_cell(
                "Attendance %",
                cell_style,
            ),
            _pdf_cell(
                (
                    f"{_percentage(summary.get('attendance_percentage')):.2f}%"
                ),
                cell_style,
            ),
        ]
    )

    summary_table = Table(
        summary_data,
        colWidths=[
            60 * mm,
            42 * mm,
        ],
        repeatRows=1,
    )
    summary_table.setStyle(
        _pdf_table_style(
            font_size=7,
        )
    )

    story.append(
        Paragraph(
            "Summary",
            heading_style,
        )
    )
    story.append(summary_table)

    def add_section(
        title: str,
        table,
    ) -> None:
        story.append(PageBreak())
        story.append(
            Paragraph(
                title,
                heading_style,
            )
        )
        story.append(
            Spacer(
                1,
                2 * mm,
            )
        )
        story.append(table)

    faculty_rows = report.get(
        "faculty_wise"
    ) or []

    if faculty_rows:
        add_section(
            "Faculty-wise Attendance",
            _group_table(
                faculty_rows,
                [
                    (
                        "faculty_employee_id",
                        "Employee",
                    ),
                    (
                        "faculty_name",
                        "Faculty",
                    ),
                    (
                        "session_count",
                        "Sessions",
                    ),
                    (
                        "student_count",
                        "Students",
                    ),
                    (
                        "attendance_opportunities",
                        "Opportunities",
                    ),
                    (
                        "attendance_records",
                        "Records",
                    ),
                    ("present", "Present"),
                    ("pending", "Pending"),
                    ("rejected", "Rejected"),
                    (
                        "not_marked",
                        "Not Marked",
                    ),
                    (
                        "attendance_percentage",
                        "Attendance %",
                    ),
                ],
                [
                    18 * mm,
                    42 * mm,
                    17 * mm,
                    17 * mm,
                    23 * mm,
                    19 * mm,
                    17 * mm,
                    17 * mm,
                    17 * mm,
                    21 * mm,
                    23 * mm,
                ],
                cell_style,
            ),
        )

    session_rows = report.get(
        "session_wise"
    ) or []

    if session_rows:
        add_section(
            "Session-wise Attendance",
            _group_table(
                session_rows,
                [
                    ("date", "Date"),
                    (
                        "session_id",
                        "Session",
                    ),
                    (
                        "faculty_name",
                        "Faculty",
                    ),
                    (
                        "subject_code",
                        "Subject",
                    ),
                    (
                        "section_name",
                        "Section",
                    ),
                    (
                        "qr_status",
                        "QR Status",
                    ),
                    (
                        "attendance_opportunities",
                        "Opportunities",
                    ),
                    (
                        "attendance_records",
                        "Records",
                    ),
                    (
                        "present",
                        "Present",
                    ),
                    (
                        "pending",
                        "Pending",
                    ),
                    (
                        "rejected",
                        "Rejected",
                    ),
                    (
                        "not_marked",
                        "Not Marked",
                    ),
                    (
                        "attendance_percentage",
                        "Attendance %",
                    ),
                ],
                [
                    19 * mm,
                    14 * mm,
                    38 * mm,
                    18 * mm,
                    18 * mm,
                    20 * mm,
                    23 * mm,
                    18 * mm,
                    15 * mm,
                    15 * mm,
                    15 * mm,
                    20 * mm,
                    22 * mm,
                ],
                cell_style,
            ),
        )

    records = report.get(
        "records"
    ) or []

    if records:
        add_section(
            "Detailed Attendance Records",
            _group_table(
                records,
                [
                    ("date", "Date"),
                    (
                        "session_id",
                        "Session",
                    ),
                    (
                        "faculty_name",
                        "Faculty",
                    ),
                    (
                        "subject_code",
                        "Subject",
                    ),
                    (
                        "section_name",
                        "Section",
                    ),
                    (
                        "roll_number",
                        "Roll",
                    ),
                    (
                        "student_name",
                        "Student",
                    ),
                    (
                        "qr_status",
                        "QR Status",
                    ),
                    (
                        "attendance_status",
                        "Attendance",
                    ),
                    (
                        "qr_verified",
                        "QR Verified",
                    ),
                    (
                        "geofence_verified",
                        "Geo",
                    ),
                    (
                        "face_verified",
                        "Face",
                    ),
                    (
                        "liveness_verified",
                        "Live",
                    ),
                    (
                        "rejection_reason",
                        "Rejection",
                    ),
                    (
                        "result_explanation",
                        "Explanation",
                    ),
                ],
                [
                    17 * mm,
                    12 * mm,
                    28 * mm,
                    16 * mm,
                    15 * mm,
                    13 * mm,
                    31 * mm,
                    18 * mm,
                    19 * mm,
                    15 * mm,
                    12 * mm,
                    12 * mm,
                    12 * mm,
                    35 * mm,
                    48 * mm,
                ],
                cell_style,
            ),
        )

    document.build(
        story,
        onFirstPage=_page_number,
        onLaterPages=_page_number,
    )

    return buffer.getvalue()