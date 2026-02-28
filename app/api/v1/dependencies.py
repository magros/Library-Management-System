from typing import Annotated
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.core.logging import get_logger, current_user_id_ctx
from app.db.session import get_db
from app.db.models import User, UserRole
from app.services.auth import is_token_blacklisted
from app.services.user import get_user_by_id

logger = get_logger("api.dependencies")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Decode JWT, check blacklist, and return the current user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    jti = payload.get("jti")
    user_id = payload.get("sub")
    if not user_id or not jti:
        raise credentials_exception

    # Check blacklist
    if await is_token_blacklisted(db, jti):
        logger.warning(f"Blacklisted token used: jti={jti}")
        raise credentials_exception

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Set user context for logging
    current_user_id_ctx.set(user.id)

    return user


def require_role(*roles: UserRole) -> Callable:
    """Dependency factory that checks if the current user has one of the required roles."""

    async def role_checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in roles:
            logger.warning(
                f"Access denied: user={current_user.id} role={current_user.role.value} "
                f"required={[r.value for r in roles]}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return role_checker

