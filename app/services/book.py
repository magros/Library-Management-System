import math
from typing import Optional, List, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Book

logger = get_logger("services.book")


async def create_book(db: AsyncSession, data: dict, actor_id: str) -> Book:
    """Create a new book."""
    data["available_copies"] = data.get("total_copies", 1)

    book = Book(**data)
    db.add(book)
    await db.flush()
    await db.refresh(book)

    logger.info(f"Book created: id={book.id} title='{book.title}' by actor={actor_id}")
    return book


async def get_books(
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
    branch_id: Optional[str] = None,
    genre: Optional[str] = None,
    author: Optional[str] = None,
    available: Optional[bool] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> Tuple[List[Book], int]:
    """List books with filtering, sorting, and pagination."""
    query = select(Book)
    count_query = select(func.count()).select_from(Book)

    if branch_id:
        query = query.where(Book.branch_id == branch_id)
        count_query = count_query.where(Book.branch_id == branch_id)
    if genre:
        query = query.where(Book.genre.ilike(f"%{genre}%"))
        count_query = count_query.where(Book.genre.ilike(f"%{genre}%"))
    if author:
        query = query.where(Book.author.ilike(f"%{author}%"))
        count_query = count_query.where(Book.author.ilike(f"%{author}%"))
    if available is True:
        query = query.where(Book.available_copies > 0)
        count_query = count_query.where(Book.available_copies > 0)
    if search:
        search_filter = (
            Book.title.ilike(f"%{search}%")
            | Book.author.ilike(f"%{search}%")
            | Book.isbn.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    sort_column = getattr(Book, sort_by, Book.created_at)
    if sort_order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    offset = (page - 1) * size
    query = query.offset(offset).limit(size)

    result = await db.execute(query)
    books = list(result.scalars().all())

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    return books, total


async def get_book_by_id(db: AsyncSession, book_id: str) -> Optional[Book]:
    """Get a single book by ID."""
    result = await db.execute(select(Book).where(Book.id == book_id))
    return result.scalar_one_or_none()


async def update_book(
    db: AsyncSession, book_id: str, data: dict, actor_id: str
) -> Optional[Book]:
    """Update a book."""
    book = await get_book_by_id(db, book_id)
    if not book:
        return None

    if "total_copies" in data and data["total_copies"] is not None:
        new_total = data["total_copies"]
        old_total = book.total_copies
        diff = new_total - old_total
        new_available = book.available_copies + diff
        if new_available < 0:
            raise ValueError("Cannot reduce total copies below the number currently on loan")
        data["available_copies"] = new_available

    for key, value in data.items():
        if value is not None:
            setattr(book, key, value)

    await db.flush()
    await db.refresh(book)

    logger.info(f"Book updated: id={book_id} by actor={actor_id}")
    return book


async def delete_book(db: AsyncSession, book_id: str, actor_id: str) -> bool:
    """Delete a book."""
    book = await get_book_by_id(db, book_id)
    if not book:
        return False

    await db.delete(book)
    await db.flush()

    logger.info(f"Book deleted: id={book_id} by actor={actor_id}")
    return True


def calculate_pages(total: int, size: int) -> int:
    return math.ceil(total / size) if size > 0 else 0
