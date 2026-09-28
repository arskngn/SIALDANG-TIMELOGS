from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime, date
from enum import IntEnum
class FTE(IntEnum):
    FULL_TIME = 100
    HALF_TIME = 50
    QUARTER_TIME = 25

class CreateProject(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    project_name: str
    description: Optional[str] = None
    manager_id: Optional[int] = None
    manager_role_id: Optional[int] = None
    customer_id: int # Made required as per user instruction
    branch_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = "Pending"

class CreateProjectResource(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    project_id:int
    role_in_project:str
    fte:FTE


class UpdateProjectResource(BaseModel):
    fte:Optional[FTE]=None
    role_in_project:Optional[str]=None

class UpdateProjectResourceInDB(BaseModel):
    fte:Optional[int]=None
    role_in_project:Optional[str]=None

class ProjectResourceResponse(CreateProjectResource):
    id:int
    assigned_at:datetime

class UpdateProject(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    project_name: Optional[str] = None
    description: Optional[str] = None
    manager_id: Optional[int] = None
    manager_role_id: Optional[int] = None
    branch_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = None

class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_name: str
    description: Optional[str] = None
    manager_id: Optional[int] = None
    manager_username: Optional[str] = None
    manager_role_id: Optional[int] = None
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    branch_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: str
    created_at: datetime
    updated_at: datetime
