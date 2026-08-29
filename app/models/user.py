from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Enum,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    role_id = Column(
        Integer,
        ForeignKey("roles.role_id"),
        nullable=False,
    )

    email = Column(
        String(150),
        nullable=False,
        unique=True,
    )

    password_hash = Column(
        String(255),
        nullable=False,
    )

    full_name = Column(
        String(120),
        nullable=False,
    )

    phone = Column(
        String(20),
        nullable=True,
    )

    account_status = Column(
        Enum(
            "PENDING",
            "ACTIVE",
            "SUSPENDED",
            "INACTIVE",
        ),
        nullable=False,
        default="PENDING",
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    last_login_at = Column(
        DateTime,
        nullable=True,
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------

    role = relationship(
        "Role",
        back_populates="users",
    )

    admin_profile = relationship(
        "AdminProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    faculty_profile = relationship(
        "FacultyProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    student_profile = relationship(
        "StudentProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )