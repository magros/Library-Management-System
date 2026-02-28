"""
Unit tests for app.core.config – Settings defaults and env overrides.
"""
import os
from unittest.mock import patch


from app.core.config import Settings

# Keys that may be set by CI or .env that would override defaults
_SETTINGS_ENV_KEYS = [
    "APP_NAME", "APP_VERSION", "DEBUG", "DATABASE_URL", "TEST_DATABASE_URL",
    "JWT_SECRET_KEY", "JWT_ALGORITHM", "JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
    "ADMIN_EMAIL", "ADMIN_PASSWORD", "LOG_LEVEL", "OVERDUE_CHECK_INTERVAL",
]


def _clean_env():
    """Return a dict suitable for patch.dict that removes all Settings-related env vars."""
    return {k: "" for k in _SETTINGS_ENV_KEYS}


class TestSettingsDefaults:
    """Each test clears env vars so that only hard-coded defaults are evaluated."""

    def test_app_name(self):
        with patch.dict(os.environ, {}, clear=True):
            s = Settings(_env_file=None)
            assert s.APP_NAME == "Library Management API"

    def test_app_version(self):
        with patch.dict(os.environ, {}, clear=True):
            s = Settings(_env_file=None)
            assert s.APP_VERSION == "1.0.0"

    def test_debug_false_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            s = Settings(_env_file=None)
            assert s.DEBUG is False

    def test_jwt_algorithm(self):
        with patch.dict(os.environ, {}, clear=True):
            s = Settings(_env_file=None)
            assert s.JWT_ALGORITHM == "HS256"

    def test_jwt_expire_minutes(self):
        with patch.dict(os.environ, {}, clear=True):
            s = Settings(_env_file=None)
            assert s.JWT_ACCESS_TOKEN_EXPIRE_MINUTES == 30

    def test_admin_email_default(self):
        with patch.dict(os.environ, {}, clear=True):
            s = Settings(_env_file=None)
            assert s.ADMIN_EMAIL == "admin@library.com"

    def test_log_level_default(self):
        with patch.dict(os.environ, {}, clear=True):
            s = Settings(_env_file=None)
            assert s.LOG_LEVEL == "INFO"

    def test_overdue_check_interval_default(self):
        with patch.dict(os.environ, {}, clear=True):
            s = Settings(_env_file=None)
            assert s.OVERDUE_CHECK_INTERVAL == 86400

    def test_database_url_default(self):
        with patch.dict(os.environ, {}, clear=True):
            s = Settings(_env_file=None)
            assert "postgresql" in s.DATABASE_URL


class TestSettingsEnvOverride:
    def test_override_app_name(self):
        with patch.dict(os.environ, {"APP_NAME": "Custom App"}):
            s = Settings()
            assert s.APP_NAME == "Custom App"

    def test_override_debug(self):
        with patch.dict(os.environ, {"DEBUG": "true"}):
            s = Settings()
            assert s.DEBUG is True

    def test_override_jwt_expire(self):
        with patch.dict(os.environ, {"JWT_ACCESS_TOKEN_EXPIRE_MINUTES": "60"}):
            s = Settings()
            assert s.JWT_ACCESS_TOKEN_EXPIRE_MINUTES == 60

    def test_override_log_level(self):
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            s = Settings()
            assert s.LOG_LEVEL == "DEBUG"

