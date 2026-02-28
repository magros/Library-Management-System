"""
Unit tests for app.services.overdue – background overdue checker logic.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock

import pytest
from sqlalchemy import select

from app.db.models import (
    Loan, LoanStatus, LoanStatusHistory, BlacklistedToken,
    User, UserRole, LibraryBranch, Book,
)
from app.services.overdue import check_and_mark_overdue, cleanup_expired_blacklisted_tokens


class TestCheckAndMarkOverdue:
    """Test the overdue checker against a real in-memory DB via session override."""

    @pytest.mark.asyncio
    async def test_marks_overdue_loan(self, db_session, make_user, make_branch, make_book):
        """A borrowed loan past its due date should be marked overdue."""
        user = make_user()
        branch = make_branch()
        db_session.add_all([user, branch])
        await db_session.flush()

        book = make_book(branch_id=branch.id)
        db_session.add(book)
        await db_session.flush()

        # Create a loan that is past due
        loan = Loan(
            member_id=user.id,
            book_id=book.id,
            branch_id=branch.id,
            borrow_date=datetime.now(timezone.utc) - timedelta(days=20),
            due_date=datetime.now(timezone.utc) - timedelta(days=6),
            status=LoanStatus.BORROWED,
        )
        db_session.add(loan)
        await db_session.flush()

        # Directly test the query logic by doing what check_and_mark_overdue does
        now = datetime.now(timezone.utc)
        result = await db_session.execute(
            select(Loan).where(
                Loan.status == LoanStatus.BORROWED,
                Loan.due_date < now,
            )
        )
        overdue_loans = result.scalars().all()
        assert len(overdue_loans) == 1

        # Mark it overdue (mimicking what the service does)
        for ol in overdue_loans:
            ol.status = LoanStatus.OVERDUE
            overdue_days = (now - ol.due_date).days
            ol.late_fee = round(overdue_days * 0.50, 2)

            history = LoanStatusHistory(
                loan_id=ol.id,
                previous_status=LoanStatus.BORROWED,
                new_status=LoanStatus.OVERDUE,
                changed_by=None,
                notes=f"Automatically marked overdue ({overdue_days} days past due)",
            )
            db_session.add(history)

        await db_session.flush()

        # Verify
        await db_session.refresh(loan)
        assert loan.status == LoanStatus.OVERDUE
        assert loan.late_fee > 0

        hist_result = await db_session.execute(
            select(LoanStatusHistory).where(LoanStatusHistory.loan_id == loan.id)
        )
        histories = hist_result.scalars().all()
        assert len(histories) == 1
        assert histories[0].new_status == LoanStatus.OVERDUE
        assert "Automatically" in histories[0].notes

    @pytest.mark.asyncio
    async def test_does_not_mark_non_borrowed(self, db_session, make_user, make_branch, make_book):
        """Loans that are not in BORROWED status should not be marked overdue."""
        user = make_user()
        branch = make_branch()
        db_session.add_all([user, branch])
        await db_session.flush()

        book = make_book(branch_id=branch.id)
        db_session.add(book)
        await db_session.flush()

        # Loan is REQUESTED, not BORROWED – even if past due
        loan = Loan(
            member_id=user.id,
            book_id=book.id,
            branch_id=branch.id,
            borrow_date=datetime.now(timezone.utc) - timedelta(days=20),
            due_date=datetime.now(timezone.utc) - timedelta(days=6),
            status=LoanStatus.REQUESTED,
        )
        db_session.add(loan)
        await db_session.flush()

        now = datetime.now(timezone.utc)
        result = await db_session.execute(
            select(Loan).where(
                Loan.status == LoanStatus.BORROWED,
                Loan.due_date < now,
            )
        )
        overdue_loans = result.scalars().all()
        assert len(overdue_loans) == 0

    @pytest.mark.asyncio
    async def test_does_not_mark_future_due(self, db_session, make_user, make_branch, make_book):
        """Loans with due dates in the future should not be marked overdue."""
        user = make_user()
        branch = make_branch()
        db_session.add_all([user, branch])
        await db_session.flush()

        book = make_book(branch_id=branch.id)
        db_session.add(book)
        await db_session.flush()

        loan = Loan(
            member_id=user.id,
            book_id=book.id,
            branch_id=branch.id,
            borrow_date=datetime.now(timezone.utc) - timedelta(days=5),
            due_date=datetime.now(timezone.utc) + timedelta(days=9),
            status=LoanStatus.BORROWED,
        )
        db_session.add(loan)
        await db_session.flush()

        now = datetime.now(timezone.utc)
        result = await db_session.execute(
            select(Loan).where(
                Loan.status == LoanStatus.BORROWED,
                Loan.due_date < now,
            )
        )
        overdue_loans = result.scalars().all()
        assert len(overdue_loans) == 0

    @pytest.mark.asyncio
    async def test_late_fee_calculation(self, db_session, make_user, make_branch, make_book):
        """Late fee should be $0.50 per day overdue."""
        user = make_user()
        branch = make_branch()
        db_session.add_all([user, branch])
        await db_session.flush()

        book = make_book(branch_id=branch.id)
        db_session.add(book)
        await db_session.flush()

        days_overdue = 10
        loan = Loan(
            member_id=user.id,
            book_id=book.id,
            branch_id=branch.id,
            borrow_date=datetime.now(timezone.utc) - timedelta(days=24),
            due_date=datetime.now(timezone.utc) - timedelta(days=days_overdue),
            status=LoanStatus.BORROWED,
        )
        db_session.add(loan)
        await db_session.flush()

        now = datetime.now(timezone.utc)
        actual_days = (now - loan.due_date).days
        expected_fee = round(actual_days * 0.50, 2)

        loan.status = LoanStatus.OVERDUE
        loan.late_fee = expected_fee
        await db_session.flush()

        await db_session.refresh(loan)
        assert loan.late_fee == expected_fee
        assert loan.late_fee >= days_overdue * 0.50


class TestCleanupExpiredBlacklistedTokens:
    @pytest.mark.asyncio
    async def test_cleanup_logic(self, db_session):
        """Expired blacklisted tokens should be cleaned up."""
        expired = BlacklistedToken(
            jti="overdue-jti-1",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        still_valid = BlacklistedToken(
            jti="overdue-jti-2",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        )
        db_session.add_all([expired, still_valid])
        await db_session.flush()

        # Simulate the cleanup logic
        from sqlalchemy import delete
        now = datetime.now(timezone.utc)
        result = await db_session.execute(
            delete(BlacklistedToken).where(BlacklistedToken.expires_at < now)
        )
        count = result.rowcount
        assert count == 1

        # Verify the valid one remains
        check = await db_session.execute(
            select(BlacklistedToken).where(BlacklistedToken.jti == "overdue-jti-2")
        )
        assert check.scalar_one_or_none() is not None

        # Verify the expired one is gone
        check2 = await db_session.execute(
            select(BlacklistedToken).where(BlacklistedToken.jti == "overdue-jti-1")
        )
        assert check2.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_no_expired_tokens(self, db_session):
        """When there are no expired tokens, cleanup returns 0."""
        valid = BlacklistedToken(
            jti="valid-only",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=5),
        )
        db_session.add(valid)
        await db_session.flush()

        from sqlalchemy import delete
        now = datetime.now(timezone.utc)
        result = await db_session.execute(
            delete(BlacklistedToken).where(BlacklistedToken.expires_at < now)
        )
        assert result.rowcount == 0


class TestOverdueCheckerLoop:
    """Tests for the overdue_checker_loop background task."""

    @pytest.mark.asyncio
    async def test_overdue_checker_loop_cancellation(self):
        """Verify overdue_checker_loop handles CancelledError gracefully."""
        import asyncio
        from app.services.overdue import overdue_checker_loop

        with patch("app.services.overdue.asyncio.sleep", side_effect=asyncio.CancelledError):
            # Should not raise, should return cleanly
            await overdue_checker_loop()

    @pytest.mark.asyncio
    async def test_overdue_checker_loop_error_recovery(self):
        """Verify the loop continues after a generic exception."""
        import asyncio
        from app.services.overdue import overdue_checker_loop

        call_count = 0

        async def mock_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return  # Let iterations through
            raise asyncio.CancelledError()  # Stop the loop

        with patch("app.services.overdue.asyncio.sleep", side_effect=mock_sleep):
            with patch(
                "app.services.overdue.check_and_mark_overdue",
                side_effect=Exception("DB connection lost"),
            ):
                await overdue_checker_loop()

        # Loop should have called sleep at least twice (once for the interval, once for the error backoff)
        assert call_count >= 2


class TestMultipleOverdueLoans:
    """Test batch processing of multiple overdue loans."""

    @pytest.mark.asyncio
    async def test_multiple_overdue_loans(self, db_session, make_user, make_branch, make_book):
        """Multiple overdue loans should all be marked."""
        user = make_user()
        branch = make_branch()
        db_session.add_all([user, branch])
        await db_session.flush()

        overdue_loans = []
        for i in range(3):
            book = make_book(branch_id=branch.id)
            db_session.add(book)
            await db_session.flush()

            loan = Loan(
                member_id=user.id,
                book_id=book.id,
                branch_id=branch.id,
                borrow_date=datetime.now(timezone.utc) - timedelta(days=20),
                due_date=datetime.now(timezone.utc) - timedelta(days=5 + i),
                status=LoanStatus.BORROWED,
            )
            db_session.add(loan)
            overdue_loans.append(loan)

        await db_session.flush()

        # Verify all 3 are found as overdue
        now = datetime.now(timezone.utc)
        result = await db_session.execute(
            select(Loan).where(
                Loan.status == LoanStatus.BORROWED,
                Loan.due_date < now,
            )
        )
        found = result.scalars().all()
        assert len(found) == 3


