from pydantic import BaseModel, ConfigDict
from typing import Optional

class CreateSystemOption(BaseModel):
    category: str
    value: str

class UpdateSystemOption(BaseModel):
    value: str

class SystemOptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category: str
    value: str
