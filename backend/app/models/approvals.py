from datetime import datetime
from sqlalchemy import Column, Integer, Text, DateTime, Enum, ForeignKey
from app.database import Base


class Approval(Base):
    __tablename__ = "approvals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timelog_id = Column(Integer, ForeignKey("timelogs.id"), nullable=False)
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    approver_role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    action = Column(Enum("Approved", "Rejected", name="approval_action"), nullable=False)
    remarks = Column(Text, nullable=True)
    action_date = Column(DateTime, nullable=False, default=datetime.now)
