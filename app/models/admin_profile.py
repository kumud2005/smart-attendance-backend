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


class AdminProfile(Base):
    __tablename__ = "admin_profiles"

    admin_id = Column(
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
        back_populates="admin_profile",
    )