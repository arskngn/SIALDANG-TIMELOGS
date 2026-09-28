from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey, Boolean
from app.database import Base


class Timelog(Base):
    __tablename__ = "timelogs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    task_type_id = Column(Integer, ForeignKey("task_types.id"), nullable=True)
    type = Column(Enum("project", "other", "leave", name="timelog_type"), nullable=False, default="project")
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String(100), nullable=True)
    status = Column(Enum("Pending", "Approved", "Rejected", name="timelog_status"), nullable=False, default="Pending")
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    exclude_lunch = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now().replace(microsecond=0))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now().replace(microsecond=0))
