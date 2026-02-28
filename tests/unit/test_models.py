"""
Unit tests for database models – enums, defaults, constraints, relationships.
"""
from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest

from app.db.models import (
    User, UserRole,
    LibraryBranch,
    Book,
    Loan, LoanStatus,
    LoanStatusHistory,
    BlacklistedToken,
)


# ─── Enum values ────────────────────────────────────────────────


class TestUserRoleEnum:
    def test_member_value(self):
        assert UserRole.MEMBER.value == "member"

    def test_librarian_value(self):
        assert UserRole.LIBRARIAN.value == "librarian"

    def test_admin_value(self):
        assert UserRole.ADMIN.value == "admin"

    def test_all_roles(self):
        assert set(UserRole) == {UserRole.MEMBER, UserRole.LIBRARIAN, UserRole.ADMIN}

    def test_role_is_str_enum(self):
        assert isinstance(UserRole.MEMBER, str)
        assert UserRole.MEMBER == "member"


class TestLoanStatusEnum:
    def test_all_statuses(self):
        expected = {"requested", "canceled", "approved", "borrowed", "overdue", "returned", "lost"}
        assert {s.value for s in LoanStatus} == expected

    def test_status_is_str_enum(self):
        assert isinstance(LoanStatus.REQUESTED, str)
        assert LoanStatus.REQUESTED == "requested"


# ─── Model instantiation & defaults ────────────────────────────


class TestUserModel:
    def test_default_role_is_member(self, make_user):
        user = make_user()
        assert user.role == UserRole.MEMBER

    def test_default_is_active(self, make_user):
        user = make_user()
        assert user.is_active is True

    def test_default_is_not_built_in(self, make_user):
        user = make_user()
        assert user.is_built_in is False

    def test_built_in_flag(self, make_user):
        user = make_user(is_built_in=True)
        assert user.is_built_in is True

    def test_admin_role(self, make_user):
        user = make_user(role=UserRole.ADMIN)
        assert user.role == UserRole.ADMIN

    def test_inactive_user(self, make_user):
        user = make_user(is_active=False)
        assert user.is_active is False

    def test_user_has_id(self, make_user):
        user = make_user()
        assert user.id is not None
        assert isinstance(user.id, str)


class TestLibraryBranchModel:
    def test_branch_creation(self, make_branch):
        branch = make_branch(name="Downtown", address="1 Main St")
        assert branch.name == "Downtown"
        assert branch.address == "1 Main St"

    def test_default_is_active(self, make_branch):
        branch = make_branch()
        assert branch.is_active is True

    def test_inactive_branch(self, make_branch):
        branch = make_branch(is_active=False)
        assert branch.is_active is False


class TestBookModel:
    def test_book_creation(self, make_book):
        book = make_book(title="Clean Code", author="Robert Martin")
        assert book.title == "Clean Code"
        assert book.author == "Robert Martin"

    def test_default_copies(self, make_book):
        book = make_book(total_copies=5, available_copies=5)
        assert book.total_copies == 5
        assert book.available_copies == 5

    def test_book_has_branch_id(self, make_book):
        bid = str(uuid4())
        book = make_book(branch_id=bid)
        assert book.branch_id == bid


class TestLoanModel:
    def test_loan_creation(self, make_loan):
        loan = make_loan()
        assert loan.status == LoanStatus.REQUESTED
        assert loan.late_fee == 0.0

    def test_loan_due_date_after_borrow(self, make_loan):
        loan = make_loan()
        assert loan.due_date > loan.borrow_date

    def test_return_date_initially_none(self, make_loan):
        loan = make_loan()
        assert loan.return_date is None


class TestLoanStatusHistoryModel:
    def test_creation_defaults(self):
        history = LoanStatusHistory(
            loan_id="loan-1",
            previous_status=LoanStatus.REQUESTED,
            new_status=LoanStatus.APPROVED,
            changed_by="user-1",
            notes="Approved by librarian",
        )
        assert history.previous_status == LoanStatus.REQUESTED
        assert history.new_status == LoanStatus.APPROVED
        assert history.notes == "Approved by librarian"

    def test_nullable_previous_status(self):
        history = LoanStatusHistory(
            loan_id="loan-2",
            previous_status=None,
            new_status=LoanStatus.REQUESTED,
        )
        assert history.previous_status is None

    def test_nullable_changed_by(self):
        history = LoanStatusHistory(
            loan_id="loan-3",
            new_status=LoanStatus.OVERDUE,
            changed_by=None,
            notes="System auto",
        )
        assert history.changed_by is None


class TestBlacklistedTokenModel:
    def test_creation(self):
        token = BlacklistedToken(
            jti="test-jti",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        assert token.jti == "test-jti"
        assert token.expires_at is not None


# ─── Model persistence (in-memory DB) ──────────────────────────


class TestModelPersistence:
    @pytest.mark.asyncio
    async def test_create_user(self, db_session, make_user):
        user = make_user(email="persist@test.com")
        db_session.add(user)
        await db_session.flush()

        from sqlalchemy import select
        result = await db_session.execute(select(User).where(User.email == "persist@test.com"))
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.email == "persist@test.com"

    @pytest.mark.asyncio
    async def test_create_branch(self, db_session, make_branch):
        branch = make_branch(name="Persist Branch")
        db_session.add(branch)
        await db_session.flush()

        from sqlalchemy import select
        result = await db_session.execute(
            select(LibraryBranch).where(LibraryBranch.name == "Persist Branch")
        )
        found = result.scalar_one_or_none()
        assert found is not None

    @pytest.mark.asyncio
    async def test_create_book_with_branch(self, db_session, make_branch, make_book):
        branch = make_branch()
        db_session.add(branch)
        await db_session.flush()

        book = make_book(branch_id=branch.id)
        db_session.add(book)
        await db_session.flush()

        from sqlalchemy import select
        result = await db_session.execute(select(Book).where(Book.branch_id == branch.id))
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.branch_id == branch.id

    @pytest.mark.asyncio
    async def test_create_loan_with_relationships(
        self, db_session, make_user, make_branch, make_book, make_loan
    ):
        user = make_user()
        branch = make_branch()
        db_session.add_all([user, branch])
        await db_session.flush()

        book = make_book(branch_id=branch.id)
        db_session.add(book)
        await db_session.flush()

        loan = make_loan(member_id=user.id, book_id=book.id, branch_id=branch.id)
        db_session.add(loan)
        await db_session.flush()

        from sqlalchemy import select
        result = await db_session.execute(select(Loan).where(Loan.member_id == user.id))
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.book_id == book.id

    @pytest.mark.asyncio
    async def test_unique_email_constraint(self, db_session, make_user):
        u1 = make_user(email="unique@test.com")
        u2 = make_user(email="unique@test.com")
        db_session.add(u1)
        await db_session.flush()
        db_session.add(u2)
        with pytest.raises(Exception):  # IntegrityError
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_unique_isbn_constraint(self, db_session, make_branch, make_book):
        branch = make_branch()
        db_session.add(branch)
        await db_session.flush()

        b1 = make_book(isbn="9781234567890", branch_id=branch.id)
        b2 = make_book(isbn="9781234567890", branch_id=branch.id)
        db_session.add(b1)
        await db_session.flush()
        db_session.add(b2)
        with pytest.raises(Exception):  # IntegrityError
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_blacklisted_token_creation(self, db_session):
        token = BlacklistedToken(
            jti="test-jti-123",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db_session.add(token)
        await db_session.flush()

        from sqlalchemy import select
        result = await db_session.execute(
            select(BlacklistedToken).where(BlacklistedToken.jti == "test-jti-123")
        )
        found = result.scalar_one_or_none()
        assert found is not None

    @pytest.mark.asyncio
    async def test_loan_status_history(self, db_session, make_user, make_branch, make_book, make_loan):
        user = make_user()
        branch = make_branch()
        db_session.add_all([user, branch])
        await db_session.flush()

        book = make_book(branch_id=branch.id)
        db_session.add(book)
        await db_session.flush()

        loan = make_loan(member_id=user.id, book_id=book.id, branch_id=branch.id)
        db_session.add(loan)
        await db_session.flush()

        history = LoanStatusHistory(
            loan_id=loan.id,
            previous_status=None,
            new_status=LoanStatus.REQUESTED,
            changed_by=user.id,
            notes="Initial request",
        )
        db_session.add(history)
        await db_session.flush()

        from sqlalchemy import select
        result = await db_session.execute(
            select(LoanStatusHistory).where(LoanStatusHistory.loan_id == loan.id)
        )
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.new_status == LoanStatus.REQUESTED

