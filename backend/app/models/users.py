from datetime import datetime
from app.database import Base
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Date, Boolean
from app.utils.encryption import EncryptedString


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(200), nullable=False, unique=True)
    password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="user")
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)
    first_name = Column(String(150), nullable=True)
    last_name = Column(String(150), nullable=True)
    email = Column(String(255), nullable=True, unique=True)
    phone_number = Column(String(32),nullable=False)
    civil_status = Column(String(32),nullable=False)
    birthdate = Column(Date,nullable=False)
    permanent_address_line = Column(String(128),nullable=True)
    current_address_line = Column(String(128),nullable=True)
    permanent_address_psgc = Column(String(32),nullable=False)
    current_address_psgc = Column(String(32),nullable=False)
    # New fields
    salutation = Column(String(20), nullable=True)
    department = Column(String(100), nullable=True)
    job_level = Column(String(50), nullable=True)
    emergency_contact_name = Column(EncryptedString(512), nullable=True)
    emergency_contact_number = Column(EncryptedString(512), nullable=True)
    # Payroll and government IDs
    gotyme_account_name = Column(EncryptedString(512), nullable=True)
    gotyme_account_number = Column(EncryptedString(512), nullable=True)
    tin_number = Column(EncryptedString(512), nullable=True)
    sss_number = Column(EncryptedString(512), nullable=True)
    philhealth_number = Column(EncryptedString(512), nullable=True)
    pagibig_number = Column(EncryptedString(512), nullable=True)
    # Contract dates for account lifecycle
    emp_start_date = Column(Date, nullable=True)
    emp_end_date = Column(Date, nullable=True)
    # Explicit block flag (when true, user cannot login)
    blocked = Column(Boolean, nullable=False, default=False)
    # Timestamps
    date_created = Column(DateTime, nullable=False)
    date_updated = Column(DateTime, nullable=False)
