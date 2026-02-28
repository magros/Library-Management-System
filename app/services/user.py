import math
from typing import Optional, List, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import hash_password
from app.db.models import User, UserRole

logger = get_logger("services.user")


async def get_users(
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> Tuple[List[User], int]:
    """List users with filtering, sorting, and pagination."""
    query = select(User)
    count_query = select(func.count()).select_from(User)

    if role is not None:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)
    if search:
        search_filter = User.full_name.ilike(f"%{search}%") | User.email.ilike(f"%{search}%")
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    sort_column = getattr(User, sort_by, User.created_at)
    if sort_order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    offset = (page - 1) * size
    query = query.offset(offset).limit(size)

    result = await db.execute(query)
    users = list(result.scalars().all())

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    return users, total


async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    """Get a single user by ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def update_user(
    db: AsyncSession, user_id: str, update_data: dict, actor_id: str
) -> Optional[User]:
    """Update a user's fields."""
    user = await get_user_by_id(db, user_id)
    if not user:
        return None

    if "password" in update_data and update_data["password"]:
        update_data["hashed_password"] = hash_password(update_data.pop("password"))
    else:
        update_data.pop("password", None)

    for key, value in update_data.items():
        if value is not None:
            setattr(user, key, value)

    await db.flush()
    await db.refresh(user)

    logger.info(f"User updated: id={user_id} by actor={actor_id}")
    return user


async def delete_user(db: AsyncSession, user_id: str, actor_id: str) -> bool:
    """Delete a user. Prevents deleting built-in admin."""
    user = await get_user_by_id(db, user_id)
    if not user:
        return False

    if user.is_built_in:
        raise ValueError("Cannot delete the built-in admin account")

    await db.delete(user)
    await db.flush()

    logger.info(f"User deleted: id={user_id} by actor={actor_id}")
    return True


def calculate_pages(total: int, size: int) -> int:
    return math.ceil(total / size) if size > 0 else 0
