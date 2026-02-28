from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import User, UserRole
from app.api.v1.dependencies import require_role
from app.schemas.user import UserResponse, UserUpdate, UserListResponse
from app.services.user import get_users, get_user_by_id, update_user, delete_user, calculate_pages

router = APIRouter(prefix="/users", tags=["Users"])

AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]


@router.get(
    "",
    response_model=UserListResponse,
    summary="List users",
    description="Retrieve a paginated list of users with optional filters. Requires Admin role.",
    responses={
        200: {"description": "Paginated list of users"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
    },
)
async def list_users(
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    role: UserRole | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
):
    """List all users (Admin only)."""
    users, total = await get_users(
        db, page=page, size=size, role=role, is_active=is_active,
        search=search, sort_by=sort_by, sort_order=sort_order,
    )
    return UserListResponse(
        items=users, total=total, page=page, size=size, pages=calculate_pages(total, size)
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user details",
    description="Retrieve a single user by their ID. Requires Admin role.",
    responses={
        200: {"description": "User details"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "User not found"},
    },
)
async def get_user(
    user_id: str,
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get user details (Admin only)."""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update a user",
    description="Update user details (email, name, role, status, password). Requires Admin role.",
    responses={
        200: {"description": "User updated successfully"},
        400: {"description": "Invalid data"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "User not found"},
        422: {"description": "Validation error"},
    },
)
async def update_user_endpoint(
    user_id: str,
    data: UserUpdate,
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update a user (Admin only)."""
    update_data = data.model_dump(exclude_unset=True)
    try:
        user = await update_user(db, user_id, update_data, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a user",
    description="Permanently delete a user. Cannot delete the built-in admin. Requires Admin role.",
    responses={
        204: {"description": "User deleted successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Cannot delete built-in admin"},
        404: {"description": "User not found"},
    },
)
async def delete_user_endpoint(
    user_id: str,
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete a user (Admin only). Cannot delete the built-in admin."""
    try:
        deleted = await delete_user(db, user_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

