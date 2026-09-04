from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class FacultyProfile(Base):
    __tablename__ = "faculty_profiles"

    faculty_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id = Column(
        Integer,
        ForeignKey(
            "users.user_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
    )

    employee_id = Column(
        String(50),
        nullable=False,
        unique=True,
    )

    department = Column(
        String(100),
        nullable=True,
    )

    # Authoritative academic branch. The legacy department text column is
    # retained for backward compatibility with existing screens/reports.
    # Program is derived through branches.program_id.
    branch_id = Column(
        Integer,
        ForeignKey("branches.branch_id"),
        nullable=True,
    )

    designation = Column(
        String(100),
        nullable=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    # ---------------------------------------------------------
    # Relationship
    # ---------------------------------------------------------

    user = relationship(
        "User",
        back_populates="faculty_profile",
    )