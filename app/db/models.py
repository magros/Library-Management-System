import enum
from datetime import datetime, timezone
from typing import Optional, List
from uuid import uuid4

from sqlalchemy import (
    String,
    Text,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
    Numeric,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ──────────────────────────── Enums ────────────────────────────


class UserRole(str, enum.Enum):
    MEMBER = "member"
    LIBRARIAN = "librarian"
    ADMIN = "admin"


class LoanStatus(str, enum.Enum):
    REQUESTED = "requested"
    CANCELED = "canceled"
    APPROVED = "approved"
    BORROWED = "borrowed"
    OVERDUE = "overdue"
    RETURNED = "returned"
    LOST = "lost"


# ──────────────────────────── Models ────────────────────────────


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), nullable=False, default=UserRole.MEMBER
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_built_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    loans: Mapped[List["Loan"]] = relationship("Loan", back_populates="member", lazy="selectin")


class LibraryBranch(Base):
    __tablename__ = "library_branches"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    books: Mapped[List["Book"]] = relationship("Book", back_populates="branch", lazy="selectin")
    loans: Mapped[List["Loan"]] = relationship("Loan", back_populates="branch", lazy="selectin")


class Book(Base):
    __tablename__ = "books"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    isbn: Mapped[str] = mapped_column(String(13), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    genre: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    publication_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_copies: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    available_copies: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    branch_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("library_branches.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    branch: Mapped["LibraryBranch"] = relationship("LibraryBranch", back_populates="books")
    loans: Mapped[List["Loan"]] = relationship("Loan", back_populates="book", lazy="selectin")

    __table_args__ = (
        CheckConstraint("total_copies >= 0", name="ck_books_total_copies_positive"),
        CheckConstraint("available_copies >= 0", name="ck_books_available_copies_positive"),
        CheckConstraint(
            "available_copies <= total_copies", name="ck_books_available_lte_total"
        ),
    )


class Loan(Base):
    __tablename__ = "loans"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    member_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id"), nullable=False
    )
    book_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("books.id"), nullable=False
    )
    branch_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("library_branches.id"), nullable=False
    )
    borrow_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    return_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[LoanStatus] = mapped_column(
        Enum(LoanStatus, name="loan_status"),
        nullable=False,
        default=LoanStatus.REQUESTED,
        index=True,
    )
    late_fee: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.00)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    member: Mapped["User"] = relationship("User", back_populates="loans")
    book: Mapped["Book"] = relationship("Book", back_populates="loans")
    branch: Mapped["LibraryBranch"] = relationship("LibraryBranch", back_populates="loans")
    status_history: Mapped[List["LoanStatusHistory"]] = relationship(
        "LoanStatusHistory", back_populates="loan", lazy="selectin", order_by="LoanStatusHistory.changed_at"
    )

    __table_args__ = (
        Index("ix_loans_member_status", "member_id", "status"),
    )


class LoanStatusHistory(Base):
    __tablename__ = "loan_status_history"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    loan_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("loans.id"), nullable=False
    )
    previous_status: Mapped[Optional[LoanStatus]] = mapped_column(
        Enum(LoanStatus, name="loan_status", create_type=False), nullable=True
    )
    new_status: Mapped[LoanStatus] = mapped_column(
        Enum(LoanStatus, name="loan_status", create_type=False), nullable=False
    )
    changed_by: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    loan: Mapped["Loan"] = relationship("Loan", back_populates="status_history")


class BlacklistedToken(Base):
    __tablename__ = "blacklisted_tokens"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    jti: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

