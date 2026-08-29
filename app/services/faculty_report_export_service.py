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


# ============================================================
# COMMON HELPERS
# ============================================================

def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _yes_no(value: Any) -> str:
    return "YES" if bool(value) else "NO"


def _percentage(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _excel_bool(value: Any) -> str:
    return "Yes" if bool(value) else "No"


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

        return "Attendance attempt was rejected."

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
# EXCEL EXPORT
# ============================================================

def build_faculty_attendance_excel(
    report: dict,
) -> bytes:
    """
    Build a formatted .xlsx workbook for the authenticated faculty
    attendance report.

    Sheets:
        Summary
        Subject Wise
        Section Wise
        Day Wise
        Session Wise
        Detailed Records
    """

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
            "title": "Faculty Attendance Report",
            "subject": "Smart Attendance System",
            "author": "Smart Attendance System",
            "company": "Smart Attendance System",
        }
    )

    title_fmt = workbook.add_format(
        {
            "bold": True,
            "font_size": 16,
            "align": "left",
            "valign": "vcenter",
        }
    )

    section_fmt = workbook.add_format(
        {
            "bold": True,
            "font_size": 12,
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

    date_fmt = workbook.add_format(
        {
            "border": 1,
            "num_format": "yyyy-mm-dd",
            "align": "center",
        }
    )

    datetime_fmt = workbook.add_format(
        {
            "border": 1,
            "num_format": "yyyy-mm-dd hh:mm",
        }
    )

    status_present_fmt = workbook.add_format(
        {
            "border": 1,
            "bg_color": "#E8F5E9",
            "font_color": "#1B5E20",
            "align": "center",
        }
    )

    status_pending_fmt = workbook.add_format(
        {
            "border": 1,
            "bg_color": "#FFF8E1",
            "font_color": "#8D6E00",
            "align": "center",
        }
    )

    status_rejected_fmt = workbook.add_format(
        {
            "border": 1,
            "bg_color": "#FFEBEE",
            "font_color": "#B71C1C",
            "align": "center",
        }
    )

    status_not_marked_fmt = workbook.add_format(
        {
            "border": 1,
            "bg_color": "#ECEFF1",
            "font_color": "#37474F",
            "align": "center",
        }
    )

    def _status_format(status: Any):
        value = _text(status).upper()
        if value == "PRESENT":
            return status_present_fmt
        if value == "PENDING":
            return status_pending_fmt
        if value == "REJECTED":
            return status_rejected_fmt
        if value == "NOT_MARKED":
            return status_not_marked_fmt
        return center_fmt

    faculty = report.get("faculty") or {}
    filters = report.get("filters") or {}
    summary = report.get("summary") or {}

    # --------------------------------------------------------
    # SUMMARY SHEET
    # --------------------------------------------------------

    ws = workbook.add_worksheet("Summary")
    ws.hide_gridlines(2)
    ws.set_column("A:A", 28)
    ws.set_column("B:B", 32)
    ws.set_column("C:H", 16)

    ws.merge_range(
        "A1:H1",
        "Smart Attendance System - Faculty Attendance Report",
        title_fmt,
    )

    row = 2
    ws.write(row, 0, "Faculty Information", section_fmt)
    ws.merge_range(row, 1, row, 7, "", section_fmt)
    row += 1

    for label, value in (
        ("Faculty", faculty.get("full_name")),
        ("Employee ID", faculty.get("employee_id")),
        ("Department", faculty.get("department")),
        ("Designation", faculty.get("designation")),
    ):
        ws.write(row, 0, label, label_fmt)
        ws.write(row, 1, _text(value), value_fmt)
        row += 1

    row += 1
    ws.write(row, 0, "Applied Filters", section_fmt)
    ws.merge_range(row, 1, row, 7, "", section_fmt)
    row += 1

    for label, value in (
        ("Semester ID", filters.get("semester_id")),
        ("Section ID", filters.get("section_id")),
        ("Subject ID", filters.get("subject_id")),
        ("Date From", filters.get("date_from")),
        ("Date To", filters.get("date_to")),
    ):
        ws.write(row, 0, label, label_fmt)
        ws.write(row, 1, _text(value) if value is not None else "All", value_fmt)
        row += 1

    row += 1
    ws.write(row, 0, "Summary", section_fmt)
    ws.merge_range(row, 1, row, 7, "", section_fmt)
    row += 1

    summary_rows = [
        ("Total Sessions", summary.get("total_sessions")),
        ("Total Students", summary.get("total_students")),
        ("Active QR Sessions", summary.get("active_sessions")),
        ("Completed QR Sessions", summary.get("completed_sessions")),
        ("Cancelled QR Sessions", summary.get("cancelled_sessions")),
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
        ws.write(row, 0, label, label_fmt)
        ws.write_number(
            row,
            1,
            float(value or 0),
            value_fmt,
        )
        row += 1

    ws.write(row, 0, "Attendance Percentage", label_fmt)
    ws.write_number(
        row,
        1,
        _percentage(summary.get("attendance_percentage")) / 100.0,
        percent_fmt,
    )

    # --------------------------------------------------------
    # REUSABLE TABLE WRITER
    # --------------------------------------------------------

    def write_table_sheet(
        sheet_name: str,
        rows: list[dict],
        columns: list[tuple[str, str]],
        widths: list[float],
        *,
        percent_keys: set[str] | None = None,
        status_key: str | None = None,
    ) -> None:
        sheet = workbook.add_worksheet(sheet_name)
        sheet.hide_gridlines(2)
        sheet.freeze_panes(1, 0)

        for col_index, width in enumerate(widths):
            sheet.set_column(col_index, col_index, width)

        for col_index, (_, label) in enumerate(columns):
            sheet.write(0, col_index, label, header_fmt)

        for row_index, row_data in enumerate(rows, start=1):
            for col_index, (key, _) in enumerate(columns):
                if key == "result_explanation":
                    value = _result_explanation(row_data)
                else:
                    value = row_data.get(key)

                if percent_keys and key in percent_keys:
                    sheet.write_number(
                        row_index,
                        col_index,
                        _percentage(value) / 100.0,
                        percent_fmt,
                    )
                    continue

                if status_key and key == status_key:
                    sheet.write(
                        row_index,
                        col_index,
                        _text(value),
                        _status_format(value),
                    )
                    continue

                if isinstance(value, bool):
                    sheet.write(
                        row_index,
                        col_index,
                        _excel_bool(value),
                        center_fmt,
                    )
                    continue

                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    sheet.write_number(
                        row_index,
                        col_index,
                        float(value),
                        cell_fmt,
                    )
                    continue

                sheet.write(
                    row_index,
                    col_index,
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

    write_table_sheet(
        "Subject Wise",
        report.get("subject_wise") or [],
        [
            ("subject_code", "Subject Code"),
            ("subject_name", "Subject Name"),
            ("session_count", "Sessions"),
            ("attendance_opportunities", "Opportunities"),
            ("attendance_records", "Records"),
            ("present", "Present"),
            ("pending", "Pending"),
            ("rejected", "Rejected"),
            ("not_marked", "Not Marked"),
            ("attendance_percentage", "Attendance %"),
        ],
        [16, 34, 12, 16, 13, 11, 11, 11, 14, 15],
        percent_keys={"attendance_percentage"},
    )

    write_table_sheet(
        "Section Wise",
        report.get("section_wise") or [],
        [
            ("semester_id", "Semester ID"),
            ("section_name", "Section"),
            ("session_count", "Sessions"),
            ("attendance_opportunities", "Opportunities"),
            ("attendance_records", "Records"),
            ("present", "Present"),
            ("pending", "Pending"),
            ("rejected", "Rejected"),
            ("not_marked", "Not Marked"),
            ("attendance_percentage", "Attendance %"),
        ],
        [14, 20, 12, 16, 13, 11, 11, 11, 14, 15],
        percent_keys={"attendance_percentage"},
    )

    write_table_sheet(
        "Day Wise",
        report.get("day_wise") or [],
        [
            ("date", "Date"),
            ("session_count", "Sessions"),
            ("attendance_opportunities", "Opportunities"),
            ("attendance_records", "Records"),
            ("present", "Present"),
            ("pending", "Pending"),
            ("rejected", "Rejected"),
            ("not_marked", "Not Marked"),
            ("attendance_percentage", "Attendance %"),
        ],
        [14, 12, 16, 13, 11, 11, 11, 14, 15],
        percent_keys={"attendance_percentage"},
    )

    write_table_sheet(
        "Session Wise",
        report.get("session_wise") or [],
        [
            ("date", "Date"),
            ("session_id", "Session ID"),
            ("subject_code", "Subject Code"),
            ("subject_name", "Subject Name"),
            ("section_name", "Section"),
            ("qr_status", "QR Status"),
            ("expected_students", "Expected"),
            ("attendance_records", "Records"),
            ("present", "Present"),
            ("pending", "Pending"),
            ("rejected", "Rejected"),
            ("not_marked", "Not Marked"),
            ("attendance_percentage", "Attendance %"),
        ],
        [14, 12, 15, 32, 16, 16, 12, 12, 11, 11, 11, 14, 15],
        percent_keys={"attendance_percentage"},
    )

    detailed_rows = report.get("records") or []
    detailed_columns = [
        ("date", "Date"),
        ("session_id", "Session ID"),
        ("semester_id", "Semester ID"),
        ("subject_code", "Subject Code"),
        ("subject_name", "Subject Name"),
        ("section_name", "Section"),
        ("student_id", "Student ID"),
        ("enrollment_number", "Enrollment Number"),
        ("roll_number", "Roll Number"),
        ("student_name", "Student Name"),
        ("student_email", "Student Email"),
        ("qr_status", "QR Status"),
        ("attendance_status", "Attendance Status"),
        ("qr_verified", "QR Verified"),
        ("geofence_verified", "Geofence Verified"),
        ("face_verified", "Face Verified"),
        ("liveness_verified", "Liveness Verified"),
        ("marked_at", "Marked At"),
        (
            "distance_from_classroom_meters",
            "Distance From Classroom (m)",
        ),
        ("rejection_reason", "Rejection Reason"),
        ("result_explanation", "Result Explanation"),
    ]

    write_table_sheet(
        "Detailed Records",
        detailed_rows,
        detailed_columns,
        [
            14, 12, 12, 15, 30, 16, 12, 18, 14, 26,
            30, 16, 18, 12, 14, 12, 14, 20, 18, 34, 48,
        ],
        status_key="attendance_status",
    )

    workbook.close()
    return output.getvalue()


# ============================================================
# PDF EXPORT
# ============================================================

def _safe(value: Any) -> str:
    return escape(_text(value), quote=False)


def _pdf_table_style(
    *,
    header: bool = True,
    font_size: float = 7,
) -> TableStyle:
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]

    if header:
        commands.extend(
            [
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
            ]
        )

    return TableStyle(commands)


def _pdf_cell(
    value: Any,
    style: ParagraphStyle,
) -> Paragraph:
    return Paragraph(
        _safe(value),
        style,
    )


def _summary_table(
    summary: dict,
    cell_style: ParagraphStyle,
) -> Table:
    data = [
        [
            _pdf_cell("Metric", cell_style),
            _pdf_cell("Value", cell_style),
        ],
        [
            _pdf_cell("Total Sessions", cell_style),
            _pdf_cell(summary.get("total_sessions"), cell_style),
        ],
        [
            _pdf_cell("Total Students", cell_style),
            _pdf_cell(summary.get("total_students"), cell_style),
        ],
        [
            _pdf_cell("Active QR Sessions", cell_style),
            _pdf_cell(summary.get("active_sessions"), cell_style),
        ],
        [
            _pdf_cell("Completed QR Sessions", cell_style),
            _pdf_cell(summary.get("completed_sessions"), cell_style),
        ],
        [
            _pdf_cell("Cancelled QR Sessions", cell_style),
            _pdf_cell(summary.get("cancelled_sessions"), cell_style),
        ],
        [
            _pdf_cell("Attendance Opportunities", cell_style),
            _pdf_cell(
                summary.get("attendance_opportunities"),
                cell_style,
            ),
        ],
        [
            _pdf_cell("Attendance Records", cell_style),
            _pdf_cell(
                summary.get("attendance_records"),
                cell_style,
            ),
        ],
        [
            _pdf_cell("Present", cell_style),
            _pdf_cell(summary.get("present"), cell_style),
        ],
        [
            _pdf_cell("Pending", cell_style),
            _pdf_cell(summary.get("pending"), cell_style),
        ],
        [
            _pdf_cell("Rejected", cell_style),
            _pdf_cell(summary.get("rejected"), cell_style),
        ],
        [
            _pdf_cell("Not Marked", cell_style),
            _pdf_cell(summary.get("not_marked"), cell_style),
        ],
        [
            _pdf_cell("Attendance %", cell_style),
            _pdf_cell(
                f"{_percentage(summary.get('attendance_percentage')):.2f}%",
                cell_style,
            ),
        ],
    ]

    table = Table(
        data,
        colWidths=[70 * mm, 45 * mm],
        repeatRows=1,
    )
    table.setStyle(
        _pdf_table_style(
            font_size=8,
        )
    )
    return table


def _group_table(
    rows: list[dict],
    columns: list[tuple[str, str]],
    cell_style: ParagraphStyle,
    *,
    col_widths: list[float],
    font_size: float = 7,
) -> LongTable:
    data = [
        [
            _pdf_cell(label, cell_style)
            for _, label in columns
        ]
    ]

    for row in rows:
        rendered = []

        for key, _ in columns:
            value = row.get(key)

            if key == "attendance_percentage":
                rendered.append(
                    _pdf_cell(
                        f"{_percentage(value):.2f}%",
                        cell_style,
                    )
                )
            else:
                rendered.append(
                    _pdf_cell(
                        value,
                        cell_style,
                    )
                )

        data.append(rendered)

    table = LongTable(
        data,
        colWidths=col_widths,
        repeatRows=1,
        splitByRow=1,
    )

    table.setStyle(
        _pdf_table_style(
            font_size=font_size,
        )
    )

    return table


def _page_number(
    canvas,
    document,
) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.grey)
    canvas.drawRightString(
        landscape(A4)[0] - 10 * mm,
        6 * mm,
        f"Page {document.page}",
    )
    canvas.restoreState()


def build_faculty_attendance_pdf(
    report: dict,
) -> bytes:
    """
    Build a robust multi-page landscape A4 PDF containing the
    faculty attendance report.

    Long tables use fixed widths and wrapped Paragraph cells to
    prevent wide content from causing ReportLab layout failures.
    """

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=12 * mm,
        title="Faculty Attendance Report",
        author="Smart Attendance System",
    )

    styles = getSampleStyleSheet()

    title_style = styles["Title"]
    heading_style = styles["Heading2"]
    body_style = styles["BodyText"]

    cell_style = ParagraphStyle(
        "ReportCell",
        parent=body_style,
        fontName="Helvetica",
        fontSize=6.5,
        leading=8,
        spaceAfter=0,
        spaceBefore=0,
    )

    story = []

    faculty = report.get("faculty") or {}
    filters = report.get("filters") or {}
    summary = report.get("summary") or {}

    story.append(
        Paragraph(
            "Smart Attendance System - Faculty Attendance Report",
            title_style,
        )
    )
    story.append(Spacer(1, 5 * mm))

    faculty_lines = [
        f"<b>Faculty:</b> {_safe(faculty.get('full_name'))}",
        f"<b>Employee ID:</b> {_safe(faculty.get('employee_id'))}",
        f"<b>Department:</b> {_safe(faculty.get('department'))}",
        f"<b>Designation:</b> {_safe(faculty.get('designation'))}",
    ]

    story.append(
        Paragraph(
            "<br/>".join(faculty_lines),
            body_style,
        )
    )
    story.append(Spacer(1, 4 * mm))

    filter_parts = []

    for key, label in (
        ("semester_id", "Semester"),
        ("section_id", "Section"),
        ("subject_id", "Subject"),
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
    story.append(Spacer(1, 5 * mm))

    story.append(
        Paragraph(
            "Summary",
            heading_style,
        )
    )
    story.append(
        _summary_table(
            summary,
            cell_style,
        )
    )

    sections_added = 0

    def add_section(
        title: str,
        table,
    ) -> None:
        nonlocal sections_added

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
        sections_added += 1

    subject_rows = report.get("subject_wise") or []

    if subject_rows:
        add_section(
            "Subject-wise Attendance",
            _group_table(
                subject_rows,
                [
                    ("subject_code", "Code"),
                    ("subject_name", "Subject"),
                    ("session_count", "Sessions"),
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
                    ("not_marked", "Not Marked"),
                    (
                        "attendance_percentage",
                        "Attendance %",
                    ),
                ],
                cell_style,
                col_widths=[
                    18 * mm,
                    48 * mm,
                    18 * mm,
                    25 * mm,
                    20 * mm,
                    18 * mm,
                    18 * mm,
                    18 * mm,
                    22 * mm,
                    24 * mm,
                ],
                font_size=6.5,
            ),
        )

    section_rows = report.get("section_wise") or []

    if section_rows:
        add_section(
            "Section-wise Attendance",
            _group_table(
                section_rows,
                [
                    ("semester_id", "Semester"),
                    ("section_name", "Section"),
                    ("session_count", "Sessions"),
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
                    ("not_marked", "Not Marked"),
                    (
                        "attendance_percentage",
                        "Attendance %",
                    ),
                ],
                cell_style,
                col_widths=[
                    20 * mm,
                    35 * mm,
                    18 * mm,
                    25 * mm,
                    20 * mm,
                    18 * mm,
                    18 * mm,
                    18 * mm,
                    22 * mm,
                    24 * mm,
                ],
                font_size=6.5,
            ),
        )

    day_rows = report.get("day_wise") or []

    if day_rows:
        add_section(
            "Day-wise Attendance",
            _group_table(
                day_rows,
                [
                    ("date", "Date"),
                    ("session_count", "Sessions"),
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
                    ("not_marked", "Not Marked"),
                    (
                        "attendance_percentage",
                        "Attendance %",
                    ),
                ],
                cell_style,
                col_widths=[
                    25 * mm,
                    18 * mm,
                    28 * mm,
                    22 * mm,
                    18 * mm,
                    18 * mm,
                    18 * mm,
                    22 * mm,
                    24 * mm,
                ],
                font_size=6.5,
            ),
        )

    session_rows = report.get("session_wise") or []

    if session_rows:
        add_section(
            "Session-wise Attendance",
            _group_table(
                session_rows,
                [
                    ("date", "Date"),
                    ("session_id", "Session"),
                    ("subject_code", "Subject"),
                    ("section_name", "Section"),
                    ("qr_status", "QR Status"),
                    (
                        "expected_students",
                        "Expected",
                    ),
                    (
                        "attendance_records",
                        "Records",
                    ),
                    ("present", "Present"),
                    ("pending", "Pending"),
                    ("rejected", "Rejected"),
                    ("not_marked", "Not Marked"),
                    (
                        "attendance_percentage",
                        "Attendance %",
                    ),
                ],
                cell_style,
                col_widths=[
                    22 * mm,
                    16 * mm,
                    20 * mm,
                    24 * mm,
                    20 * mm,
                    18 * mm,
                    18 * mm,
                    16 * mm,
                    16 * mm,
                    16 * mm,
                    20 * mm,
                    22 * mm,
                ],
                font_size=6.0,
            ),
        )

    records = report.get("records") or []

    if records:
        detail_data = [
            [
                _pdf_cell("Date", cell_style),
                _pdf_cell("Session", cell_style),
                _pdf_cell("Subject", cell_style),
                _pdf_cell("Section", cell_style),
                _pdf_cell("Roll", cell_style),
                _pdf_cell("Student", cell_style),
                _pdf_cell("QR Status", cell_style),
                _pdf_cell("Attendance", cell_style),
                _pdf_cell("QR Verified", cell_style),
                _pdf_cell("Geo", cell_style),
                _pdf_cell("Face", cell_style),
                _pdf_cell("Live", cell_style),
                _pdf_cell("Rejection", cell_style),
                _pdf_cell("Explanation", cell_style),
            ]
        ]

        for row in records:
            detail_data.append(
                [
                    _pdf_cell(row.get("date"), cell_style),
                    _pdf_cell(row.get("session_id"), cell_style),
                    _pdf_cell(row.get("subject_code"), cell_style),
                    _pdf_cell(row.get("section_name"), cell_style),
                    _pdf_cell(row.get("roll_number"), cell_style),
                    _pdf_cell(row.get("student_name"), cell_style),
                    _pdf_cell(
                        row.get("qr_status")
                        or row.get("session_status"),
                        cell_style,
                    ),
                    _pdf_cell(
                        row.get("attendance_status"),
                        cell_style,
                    ),
                    _pdf_cell(
                        _yes_no(row.get("qr_verified")),
                        cell_style,
                    ),
                    _pdf_cell(
                        _yes_no(row.get("geofence_verified")),
                        cell_style,
                    ),
                    _pdf_cell(
                        _yes_no(row.get("face_verified")),
                        cell_style,
                    ),
                    _pdf_cell(
                        _yes_no(row.get("liveness_verified")),
                        cell_style,
                    ),
                    _pdf_cell(
                        row.get("rejection_reason"),
                        cell_style,
                    ),
                    _pdf_cell(
                        _result_explanation(row),
                        cell_style,
                    ),
                ]
            )

        detail_table = LongTable(
            detail_data,
            colWidths=[
                17 * mm,
                12 * mm,
                17 * mm,
                15 * mm,
                13 * mm,
                31 * mm,
                18 * mm,
                19 * mm,
                15 * mm,
                12 * mm,
                12 * mm,
                12 * mm,
                32 * mm,
                48 * mm,
            ],
            repeatRows=1,
            splitByRow=1,
        )

        detail_table.setStyle(
            _pdf_table_style(
                font_size=5.3,
            )
        )

        add_section(
            "Detailed Attendance Records",
            detail_table,
        )

    document.build(
        story,
        onFirstPage=_page_number,
        onLaterPages=_page_number,
    )

    return buffer.getvalue()