from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.v1.dependencies import get_current_user, oauth2_scheme
from app.db.models import User
from app.schemas.auth import RegisterRequest, TokenResponse, LogoutResponse
from app.services.auth import register_user, authenticate_user, create_user_token, blacklist_token

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new member account and receive a JWT access token.",
    responses={
        201: {"description": "User registered successfully, JWT token returned"},
        409: {"description": "Email already registered"},
        422: {"description": "Validation error"},
    },
)
async def register(
    data: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Register a new user account and return a JWT token."""
    try:
        user = await register_user(db, data.email, data.password, data.full_name)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    token = create_user_token(user)
    return TokenResponse(access_token=token)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login",
    description="Authenticate with email and password using OAuth2 form. "
                "The `username` field should contain the email address.",
    responses={
        200: {"description": "Login successful, JWT token returned"},
        401: {"description": "Invalid email or password"},
        422: {"description": "Validation error"},
    },
)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Login with email and password, returns a JWT token.

    Uses OAuth2 form: `username` field = email, `password` field = password.
    """
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_user_token(user)
    return TokenResponse(access_token=token)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Logout",
    description="Invalidate the current JWT token. Requires a valid Bearer token.",
    responses={
        200: {"description": "Successfully logged out"},
        401: {"description": "Not authenticated or token already invalid"},
    },
)
async def logout(
    token: Annotated[str, Depends(oauth2_scheme)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Logout and invalidate the current JWT token."""
    await blacklist_token(db, token)
    return LogoutResponse()

