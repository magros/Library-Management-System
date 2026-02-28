from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import DBAPIError

from app.db.session import get_db
from app.db.models import User, UserRole, LoanStatus
from app.api.v1.dependencies import get_current_user, require_role
from app.schemas.loan import LoanCreate, LoanStatusUpdate, LoanResponse, LoanListResponse
from app.services.loan import (
    create_loan,
    update_loan_status,
    get_loans,
    get_loan_by_id,
    calculate_pages,
)

router = APIRouter(prefix="/loans", tags=["Loans"])


@router.post(
    "",
    response_model=LoanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request a new loan",
    description="Request to borrow a book from a specific branch. Any authenticated user can request a loan.",
    responses={
        201: {"description": "Loan request created successfully"},
        400: {"description": "Invalid data (e.g. book not available)"},
        401: {"description": "Not authenticated"},
        422: {"description": "Validation error"},
    },
)
async def create_loan_endpoint(
    data: LoanCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Request a new loan (any authenticated user)."""
    try:
        loan = await create_loan(
            db,
            member_id=current_user.id,
            book_id=data.book_id,
            branch_id=data.branch_id,
            notes=data.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return loan


@router.get(
    "/my-history",
    response_model=LoanListResponse,
    summary="My loan history",
    description="Retrieve the current authenticated user's loan history with optional status filter.",
    responses={
        200: {"description": "Paginated list of user's loans"},
        401: {"description": "Not authenticated"},
    },
)
async def my_loan_history(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    loan_status: LoanStatus | None = Query(None, alias="status"),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
):
    """Get current user's loan history."""
    loans, total = await get_loans(
        db, page=page, size=size, member_id=current_user.id,
        status=loan_status, sort_by=sort_by, sort_order=sort_order,
    )
    return LoanListResponse(
        items=loans, total=total, page=page, size=size, pages=calculate_pages(total, size)
    )


@router.get(
    "",
    response_model=LoanListResponse,
    summary="List loans",
    description="Retrieve a paginated list of loans. Members see only their own; Librarians and Admins see all loans with optional filters.",
    responses={
        200: {"description": "Paginated list of loans"},
        401: {"description": "Not authenticated"},
    },
)
async def list_loans(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    member_id: str | None = None,
    branch_id: str | None = None,
    loan_status: LoanStatus | None = Query(None, alias="status"),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
):
    """List loans (filtered by role).

    - Members: see only their own loans
    - Librarians: see all loans (can filter by branch)
    - Admins: see all loans
    """
    if current_user.role == UserRole.MEMBER:
        # Members can only see their own loans
        member_id = current_user.id

    loans, total = await get_loans(
        db, page=page, size=size, member_id=member_id,
        branch_id=branch_id, status=loan_status,
        sort_by=sort_by, sort_order=sort_order,
    )
    return LoanListResponse(
        items=loans, total=total, page=page, size=size, pages=calculate_pages(total, size)
    )


@router.get(
    "/{loan_id}",
    response_model=LoanResponse,
    summary="Get loan details",
    description="Retrieve a single loan by its ID. Members can only view their own loans.",
    responses={
        200: {"description": "Loan details"},
        401: {"description": "Not authenticated"},
        403: {"description": "Access denied (member viewing another user's loan)"},
        404: {"description": "Loan not found"},
    },
)
async def get_loan_endpoint(
    loan_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get loan details."""
    try:
        loan = await get_loan_by_id(db, loan_id)
    except (DBAPIError, ValueError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
    if not loan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")

    # Members can only see their own loans
    if current_user.role == UserRole.MEMBER and loan.member_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return loan


@router.patch(
    "/{loan_id}/status",
    response_model=LoanResponse,
    summary="Update loan status",
    description=(
        "Transition the loan to a new status. Allowed transitions depend on the user's role:\n\n"
        "- **Member**: can cancel their own `requested` loan\n"
        "- **Librarian**: can approve, reject, mark as borrowed/returned\n"
        "- **Admin**: full control over all status transitions\n\n"
        "Status flow: `requested` → `approved` → `borrowed` → `returned` (or `overdue` / `lost`)"
    ),
    responses={
        200: {"description": "Loan status updated successfully"},
        400: {"description": "Invalid status transition"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions for this transition"},
        422: {"description": "Validation error"},
    },
)
async def update_loan_status_endpoint(
    loan_id: str,
    data: LoanStatusUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update loan status (respects role-based permissions and status flow)."""
    try:
        loan = await update_loan_status(
            db, loan_id=loan_id, new_status=data.status,
            actor=current_user, notes=data.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except DBAPIError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
    return loan

