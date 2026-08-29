from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.db.database import engine

from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.faculty import router as faculty_router
from app.api.student import router as student_router


# ============================================================================
# APPLICATION
# ============================================================================

app = FastAPI(
    title=settings.APP_NAME,
    description="Smart Attendance System API",
    version="1.0.0",
)


# ============================================================================
# CORS
# ============================================================================
#
# Allowed frontend origins:
#
# 1. Local Flutter Web development:
#    http://localhost:<dynamic-port>
#    http://127.0.0.1:<dynamic-port>
#
# 2. Production Flutter Web deployed on Firebase Hosting.
#
# ============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://smart-attendance-system-e5a54.web.app",
        "https://smart-attendance-system-e5a54.firebaseapp.com",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# API ROUTERS
# ============================================================================

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(faculty_router)
app.include_router(student_router)


# ============================================================================
# ROOT
# ============================================================================

@app.get("/")
def root():
    return {
        "message": "Smart Attendance System API is running",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "status": "ok",
    }


# ============================================================================
# BASIC HEALTH CHECK
# ============================================================================

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "smart-attendance-backend",
    }


# ============================================================================
# DATABASE HEALTH CHECK
# ============================================================================

@app.get("/health/database")
def database_health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "ok",
            "database": "connected",
        }

    except Exception:
        return {
            "status": "error",
            "database": "disconnected",
        }