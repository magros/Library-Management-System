from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import User, UserRole
from app.api.v1.dependencies import get_current_user, require_role
from app.schemas.branch import BranchCreate, BranchUpdate, BranchResponse, BranchListResponse
from app.services.branch import (
    create_branch,
    get_branches,
    get_branch_by_id,
    update_branch,
    delete_branch,
    calculate_pages,
)

router = APIRouter(prefix="/branches", tags=["Library Branches"])

LibrarianOrAdmin = Annotated[User, Depends(require_role(UserRole.LIBRARIAN, UserRole.ADMIN))]
AdminOnly = Annotated[User, Depends(require_role(UserRole.ADMIN))]


@router.get(
    "",
    response_model=BranchListResponse,
    summary="List branches",
    description="Retrieve a paginated list of library branches with optional filters.",
    responses={
        200: {"description": "Paginated list of branches"},
        401: {"description": "Not authenticated"},
    },
)
async def list_branches(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    is_active: bool | None = None,
    search: str | None = None,
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
):
    """List all library branches (all authenticated users)."""
    branches, total = await get_branches(
        db, page=page, size=size, is_active=is_active,
        search=search, sort_by=sort_by, sort_order=sort_order,
    )
    return BranchListResponse(
        items=branches, total=total, page=page, size=size, pages=calculate_pages(total, size)
    )


@router.post(
    "",
    response_model=BranchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a branch",
    description="Create a new library branch. Requires Librarian or Admin role.",
    responses={
        201: {"description": "Branch created successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        422: {"description": "Validation error"},
    },
)
async def create_branch_endpoint(
    data: BranchCreate,
    current_user: LibrarianOrAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a library branch (Librarian/Admin)."""
    branch = await create_branch(db, data.model_dump(), current_user.id)
    return branch


@router.get(
    "/{branch_id}",
    response_model=BranchResponse,
    summary="Get branch details",
    description="Retrieve a single library branch by its ID.",
    responses={
        200: {"description": "Branch details"},
        401: {"description": "Not authenticated"},
        404: {"description": "Branch not found"},
    },
)
async def get_branch(
    branch_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get branch details."""
    branch = await get_branch_by_id(db, branch_id)
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    return branch


@router.put(
    "/{branch_id}",
    response_model=BranchResponse,
    summary="Update a branch",
    description="Update library branch details. Requires Librarian or Admin role.",
    responses={
        200: {"description": "Branch updated successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Branch not found"},
        422: {"description": "Validation error"},
    },
)
async def update_branch_endpoint(
    branch_id: str,
    data: BranchUpdate,
    current_user: LibrarianOrAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update a library branch (Librarian/Admin)."""
    branch = await update_branch(db, branch_id, data.model_dump(exclude_unset=True), current_user.id)
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    return branch


@router.delete(
    "/{branch_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a branch",
    description="Permanently delete a library branch. Requires Admin role.",
    responses={
        204: {"description": "Branch deleted successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Branch not found"},
    },
)
async def delete_branch_endpoint(
    branch_id: str,
    current_user: AdminOnly,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete a library branch (Admin only)."""
    deleted = await delete_branch(db, branch_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")

