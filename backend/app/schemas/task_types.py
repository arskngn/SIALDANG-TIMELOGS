from pydantic import BaseModel, ConfigDict
from typing import Optional, Literal
from datetime import datetime


class CreateTaskType(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    description: Optional[str] = None
    category: Literal["other", "leave"]


class UpdateTaskType(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[Literal["other", "leave"]] = None


class TaskTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: Optional[str] = None
    category: Literal["other", "leave"]
    created_at: datetime