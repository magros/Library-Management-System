from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field

from app.db.models import UserRole


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    is_built_in: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=6, max_length=128)


class UserListResponse(BaseModel):
    items: List[UserResponse]
    total: int
    page: int
    size: int
    pages: int
