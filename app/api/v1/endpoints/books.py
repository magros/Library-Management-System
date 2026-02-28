from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import User, UserRole
from app.api.v1.dependencies import get_current_user, require_role
from app.schemas.book import BookCreate, BookUpdate, BookResponse, BookListResponse
from app.services.book import (
    create_book,
    get_books,
    get_book_by_id,
    update_book,
    delete_book,
    calculate_pages,
)

router = APIRouter(prefix="/books", tags=["Books"])

LibrarianOrAdmin = Annotated[User, Depends(require_role(UserRole.LIBRARIAN, UserRole.ADMIN))]
AdminOnly = Annotated[User, Depends(require_role(UserRole.ADMIN))]


@router.get(
    "",
    response_model=BookListResponse,
    summary="List books",
    description="Retrieve a paginated list of books with optional filters for branch, genre, author, availability, and free-text search.",
    responses={
        200: {"description": "Paginated list of books"},
        401: {"description": "Not authenticated"},
    },
)
async def list_books(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    branch_id: str | None = None,
    genre: str | None = None,
    author: str | None = None,
    available: bool | None = None,
    search: str | None = None,
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
):
    """List all books with optional filters (all authenticated users)."""
    books, total = await get_books(
        db, page=page, size=size, branch_id=branch_id, genre=genre,
        author=author, available=available, search=search,
        sort_by=sort_by, sort_order=sort_order,
    )
    return BookListResponse(
        items=books, total=total, page=page, size=size, pages=calculate_pages(total, size)
    )


@router.post(
    "",
    response_model=BookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a book",
    description="Add a new book to the catalog. Requires Librarian or Admin role.",
    responses={
        201: {"description": "Book created successfully"},
        400: {"description": "Invalid data (e.g. duplicate ISBN)"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        422: {"description": "Validation error"},
    },
)
async def create_book_endpoint(
    data: BookCreate,
    current_user: LibrarianOrAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a book (Librarian/Admin)."""
    try:
        book = await create_book(db, data.model_dump(), current_user.id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return book


@router.get(
    "/{book_id}",
    response_model=BookResponse,
    summary="Get book details",
    description="Retrieve a single book by its ID.",
    responses={
        200: {"description": "Book details"},
        401: {"description": "Not authenticated"},
        404: {"description": "Book not found"},
    },
)
async def get_book(
    book_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get book details."""
    book = await get_book_by_id(db, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    return book


@router.put(
    "/{book_id}",
    response_model=BookResponse,
    summary="Update a book",
    description="Update book details. Requires Librarian or Admin role.",
    responses={
        200: {"description": "Book updated successfully"},
        400: {"description": "Invalid data"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Book not found"},
        422: {"description": "Validation error"},
    },
)
async def update_book_endpoint(
    book_id: str,
    data: BookUpdate,
    current_user: LibrarianOrAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update a book (Librarian/Admin)."""
    try:
        book = await update_book(db, book_id, data.model_dump(exclude_unset=True), current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    return book


@router.delete(
    "/{book_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a book",
    description="Permanently delete a book from the catalog. Requires Admin role.",
    responses={
        204: {"description": "Book deleted successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Book not found"},
    },
)
async def delete_book_endpoint(
    book_id: str,
    current_user: AdminOnly,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete a book (Admin only)."""
    deleted = await delete_book(db, book_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

