import math
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple, Dict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Loan, LoanStatus, LoanStatusHistory, Book, User, UserRole

logger = get_logger("services.loan")

LATE_FEE_PER_DAY = 0.50
DEFAULT_LOAN_DAYS = 14
MAX_ACTIVE_LOANS = 5

VALID_TRANSITIONS: Dict[LoanStatus, List[LoanStatus]] = {
    LoanStatus.REQUESTED: [LoanStatus.CANCELED, LoanStatus.APPROVED],
    LoanStatus.APPROVED: [LoanStatus.BORROWED, LoanStatus.CANCELED],
    LoanStatus.BORROWED: [LoanStatus.RETURNED, LoanStatus.LOST, LoanStatus.OVERDUE],
    LoanStatus.OVERDUE: [LoanStatus.RETURNED, LoanStatus.LOST],
}

MEMBER_ALLOWED_STATUSES = {LoanStatus.REQUESTED, LoanStatus.CANCELED}
LIBRARIAN_ALLOWED_STATUSES = {
    LoanStatus.APPROVED,
    LoanStatus.BORROWED,
    LoanStatus.RETURNED,
    LoanStatus.LOST,
    LoanStatus.CANCELED,
}


async def create_loan(
    db: AsyncSession,
    member_id: str,
    book_id: str,
    branch_id: str,
    notes: Optional[str] = None,
) -> Loan:
    """Create a new loan request."""
    active_statuses = [
        LoanStatus.REQUESTED,
        LoanStatus.APPROVED,
        LoanStatus.BORROWED,
        LoanStatus.OVERDUE,
    ]
    count_result = await db.execute(
        select(func.count())
        .select_from(Loan)
        .where(Loan.member_id == member_id, Loan.status.in_(active_statuses))
    )
    active_count = count_result.scalar()
    if active_count >= MAX_ACTIVE_LOANS:
        raise ValueError(f"Maximum of {MAX_ACTIVE_LOANS} active loans reached")

    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise ValueError("Book not found")
    if book.available_copies <= 0:
        raise ValueError("No available copies of this book")
    if book.branch_id != branch_id:
        raise ValueError("Book does not belong to the specified branch")

    book.available_copies -= 1

    now = datetime.now(timezone.utc)
    loan = Loan(
        member_id=member_id,
        book_id=book_id,
        branch_id=branch_id,
        borrow_date=now,
        due_date=now + timedelta(days=DEFAULT_LOAN_DAYS),
        status=LoanStatus.REQUESTED,
        notes=notes,
    )
    db.add(loan)
    await db.flush()

    history = LoanStatusHistory(
        loan_id=loan.id,
        previous_status=None,
        new_status=LoanStatus.REQUESTED,
        changed_by=member_id,
        notes="Loan requested",
    )
    db.add(history)
    await db.flush()
    await db.refresh(loan)

    logger.info(f"Loan created: id={loan.id} member={member_id} book={book_id}")
    return loan


async def update_loan_status(
    db: AsyncSession,
    loan_id: str,
    new_status: LoanStatus,
    actor: User,
    notes: Optional[str] = None,
) -> Loan:
    """Update loan status with state-machine validation and permission checks."""
    result = await db.execute(select(Loan).where(Loan.id == loan_id))
    loan = result.scalar_one_or_none()
    if not loan:
        raise ValueError("Loan not found")

    if actor.role == UserRole.MEMBER:
        if loan.member_id != actor.id:
            raise PermissionError("You can only modify your own loans")
        if new_status not in MEMBER_ALLOWED_STATUSES:
            raise PermissionError(f"Members cannot set status to {new_status.value}")
        if new_status == LoanStatus.CANCELED and loan.status != LoanStatus.REQUESTED:
            raise ValueError("Can only cancel a loan that is in 'requested' status")
    elif actor.role == UserRole.LIBRARIAN:
        if new_status not in LIBRARIAN_ALLOWED_STATUSES:
            raise PermissionError(f"Librarians cannot set status to {new_status.value}")

    current = loan.status
    allowed_next = VALID_TRANSITIONS.get(current, [])
    if new_status not in allowed_next:
        raise ValueError(
            f"Cannot transition from '{current.value}' to '{new_status.value}'"
        )

    old_status = loan.status
    loan.status = new_status

    if new_status == LoanStatus.RETURNED:
        loan.return_date = datetime.now(timezone.utc)
        book_result = await db.execute(select(Book).where(Book.id == loan.book_id))
        book = book_result.scalar_one_or_none()
        if book:
            book.available_copies += 1
        loan.late_fee = _calculate_late_fee(loan.due_date, loan.return_date)

    if new_status == LoanStatus.LOST:
        loan.late_fee = _calculate_late_fee(
            loan.due_date, datetime.now(timezone.utc)
        )

    if new_status == LoanStatus.CANCELED and old_status in (
        LoanStatus.REQUESTED,
        LoanStatus.APPROVED,
    ):
        book_result = await db.execute(select(Book).where(Book.id == loan.book_id))
        book = book_result.scalar_one_or_none()
        if book:
            book.available_copies += 1

    history = LoanStatusHistory(
        loan_id=loan.id,
        previous_status=old_status,
        new_status=new_status,
        changed_by=actor.id,
        notes=notes,
    )
    db.add(history)
    await db.flush()
    await db.refresh(loan)

    logger.info(
        f"Loan status changed: id={loan_id} {old_status.value} -> {new_status.value} "
        f"by user={actor.id}"
    )
    return loan


async def get_loans(
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
    member_id: Optional[str] = None,
    branch_id: Optional[str] = None,
    status: Optional[LoanStatus] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> Tuple[List[Loan], int]:
    """List loans with filtering, sorting, and pagination."""
    query = select(Loan)
    count_query = select(func.count()).select_from(Loan)

    if member_id:
        query = query.where(Loan.member_id == member_id)
        count_query = count_query.where(Loan.member_id == member_id)
    if branch_id:
        query = query.where(Loan.branch_id == branch_id)
        count_query = count_query.where(Loan.branch_id == branch_id)
    if status:
        query = query.where(Loan.status == status)
        count_query = count_query.where(Loan.status == status)

    sort_column = getattr(Loan, sort_by, Loan.created_at)
    if sort_order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    offset = (page - 1) * size
    query = query.offset(offset).limit(size)

    result = await db.execute(query)
    loans = list(result.scalars().unique().all())

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    return loans, total


async def get_loan_by_id(db: AsyncSession, loan_id: str) -> Optional[Loan]:
    """Get a single loan by ID."""
    result = await db.execute(select(Loan).where(Loan.id == loan_id))
    return result.scalar_one_or_none()


def _calculate_late_fee(due_date: datetime, return_date: datetime) -> float:
    """Calculate late fee based on days overdue."""
    # Normalize both datetimes to aware (UTC) to avoid naive vs aware comparison
    if due_date.tzinfo is None:
        due_date = due_date.replace(tzinfo=timezone.utc)
    if return_date.tzinfo is None:
        return_date = return_date.replace(tzinfo=timezone.utc)
    if return_date <= due_date:
        return 0.00
    overdue_days = (return_date - due_date).days
    return round(overdue_days * LATE_FEE_PER_DAY, 2)


def calculate_pages(total: int, size: int) -> int:
    return math.ceil(total / size) if size > 0 else 0

