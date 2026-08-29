from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Enum,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"

    session_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    faculty_id = Column(
        Integer,
        ForeignKey(
            "faculty_profiles.faculty_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    subject_id = Column(
        Integer,
        ForeignKey(
            "subjects.subject_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    section_id = Column(
        Integer,
        ForeignKey(
            "sections.section_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    classroom_id = Column(
        Integer,
        ForeignKey(
            "classrooms.classroom_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    session_token = Column(
        String(255),
        nullable=False,
        unique=True,
    )

    started_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    ended_at = Column(
        DateTime,
        nullable=True,
    )

    qr_expires_at = Column(
        DateTime,
        nullable=False,
    )

    session_status = Column(
        Enum(
            "ACTIVE",
            "COMPLETED",
            "EXPIRED",
            "CANCELLED",
        ),
        nullable=False,
        default="ACTIVE",
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------

    faculty = relationship(
        "FacultyProfile",
    )

    # Subject, Section and Classroom currently do not have
    # SQLAlchemy model classes in this project, so these are
    # intentionally kept as foreign-key columns only for now.