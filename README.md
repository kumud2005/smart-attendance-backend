# Smart Attendance System — New Backend

This backend is being built from scratch with FastAPI.

## Current milestone

The first milestone is intentionally small:

- FastAPI application
- `/health` endpoint
- Environment configuration template
- Project structure ready for MySQL, authentication, and application APIs

## Database

MySQL database:

`smart_attendance_db`

The database already exists and is treated as the current database foundation.

## Run locally

### Windows

```powershell
py -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Then open:

`http://127.0.0.1:8000/health`

Interactive API documentation:

`http://127.0.0.1:8000/docs`

## Important

The previous backend ZIP is reference-only. This project is a new implementation.
