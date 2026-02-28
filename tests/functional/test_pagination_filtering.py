"""
Functional tests: Pagination, filtering, and sorting.
Validates query parameters across all list endpoints.
"""
import pytest
from httpx import AsyncClient
from uuid import uuid4

from tests.functional.conftest import auth_header


class TestBooksPagination:

    @pytest.mark.asyncio
    async def test_books_pagination(self, client: AsyncClient, librarian_user):
        # Create branch
        br = await client.post(
            "/api/v1/branches",
            json={"name": "Page Branch", "address": "1 Page St"},
            headers=auth_header(librarian_user["token"]),
        )
        branch_id = br.json()["id"]

        # Create 5 books
        for i in range(5):
            await client.post(
                "/api/v1/books",
                json={
                    "title": f"Page Book {i}",
                    "author": "Author",
                    "isbn": f"978000000070{i}",
                    "branch_id": branch_id,
                },
                headers=auth_header(librarian_user["token"]),
            )

        # Page 1, size 2
        resp = await client.get(
            "/api/v1/books?page=1&size=2",
            headers=auth_header(librarian_user["token"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["size"] == 2
        assert data["pages"] == 3  # ceil(5/2)

    @pytest.mark.asyncio
    async def test_books_filter_by_genre(self, client: AsyncClient, librarian_user):
        br = await client.post(
            "/api/v1/branches",
            json={"name": "Genre Branch", "address": "2 Genre St"},
            headers=auth_header(librarian_user["token"]),
        )
        branch_id = br.json()["id"]

        await client.post(
            "/api/v1/books",
            json={"title": "Fiction Book", "author": "A", "isbn": "9780000000710", "genre": "Fiction", "branch_id": branch_id},
            headers=auth_header(librarian_user["token"]),
        )
        await client.post(
            "/api/v1/books",
            json={"title": "Science Book", "author": "B", "isbn": "9780000000711", "genre": "Science", "branch_id": branch_id},
            headers=auth_header(librarian_user["token"]),
        )

        resp = await client.get(
            "/api/v1/books?genre=Fiction",
            headers=auth_header(librarian_user["token"]),
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1
        for book in resp.json()["items"]:
            assert book["genre"] == "Fiction"

    @pytest.mark.asyncio
    async def test_books_search_by_title(self, client: AsyncClient, librarian_user):
        br = await client.post(
            "/api/v1/branches",
            json={"name": "Search Branch", "address": "3 Search St"},
            headers=auth_header(librarian_user["token"]),
        )
        branch_id = br.json()["id"]

        await client.post(
            "/api/v1/books",
            json={"title": "Python Mastery", "author": "A", "isbn": "9780000000720", "branch_id": branch_id},
            headers=auth_header(librarian_user["token"]),
        )
        await client.post(
            "/api/v1/books",
            json={"title": "Java Patterns", "author": "B", "isbn": "9780000000721", "branch_id": branch_id},
            headers=auth_header(librarian_user["token"]),
        )

        resp = await client.get(
            "/api/v1/books?search=python",
            headers=auth_header(librarian_user["token"]),
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_books_sort_asc_desc(self, client: AsyncClient, librarian_user):
        br = await client.post(
            "/api/v1/branches",
            json={"name": "Sort Branch", "address": "4 Sort St"},
            headers=auth_header(librarian_user["token"]),
        )
        branch_id = br.json()["id"]

        await client.post(
            "/api/v1/books",
            json={"title": "Alpha Book", "author": "A", "isbn": "9780000000730", "branch_id": branch_id},
            headers=auth_header(librarian_user["token"]),
        )
        await client.post(
            "/api/v1/books",
            json={"title": "Zeta Book", "author": "Z", "isbn": "9780000000731", "branch_id": branch_id},
            headers=auth_header(librarian_user["token"]),
        )

        # Ascending
        resp_asc = await client.get(
            "/api/v1/books?sort_by=title&sort_order=asc",
            headers=auth_header(librarian_user["token"]),
        )
        items_asc = resp_asc.json()["items"]
        titles = [b["title"] for b in items_asc]
        assert titles == sorted(titles)

        # Descending
        resp_desc = await client.get(
            "/api/v1/books?sort_by=title&sort_order=desc",
            headers=auth_header(librarian_user["token"]),
        )
        items_desc = resp_desc.json()["items"]
        titles_desc = [b["title"] for b in items_desc]
        assert titles_desc == sorted(titles_desc, reverse=True)

    @pytest.mark.asyncio
    async def test_books_filter_available(self, client: AsyncClient, librarian_user, registered_member):
        br = await client.post(
            "/api/v1/branches",
            json={"name": "Avail Branch", "address": "5 Avail St"},
            headers=auth_header(librarian_user["token"]),
        )
        branch_id = br.json()["id"]

        # Book with 1 copy
        bk = await client.post(
            "/api/v1/books",
            json={"title": "One Copy", "author": "A", "isbn": "9780000000740", "total_copies": 1, "branch_id": branch_id},
            headers=auth_header(librarian_user["token"]),
        )
        book_id = bk.json()["id"]

        # Borrow it
        await client.post(
            "/api/v1/loans",
            json={"book_id": book_id, "branch_id": branch_id},
            headers=auth_header(registered_member["token"]),
        )

        # Filter available=true - this book should NOT appear
        resp = await client.get(
            f"/api/v1/books?available=true&branch_id={branch_id}",
            headers=auth_header(librarian_user["token"]),
        )
        assert resp.status_code == 200
        for bk in resp.json()["items"]:
            assert bk["available_copies"] > 0


class TestBranchesPagination:

    @pytest.mark.asyncio
    async def test_branches_pagination_and_search(self, client: AsyncClient, librarian_user):
        for i in range(4):
            await client.post(
                "/api/v1/branches",
                json={"name": f"PBranch {i}", "address": f"{i} PBranch St"},
                headers=auth_header(librarian_user["token"]),
            )

        resp = await client.get(
            "/api/v1/branches?page=1&size=2",
            headers=auth_header(librarian_user["token"]),
        )
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 2
        assert resp.json()["total"] >= 4

        # Search
        search_resp = await client.get(
            "/api/v1/branches?search=PBranch",
            headers=auth_header(librarian_user["token"]),
        )
        assert search_resp.status_code == 200
        assert search_resp.json()["total"] >= 4


class TestUsersPagination:

    @pytest.mark.asyncio
    async def test_users_pagination_and_filters(self, client: AsyncClient, admin_user):
        # Register some users
        for i in range(3):
            await client.post("/api/v1/auth/register", json={
                "email": f"puser{i}-{uuid4().hex[:4]}@test.com",
                "password": "password123",
                "full_name": f"Page User {i}",
            })

        resp = await client.get(
            "/api/v1/users?page=1&size=2",
            headers=auth_header(admin_user["token"]),
        )
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 2
        assert resp.json()["total"] >= 3

        # Filter by role
        role_resp = await client.get(
            "/api/v1/users?role=member",
            headers=auth_header(admin_user["token"]),
        )
        assert role_resp.status_code == 200
        for u in role_resp.json()["items"]:
            assert u["role"] == "member"


class TestLoansPagination:

    @pytest.mark.asyncio
    async def test_loans_pagination_and_status_filter(self, client: AsyncClient, librarian_user):
        # Create branch + books
        br = await client.post(
            "/api/v1/branches",
            json={"name": "Loan Page Branch", "address": "1 LP St"},
            headers=auth_header(librarian_user["token"]),
        )
        branch_id = br.json()["id"]

        # Register member
        reg = await client.post("/api/v1/auth/register", json={
            "email": f"lpage-{uuid4().hex[:6]}@test.com",
            "password": "password123",
            "full_name": "Loan Page User",
        })
        member_token = reg.json()["access_token"]

        # Create 3 books and loans
        for i in range(3):
            bk = await client.post(
                "/api/v1/books",
                json={
                    "title": f"LP Book {i}",
                    "author": "A",
                    "isbn": f"978000000080{i}",
                    "total_copies": 5,
                    "branch_id": branch_id,
                },
                headers=auth_header(librarian_user["token"]),
            )
            book_id = bk.json()["id"]
            await client.post(
                "/api/v1/loans",
                json={"book_id": book_id, "branch_id": branch_id},
                headers=auth_header(member_token),
            )

        # Pagination
        resp = await client.get(
            "/api/v1/loans?page=1&size=2",
            headers=auth_header(librarian_user["token"]),
        )
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 2
        assert resp.json()["total"] >= 3

        # Filter by status
        status_resp = await client.get(
            "/api/v1/loans?status=requested",
            headers=auth_header(librarian_user["token"]),
        )
        assert status_resp.status_code == 200
        for loan in status_resp.json()["items"]:
            assert loan["status"] == "requested"


class TestHealthEndpoint:

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

