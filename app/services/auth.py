from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.db.models import User, BlacklistedToken, UserRole

logger = get_logger("services.auth")


async def register_user(
    db: AsyncSession, email: str, password: str, full_name: str
) -> User:
    """Register a new user account."""
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()
    if existing:
        raise ValueError("A user with this email already exists")

    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role=UserRole.MEMBER,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    logger.info(f"User registered: {user.email} (id={user.id})")
    return user


async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> Optional[User]:
    """Authenticate a user and return the user if valid."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        logger.warning(f"Login failed: unknown email {email}")
        return None

    if not user.is_active:
        logger.warning(f"Login failed: user {email} is blocked/inactive")
        return None

    if not verify_password(password, user.hashed_password):
        logger.warning(f"Login failed: wrong password for {email}")
        return None

    logger.info(f"Login successful: {email} (id={user.id})")
    return user


def create_user_token(user: User) -> str:
    """Create a JWT token for a user."""
    return create_access_token(data={"sub": user.id, "role": user.role.value})


async def blacklist_token(
    db: AsyncSession, token: str
) -> None:
    """Add a token's JTI to the blacklist."""
    payload = decode_access_token(token)
    if not payload:
        return

    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or not exp:
        return

    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)

    entry = BlacklistedToken(jti=jti, expires_at=expires_at)
    db.add(entry)
    await db.flush()

    logger.info(f"Token blacklisted: jti={jti}")


async def is_token_blacklisted(db: AsyncSession, jti: str) -> bool:
    """Check if a token JTI is in the blacklist."""
    result = await db.execute(
        select(BlacklistedToken).where(BlacklistedToken.jti == jti)
    )
    return result.scalar_one_or_none() is not None


async def cleanup_expired_tokens(db: AsyncSession) -> int:
    """Remove expired tokens from the blacklist. Returns count deleted."""
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
