from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime, date

class CreateCustomer(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    customer_name: str
    description: Optional[str] = None
    customer_location: Optional[str] = None
    status: Optional[str] = "Active"

class UpdateCustomer(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    customer_name: Optional[str] = None
    description: Optional[str] = None
    customer_location: Optional[str] = None
    status: Optional[str] = None

class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    customer_name: str
    description: Optional[str] = None
    customer_location: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
