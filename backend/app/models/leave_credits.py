from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, ForeignKey, DateTime
from app.database import Base

class LeaveCredit(Base):
    __tablename__ = "leave_credits"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    
    sick_leave_balance = Column(Float, default=0.0)
    vacation_leave_balance = Column(Float, default=0.0)
    
    # Track the last month we allocated credits (format "YYYY-MM")
    last_allocation_month = Column(String(7), nullable=True)
    
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
