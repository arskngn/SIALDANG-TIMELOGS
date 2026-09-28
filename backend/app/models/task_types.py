from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum
from app.database import Base


class TaskType(Base):
    __tablename__ = "task_types"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(255), nullable=True)
    category = Column(Enum("other", "leave", name="task_category"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now)