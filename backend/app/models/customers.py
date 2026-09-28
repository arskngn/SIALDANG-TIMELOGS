from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Date, Boolean
from app.database import Base


class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_name = Column(String(255), nullable=False, unique=True)
    description = Column(String(255), nullable=True)
    customer_location = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="Active")
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now)
