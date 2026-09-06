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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days

    # Password-reset settings.
    #
    # IMPORTANT:
    # Keep ALLOW_TEST_PASSWORD_RESET=False by default.
    # For LOCAL testing only, add this to backend .env:
    #
    #     ALLOW_TEST_PASSWORD_RESET=True
    #
    # The test bypass returns a short-lived reset token directly
    # instead of sending an email/OTP. Production email verification
    # will use the same request/confirm architecture later.
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 10
    ALLOW_TEST_PASSWORD_RESET: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
