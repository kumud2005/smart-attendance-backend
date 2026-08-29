from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # MySQL connection settings are loaded from the local .env file.
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "smart_attendance_db"
    DB_USER: str = "root"
    DB_PASSWORD: str = ""

    # Application settings.
    APP_NAME: str = "Smart Attendance System API"
    APP_ENV: str = "development"
    SECRET_KEY: str = "CHANGE_THIS_LATER"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
