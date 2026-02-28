"""
Shared fixtures for unit tests.
Uses an in-memory SQLite database for fast isolated testing.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.models import (
    Base, User, UserRole, LibraryBranch, Book, Loan, LoanStatus,
    LoanStatusHistory, BlacklistedToken,
)
from app.core.security import hash_password


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for all tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def async_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Enable foreign key support for SQLite
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine) -> AsyncSession:
    """Provide a transactional database session for each test."""
    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


# ─── Helper factories ───────────────────────────────────────────


@pytest.fixture
def make_user():
    """Factory fixture to create User instances."""
    def _make(
        email: str = None,
        password: str = "testpassword123",
        full_name: str = "Test User",
        role: UserRole = UserRole.MEMBER,
        is_active: bool = True,
        is_built_in: bool = False,
    ) -> User:
        return User(
            id=str(uuid4()),
            email=email or f"user-{uuid4().hex[:8]}@test.com",
            hashed_password=hash_password(password),
            full_name=full_name,
            role=role,
            is_active=is_active,
            is_built_in=is_built_in,
        )
    return _make


@pytest.fixture
def make_branch():
    """Factory fixture to create LibraryBranch instances."""
    def _make(
        name: str = "Main Branch",
        address: str = "123 Test Street",
        description: str = "A test branch",
        phone_number: str = "555-0100",
        email: str = None,
        is_active: bool = True,
    ) -> LibraryBranch:
        return LibraryBranch(
            id=str(uuid4()),
            name=name,
            address=address,
            description=description,
            phone_number=phone_number,
            email=email or f"branch-{uuid4().hex[:6]}@test.com",
            is_active=is_active,
        )
    return _make


@pytest.fixture
def make_book():
    """Factory fixture to create Book instances."""
    def _make(
        title: str = "Test Book",
        author: str = "Test Author",
        isbn: str = None,
        description: str = "A test book",
        genre: str = "Fiction",
        publication_year: int = 2024,
        total_copies: int = 5,
        available_copies: int = 5,
        branch_id: str = None,
    ) -> Book:
        return Book(
            id=str(uuid4()),
            title=title,
            author=author,
            isbn=isbn or f"978{uuid4().int % 10**10:010d}",
            description=description,
            genre=genre,
            publication_year=publication_year,
            total_copies=total_copies,
            available_copies=available_copies,
            branch_id=branch_id or str(uuid4()),
        )
    return _make


@pytest.fixture
def make_loan():
    """Factory fixture to create Loan instances."""
    def _make(
        member_id: str = None,
        book_id: str = None,
        branch_id: str = None,
        status: LoanStatus = LoanStatus.REQUESTED,
        borrow_date: datetime = None,
        due_date: datetime = None,
        return_date: datetime = None,
        late_fee: float = 0.0,
        notes: str = None,
    ) -> Loan:
        now = datetime.now(timezone.utc)
        return Loan(
            id=str(uuid4()),
            member_id=member_id or str(uuid4()),
            book_id=book_id or str(uuid4()),
            branch_id=branch_id or str(uuid4()),
            borrow_date=borrow_date or now,
            due_date=due_date or now + timedelta(days=14),
            return_date=return_date,
            status=status,
            late_fee=late_fee,
            notes=notes,
        )
    return _make

