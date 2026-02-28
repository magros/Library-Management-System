"""
Unit tests for app.services.branch – CRUD operations for library branches.
"""
import pytest

from app.db.models import LibraryBranch
from app.services.branch import (
    create_branch,
    get_branches,
    get_branch_by_id,
    update_branch,
    delete_branch,
    calculate_pages,
)


class TestCreateBranch:
    @pytest.mark.asyncio
    async def test_create_success(self, db_session):
        branch = await create_branch(
            db_session,
            {"name": "Downtown", "address": "100 Main St", "description": "Central"},
            "actor-1",
        )
        assert branch.name == "Downtown"
        assert branch.address == "100 Main St"
        assert branch.is_active is True
        assert branch.id is not None

    @pytest.mark.asyncio
    async def test_create_with_optional_fields(self, db_session):
        branch = await create_branch(
            db_session,
            {
                "name": "Uptown",
                "address": "200 High St",
                "phone_number": "555-0200",
                "email": "uptown@lib.com",
            },
            "actor-1",
        )
        assert branch.phone_number == "555-0200"
        assert branch.email == "uptown@lib.com"


class TestGetBranches:
    @pytest.mark.asyncio
    async def test_empty_list(self, db_session):
        branches, total = await get_branches(db_session)
        assert branches == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_returns_all(self, db_session, make_branch):
        for i in range(3):
            db_session.add(make_branch(name=f"Branch {i}"))
        await db_session.flush()

        branches, total = await get_branches(db_session)
        assert total == 3

    @pytest.mark.asyncio
    async def test_pagination(self, db_session, make_branch):
        for i in range(5):
            db_session.add(make_branch(name=f"Branch {i}"))
        await db_session.flush()

        branches, total = await get_branches(db_session, page=1, size=2)
        assert len(branches) == 2
        assert total == 5

    @pytest.mark.asyncio
    async def test_filter_active(self, db_session, make_branch):
        db_session.add(make_branch(name="Active", is_active=True))
        db_session.add(make_branch(name="Inactive", is_active=False))
        await db_session.flush()

        branches, total = await get_branches(db_session, is_active=True)
        assert total == 1
        assert branches[0].name == "Active"

    @pytest.mark.asyncio
    async def test_search_by_name(self, db_session, make_branch):
        db_session.add(make_branch(name="Central Library"))
        db_session.add(make_branch(name="East Side"))
        await db_session.flush()

        branches, total = await get_branches(db_session, search="central")
        assert total == 1
        assert branches[0].name == "Central Library"

    @pytest.mark.asyncio
    async def test_search_by_address(self, db_session, make_branch):
        db_session.add(make_branch(name="A", address="123 Elm Street"))
        db_session.add(make_branch(name="B", address="456 Oak Avenue"))
        await db_session.flush()

        branches, total = await get_branches(db_session, search="elm")
        assert total == 1

    @pytest.mark.asyncio
    async def test_sort_ascending(self, db_session, make_branch):
        db_session.add(make_branch(name="Zebra"))
        db_session.add(make_branch(name="Alpha"))
        await db_session.flush()

        branches, _ = await get_branches(db_session, sort_by="name", sort_order="asc")
        assert branches[0].name == "Alpha"

    @pytest.mark.asyncio
    async def test_sort_descending(self, db_session, make_branch):
        db_session.add(make_branch(name="Alpha"))
        db_session.add(make_branch(name="Zebra"))
        await db_session.flush()

        branches, _ = await get_branches(db_session, sort_by="name", sort_order="desc")
        assert branches[0].name == "Zebra"


class TestGetBranchById:
    @pytest.mark.asyncio
    async def test_found(self, db_session, make_branch):
        branch = make_branch(name="Find Me")
        db_session.add(branch)
        await db_session.flush()

        found = await get_branch_by_id(db_session, branch.id)
        assert found is not None
        assert found.name == "Find Me"

    @pytest.mark.asyncio
    async def test_not_found(self, db_session):
        found = await get_branch_by_id(db_session, "bad-id")
        assert found is None


class TestUpdateBranch:
    @pytest.mark.asyncio
    async def test_update_name(self, db_session, make_branch):
        branch = make_branch(name="Old Name")
        db_session.add(branch)
        await db_session.flush()

        updated = await update_branch(
            db_session, branch.id, {"name": "New Name"}, "actor-1"
        )
        assert updated.name == "New Name"

    @pytest.mark.asyncio
    async def test_update_deactivate(self, db_session, make_branch):
        branch = make_branch()
        db_session.add(branch)
        await db_session.flush()

        updated = await update_branch(
            db_session, branch.id, {"is_active": False}, "actor-1"
        )
        assert updated.is_active is False

    @pytest.mark.asyncio
    async def test_update_nonexistent(self, db_session):
        result = await update_branch(db_session, "bad-id", {"name": "X"}, "actor-1")
        assert result is None


class TestDeleteBranch:
    @pytest.mark.asyncio
    async def test_delete_success(self, db_session, make_branch):
        branch = make_branch()
        db_session.add(branch)
        await db_session.flush()

        result = await delete_branch(db_session, branch.id, "actor-1")
        assert result is True

        found = await get_branch_by_id(db_session, branch.id)
        assert found is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, db_session):
        result = await delete_branch(db_session, "bad-id", "actor-1")
        assert result is False


class TestBranchCalculatePages:
    def test_exact(self):
        assert calculate_pages(20, 10) == 2

    def test_remainder(self):
        assert calculate_pages(21, 10) == 3

    def test_zero(self):
        assert calculate_pages(0, 10) == 0

    def test_zero_size(self):
        assert calculate_pages(10, 0) == 0

