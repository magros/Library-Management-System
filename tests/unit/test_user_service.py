"""
Unit tests for app.services.user – CRUD operations and business logic.
"""
import pytest

from app.db.models import User, UserRole
from app.services.user import (
    get_users,
    get_user_by_id,
    update_user,
    delete_user,
    calculate_pages,
)
from app.core.security import verify_password


class TestGetUsers:
    @pytest.mark.asyncio
    async def test_get_empty_list(self, db_session):
        users, total = await get_users(db_session)
        assert users == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_get_users_returns_all(self, db_session, make_user):
        for i in range(3):
            db_session.add(make_user(email=f"u{i}@test.com"))
        await db_session.flush()

        users, total = await get_users(db_session)
        assert total == 3
        assert len(users) == 3

    @pytest.mark.asyncio
    async def test_get_users_pagination(self, db_session, make_user):
        for i in range(5):
            db_session.add(make_user(email=f"page{i}@test.com"))
        await db_session.flush()

        users, total = await get_users(db_session, page=1, size=2)
        assert len(users) == 2
        assert total == 5

    @pytest.mark.asyncio
    async def test_filter_by_role(self, db_session, make_user):
        db_session.add(make_user(email="m@t.com", role=UserRole.MEMBER))
        db_session.add(make_user(email="l@t.com", role=UserRole.LIBRARIAN))
        db_session.add(make_user(email="a@t.com", role=UserRole.ADMIN))
        await db_session.flush()

        users, total = await get_users(db_session, role=UserRole.LIBRARIAN)
        assert total == 1
        assert users[0].role == UserRole.LIBRARIAN

    @pytest.mark.asyncio
    async def test_filter_by_active_status(self, db_session, make_user):
        db_session.add(make_user(email="active@t.com", is_active=True))
        db_session.add(make_user(email="inactive@t.com", is_active=False))
        await db_session.flush()

        users, total = await get_users(db_session, is_active=True)
        assert total == 1
        assert users[0].is_active is True

    @pytest.mark.asyncio
    async def test_search_by_name(self, db_session, make_user):
        db_session.add(make_user(email="alice@t.com", full_name="Alice Smith"))
        db_session.add(make_user(email="bob@t.com", full_name="Bob Jones"))
        await db_session.flush()

        users, total = await get_users(db_session, search="alice")
        assert total == 1
        assert users[0].full_name == "Alice Smith"

    @pytest.mark.asyncio
    async def test_search_by_email(self, db_session, make_user):
        db_session.add(make_user(email="findme@special.com", full_name="Find Me"))
        db_session.add(make_user(email="other@test.com", full_name="Other"))
        await db_session.flush()

        users, total = await get_users(db_session, search="special")
        assert total == 1

    @pytest.mark.asyncio
    async def test_sort_ascending(self, db_session, make_user):
        db_session.add(make_user(email="zzz@t.com", full_name="Zara"))
        db_session.add(make_user(email="aaa@t.com", full_name="Alice"))
        await db_session.flush()

        users, _ = await get_users(db_session, sort_by="email", sort_order="asc")
        assert users[0].email == "aaa@t.com"


class TestGetUserById:
    @pytest.mark.asyncio
    async def test_found(self, db_session, make_user):
        user = make_user(email="findbyid@t.com")
        db_session.add(user)
        await db_session.flush()

        found = await get_user_by_id(db_session, user.id)
        assert found is not None
        assert found.email == "findbyid@t.com"

    @pytest.mark.asyncio
    async def test_not_found(self, db_session):
        found = await get_user_by_id(db_session, "nonexistent-id")
        assert found is None


class TestUpdateUser:
    @pytest.mark.asyncio
    async def test_update_name(self, db_session, make_user):
        user = make_user(email="upd@t.com", full_name="Old Name")
        db_session.add(user)
        await db_session.flush()

        updated = await update_user(
            db_session, user.id, {"full_name": "New Name"}, "actor-1"
        )
        assert updated is not None
        assert updated.full_name == "New Name"

    @pytest.mark.asyncio
    async def test_update_role(self, db_session, make_user):
        user = make_user(email="role@t.com", role=UserRole.MEMBER)
        db_session.add(user)
        await db_session.flush()

        updated = await update_user(
            db_session, user.id, {"role": UserRole.LIBRARIAN}, "actor-1"
        )
        assert updated.role == UserRole.LIBRARIAN

    @pytest.mark.asyncio
    async def test_update_password(self, db_session, make_user):
        user = make_user(email="pwupd@t.com", password="oldpass")
        db_session.add(user)
        await db_session.flush()

        updated = await update_user(
            db_session, user.id, {"password": "newpass123"}, "actor-1"
        )
        assert updated is not None
        assert verify_password("newpass123", updated.hashed_password) is True

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_none(self, db_session):
        result = await update_user(
            db_session, "bad-id", {"full_name": "X"}, "actor-1"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_update_deactivate_user(self, db_session, make_user):
        user = make_user(email="deact@t.com")
        db_session.add(user)
        await db_session.flush()

        updated = await update_user(
            db_session, user.id, {"is_active": False}, "actor-1"
        )
        assert updated.is_active is False


class TestDeleteUser:
    @pytest.mark.asyncio
    async def test_delete_success(self, db_session, make_user):
        user = make_user(email="del@t.com")
        db_session.add(user)
        await db_session.flush()

        result = await delete_user(db_session, user.id, "actor-1")
        assert result is True

        found = await get_user_by_id(db_session, user.id)
        assert found is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, db_session):
        result = await delete_user(db_session, "no-such-id", "actor-1")
        assert result is False

    @pytest.mark.asyncio
    async def test_cannot_delete_built_in_admin(self, db_session, make_user):
        admin = make_user(
            email="builtin@t.com", role=UserRole.ADMIN, is_built_in=True
        )
        db_session.add(admin)
        await db_session.flush()

        with pytest.raises(ValueError, match="built-in admin"):
            await delete_user(db_session, admin.id, "actor-1")


class TestCalculatePages:
    def test_exact_division(self):
        assert calculate_pages(20, 10) == 2

    def test_with_remainder(self):
        assert calculate_pages(21, 10) == 3

    def test_single_page(self):
        assert calculate_pages(5, 10) == 1

    def test_zero_total(self):
        assert calculate_pages(0, 10) == 0

    def test_zero_size(self):
        assert calculate_pages(10, 0) == 0


class TestGetUsersSortDescending:
    @pytest.mark.asyncio
    async def test_sort_descending(self, db_session, make_user):
        db_session.add(make_user(email="aaa@t.com", full_name="Alice"))
        db_session.add(make_user(email="zzz@t.com", full_name="Zara"))
        await db_session.flush()

        users, _ = await get_users(db_session, sort_by="email", sort_order="desc")
        assert users[0].email == "zzz@t.com"


