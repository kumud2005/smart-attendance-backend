from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.db.database import Base


class Role(Base):
    __tablename__ = "roles"

    role_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    role_name = Column(
        String(30),
        nullable=False,
        unique=True,
    )

    description = Column(
        String(255),
        nullable=True,
    )

    users = relationship(
        "User",
        back_populates="role",
    )