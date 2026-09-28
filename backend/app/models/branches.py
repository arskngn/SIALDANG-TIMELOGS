from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from app.database import Base


class Branch(Base):
    __tablename__ = "branches"
    id = Column(Integer, primary_key=True, autoincrement=True)
    branch_name = Column(String(100), nullable=False, unique=True)
    branch_address = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
