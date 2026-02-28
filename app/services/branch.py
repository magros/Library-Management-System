import math
from typing import Optional, List, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import LibraryBranch

logger = get_logger("services.branch")


async def create_branch(db: AsyncSession, data: dict, actor_id: str) -> LibraryBranch:
    """Create a new library branch."""
    branch = LibraryBranch(**data)
    db.add(branch)
    await db.flush()
    await db.refresh(branch)

    logger.info(f"Branch created: id={branch.id} name='{branch.name}' by actor={actor_id}")
    return branch


async def get_branches(
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> Tuple[List[LibraryBranch], int]:
    """List branches with filtering, sorting, and pagination."""
    query = select(LibraryBranch)
    count_query = select(func.count()).select_from(LibraryBranch)

    if is_active is not None:
        query = query.where(LibraryBranch.is_active == is_active)
        count_query = count_query.where(LibraryBranch.is_active == is_active)
    if search:
        search_filter = LibraryBranch.name.ilike(f"%{search}%") | LibraryBranch.address.ilike(
            f"%{search}%"
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    sort_column = getattr(LibraryBranch, sort_by, LibraryBranch.created_at)
    if sort_order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    offset = (page - 1) * size
    query = query.offset(offset).limit(size)

    result = await db.execute(query)
    branches = list(result.scalars().all())

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    return branches, total


async def get_branch_by_id(db: AsyncSession, branch_id: str) -> Optional[LibraryBranch]:
    """Get a single branch by ID."""
    result = await db.execute(select(LibraryBranch).where(LibraryBranch.id == branch_id))
    return result.scalar_one_or_none()


async def update_branch(
    db: AsyncSession, branch_id: str, data: dict, actor_id: str
) -> Optional[LibraryBranch]:
    """Update a branch."""
    branch = await get_branch_by_id(db, branch_id)
    if not branch:
        return None

    for key, value in data.items():
        if value is not None:
            setattr(branch, key, value)

    await db.flush()
    await db.refresh(branch)

    logger.info(f"Branch updated: id={branch_id} by actor={actor_id}")
    return branch


async def delete_branch(db: AsyncSession, branch_id: str, actor_id: str) -> bool:
    """Delete a branch."""
    branch = await get_branch_by_id(db, branch_id)
    if not branch:
        return False

    await db.delete(branch)
    await db.flush()

    logger.info(f"Branch deleted: id={branch_id} by actor={actor_id}")
    return True


def calculate_pages(total: int, size: int) -> int:
    return math.ceil(total / size) if size > 0 else 0
