from pathlib import Path
import sys

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.database import engine  # noqa: E402

SQL_FILE = Path(__file__).with_name("20260901_registration_requests.sql")


def main() -> None:
    sql = SQL_FILE.read_text(encoding="utf-8")

    # The supplied migration contains only simple CREATE TABLE statements.
    # Remove full-line comments, then execute each statement separately so
    # PyMySQL does not need multi-statement mode enabled.
    cleaned_lines = [
        line for line in sql.splitlines()
        if not line.lstrip().startswith("--")
    ]
    cleaned_sql = "\n".join(cleaned_lines)

    statements = [
        statement.strip()
        for statement in cleaned_sql.split(";")
        if statement.strip()
    ]

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))

        student_table = connection.execute(
            text("SHOW TABLES LIKE 'student_section_registration_requests'")
        ).first()
        faculty_table = connection.execute(
            text("SHOW TABLES LIKE 'faculty_assignment_requests'")
        ).first()

    if student_table is None or faculty_table is None:
        raise RuntimeError("Registration migration verification failed.")

    print("Registration migration applied successfully.")
    print("Verified: student_section_registration_requests")
    print("Verified: faculty_assignment_requests")


if __name__ == "__main__":
    main()
