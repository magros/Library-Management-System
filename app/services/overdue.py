import asyncio
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Loan, LoanStatus, LoanStatusHistory, BlacklistedToken
from app.db.session import AsyncSessionLocal

logger = get_logger("services.overdue")


async def check_and_mark_overdue() -> int:
    """Check all borrowed loans and mark overdue ones. Returns count of newly overdue loans."""
    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)

        # Find all borrowed loans past due date
        result = await db.execute(
            select(Loan).where(
                Loan.status == LoanStatus.BORROWED,
                Loan.due_date < now,
            )
        )
        overdue_loans = result.scalars().all()

        count = 0
        for loan in overdue_loans:
            loan.status = LoanStatus.OVERDUE
            # Calculate current late fee
            overdue_days = (now - loan.due_date).days
            loan.late_fee = round(overdue_days * 0.50, 2)

            # Record history
            history = LoanStatusHistory(
                loan_id=loan.id,
                previous_status=LoanStatus.BORROWED,
                new_status=LoanStatus.OVERDUE,
                changed_by=None,  # System action
                notes=f"Automatically marked overdue ({overdue_days} days past due)",
            )
            db.add(history)
            count += 1

            logger.info(
                f"Loan marked overdue: id={loan.id} member={loan.member_id} "
                f"days_overdue={overdue_days} late_fee={loan.late_fee}"
            )

        await db.commit()

        if count:
            logger.info(f"Overdue check completed: {count} loans marked overdue")
        return count


async def cleanup_expired_blacklisted_tokens() -> int:
    """Remove expired tokens from the blacklist table."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy import delete

        now = datetime.now(timezone.utc)
        result = await db.execute(
            delete(BlacklistedToken).where(BlacklistedToken.expires_at < now)
        )
        count = result.rowcount
        await db.commit()
        if count:
            logger.info(f"Cleaned up {count} expired blacklisted tokens")
        return count


async def overdue_checker_loop() -> None:
    """Background loop that periodically checks for overdue loans and cleans up tokens."""
    logger.info(
        f"Overdue checker started (interval={settings.OVERDUE_CHECK_INTERVAL}s)"
    )
    while True:
        try:
            await asyncio.sleep(settings.OVERDUE_CHECK_INTERVAL)
            await check_and_mark_overdue()
            await cleanup_expired_blacklisted_tokens()
        except asyncio.CancelledError:
            logger.info("Overdue checker loop cancelled")
            break
        except Exception as e:
            logger.error(f"Error in overdue checker loop: {e}")
            # Continue running despite errors
            await asyncio.sleep(60)

