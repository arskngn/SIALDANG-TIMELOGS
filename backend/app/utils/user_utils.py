"""User utility functions for contract-based account lifecycle."""

from datetime import date
from typing import Literal, Optional
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_user_status(
    emp_start_date: Optional[date],
    emp_end_date: Optional[date],
    current_date: Optional[date] = None
) -> Literal["Active", "Inactive (Contract Ended)", "Inactive (Contract Not Started)"]:
    """
    Calculate user account status based on contract dates.
    
    Args:
        emp_start_date: Employment start date
        emp_end_date: Employment end date
        current_date: Current date to check against (defaults to today)
    
    Returns:
        User status as a string
    """
    try:
        if current_date is None:
            current_date = date.today()
        
        # If no contract dates are set, consider the account active
        if emp_start_date is None or emp_end_date is None:
            return "Active"
        
        # Ensure dates are date objects
        if not isinstance(emp_start_date, date):
            return "Active"
        if not isinstance(emp_end_date, date):
            return "Active"
        if not isinstance(current_date, date):
            return "Active"
         
        # Check if current date is within contract period
        if current_date < emp_start_date:
            return "Inactive (Contract Not Started)"
        elif current_date > emp_end_date:
            return "Inactive (Contract Ended)"
        else:
            return "Active"
    except Exception as e:
        logger.error(f"Error calculating user status: {e}", exc_info=True)
        # Default to Active if there's any error (backward compatibility)
        return "Active"


def is_user_account_active(
    emp_start_date: Optional[date],
    emp_end_date: Optional[date],
    current_date: Optional[date] = None
) -> bool:
    """
    Check if a user account is active based on contract dates.
    
    Args:
        emp_start_date: Employment start date
        emp_end_date: Employment end date
        current_date: Current date to check against (defaults to today)
    
    Returns:
        True if account is active, False otherwise
    """
    try:
        # If no contract dates are set, account is active
        if emp_start_date is None or emp_end_date is None:
            return True
        
        # Ensure dates are date objects
        if not isinstance(emp_start_date, date):
            return True
        if not isinstance(emp_end_date, date):
            return True
        
        if current_date is None:
            current_date = date.today()
        
        if not isinstance(current_date, date):
            return True
        
        return current_date >= emp_start_date and current_date <= emp_end_date
    except Exception as e:
        logger.error(f"Error checking account active status: {e}", exc_info=True)
        # Default to True if there's any error (backward compatibility)
        return True
