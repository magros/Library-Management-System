from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from app.db.models import LoanStatus


class LoanCreate(BaseModel):
    book_id: str
    branch_id: str
    notes: Optional[str] = None


class LoanStatusUpdate(BaseModel):
    status: LoanStatus
    notes: Optional[str] = None


class LoanStatusHistoryResponse(BaseModel):
    id: str
    previous_status: Optional[LoanStatus]
    new_status: LoanStatus
    changed_by: Optional[str]
    notes: Optional[str]
    changed_at: datetime

    model_config = {"from_attributes": True}


class LoanResponse(BaseModel):
    id: str
    member_id: str
    book_id: str
    branch_id: str
    borrow_date: datetime
    due_date: datetime
    return_date: Optional[datetime]
    status: LoanStatus
    late_fee: float
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    status_history: List[LoanStatusHistoryResponse] = []

    model_config = {"from_attributes": True}


class LoanListResponse(BaseModel):
    items: List[LoanResponse]
    total: int
    page: int
    size: int
    pages: int
