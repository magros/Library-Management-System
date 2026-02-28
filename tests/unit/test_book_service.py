"""
Unit tests for app.services.book – CRUD operations and business logic.
"""
import pytest

from app.db.models import Book
from app.services.book import (
    create_book,
    get_books,
    get_book_by_id,
    update_book,
    delete_book,
    calculate_pages,
)


class TestCreateBook:
    @pytest.mark.asyncio
    async def test_create_success(self, db_session, make_branch):
        branch = make_branch()
        db_session.add(branch)
        await db_session.flush()

        book = await create_book(
            db_session,
            {
                "title": "Clean Code",
                "author": "Robert Martin",
                "isbn": "9780132350884",
                "total_copies": 3,
                "branch_id": branch.id,
            },
            "actor-1",
        )
        assert book.title == "Clean Code"
        assert book.total_copies == 3
        assert book.available_copies == 3  # auto-set from total_copies

    @pytest.mark.asyncio
    async def test_create_defaults_copies_to_one(self, db_session, make_branch):
        branch = make_branch()
        db_session.add(branch)
        await db_session.flush()

        book = await create_book(
            db_session,
            {
                "title": "Test",
                "author": "Author",
                "isbn": "9781234567890",
                "branch_id": branch.id,
            },
            "actor-1",
        )
        assert book.available_copies == 1

    @pytest.mark.asyncio
    async def test_create_with_optional_fields(self, db_session, make_branch):
        branch = make_branch()
        db_session.add(branch)
        await db_session.flush()

        book = await create_book(
            db_session,
            {
                "title": "Dune",
                "author": "Frank Herbert",
                "isbn": "9780441013593",
                "genre": "Science Fiction",
                "publication_year": 1965,
                "description": "Desert planet saga",
                "total_copies": 2,
                "branch_id": branch.id,
            },
            "actor-1",
        )
        assert book.genre == "Science Fiction"
        assert book.publication_year == 1965


class TestGetBooks:
    @pytest.mark.asyncio
    async def test_empty_list(self, db_session):
        books, total = await get_books(db_session)
        assert books == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_returns_all(self, db_session, make_branch, make_book):
        branch = make_branch()
        db_session.add(branch)
        await db_session.flush()

        for i in range(3):
            db_session.add(make_book(title=f"Book {i}", branch_id=branch.id))
        await db_session.flush()

        books, total = await get_books(db_session)
        assert total == 3

    @pytest.mark.asyncio
    async def test_pagination(self, db_session, make_branch, make_book):
        branch = make_branch()
        db_session.add(branch)
        await db_session.flush()

        for i in range(5):
            db_session.add(make_book(title=f"Book {i}", branch_id=branch.id))
        await db_session.flush()

        books, total = await get_books(db_session, page=1, size=2)
        assert len(books) == 2
        assert total == 5

    @pytest.mark.asyncio
    async def test_filter_by_branch(self, db_session, make_branch, make_book):
        b1 = make_branch(name="Branch 1")
        b2 = make_branch(name="Branch 2")
        db_session.add_all([b1, b2])
        await db_session.flush()

        db_session.add(make_book(title="B1 Book", branch_id=b1.id))
        db_session.add(make_book(title="B2 Book", branch_id=b2.id))
        await db_session.flush()

        books, total = await get_books(db_session, branch_id=b1.id)
        assert total == 1
        assert books[0].title == "B1 Book"

    @pytest.mark.asyncio
    async def test_filter_by_genre(self, db_session, make_branch, make_book):
        branch = make_branch()
        db_session.add(branch)
        await db_session.flush()

        db_session.add(make_book(genre="Fiction", branch_id=branch.id))
        db_session.add(make_book(genre="Science", branch_id=branch.id))
        await db_session.flush()

        books, total = await get_books(db_session, genre="Fiction")
        assert total == 1

    @pytest.mark.asyncio
    async def test_filter_by_author(self, db_session, make_branch, make_book):
        branch = make_branch()
        db_session.add(branch)
        await db_session.flush()

        db_session.add(make_book(author="Alice Writer", branch_id=branch.id))
        db_session.add(make_book(author="Bob Author", branch_id=branch.id))
        await db_session.flush()

        books, total = await get_books(db_session, author="alice")
        assert total == 1

    @pytest.mark.asyncio
    async def test_filter_available_only(self, db_session, make_branch, make_book):
        branch = make_branch()
        db_session.add(branch)
        await db_session.flush()

        db_session.add(make_book(available_copies=2, branch_id=branch.id))
        db_session.add(make_book(available_copies=0, total_copies=1, branch_id=branch.id))
        await db_session.flush()

        books, total = await get_books(db_session, available=True)
        assert total == 1

    @pytest.mark.asyncio
    async def test_search(self, db_session, make_branch, make_book):
        branch = make_branch()
        db_session.add(branch)
        await db_session.flush()

        db_session.add(make_book(title="Python Cookbook", branch_id=branch.id))
        db_session.add(make_book(title="Java Patterns", branch_id=branch.id))
        await db_session.flush()

        books, total = await get_books(db_session, search="python")
        assert total == 1
        assert books[0].title == "Python Cookbook"

    @pytest.mark.asyncio
    async def test_sort_ascending(self, db_session, make_branch, make_book):
        branch = make_branch()
        db_session.add(branch)
        await db_session.flush()

        db_session.add(make_book(title="Zebra", branch_id=branch.id))
        db_session.add(make_book(title="Alpha", branch_id=branch.id))
        await db_session.flush()

        books, _ = await get_books(db_session, sort_by="title", sort_order="asc")
        assert books[0].title == "Alpha"


class TestGetBookById:
    @pytest.mark.asyncio
    async def test_found(self, db_session, make_branch, make_book):
        branch = make_branch()
        db_session.add(branch)
        await db_session.flush()

        book = make_book(title="Find Me", branch_id=branch.id)
        db_session.add(book)
        await db_session.flush()

        found = await get_book_by_id(db_session, book.id)
        assert found is not None
        assert found.title == "Find Me"

    @pytest.mark.asyncio
    async def test_not_found(self, db_session):
        found = await get_book_by_id(db_session, "bad-id")
        assert found is None


class TestUpdateBook:
    @pytest.mark.asyncio
    async def test_update_title(self, db_session, make_branch, make_book):
        branch = make_branch()
        db_session.add(branch)
        await db_session.flush()

        book = make_book(title="Old Title", branch_id=branch.id)
        db_session.add(book)
        await db_session.flush()

        updated = await update_book(
            db_session, book.id, {"title": "New Title"}, "actor-1"
        )
        assert updated.title == "New Title"

    @pytest.mark.asyncio
    async def test_update_total_copies_adjusts_available(self, db_session, make_branch, make_book):
        branch = make_branch()
        db_session.add(branch)
        await db_session.flush()

        book = make_book(total_copies=5, available_copies=3, branch_id=branch.id)
        db_session.add(book)
        await db_session.flush()

        # Increase total by 2 → available should also increase by 2
        updated = await update_book(
            db_session, book.id, {"total_copies": 7}, "actor-1"
        )
        assert updated.total_copies == 7
        assert updated.available_copies == 5  # 3 + 2

    @pytest.mark.asyncio
    async def test_reduce_copies_below_loaned_raises(self, db_session, make_branch, make_book):
        branch = make_branch()
        db_session.add(branch)
        await db_session.flush()

        book = make_book(total_copies=5, available_copies=1, branch_id=branch.id)
        db_session.add(book)
        await db_session.flush()

        # 4 copies on loan, trying to set total to 2 → available = 1 + (2-5) = -2 → error
        with pytest.raises(ValueError, match="Cannot reduce total copies"):
            await update_book(db_session, book.id, {"total_copies": 2}, "actor-1")

    @pytest.mark.asyncio
    async def test_update_nonexistent(self, db_session):
        result = await update_book(db_session, "bad-id", {"title": "X"}, "actor-1")
        assert result is None


class TestDeleteBook:
    @pytest.mark.asyncio
    async def test_delete_success(self, db_session, make_branch, make_book):
        branch = make_branch()
        db_session.add(branch)
        await db_session.flush()

        book = make_book(branch_id=branch.id)
        db_session.add(book)
        await db_session.flush()

        result = await delete_book(db_session, book.id, "actor-1")
        assert result is True

        found = await get_book_by_id(db_session, book.id)
        assert found is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, db_session):
        result = await delete_book(db_session, "bad-id", "actor-1")
        assert result is False


class TestBookCalculatePages:
    def test_exact(self):
        assert calculate_pages(20, 10) == 2

    def test_remainder(self):
        assert calculate_pages(21, 10) == 3

    def test_zero_total(self):
        assert calculate_pages(0, 10) == 0

    def test_zero_size(self):
        assert calculate_pages(10, 0) == 0

    def test_single_page(self):
        assert calculate_pages(5, 10) == 1


class TestGetBooksSortDescending:
    @pytest.mark.asyncio
    async def test_sort_descending(self, db_session, make_branch, make_book):
        branch = make_branch()
        db_session.add(branch)
        await db_session.flush()

        db_session.add(make_book(title="Alpha", branch_id=branch.id))
        db_session.add(make_book(title="Zebra", branch_id=branch.id))
        await db_session.flush()

        books, _ = await get_books(db_session, sort_by="title", sort_order="desc")
        assert books[0].title == "Zebra"

    @pytest.mark.asyncio
    async def test_update_with_no_changes(self, db_session, make_branch, make_book):
        branch = make_branch()
        db_session.add(branch)
        await db_session.flush()

        book = make_book(title="No Change", branch_id=branch.id)
        db_session.add(book)
        await db_session.flush()

        updated = await update_book(db_session, book.id, {}, "actor-1")
        assert updated is not None
        assert updated.title == "No Change"

    def test_zero(self):
        assert calculate_pages(0, 10) == 0

