"""
Unit tests for app.services.loan – loan creation, status transitions, permissions.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db.models import (
    Loan, LoanStatus, LoanStatusHistory, Book, User, UserRole,
)
from app.services.loan import (
    create_loan,
    update_loan_status,
    get_loans,
    get_loan_by_id,
    _calculate_late_fee,
    calculate_pages,
    VALID_TRANSITIONS,
    MAX_ACTIVE_LOANS,
    LATE_FEE_PER_DAY,
    DEFAULT_LOAN_DAYS,
)


# ─── Late fee calculation (pure function) ───────────────────────


class TestCalculateLateFee:
    def test_no_fee_when_returned_early(self):
        due = datetime(2025, 3, 1, tzinfo=timezone.utc)
        returned = datetime(2025, 2, 28, tzinfo=timezone.utc)
        assert _calculate_late_fee(due, returned) == 0.00

    def test_no_fee_when_returned_on_time(self):
        due = datetime(2025, 3, 1, tzinfo=timezone.utc)
        returned = datetime(2025, 3, 1, tzinfo=timezone.utc)
        assert _calculate_late_fee(due, returned) == 0.00

    def test_fee_for_one_day_late(self):
        due = datetime(2025, 3, 1, tzinfo=timezone.utc)
        returned = datetime(2025, 3, 2, tzinfo=timezone.utc)
        assert _calculate_late_fee(due, returned) == LATE_FEE_PER_DAY

    def test_fee_for_multiple_days(self):
        due = datetime(2025, 3, 1, tzinfo=timezone.utc)
        returned = datetime(2025, 3, 11, tzinfo=timezone.utc)
        assert _calculate_late_fee(due, returned) == 10 * LATE_FEE_PER_DAY

    def test_fee_rounds_to_two_decimals(self):
        due = datetime(2025, 3, 1, tzinfo=timezone.utc)
        returned = datetime(2025, 3, 4, tzinfo=timezone.utc)
        fee = _calculate_late_fee(due, returned)
        assert fee == round(3 * LATE_FEE_PER_DAY, 2)


# ─── Valid transitions map ──────────────────────────────────────


class TestValidTransitions:
    def test_requested_can_be_canceled_or_approved(self):
        assert set(VALID_TRANSITIONS[LoanStatus.REQUESTED]) == {
            LoanStatus.CANCELED,
            LoanStatus.APPROVED,
        }

    def test_approved_can_be_borrowed_or_canceled(self):
        assert set(VALID_TRANSITIONS[LoanStatus.APPROVED]) == {
            LoanStatus.BORROWED,
            LoanStatus.CANCELED,
        }

    def test_borrowed_transitions(self):
        assert set(VALID_TRANSITIONS[LoanStatus.BORROWED]) == {
            LoanStatus.RETURNED,
            LoanStatus.LOST,
            LoanStatus.OVERDUE,
        }

    def test_overdue_transitions(self):
        assert set(VALID_TRANSITIONS[LoanStatus.OVERDUE]) == {
            LoanStatus.RETURNED,
            LoanStatus.LOST,
        }

    def test_returned_has_no_transitions(self):
        assert VALID_TRANSITIONS.get(LoanStatus.RETURNED) is None

    def test_canceled_has_no_transitions(self):
        assert VALID_TRANSITIONS.get(LoanStatus.CANCELED) is None

    def test_lost_has_no_transitions(self):
        assert VALID_TRANSITIONS.get(LoanStatus.LOST) is None


# ─── Loan creation ──────────────────────────────────────────────


class TestCreateLoan:
    @pytest.mark.asyncio
    async def test_create_success(self, db_session, make_user, make_branch, make_book):
        user = make_user()
        branch = make_branch()
        db_session.add_all([user, branch])
        await db_session.flush()

        book = make_book(branch_id=branch.id, available_copies=3, total_copies=3)
        db_session.add(book)
        await db_session.flush()

        loan = await create_loan(db_session, user.id, book.id, branch.id)
        assert loan.status == LoanStatus.REQUESTED
        assert loan.member_id == user.id
        assert loan.book_id == book.id
        assert loan.branch_id == branch.id

    @pytest.mark.asyncio
    async def test_create_decrements_available_copies(self, db_session, make_user, make_branch, make_book):
        user = make_user()
        branch = make_branch()
        db_session.add_all([user, branch])
        await db_session.flush()

        book = make_book(branch_id=branch.id, available_copies=3, total_copies=3)
        db_session.add(book)
        await db_session.flush()

        await create_loan(db_session, user.id, book.id, branch.id)
        await db_session.refresh(book)
        assert book.available_copies == 2

    @pytest.mark.asyncio
    async def test_create_sets_due_date_14_days(self, db_session, make_user, make_branch, make_book):
        user = make_user()
        branch = make_branch()
        db_session.add_all([user, branch])
        await db_session.flush()

        book = make_book(branch_id=branch.id)
        db_session.add(book)
        await db_session.flush()

        loan = await create_loan(db_session, user.id, book.id, branch.id)
        diff = (loan.due_date - loan.borrow_date).days
        assert diff == DEFAULT_LOAN_DAYS

    @pytest.mark.asyncio
    async def test_create_records_status_history(self, db_session, make_user, make_branch, make_book):
        user = make_user()
        branch = make_branch()
        db_session.add_all([user, branch])
        await db_session.flush()

        book = make_book(branch_id=branch.id)
        db_session.add(book)
        await db_session.flush()

        loan = await create_loan(db_session, user.id, book.id, branch.id)

        result = await db_session.execute(
            select(LoanStatusHistory).where(LoanStatusHistory.loan_id == loan.id)
        )
        history = result.scalars().all()
        assert len(history) == 1
        assert history[0].new_status == LoanStatus.REQUESTED
        assert history[0].previous_status is None

    @pytest.mark.asyncio
    async def test_create_no_available_copies_raises(self, db_session, make_user, make_branch, make_book):
        user = make_user()
        branch = make_branch()
        db_session.add_all([user, branch])
        await db_session.flush()

        book = make_book(branch_id=branch.id, available_copies=0, total_copies=1)
        db_session.add(book)
        await db_session.flush()

        with pytest.raises(ValueError, match="No available copies"):
            await create_loan(db_session, user.id, book.id, branch.id)

    @pytest.mark.asyncio
    async def test_create_wrong_branch_raises(self, db_session, make_user, make_branch, make_book):
        user = make_user()
        branch1 = make_branch(name="Branch 1")
        branch2 = make_branch(name="Branch 2")
        db_session.add_all([user, branch1, branch2])
        await db_session.flush()

        book = make_book(branch_id=branch1.id)
        db_session.add(book)
        await db_session.flush()

        with pytest.raises(ValueError, match="does not belong"):
            await create_loan(db_session, user.id, book.id, branch2.id)

    @pytest.mark.asyncio
    async def test_create_book_not_found_raises(self, db_session, make_user, make_branch):
        user = make_user()
        branch = make_branch()
        db_session.add_all([user, branch])
        await db_session.flush()

        with pytest.raises(ValueError, match="Book not found"):
            await create_loan(db_session, user.id, "nonexistent-book-id", branch.id)

    @pytest.mark.asyncio
    async def test_max_active_loans_limit(self, db_session, make_user, make_branch, make_book):
        user = make_user()
        branch = make_branch()
        db_session.add_all([user, branch])
        await db_session.flush()

        # Create MAX_ACTIVE_LOANS books and loans
        for i in range(MAX_ACTIVE_LOANS):
            book = make_book(branch_id=branch.id)
            db_session.add(book)
            await db_session.flush()
            await create_loan(db_session, user.id, book.id, branch.id)

        # One more should fail
        extra_book = make_book(branch_id=branch.id)
        db_session.add(extra_book)
        await db_session.flush()

        with pytest.raises(ValueError, match="Maximum"):
            await create_loan(db_session, user.id, extra_book.id, branch.id)

    @pytest.mark.asyncio
    async def test_create_with_notes(self, db_session, make_user, make_branch, make_book):
        user = make_user()
        branch = make_branch()
        db_session.add_all([user, branch])
        await db_session.flush()

        book = make_book(branch_id=branch.id)
        db_session.add(book)
        await db_session.flush()

        loan = await create_loan(
            db_session, user.id, book.id, branch.id, notes="Rush request"
        )
        assert loan.notes == "Rush request"


# ─── Loan status updates ───────────────────────────────────────


class TestUpdateLoanStatus:
    async def _setup_loan(self, db_session, make_user, make_branch, make_book,
                          status=LoanStatus.REQUESTED, role=UserRole.MEMBER):
        """Helper: create a user, branch, book, and loan for status tests."""
        member = make_user(role=UserRole.MEMBER)
        actor = make_user(role=role)
        branch = make_branch()
        db_session.add_all([member, actor, branch])
        await db_session.flush()

        book = make_book(branch_id=branch.id, available_copies=5, total_copies=5)
        db_session.add(book)
        await db_session.flush()

        loan = await create_loan(db_session, member.id, book.id, branch.id)
        # If we need a different starting status, set it directly
        if status != LoanStatus.REQUESTED:
            loan.status = status
            await db_session.flush()

        return loan, member, actor, book

    @pytest.mark.asyncio
    async def test_member_cancel_requested(self, db_session, make_user, make_branch, make_book):
        loan, member, _, book = await self._setup_loan(
            db_session, make_user, make_branch, make_book
        )
        updated = await update_loan_status(
            db_session, loan.id, LoanStatus.CANCELED, member
        )
        assert updated.status == LoanStatus.CANCELED

    @pytest.mark.asyncio
    async def test_member_cancel_restores_copies(self, db_session, make_user, make_branch, make_book):
        loan, member, _, book = await self._setup_loan(
            db_session, make_user, make_branch, make_book
        )
        copies_before = book.available_copies
        await update_loan_status(db_session, loan.id, LoanStatus.CANCELED, member)
        await db_session.refresh(book)
        assert book.available_copies == copies_before + 1

    @pytest.mark.asyncio
    async def test_member_cannot_approve(self, db_session, make_user, make_branch, make_book):
        loan, member, _, _ = await self._setup_loan(
            db_session, make_user, make_branch, make_book
        )
        with pytest.raises(PermissionError, match="Members cannot"):
            await update_loan_status(
                db_session, loan.id, LoanStatus.APPROVED, member
            )

    @pytest.mark.asyncio
    async def test_member_cannot_modify_others_loan(self, db_session, make_user, make_branch, make_book):
        loan, _, _, _ = await self._setup_loan(
            db_session, make_user, make_branch, make_book
        )
        other_member = make_user(role=UserRole.MEMBER)
        db_session.add(other_member)
        await db_session.flush()

        with pytest.raises(PermissionError, match="your own"):
            await update_loan_status(
                db_session, loan.id, LoanStatus.CANCELED, other_member
            )

    @pytest.mark.asyncio
    async def test_librarian_approve(self, db_session, make_user, make_branch, make_book):
        loan, _, actor, _ = await self._setup_loan(
            db_session, make_user, make_branch, make_book,
            role=UserRole.LIBRARIAN,
        )
        updated = await update_loan_status(
            db_session, loan.id, LoanStatus.APPROVED, actor
        )
        assert updated.status == LoanStatus.APPROVED

    @pytest.mark.asyncio
    async def test_librarian_borrow_after_approve(self, db_session, make_user, make_branch, make_book):
        loan, _, actor, _ = await self._setup_loan(
            db_session, make_user, make_branch, make_book,
            status=LoanStatus.APPROVED,
            role=UserRole.LIBRARIAN,
        )
        updated = await update_loan_status(
            db_session, loan.id, LoanStatus.BORROWED, actor
        )
        assert updated.status == LoanStatus.BORROWED

    @pytest.mark.asyncio
    async def test_librarian_return(self, db_session, make_user, make_branch, make_book):
        loan, _, actor, book = await self._setup_loan(
            db_session, make_user, make_branch, make_book,
            status=LoanStatus.BORROWED,
            role=UserRole.LIBRARIAN,
        )
        copies_before = book.available_copies
        updated = await update_loan_status(
            db_session, loan.id, LoanStatus.RETURNED, actor
        )
        assert updated.status == LoanStatus.RETURNED
        assert updated.return_date is not None
        await db_session.refresh(book)
        assert book.available_copies == copies_before + 1

    @pytest.mark.asyncio
    async def test_return_overdue_calculates_fee(self, db_session, make_user, make_branch, make_book):
        loan, _, actor, _ = await self._setup_loan(
            db_session, make_user, make_branch, make_book,
            status=LoanStatus.OVERDUE,
            role=UserRole.LIBRARIAN,
        )
        # Make it 5 days overdue
        loan.due_date = datetime.now(timezone.utc) - timedelta(days=5)
        await db_session.flush()

        updated = await update_loan_status(
            db_session, loan.id, LoanStatus.RETURNED, actor
        )
        assert updated.late_fee > 0

    @pytest.mark.asyncio
    async def test_mark_as_lost(self, db_session, make_user, make_branch, make_book):
        loan, _, actor, _ = await self._setup_loan(
            db_session, make_user, make_branch, make_book,
            status=LoanStatus.BORROWED,
            role=UserRole.LIBRARIAN,
        )
        updated = await update_loan_status(
            db_session, loan.id, LoanStatus.LOST, actor
        )
        assert updated.status == LoanStatus.LOST

    @pytest.mark.asyncio
    async def test_invalid_transition_raises(self, db_session, make_user, make_branch, make_book):
        loan, _, actor, _ = await self._setup_loan(
            db_session, make_user, make_branch, make_book,
            status=LoanStatus.RETURNED,
            role=UserRole.LIBRARIAN,
        )
        with pytest.raises(ValueError, match="Cannot transition"):
            await update_loan_status(
                db_session, loan.id, LoanStatus.BORROWED, actor
            )

    @pytest.mark.asyncio
    async def test_status_history_recorded(self, db_session, make_user, make_branch, make_book):
        loan, _, actor, _ = await self._setup_loan(
            db_session, make_user, make_branch, make_book,
            role=UserRole.LIBRARIAN,
        )
        await update_loan_status(
            db_session, loan.id, LoanStatus.APPROVED, actor, notes="Looks good"
        )

        result = await db_session.execute(
            select(LoanStatusHistory).where(LoanStatusHistory.loan_id == loan.id)
        )
        history = result.scalars().all()
        # 1 from creation + 1 from status update
        assert len(history) == 2
        last = history[-1]
        assert last.previous_status == LoanStatus.REQUESTED
        assert last.new_status == LoanStatus.APPROVED
        assert last.notes == "Looks good"

    @pytest.mark.asyncio
    async def test_loan_not_found_raises(self, db_session, make_user):
        actor = make_user(role=UserRole.LIBRARIAN)
        db_session.add(actor)
        await db_session.flush()

        with pytest.raises(ValueError, match="Loan not found"):
            await update_loan_status(
                db_session, "nonexistent", LoanStatus.APPROVED, actor
            )


# ─── Loan queries ───────────────────────────────────────────────


class TestGetLoans:
    @pytest.mark.asyncio
    async def test_empty(self, db_session):
        loans, total = await get_loans(db_session)
        assert loans == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_filter_by_member(self, db_session, make_user, make_branch, make_book):
        u1 = make_user()
        u2 = make_user()
        branch = make_branch()
        db_session.add_all([u1, u2, branch])
        await db_session.flush()

        b1 = make_book(branch_id=branch.id)
        b2 = make_book(branch_id=branch.id)
        db_session.add_all([b1, b2])
        await db_session.flush()

        await create_loan(db_session, u1.id, b1.id, branch.id)
        await create_loan(db_session, u2.id, b2.id, branch.id)

        loans, total = await get_loans(db_session, member_id=u1.id)
        assert total == 1

    @pytest.mark.asyncio
    async def test_filter_by_status(self, db_session, make_user, make_branch, make_book):
        user = make_user()
        branch = make_branch()
        db_session.add_all([user, branch])
        await db_session.flush()

        b1 = make_book(branch_id=branch.id)
        b2 = make_book(branch_id=branch.id)
        db_session.add_all([b1, b2])
        await db_session.flush()

        loan1 = await create_loan(db_session, user.id, b1.id, branch.id)
        loan2 = await create_loan(db_session, user.id, b2.id, branch.id)
        # Change one to approved
        librarian = make_user(role=UserRole.LIBRARIAN)
        db_session.add(librarian)
        await db_session.flush()
        await update_loan_status(db_session, loan1.id, LoanStatus.APPROVED, librarian)

        loans, total = await get_loans(db_session, status=LoanStatus.APPROVED)
        assert total == 1

    @pytest.mark.asyncio
    async def test_pagination(self, db_session, make_user, make_branch, make_book):
        user = make_user()
        branch = make_branch()
        db_session.add_all([user, branch])
        await db_session.flush()

        for i in range(4):
            book = make_book(branch_id=branch.id)
            db_session.add(book)
            await db_session.flush()
            await create_loan(db_session, user.id, book.id, branch.id)

        loans, total = await get_loans(db_session, page=1, size=2)
        assert len(loans) == 2
        assert total == 4


class TestGetLoanById:
    @pytest.mark.asyncio
    async def test_found(self, db_session, make_user, make_branch, make_book):
        user = make_user()
        branch = make_branch()
        db_session.add_all([user, branch])
        await db_session.flush()

        book = make_book(branch_id=branch.id)
        db_session.add(book)
        await db_session.flush()

        loan = await create_loan(db_session, user.id, book.id, branch.id)
        found = await get_loan_by_id(db_session, loan.id)
        assert found is not None

    @pytest.mark.asyncio
    async def test_not_found(self, db_session):
        found = await get_loan_by_id(db_session, "bad-id")
        assert found is None


class TestLoanCalculatePages:
    def test_exact(self):
        assert calculate_pages(20, 10) == 2

    def test_remainder(self):
        assert calculate_pages(25, 10) == 3

    def test_zero(self):
        assert calculate_pages(0, 10) == 0

    def test_zero_size(self):
        assert calculate_pages(10, 0) == 0


class TestAdminStatusTransitions:
    """Admin should be able to perform any valid transition."""

    async def _setup_loan(self, db_session, make_user, make_branch, make_book,
                          status=LoanStatus.REQUESTED):
        member = make_user(role=UserRole.MEMBER)
        admin = make_user(role=UserRole.ADMIN)
        branch = make_branch()
        db_session.add_all([member, admin, branch])
        await db_session.flush()

        book = make_book(branch_id=branch.id, available_copies=5, total_copies=5)
        db_session.add(book)
        await db_session.flush()

        loan = await create_loan(db_session, member.id, book.id, branch.id)
        if status != LoanStatus.REQUESTED:
            loan.status = status
            await db_session.flush()

        return loan, member, admin, book

    @pytest.mark.asyncio
    async def test_admin_can_approve(self, db_session, make_user, make_branch, make_book):
        loan, _, admin, _ = await self._setup_loan(db_session, make_user, make_branch, make_book)
        updated = await update_loan_status(db_session, loan.id, LoanStatus.APPROVED, admin)
        assert updated.status == LoanStatus.APPROVED

    @pytest.mark.asyncio
    async def test_admin_can_mark_borrowed(self, db_session, make_user, make_branch, make_book):
        loan, _, admin, _ = await self._setup_loan(
            db_session, make_user, make_branch, make_book, status=LoanStatus.APPROVED
        )
        updated = await update_loan_status(db_session, loan.id, LoanStatus.BORROWED, admin)
        assert updated.status == LoanStatus.BORROWED

    @pytest.mark.asyncio
    async def test_admin_can_mark_returned(self, db_session, make_user, make_branch, make_book):
        loan, _, admin, _ = await self._setup_loan(
            db_session, make_user, make_branch, make_book, status=LoanStatus.BORROWED
        )
        updated = await update_loan_status(db_session, loan.id, LoanStatus.RETURNED, admin)
        assert updated.status == LoanStatus.RETURNED

    @pytest.mark.asyncio
    async def test_admin_can_mark_lost(self, db_session, make_user, make_branch, make_book):
        loan, _, admin, _ = await self._setup_loan(
            db_session, make_user, make_branch, make_book, status=LoanStatus.BORROWED
        )
        updated = await update_loan_status(db_session, loan.id, LoanStatus.LOST, admin)
        assert updated.status == LoanStatus.LOST


class TestCancelFromApproved:
    @pytest.mark.asyncio
    async def test_cancel_approved_restores_copies(self, db_session, make_user, make_branch, make_book):
        """Canceling an approved loan should restore available copies."""
        member = make_user(role=UserRole.MEMBER)
        librarian = make_user(role=UserRole.LIBRARIAN)
        branch = make_branch()
        db_session.add_all([member, librarian, branch])
        await db_session.flush()

        book = make_book(branch_id=branch.id, available_copies=5, total_copies=5)
        db_session.add(book)
        await db_session.flush()

        loan = await create_loan(db_session, member.id, book.id, branch.id)
        await update_loan_status(db_session, loan.id, LoanStatus.APPROVED, librarian)

        copies_before = book.available_copies
        await update_loan_status(db_session, loan.id, LoanStatus.CANCELED, librarian)
        await db_session.refresh(book)
        assert book.available_copies == copies_before + 1


class TestReturnOnTime:
    @pytest.mark.asyncio
    async def test_return_on_time_no_fee(self, db_session, make_user, make_branch, make_book):
        """Returning a borrowed book before due date should have no late fee."""
        member = make_user(role=UserRole.MEMBER)
        librarian = make_user(role=UserRole.LIBRARIAN)
        branch = make_branch()
        db_session.add_all([member, librarian, branch])
        await db_session.flush()

        book = make_book(branch_id=branch.id, available_copies=5, total_copies=5)
        db_session.add(book)
        await db_session.flush()

        loan = await create_loan(db_session, member.id, book.id, branch.id)
        # Move to BORROWED state
        loan.status = LoanStatus.BORROWED
        await db_session.flush()

        # Due date is in the future – return on time
        updated = await update_loan_status(db_session, loan.id, LoanStatus.RETURNED, librarian)
        assert updated.late_fee == 0.0 or updated.late_fee is None or updated.late_fee == 0


class TestLostFromOverdue:
    @pytest.mark.asyncio
    async def test_lost_from_overdue(self, db_session, make_user, make_branch, make_book):
        """Overdue loan can be marked as lost."""
        member = make_user(role=UserRole.MEMBER)
        librarian = make_user(role=UserRole.LIBRARIAN)
        branch = make_branch()
        db_session.add_all([member, librarian, branch])
        await db_session.flush()

        book = make_book(branch_id=branch.id, available_copies=5, total_copies=5)
        db_session.add(book)
        await db_session.flush()

        loan = await create_loan(db_session, member.id, book.id, branch.id)
        loan.status = LoanStatus.OVERDUE
        await db_session.flush()

        updated = await update_loan_status(db_session, loan.id, LoanStatus.LOST, librarian)
        assert updated.status == LoanStatus.LOST


class TestGetLoansSort:
    @pytest.mark.asyncio
    async def test_sort_loans(self, db_session, make_user, make_branch, make_book):
        user = make_user()
        branch = make_branch()
        db_session.add_all([user, branch])
        await db_session.flush()

        for i in range(3):
            book = make_book(branch_id=branch.id)
            db_session.add(book)
            await db_session.flush()
            await create_loan(db_session, user.id, book.id, branch.id)

        loans, total = await get_loans(db_session, sort_by="created_at", sort_order="desc")
        assert total == 3

    @pytest.mark.asyncio
    async def test_filter_by_branch(self, db_session, make_user, make_branch, make_book):
        user = make_user()
        branch1 = make_branch(name="B1")
        branch2 = make_branch(name="B2")
        db_session.add_all([user, branch1, branch2])
        await db_session.flush()

        b1 = make_book(branch_id=branch1.id)
        b2 = make_book(branch_id=branch2.id)
        db_session.add_all([b1, b2])
        await db_session.flush()

        await create_loan(db_session, user.id, b1.id, branch1.id)
        await create_loan(db_session, user.id, b2.id, branch2.id)

        loans, total = await get_loans(db_session, branch_id=branch1.id)
        assert total == 1

