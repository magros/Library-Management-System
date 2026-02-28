from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class BookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    author: str = Field(..., min_length=1, max_length=255)
    isbn: str = Field(..., min_length=10, max_length=13)
    description: Optional[str] = None
    genre: Optional[str] = Field(None, max_length=100)
    publication_year: Optional[int] = None
    total_copies: int = Field(1, ge=1)
    branch_id: str


class BookUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    author: Optional[str] = Field(None, min_length=1, max_length=255)
    isbn: Optional[str] = Field(None, min_length=10, max_length=13)
    description: Optional[str] = None
    genre: Optional[str] = Field(None, max_length=100)
    publication_year: Optional[int] = None
    total_copies: Optional[int] = Field(None, ge=0)
    branch_id: Optional[str] = None


class BookResponse(BaseModel):
    id: str
    title: str
    author: str
    isbn: str
    description: Optional[str]
    genre: Optional[str]
    publication_year: Optional[int]
    total_copies: int
    available_copies: int
    branch_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BookListResponse(BaseModel):
    items: List[BookResponse]
    total: int
    page: int
    size: int
    pages: int
