"""
Functional tests: Role-Based Access Control.
Verifies that each role can only access the endpoints it's authorized for.
"""
import pytest
from httpx import AsyncClient

from tests.functional.conftest import auth_header


class TestMemberPermissions:
    """Members should NOT be able to manage books, branches, or users."""

    @pytest.mark.asyncio
    async def test_member_cannot_create_book(self, client: AsyncClient, registered_member, librarian_user):
        # First create a branch (librarian) so we have a branch_id
        br = await client.post(
            "/api/v1/branches",
            json={"name": "RBAC Branch", "address": "1 RBAC St"},
            headers=auth_header(librarian_user["token"]),
        )
        branch_id = br.json()["id"]

        resp = await client.post(
            "/api/v1/books",
            json={"title": "X", "author": "Y", "isbn": "9780000000010", "branch_id": branch_id},
            headers=auth_header(registered_member["token"]),
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_member_cannot_create_branch(self, client: AsyncClient, registered_member):
        resp = await client.post(
            "/api/v1/branches",
            json={"name": "Unauthorized", "address": "X"},
            headers=auth_header(registered_member["token"]),
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_member_cannot_list_users(self, client: AsyncClient, registered_member):
        resp = await client.get(
            "/api/v1/users",
            headers=auth_header(registered_member["token"]),
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_member_cannot_delete_book(self, client: AsyncClient, registered_member, librarian_user):
        # Create branch + book as librarian
        br = await client.post(
            "/api/v1/branches",
            json={"name": "Del Branch", "address": "1 Del St"},
            headers=auth_header(librarian_user["token"]),
        )
        branch_id = br.json()["id"]
        bk = await client.post(
            "/api/v1/books",
            json={"title": "Del Book", "author": "A", "isbn": "9780000000011", "branch_id": branch_id},
            headers=auth_header(librarian_user["token"]),
        )
        book_id = bk.json()["id"]

        resp = await client.delete(
            f"/api/v1/books/{book_id}",
            headers=auth_header(registered_member["token"]),
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_member_can_list_branches(self, client: AsyncClient, registered_member):
        resp = await client.get(
            "/api/v1/branches",
            headers=auth_header(registered_member["token"]),
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_member_can_list_books(self, client: AsyncClient, registered_member):
        resp = await client.get(
            "/api/v1/books",
            headers=auth_header(registered_member["token"]),
        )
        assert resp.status_code == 200


class TestLibrarianPermissions:
    """Librarians can manage books and branches but NOT users."""

    @pytest.mark.asyncio
    async def test_librarian_can_create_branch(self, client: AsyncClient, librarian_user):
        resp = await client.post(
            "/api/v1/branches",
            json={"name": "Lib Branch", "address": "100 Lib St"},
            headers=auth_header(librarian_user["token"]),
        )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_librarian_can_create_book(self, client: AsyncClient, librarian_user):
        br = await client.post(
            "/api/v1/branches",
            json={"name": "Book Branch", "address": "200 Book St"},
            headers=auth_header(librarian_user["token"]),
        )
        branch_id = br.json()["id"]

        resp = await client.post(
            "/api/v1/books",
            json={"title": "Lib Book", "author": "A", "isbn": "9780000000020", "branch_id": branch_id},
            headers=auth_header(librarian_user["token"]),
        )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_librarian_cannot_list_users(self, client: AsyncClient, librarian_user):
        resp = await client.get(
            "/api/v1/users",
            headers=auth_header(librarian_user["token"]),
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_librarian_cannot_delete_branch(self, client: AsyncClient, librarian_user):
        br = await client.post(
            "/api/v1/branches",
            json={"name": "Lib NoDel", "address": "300 NoDel"},
            headers=auth_header(librarian_user["token"]),
        )
        branch_id = br.json()["id"]

        resp = await client.delete(
            f"/api/v1/branches/{branch_id}",
            headers=auth_header(librarian_user["token"]),
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_librarian_cannot_delete_book(self, client: AsyncClient, librarian_user):
        br = await client.post(
            "/api/v1/branches",
            json={"name": "Book NoDel", "address": "400 NoDel"},
            headers=auth_header(librarian_user["token"]),
        )
        branch_id = br.json()["id"]
        bk = await client.post(
            "/api/v1/books",
            json={"title": "NoDel Book", "author": "A", "isbn": "9780000000021", "branch_id": branch_id},
            headers=auth_header(librarian_user["token"]),
        )
        book_id = bk.json()["id"]

        resp = await client.delete(
            f"/api/v1/books/{book_id}",
            headers=auth_header(librarian_user["token"]),
        )
        assert resp.status_code == 403


class TestAdminPermissions:
    """Admin has full access to all resources."""

    @pytest.mark.asyncio
    async def test_admin_can_list_users(self, client: AsyncClient, admin_user):
        resp = await client.get(
            "/api/v1/users",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_can_create_branch(self, client: AsyncClient, admin_user):
        resp = await client.post(
            "/api/v1/branches",
            json={"name": "Admin Branch", "address": "1 Admin St"},
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_admin_can_create_book(self, client: AsyncClient, admin_user):
        br = await client.post(
            "/api/v1/branches",
            json={"name": "Admin Book Branch", "address": "2 Admin St"},
            headers=auth_header(admin_user["token"]),
        )
        branch_id = br.json()["id"]

        resp = await client.post(
            "/api/v1/books",
            json={"title": "Admin Book", "author": "A", "isbn": "9780000000030", "branch_id": branch_id},
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_admin_can_delete_branch(self, client: AsyncClient, admin_user):
        br = await client.post(
            "/api/v1/branches",
            json={"name": "Deletable Branch", "address": "3 Admin St"},
            headers=auth_header(admin_user["token"]),
        )
        branch_id = br.json()["id"]

        resp = await client.delete(
            f"/api/v1/branches/{branch_id}",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_admin_can_delete_book(self, client: AsyncClient, admin_user):
        br = await client.post(
            "/api/v1/branches",
            json={"name": "Del Book Branch", "address": "4 Admin St"},
            headers=auth_header(admin_user["token"]),
        )
        branch_id = br.json()["id"]
        bk = await client.post(
            "/api/v1/books",
            json={"title": "Del Admin Book", "author": "A", "isbn": "9780000000031", "branch_id": branch_id},
            headers=auth_header(admin_user["token"]),
        )
        book_id = bk.json()["id"]

        resp = await client.delete(
            f"/api/v1/books/{book_id}",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 204


class TestUnauthenticatedAccess:
    """Requests without a token should be rejected."""

    @pytest.mark.asyncio
    async def test_list_branches_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/branches")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_list_books_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/books")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_list_loans_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/loans")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_list_users_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/users")
        assert resp.status_code == 401

