from pydantic import BaseModel, ConfigDict, AwareDatetime, field_validator, ValidationInfo
from datetime import datetime, date
from datetime import timezone
from typing import Optional, Literal, List
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from app.secrets import DEFAULT_TIMEZONE


class CreateTimelog(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: Optional[int] = None
    type: Literal["project", "other", "leave"]
    project_id: Optional[int] = None
    task_type_id: Optional[int] = None
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: AwareDatetime
    end_time: AwareDatetime
    duration_minutes: Optional[int] = None
    status: Optional[Literal["Pending", "Approved", "Rejected"]] = "Pending"
    exclude_lunch: Optional[bool] = False
    date_created: Optional[datetime] = None
    date_updated: Optional[datetime] = None
    
    @field_validator("description", mode="before")
    @classmethod
    def validate_description_required(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        """Require a non-empty description/summary when creating a timelog."""
        if v is None:
            raise ValueError("description is required")
        if isinstance(v, str) and v.strip() == "":
            raise ValueError("description cannot be empty")
        return v

    @field_validator("task_type_id", mode="before")
    @classmethod
    def validate_task_type_required_for_non_project(cls, v: Optional[int], info: ValidationInfo) -> Optional[int]:
        """Enforce that task_type_id is provided when type is 'other' or 'leave'."""
        if info.data.get("type") in ("other", "leave"):
            if v is None:
                raise ValueError(f"task_type_id is required when type is '{info.data.get('type')}'")
        return v

    @field_validator("project_id", mode="before")
    @classmethod
    def validate_project_required_for_project_type(cls, v: Optional[int], info: ValidationInfo) -> Optional[int]:
        """Enforce that project_id is provided when type is 'project'."""
        if info.data.get("type") == "project":
            if v is None:
                raise ValueError("project_id is required when type is 'project'")
        return v


    # duplicates removed to prevent decorator override warnings


class UpdateTimelog(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    type: Optional[Literal["project", "other", "leave"]] = None
    project_id: Optional[int] = None
    task_type_id: Optional[int] = None
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: Optional[AwareDatetime] = None
    end_time: Optional[AwareDatetime] = None
    duration_minutes: Optional[int] = None
    status: Optional[Literal["Pending", "Approved", "Rejected"]] = None
    exclude_lunch: Optional[bool] = None
    date_updated: Optional[datetime] = None


class TimelogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    type: Literal["project", "other", "leave"]
    project_id: Optional[int] = None
    task_type_id: Optional[int] = None
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    status: Literal["Pending", "Approved", "Rejected"]
    exclude_lunch: Optional[bool] = None
    approver_id: Optional[int] = None
    approver_name: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    @field_validator("start_time", "end_time", "created_at", "updated_at", mode="before")
    @classmethod
    def make_aware(cls, v: Optional[datetime], info: ValidationInfo) -> Optional[datetime]:
        """Convert naive datetimes to aware datetimes in DEFAULT_TIMEZONE."""
        if v is None:
            return v
        if isinstance(v, datetime):
            if v.tzinfo is None:
                try:
                    tz = ZoneInfo(DEFAULT_TIMEZONE)
                    return v.replace(tzinfo=tz)
                except ZoneInfoNotFoundError:
                    # Fallback to UTC if timezone is invalid
                    return v.replace(tzinfo=timezone.utc)
            return v
        return v


class DuplicateTimelog(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    start_date: date
    end_date: date
    frequency: Literal["daily", "weekdays", "weekly"]

class DuplicateTimelogToDates(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    dates: List[date]  # List of specific dates to duplicate to


class UpdateTimelogStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: Literal["Pending", "Approved", "Rejected"]

