from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field


class BranchCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    address: str = Field(..., min_length=1)
    description: Optional[str] = None
    phone_number: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None


class BranchUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    address: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    phone_number: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None


class BranchResponse(BaseModel):
    id: str
    name: str
    address: str
    description: Optional[str]
    phone_number: Optional[str]
    email: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BranchListResponse(BaseModel):
    items: List[BranchResponse]
    total: int
    page: int
    size: int
    pages: int
