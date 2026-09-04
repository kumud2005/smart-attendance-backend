from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    student_id = Column(
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

    enrollment_number = Column(
        String(50),
        nullable=False,
        unique=True,
    )

    roll_number = Column(
        String(50),
        nullable=True,
    )

    date_of_birth = Column(
        Date,
        nullable=True,
    )

    # Academic branch selected during registration. Program is derived
    # through branches.program_id so it is not duplicated here.
    branch_id = Column(
        Integer,
        ForeignKey("branches.branch_id"),
        nullable=True,
    )

    # Academic Bank of Credits identifier. Nullable for legacy students
    # created before this field was introduced; required for new registration.
    abc_id = Column(
        String(20),
        nullable=True,
        unique=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------

    user = relationship(
        "User",
        back_populates="student_profile",
    )