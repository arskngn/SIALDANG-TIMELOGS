from pydantic import BaseModel, ConfigDict
from typing import Optional, Literal
from datetime import datetime


class CreateDocumentType(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    name: str
    category: Literal["pre-employment", "payroll", "government"]
    required: bool = False


class UpdateDocumentType(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: Optional[str] = None
    name: Optional[str] = None
    category: Optional[Literal["pre-employment", "payroll", "government"]] = None
    required: Optional[bool] = None


class DocumentTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    category: Literal["pre-employment", "payroll", "government"]
    required: bool
    created_at: datetime
