"""
Functional tests: Loan status transitions.
Validates all valid/invalid status changes and role-based permissions.
"""
import pytest
from httpx import AsyncClient

from tests.functional.conftest import auth_header


async def _create_branch_and_book(client, librarian_token, isbn_suffix="00"):
    """Helper: create a branch and book, return (branch_id, book_id)."""
    br = await client.post(
        "/api/v1/branches",
        json={"name": f"Trans Branch {isbn_suffix}", "address": "1 Trans St"},
        headers=auth_header(librarian_token),
    )
    branch_id = br.json()["id"]

    bk = await client.post(
        "/api/v1/books",
        json={
            "title": f"Trans Book {isbn_suffix}",
            "author": "Author",
            "isbn": f"97800000001{isbn_suffix}",
            "total_copies": 5,
            "branch_id": branch_id,
        },
        headers=auth_header(librarian_token),
    )
    book_id = bk.json()["id"]
    return branch_id, book_id


async def _create_loan(client, member_token, book_id, branch_id):
    """Helper: create a loan and return loan_id."""
    resp = await client.post(
        "/api/v1/loans",
        json={"book_id": book_id, "branch_id": branch_id},
        headers=auth_header(member_token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


class TestHappyPathTransitions:
    """Test the full valid status flow: requested → approved → borrowed → returned."""

    @pytest.mark.asyncio
    async def test_full_happy_path(self, client: AsyncClient, registered_member, librarian_user):
        branch_id, book_id = await _create_branch_and_book(client, librarian_user["token"], "40")
        loan_id = await _create_loan(client, registered_member["token"], book_id, branch_id)

        # REQUESTED → APPROVED (librarian)
        resp = await client.patch(
            f"/api/v1/loans/{loan_id}/status",
            json={"status": "approved"},
            headers=auth_header(librarian_user["token"]),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

        # APPROVED → BORROWED (librarian)
        resp = await client.patch(
            f"/api/v1/loans/{loan_id}/status",
            json={"status": "borrowed"},
            headers=auth_header(librarian_user["token"]),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "borrowed"

        # BORROWED → RETURNED (librarian)
        resp = await client.patch(
            f"/api/v1/loans/{loan_id}/status",
            json={"status": "returned"},
            headers=auth_header(librarian_user["token"]),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "returned"


class TestMemberTransitions:

    @pytest.mark.asyncio
    async def test_member_can_cancel_requested_loan(self, client: AsyncClient, registered_member, librarian_user):
        branch_id, book_id = await _create_branch_and_book(client, librarian_user["token"], "41")
        loan_id = await _create_loan(client, registered_member["token"], book_id, branch_id)

        resp = await client.patch(
            f"/api/v1/loans/{loan_id}/status",
            json={"status": "canceled"},
            headers=auth_header(registered_member["token"]),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "canceled"

    @pytest.mark.asyncio
    async def test_member_cannot_approve_own_loan(self, client: AsyncClient, registered_member, librarian_user):
        branch_id, book_id = await _create_branch_and_book(client, librarian_user["token"], "42")
        loan_id = await _create_loan(client, registered_member["token"], book_id, branch_id)

        resp = await client.patch(
            f"/api/v1/loans/{loan_id}/status",
            json={"status": "approved"},
            headers=auth_header(registered_member["token"]),
        )
        assert resp.status_code == 403


class TestInvalidTransitions:

    @pytest.mark.asyncio
    async def test_returned_cannot_be_borrowed_again(self, client: AsyncClient, registered_member, librarian_user):
        branch_id, book_id = await _create_branch_and_book(client, librarian_user["token"], "43")
        loan_id = await _create_loan(client, registered_member["token"], book_id, branch_id)

        # Move to returned
        for status in ["approved", "borrowed", "returned"]:
            await client.patch(
                f"/api/v1/loans/{loan_id}/status",
                json={"status": status},
                headers=auth_header(librarian_user["token"]),
            )

        # Try to go back to borrowed
        resp = await client.patch(
            f"/api/v1/loans/{loan_id}/status",
            json={"status": "borrowed"},
            headers=auth_header(librarian_user["token"]),
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_canceled_cannot_be_approved(self, client: AsyncClient, registered_member, librarian_user):
        branch_id, book_id = await _create_branch_and_book(client, librarian_user["token"], "44")
        loan_id = await _create_loan(client, registered_member["token"], book_id, branch_id)

        # Cancel
        await client.patch(
            f"/api/v1/loans/{loan_id}/status",
            json={"status": "canceled"},
            headers=auth_header(registered_member["token"]),
        )

        # Try to approve canceled loan
        resp = await client.patch(
            f"/api/v1/loans/{loan_id}/status",
            json={"status": "approved"},
            headers=auth_header(librarian_user["token"]),
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_requested_cannot_be_borrowed_directly(self, client: AsyncClient, registered_member, librarian_user):
        branch_id, book_id = await _create_branch_and_book(client, librarian_user["token"], "45")
        loan_id = await _create_loan(client, registered_member["token"], book_id, branch_id)

        resp = await client.patch(
            f"/api/v1/loans/{loan_id}/status",
            json={"status": "borrowed"},
            headers=auth_header(librarian_user["token"]),
        )
        assert resp.status_code == 400


class TestLoanDetails:

    @pytest.mark.asyncio
    async def test_member_can_view_own_loan(self, client: AsyncClient, registered_member, librarian_user):
        branch_id, book_id = await _create_branch_and_book(client, librarian_user["token"], "46")
        loan_id = await _create_loan(client, registered_member["token"], book_id, branch_id)

        resp = await client.get(
            f"/api/v1/loans/{loan_id}",
            headers=auth_header(registered_member["token"]),
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == loan_id

    @pytest.mark.asyncio
    async def test_loan_not_found_returns_404(self, client: AsyncClient, registered_member):
        resp = await client.get(
            "/api/v1/loans/nonexistent-loan-id",
            headers=auth_header(registered_member["token"]),
        )
        assert resp.status_code == 404

