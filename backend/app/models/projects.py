from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Enum, ForeignKey
from app.database import Base


class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    manager_role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    status = Column(Enum("Pending", "Ongoing", "Completed", name="project_status"), nullable=False, default="Pending")
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now)
    
    # Note: Project managers are assigned through user_projects table with role_in_project='Project Manager'
    # This allows multiple project managers per project
    # Project managers can view, approve, and reject timelogs for their assigned project
