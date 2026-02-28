"""
Unit tests for app.services.auth – registration, authentication, token management.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import create_access_token, decode_access_token, hash_password
from app.db.models import User, UserRole, BlacklistedToken
from app.services.auth import (
    register_user,
    authenticate_user,
    create_user_token,
    blacklist_token,
    is_token_blacklisted,
    cleanup_expired_tokens,
)


class TestRegisterUser:
    @pytest.mark.asyncio
    async def test_register_success(self, db_session):
        user = await register_user(
            db_session, "new@test.com", "password123", "New User"
        )
        assert user.email == "new@test.com"
        assert user.full_name == "New User"
        assert user.role == UserRole.MEMBER
        assert user.is_active is True
        assert user.id is not None

    @pytest.mark.asyncio
    async def test_register_duplicate_email_raises(self, db_session):
        await register_user(db_session, "dup@test.com", "pass123", "First")
        await db_session.commit()

        with pytest.raises(ValueError, match="already exists"):
            await register_user(db_session, "dup@test.com", "pass123", "Second")

    @pytest.mark.asyncio
    async def test_registered_password_is_hashed(self, db_session):
        user = await register_user(db_session, "hash@test.com", "plaintext", "Hash User")
        assert user.hashed_password != "plaintext"
        assert user.hashed_password.startswith("$2")


class TestAuthenticateUser:
    @pytest.mark.asyncio
    async def test_authenticate_success(self, db_session, make_user):
        user = make_user(email="auth@test.com", password="secret123")
        db_session.add(user)
        await db_session.flush()

        result = await authenticate_user(db_session, "auth@test.com", "secret123")
        assert result is not None
        assert result.email == "auth@test.com"

    @pytest.mark.asyncio
    async def test_authenticate_wrong_password(self, db_session, make_user):
        user = make_user(email="auth2@test.com", password="secret123")
        db_session.add(user)
        await db_session.flush()

        result = await authenticate_user(db_session, "auth2@test.com", "wrongpass")
        assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_unknown_email(self, db_session):
        result = await authenticate_user(db_session, "nobody@test.com", "whatever")
        assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_inactive_user(self, db_session, make_user):
        user = make_user(email="inactive@test.com", password="pass123", is_active=False)
        db_session.add(user)
        await db_session.flush()

        result = await authenticate_user(db_session, "inactive@test.com", "pass123")
        assert result is None


class TestCreateUserToken:
    def test_token_contains_user_data(self, make_user):
        user = make_user(role=UserRole.LIBRARIAN)
        token = create_user_token(user)
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == user.id
        assert payload["role"] == "librarian"

    def test_token_contains_jti(self, make_user):
        user = make_user()
        token = create_user_token(user)
        payload = decode_access_token(token)
        assert "jti" in payload


class TestBlacklistToken:
    @pytest.mark.asyncio
    async def test_blacklist_valid_token(self, db_session, make_user):
        user = make_user()
        token = create_user_token(user)
        payload = decode_access_token(token)

        await blacklist_token(db_session, token)
        await db_session.flush()

        result = await is_token_blacklisted(db_session, payload["jti"])
        assert result is True

    @pytest.mark.asyncio
    async def test_non_blacklisted_token(self, db_session):
        result = await is_token_blacklisted(db_session, "random-jti-value")
        assert result is False

    @pytest.mark.asyncio
    async def test_blacklist_invalid_token_does_nothing(self, db_session):
        # Should not raise
        await blacklist_token(db_session, "invalid.token.string")


class TestCleanupExpiredTokens:
    @pytest.mark.asyncio
    async def test_cleanup_removes_expired(self, db_session):
        expired = BlacklistedToken(
            jti="expired-jti",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        valid = BlacklistedToken(
            jti="valid-jti",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db_session.add_all([expired, valid])
        await db_session.flush()

        count = await cleanup_expired_tokens(db_session)
        assert count == 1

        # Valid token should still exist
        assert await is_token_blacklisted(db_session, "valid-jti") is True
        # Expired token should be gone
        assert await is_token_blacklisted(db_session, "expired-jti") is False

