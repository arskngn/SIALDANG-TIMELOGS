from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class LeaveCreditBase(BaseModel):
    sick_leave_balance: float = 0.0
    vacation_leave_balance: float = 0.0
    last_allocation_month: Optional[str] = None

class LeaveCreditCreate(LeaveCreditBase):
    user_id: int

class LeaveCreditUpdate(BaseModel):
    sick_leave_balance: Optional[float] = None
    vacation_leave_balance: Optional[float] = None
    last_allocation_month: Optional[str] = None

class LeaveCreditResponse(LeaveCreditBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    updated_at: datetime
