from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class CreateUser201File(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    file_name: str
    document_type_id: int
    file_url: Optional[str] = None
    s3_path: Optional[str] = None
    notes: Optional[str] = None
    remarks: Optional[str] = None
    status: Optional[str] = None
    version: Optional[int] = None
    is_active: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UpdateUser201File(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    file_name: Optional[str] = None
    document_type: Optional[str] = None
    file_url: Optional[str] = None
    s3_path: Optional[str] = None
    notes: Optional[str] = None
    remarks: Optional[str] = None
    status: Optional[str] = None
    approver_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[int] = None
    version: Optional[int] = None
    is_active: Optional[bool] = None
    updated_at: Optional[datetime] = None


class User201FileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    file_name: str
    document_type_id: int
    file_url: Optional[str] = None
    s3_path: Optional[str] = None
    notes: Optional[str] = None
    remarks: Optional[str] = None
    status: str
    approver_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[int] = None
    uploaded_at: Optional[datetime] = None
    version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
