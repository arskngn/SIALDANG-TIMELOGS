from pydantic import BaseModel, ConfigDict
from typing import Optional

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    model_config = ConfigDict(extra='ignore')
    
    sub: Optional[int] = None
    role: Optional[str] = None
    exp: Optional[int] = None