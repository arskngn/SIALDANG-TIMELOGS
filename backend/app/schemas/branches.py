from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class CreateBranch(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    branch_name: str
    branch_address: Optional[str] = None

class UpdateBranch(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    branch_name: Optional[str] = None
    branch_address: Optional[str] = None

class BranchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    branch_name: str
    branch_address: Optional[str] = None
    created_at: datetime