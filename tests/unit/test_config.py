"""
Unit tests for app.core.config – Settings defaults and env overrides.
"""
import os
from unittest.mock import patch


from app.core.config import Settings


class TestSettingsDefaults:
    def test_app_name(self):
        s = Settings()
        assert s.APP_NAME == "Library Management API"

    def test_app_version(self):
        s = Settings()
        assert s.APP_VERSION == "1.0.0"

    def test_debug_false_by_default(self):
        s = Settings()
        assert s.DEBUG is False

    def test_jwt_algorithm(self):
        s = Settings()
        assert s.JWT_ALGORITHM == "HS256"

    def test_jwt_expire_minutes(self):
        s = Settings()
        assert s.JWT_ACCESS_TOKEN_EXPIRE_MINUTES == 30

    def test_admin_email_default(self):
        s = Settings()
        assert s.ADMIN_EMAIL == "admin@library.com"

    def test_log_level_default(self):
        s = Settings()
        assert s.LOG_LEVEL == "INFO"

    def test_overdue_check_interval_default(self):
        s = Settings()
        assert s.OVERDUE_CHECK_INTERVAL == 86400

    def test_database_url_default(self):
        s = Settings()
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

