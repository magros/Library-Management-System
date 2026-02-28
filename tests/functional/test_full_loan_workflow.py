"""
Functional tests: Complete user workflows.
Registration → Login → Borrow book → Return book.
"""
import pytest
from httpx import AsyncClient

from tests.functional.conftest import auth_header


class TestFullLoanWorkflow:
    """Complete happy-path: register → login → create branch/book → request loan → approve → borrow → return."""

    @pytest.mark.asyncio
    async def test_register_login_borrow_return_flow(
        self, client: AsyncClient, librarian_user
    ):
        # 1. Register a new member
        reg_resp = await client.post("/api/v1/auth/register", json={
            "email": "workflow@test.com",
            "password": "password123",
            "full_name": "Workflow User",
        })
        assert reg_resp.status_code == 201
        member_token = reg_resp.json()["access_token"]

        # 2. Login (verify it works)
        login_resp = await client.post("/api/v1/auth/login", data={
            "username": "workflow@test.com",
            "password": "password123",
        })
        assert login_resp.status_code == 200
        member_token = login_resp.json()["access_token"]

        # 3. Librarian creates a branch
        branch_resp = await client.post(
            "/api/v1/branches",
            json={"name": "Central Library", "address": "100 Main St"},
            headers=auth_header(librarian_user["token"]),
        )
        assert branch_resp.status_code == 201
        branch_id = branch_resp.json()["id"]

        # 4. Librarian creates a book
        book_resp = await client.post(
            "/api/v1/books",
            json={
                "title": "Clean Code",
                "author": "Robert Martin",
                "isbn": "9780132350884",
                "total_copies": 3,
                "branch_id": branch_id,
            },
            headers=auth_header(librarian_user["token"]),
        )
        assert book_resp.status_code == 201
        book_id = book_resp.json()["id"]

        # 5. Member requests a loan
        loan_resp = await client.post(
            "/api/v1/loans",
            json={"book_id": book_id, "branch_id": branch_id},
            headers=auth_header(member_token),
        )
        assert loan_resp.status_code == 201
        loan_id = loan_resp.json()["id"]
        assert loan_resp.json()["status"] == "requested"

        # 6. Librarian approves the loan
        approve_resp = await client.patch(
            f"/api/v1/loans/{loan_id}/status",
            json={"status": "approved"},
            headers=auth_header(librarian_user["token"]),
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["status"] == "approved"

        # 7. Librarian marks as borrowed
        borrow_resp = await client.patch(
            f"/api/v1/loans/{loan_id}/status",
            json={"status": "borrowed"},
            headers=auth_header(librarian_user["token"]),
        )
        assert borrow_resp.status_code == 200
        assert borrow_resp.json()["status"] == "borrowed"

        # 8. Librarian marks as returned
        return_resp = await client.patch(
            f"/api/v1/loans/{loan_id}/status",
            json={"status": "returned"},
            headers=auth_header(librarian_user["token"]),
        )
        assert return_resp.status_code == 200
        assert return_resp.json()["status"] == "returned"
        assert return_resp.json()["return_date"] is not None

        # 9. Member can see in their history
        history_resp = await client.get(
            "/api/v1/loans/my-history",
            headers=auth_header(member_token),
        )
        assert history_resp.status_code == 200
        assert history_resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_register_login_borrow_cancel_flow(
        self, client: AsyncClient, librarian_user
    ):
        """Member requests loan then cancels before approval."""
        # Register member
        reg_resp = await client.post("/api/v1/auth/register", json={
            "email": "cancel-flow@test.com",
            "password": "password123",
            "full_name": "Cancel User",
        })
        assert reg_resp.status_code == 201
        member_token = reg_resp.json()["access_token"]

        # Create branch & book (librarian)
        branch_resp = await client.post(
            "/api/v1/branches",
            json={"name": "Cancel Branch", "address": "200 Cancel St"},
            headers=auth_header(librarian_user["token"]),
        )
        branch_id = branch_resp.json()["id"]

        book_resp = await client.post(
            "/api/v1/books",
            json={"title": "Cancel Book", "author": "Author", "isbn": "9780000000001", "total_copies": 2, "branch_id": branch_id},
            headers=auth_header(librarian_user["token"]),
        )
        book_id = book_resp.json()["id"]

        # Request loan
        loan_resp = await client.post(
            "/api/v1/loans",
            json={"book_id": book_id, "branch_id": branch_id},
            headers=auth_header(member_token),
        )
        loan_id = loan_resp.json()["id"]

        # Cancel loan
        cancel_resp = await client.patch(
            f"/api/v1/loans/{loan_id}/status",
            json={"status": "canceled"},
            headers=auth_header(member_token),
        )
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["status"] == "canceled"

    @pytest.mark.asyncio
    async def test_borrow_lost_book_flow(
        self, client: AsyncClient, librarian_user
    ):
        """Full flow ending in LOST status."""
        reg_resp = await client.post("/api/v1/auth/register", json={
            "email": "lost-flow@test.com",
            "password": "password123",
            "full_name": "Lost User",
        })
        member_token = reg_resp.json()["access_token"]

        branch_resp = await client.post(
            "/api/v1/branches",
            json={"name": "Lost Branch", "address": "300 Lost St"},
            headers=auth_header(librarian_user["token"]),
        )
        branch_id = branch_resp.json()["id"]

        book_resp = await client.post(
            "/api/v1/books",
            json={"title": "Lost Book", "author": "Author", "isbn": "9780000000002", "total_copies": 1, "branch_id": branch_id},
            headers=auth_header(librarian_user["token"]),
        )
        book_id = book_resp.json()["id"]

        # Request → Approve → Borrow → Lost
        loan_resp = await client.post(
            "/api/v1/loans",
            json={"book_id": book_id, "branch_id": branch_id},
            headers=auth_header(member_token),
        )
        loan_id = loan_resp.json()["id"]

        await client.patch(
            f"/api/v1/loans/{loan_id}/status",
            json={"status": "approved"},
            headers=auth_header(librarian_user["token"]),
        )
        await client.patch(
            f"/api/v1/loans/{loan_id}/status",
            json={"status": "borrowed"},
            headers=auth_header(librarian_user["token"]),
        )
        lost_resp = await client.patch(
            f"/api/v1/loans/{loan_id}/status",
            json={"status": "lost"},
            headers=auth_header(librarian_user["token"]),
        )
        assert lost_resp.status_code == 200
        assert lost_resp.json()["status"] == "lost"

    @pytest.mark.asyncio
    async def test_logout_invalidates_token(self, client: AsyncClient):
        """After logout, the same token should no longer work."""
        reg_resp = await client.post("/api/v1/auth/register", json={
            "email": "logout-test@test.com",
            "password": "password123",
            "full_name": "Logout User",
        })
        token = reg_resp.json()["access_token"]

        # Token works before logout
        resp = await client.get("/api/v1/branches", headers=auth_header(token))
        assert resp.status_code == 200

        # Logout
        logout_resp = await client.post(
            "/api/v1/auth/logout",
            headers=auth_header(token),
        )
        assert logout_resp.status_code == 200

        # Token should no longer work
        resp2 = await client.get("/api/v1/branches", headers=auth_header(token))
        assert resp2.status_code == 401

