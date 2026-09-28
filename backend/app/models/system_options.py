from sqlalchemy import Column, Integer, String, Enum
from app.database import Base
import enum

class OptionCategory(str, enum.Enum):
    DEPARTMENT = "Department"
    SALUTATION = "Salutation"
    JOB_LEVEL = "Job Level"

class SystemOption(Base):
    __tablename__ = "system_options"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(50), nullable=False) # Storing as string to allow flexibility or mapped to Enum
    value = Column(String(255), nullable=False)
