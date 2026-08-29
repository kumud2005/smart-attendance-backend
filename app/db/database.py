from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


# URL-encode the password so special characters such as @, #, %, etc.
# are handled correctly inside the MySQL connection URL.
encoded_password = quote_plus(settings.DB_PASSWORD)

# SQLAlchemy connection URL for MySQL using PyMySQL.
DATABASE_URL = (
    f"mysql+pymysql://{settings.DB_USER}:{encoded_password}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


def get_db():
    """Provide a database session to FastAPI endpoints."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_database_connection() -> bool:
    """Return True when the configured MySQL database is reachable."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True