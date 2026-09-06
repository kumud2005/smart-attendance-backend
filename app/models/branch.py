from sqlalchemy import (
    Column,
    Integer,
    String,
)

from app.db.database import Base


class Branch(Base):
    """
    ORM metadata model for the existing `branches` table.

    The database table already exists. This model is required so
    SQLAlchemy can resolve ForeignKey("branches.branch_id") used by
    StudentProfile and FacultyProfile during ORM flush operations.

    program_id is intentionally kept as a normal Integer column here.
    Program/Branch validity is already checked by auth_service using
    the existing database tables directly.
    """

    __tablename__ = "branches"

    branch_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    program_id = Column(
        Integer,
        nullable=False,
    )

    branch_name = Column(
        String(100),
        nullable=False,
    )

    branch_code = Column(
        String(30),
        nullable=False,
    )

    is_active = Column(
        Integer,
        nullable=False,
        default=1,
    )
