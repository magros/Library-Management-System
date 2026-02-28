"""
Unit tests for app.api.v1.dependencies – get_current_user, require_role.
"""
from datetime import timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.security import create_access_token, decode_access_token
from app.db.models import User, UserRole
from app.api.v1.dependencies import get_current_user, require_role


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self, db_session, make_user):
        """A valid non-blacklisted token should return the active user."""
        user = make_user(email="dep@test.com", role=UserRole.MEMBER)
        db_session.add(user)
        await db_session.flush()

        token = create_access_token(data={"sub": user.id, "role": "member"})

        with patch("app.api.v1.dependencies.is_token_blacklisted", return_value=False):
            with patch("app.api.v1.dependencies.get_user_by_id", return_value=user):
                result = await get_current_user(token, db_session)
                assert result.id == user.id
                assert result.email == "dep@test.com"

    @pytest.mark.asyncio
    async def test_expired_token_raises_401(self, db_session):
        """An expired token should raise 401."""
        token = create_access_token(
            data={"sub": "user-1", "role": "member"},
            expires_delta=timedelta(seconds=-1),
        )
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token, db_session)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self, db_session):
        """A garbage token should raise 401."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("garbage.token.here", db_session)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_blacklisted_token_raises_401(self, db_session, make_user):
        """A blacklisted token should raise 401."""
        user = make_user()
        db_session.add(user)
        await db_session.flush()

        token = create_access_token(data={"sub": user.id, "role": "member"})

        with patch("app.api.v1.dependencies.is_token_blacklisted", return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(token, db_session)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_user_not_found_raises_401(self, db_session, make_user):
        """If user no longer exists in DB, should raise 401."""
        user_id = str(uuid4())
        token = create_access_token(data={"sub": user_id, "role": "member"})

        with patch("app.api.v1.dependencies.is_token_blacklisted", return_value=False):
            with patch("app.api.v1.dependencies.get_user_by_id", return_value=None):
                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user(token, db_session)
                assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_inactive_user_raises_403(self, db_session, make_user):
        """An inactive user should raise 403."""
        user = make_user(is_active=False)
        db_session.add(user)
        await db_session.flush()

        token = create_access_token(data={"sub": user.id, "role": "member"})

        with patch("app.api.v1.dependencies.is_token_blacklisted", return_value=False):
            with patch("app.api.v1.dependencies.get_user_by_id", return_value=user):
                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user(token, db_session)
                assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_token_missing_sub_raises_401(self, db_session):
        """A token without 'sub' claim should raise 401."""
        token = create_access_token(data={"role": "member"})  # no sub
        with patch("app.api.v1.dependencies.is_token_blacklisted", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(token, db_session)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_token_missing_jti_raises_401(self, db_session):
        """A token with 'sub' but no 'jti' should raise 401."""
        from jose import jwt
        from app.core.config import settings

        # Create a token manually without jti
        payload = {"sub": "user-1", "role": "member"}
        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

        with patch("app.api.v1.dependencies.is_token_blacklisted", return_value=False):
            # decode_access_token might return None or return the payload without jti
            # Either way, get_current_user should reject it
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(token, db_session)
            assert exc_info.value.status_code == 401


class TestRequireRole:
    @pytest.mark.asyncio
    async def test_allowed_role_passes(self, make_user):
        """User with required role should pass through."""
        checker = require_role(UserRole.ADMIN, UserRole.LIBRARIAN)
        user = make_user(role=UserRole.ADMIN)

        # Call the inner function directly
        result = await checker(user)
        assert result.role == UserRole.ADMIN

    @pytest.mark.asyncio
    async def test_disallowed_role_raises_403(self, make_user):
        """User without required role should get 403."""
        checker = require_role(UserRole.ADMIN)
        user = make_user(role=UserRole.MEMBER)

        with pytest.raises(HTTPException) as exc_info:
            await checker(user)
        assert exc_info.value.status_code == 403
        assert "permissions" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_multiple_roles_any_matches(self, make_user):
        """If multiple roles are required, any match should pass."""
        checker = require_role(UserRole.LIBRARIAN, UserRole.ADMIN)
        user = make_user(role=UserRole.LIBRARIAN)

        result = await checker(user)
        assert result.role == UserRole.LIBRARIAN

    @pytest.mark.asyncio
    async def test_member_role_when_admin_required(self, make_user):
        """Member should not pass admin-only check."""
        checker = require_role(UserRole.ADMIN)
        member = make_user(role=UserRole.MEMBER)

        with pytest.raises(HTTPException) as exc_info:
            await checker(member)
        assert exc_info.value.status_code == 403

