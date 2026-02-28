"""
Functional tests: Edge cases.
Unavailable books, max loans, built-in admin protection, inactive users, etc.
"""
import pytest
from httpx import AsyncClient
from uuid import uuid4

from tests.functional.conftest import auth_header


class TestBookAvailability:

    @pytest.mark.asyncio
    async def test_borrow_unavailable_book(self, client: AsyncClient, registered_member, librarian_user):
        """Should return 400 when no copies are available."""
        # Create branch and book with 1 copy
        br = await client.post(
            "/api/v1/branches",
            json={"name": "Edge Branch", "address": "1 Edge St"},
            headers=auth_header(librarian_user["token"]),
        )
        branch_id = br.json()["id"]

        bk = await client.post(
            "/api/v1/books",
            json={"title": "Edge Book", "author": "A", "isbn": "9780000000050", "total_copies": 1, "branch_id": branch_id},
            headers=auth_header(librarian_user["token"]),
        )
        book_id = bk.json()["id"]

        # First loan (takes last copy)
        resp1 = await client.post(
            "/api/v1/loans",
            json={"book_id": book_id, "branch_id": branch_id},
            headers=auth_header(registered_member["token"]),
        )
        assert resp1.status_code == 201

        # Register a second member
        reg2 = await client.post("/api/v1/auth/register", json={
            "email": f"edge2-{uuid4().hex[:6]}@test.com",
            "password": "password123",
            "full_name": "Edge User 2",
        })
        token2 = reg2.json()["access_token"]

        # Second loan should fail (no copies)
        resp2 = await client.post(
            "/api/v1/loans",
            json={"book_id": book_id, "branch_id": branch_id},
            headers=auth_header(token2),
        )
        assert resp2.status_code == 400
        assert "available" in resp2.json()["detail"].lower() or "copies" in resp2.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_borrow_book_from_wrong_branch(self, client: AsyncClient, registered_member, librarian_user):
        """Should return 400 when borrowing from a branch that doesn't have the book."""
        br1 = await client.post(
            "/api/v1/branches",
            json={"name": "Branch A", "address": "1 A St"},
            headers=auth_header(librarian_user["token"]),
        )
        branch1_id = br1.json()["id"]

        br2 = await client.post(
            "/api/v1/branches",
            json={"name": "Branch B", "address": "1 B St"},
            headers=auth_header(librarian_user["token"]),
        )
        branch2_id = br2.json()["id"]

        # Book belongs to branch 1
        bk = await client.post(
            "/api/v1/books",
            json={"title": "Wrong Branch Book", "author": "A", "isbn": "9780000000051", "branch_id": branch1_id},
            headers=auth_header(librarian_user["token"]),
        )
        book_id = bk.json()["id"]

        # Try to borrow from branch 2
        resp = await client.post(
            "/api/v1/loans",
            json={"book_id": book_id, "branch_id": branch2_id},
            headers=auth_header(registered_member["token"]),
        )
        assert resp.status_code == 400
        assert "belong" in resp.json()["detail"].lower()


class TestMaxActiveLoans:

    @pytest.mark.asyncio
    async def test_borrow_exceeds_max_active_loans(self, client: AsyncClient, librarian_user):
        """6th active loan should be rejected (limit is 5)."""
        # Register member
        reg = await client.post("/api/v1/auth/register", json={
            "email": f"maxloans-{uuid4().hex[:6]}@test.com",
            "password": "password123",
            "full_name": "Max Loans User",
        })
        member_token = reg.json()["access_token"]

        # Create branch
        br = await client.post(
            "/api/v1/branches",
            json={"name": "Max Loans Branch", "address": "1 Max St"},
            headers=auth_header(librarian_user["token"]),
        )
        branch_id = br.json()["id"]

        # Create 6 books and try to borrow all 6
        for i in range(6):
            bk = await client.post(
                "/api/v1/books",
                json={
                    "title": f"Max Book {i}",
                    "author": "A",
                    "isbn": f"978000000006{i}",
                    "total_copies": 5,
                    "branch_id": branch_id,
                },
                headers=auth_header(librarian_user["token"]),
            )
            book_id = bk.json()["id"]

            resp = await client.post(
                "/api/v1/loans",
                json={"book_id": book_id, "branch_id": branch_id},
                headers=auth_header(member_token),
            )

            if i < 5:
                assert resp.status_code == 201, f"Loan {i} should succeed"
            else:
                assert resp.status_code == 400, f"Loan {i} should fail (max active)"
                assert "maximum" in resp.json()["detail"].lower() or "max" in resp.json()["detail"].lower()


class TestBuiltInAdmin:

    @pytest.mark.asyncio
    async def test_delete_built_in_admin_blocked(self, client: AsyncClient, admin_user, built_in_admin):
        """Cannot delete the built-in admin user."""
        resp = await client.delete(
            f"/api/v1/users/{built_in_admin['id']}",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 403


class TestInactiveUser:

    @pytest.mark.asyncio
    async def test_inactive_user_cannot_access_endpoints(
        self, client: AsyncClient, admin_user, test_session_factory
    ):
        """An inactive user's token should be rejected with 403."""

        # Create an active user
        reg = await client.post("/api/v1/auth/register", json={
            "email": f"inactive-{uuid4().hex[:6]}@test.com",
            "password": "password123",
            "full_name": "Inactive User",
        })
        token = reg.json()["access_token"]

        # Verify they can access
        resp = await client.get("/api/v1/branches", headers=auth_header(token))
        assert resp.status_code == 200

        # Admin deactivates user via API
        # First find the user
        users_resp = await client.get(
            "/api/v1/users",
            headers=auth_header(admin_user["token"]),
        )
        users = users_resp.json()["items"]
        target = next(u for u in users if "inactive" in u["email"])

        deactivate_resp = await client.put(
            f"/api/v1/users/{target['id']}",
            json={"is_active": False},
            headers=auth_header(admin_user["token"]),
        )
        assert deactivate_resp.status_code == 200

        # Now the token should be rejected (403 = inactive)
        resp2 = await client.get("/api/v1/branches", headers=auth_header(token))
        assert resp2.status_code == 403


class TestAuthEdgeCases:

    @pytest.mark.asyncio
    async def test_register_duplicate_email_returns_409(self, client: AsyncClient):
        email = f"dup-{uuid4().hex[:6]}@test.com"
        await client.post("/api/v1/auth/register", json={
            "email": email, "password": "password123", "full_name": "First",
        })
        resp = await client.post("/api/v1/auth/register", json={
            "email": email, "password": "password123", "full_name": "Second",
        })
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_login_wrong_password_returns_401(self, client: AsyncClient):
        email = f"wrongpw-{uuid4().hex[:6]}@test.com"
        await client.post("/api/v1/auth/register", json={
            "email": email, "password": "password123", "full_name": "WP User",
        })
        resp = await client.post("/api/v1/auth/login", data={
            "username": email, "password": "wrongpassword",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_unknown_email_returns_401(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", data={
            "username": "nobody@nowhere.com", "password": "whatever",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_register_invalid_email_returns_422(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "not-an-email", "password": "password123", "full_name": "Invalid",
        })
        assert resp.status_code == 422


class TestResourceNotFound:

    @pytest.mark.asyncio
    async def test_get_nonexistent_book_returns_404(self, client: AsyncClient, registered_member):
        resp = await client.get(
            "/api/v1/books/nonexistent-id",
            headers=auth_header(registered_member["token"]),
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_nonexistent_branch_returns_404(self, client: AsyncClient, registered_member):
        resp = await client.get(
            "/api/v1/branches/nonexistent-id",
            headers=auth_header(registered_member["token"]),
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_nonexistent_user_returns_404(self, client: AsyncClient, admin_user):
        resp = await client.get(
            "/api/v1/users/nonexistent-id",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_nonexistent_book_returns_404(self, client: AsyncClient, librarian_user):
        resp = await client.put(
            "/api/v1/books/nonexistent-id",
            json={"title": "New Title"},
            headers=auth_header(librarian_user["token"]),
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_book_returns_404(self, client: AsyncClient, admin_user):
        resp = await client.delete(
            "/api/v1/books/nonexistent-id",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 404

