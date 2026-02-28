from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    APP_NAME: str = "Library Management API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5432/library_db"
    TEST_DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5432/library_test_db"

    # JWT
    JWT_SECRET_KEY: str = "change-me-to-a-random-secret-key-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Built-in Admin
    ADMIN_EMAIL: str = "admin@library.com"
    ADMIN_PASSWORD: str = "admin123456"

    # Logging
    LOG_LEVEL: str = "INFO"

    # Overdue checker interval (seconds)
    OVERDUE_CHECK_INTERVAL: int = 86400

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()

