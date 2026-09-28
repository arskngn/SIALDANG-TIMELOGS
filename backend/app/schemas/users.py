from pydantic import BaseModel, ConfigDict, AfterValidator
from datetime import datetime, date
from enum import Enum
from typing import Optional, List, Literal, Annotated
import re
#import psgc


# ---------------------------------------------------------------------------
# Civil status enum
# ---------------------------------------------------------------------------
class CivilStatus(str, Enum):
    SINGLE = "Single"
    MARRIED = "Married"
    WIDOWED = "Widowed"
    SEPARATED = "Separated"
    DIVORCED = "Divorced"
    ANNULLED = "Annulled"


# ---------------------------------------------------------------------------
# PSGC validator
# ---------------------------------------------------------------------------
# psgc.validate() requires the code to be exactly 10 digits, then checks it
# against the actual PSA PSGC masterlist (region/province/city/barangay).
# PSGC_FORMAT_REGEX = re.compile(r"^\d{10}$")


# def is_valid_psgc(value: str) -> str:
#     value = value.strip()
#     if not PSGC_FORMAT_REGEX.match(value):
#         raise ValueError("PSGC code must be exactly 10 digits")
#     is_valid, reason = psgc.validate(value)
#     if not is_valid:
#         raise ValueError(f"Invalid PSGC code: {reason}")
#     return value


# PSGCCode = Annotated[str, AfterValidator(is_valid_psgc)]


class CreateUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    username: str
    password: str
    role: str
    role_id: Optional[int] = None
    branch_id: Optional[int] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: str
    civil_status: CivilStatus
    birthdate: date
    permanent_address_line: str
    current_address_line: str
    # permanent_address_psgc: PSGCCode
    # current_address_psgc: PSGCCode
    permanent_address_psgc: str
    current_address_psgc: str
    salutation: Optional[str] = None
    department: Optional[str] = None
    job_level: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_number: Optional[str] = None
    # Payroll and government IDs
    gotyme_account_name: Optional[str] = None
    gotyme_account_number: Optional[str] = None
    tin_number: Optional[str] = None
    sss_number: Optional[str] = None
    philhealth_number: Optional[str] = None
    pagibig_number: Optional[str] = None
    # Contract dates
    emp_start_date: Optional[date] = None
    emp_end_date: Optional[date] = None
    # Block flag
    blocked: Optional[bool] = False
    # Let the server populate timestamps if not provided
    date_created: Optional[datetime] = None
    date_updated: Optional[datetime] = None


class UpdateUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    role_id: Optional[int] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    civil_status: Optional[CivilStatus] = None
    birthdate: Optional[date] = None
    permanent_address_line: Optional[str] = None
    current_address_line: Optional[str] = None
    # permanent_address_psgc: Optional[PSGCCode] = None
    # current_address_psgc: Optional[PSGCCode] = None
    permanent_address_psgc: Optional[str] = None
    current_address_psgc: Optional[str] = None
    branch_id: Optional[int] = None
    salutation: Optional[str] = None
    department: Optional[str] = None
    job_level: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_number: Optional[str] = None
    # Payroll and government IDs
    gotyme_account_name: Optional[str] = None
    gotyme_account_number: Optional[str] = None
    tin_number: Optional[str] = None
    sss_number: Optional[str] = None
    philhealth_number: Optional[str] = None
    pagibig_number: Optional[str] = None
    # Contract dates
    emp_start_date: Optional[date] = None
    emp_end_date: Optional[date] = None
    # Block flag
    blocked: Optional[bool] = None
    # date_updated will be set server-side during updates
    date_updated: Optional[datetime] = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: Optional[str] = None
    role_id: Optional[int] = None
    branch_id: Optional[int] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    civil_status: Optional[str] = None
    birthdate: Optional[date] = None
    permanent_address_line: Optional[str] = None
    current_address_line: Optional[str] = None
    permanent_address_psgc: Optional[str] = None
    current_address_psgc: Optional[str] = None
    salutation: Optional[str] = None
    department: Optional[str] = None
    job_level: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_number: Optional[str] = None
    # Payroll and government IDs
    gotyme_account_name: Optional[str] = None
    gotyme_account_number: Optional[str] = None
    tin_number: Optional[str] = None
    sss_number: Optional[str] = None
    philhealth_number: Optional[str] = None
    pagibig_number: Optional[str] = None
    # Contract dates
    emp_start_date: Optional[date] = None
    emp_end_date: Optional[date] = None
    # Block flag
    blocked: Optional[bool] = False
    # Account status based on contract dates
    status: Literal["Active", "Inactive (Contract Ended)", "Inactive (Contract Not Started)"] = "Active"
    date_created: Optional[datetime] = None
    date_updated: Optional[datetime] = None


class ProjectAssignment(BaseModel):
    project_id: int
    role_id: Optional[int] = None


class ProjectsAssignRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    project_ids: Optional[List[int]] = None
    assignments: Optional[List[ProjectAssignment]] = None