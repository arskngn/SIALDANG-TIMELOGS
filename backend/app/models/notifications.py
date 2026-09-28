from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(50), nullable=False)  # "approved", "rejected", "declined"
    item_type = Column(String(50), nullable=False)  # "timelog", "user201"
    item_id = Column(Integer, nullable=False)
    item_title = Column(String(255), nullable=True)
    item_description = Column(Text, nullable=True)
    target_route = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    is_read = Column(Integer, nullable=False, default=0)  # 0 = unread, 1 = read
