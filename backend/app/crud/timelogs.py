from app.crud.base import CRUDRepository
from app.models.timelogs import Timelog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, date, timedelta
from typing import List, Union


class TimelogCRUD(CRUDRepository):
    """Extended CRUD operations for Timelog model."""
    
    async def duplicate_timelog(
        self,
        session: AsyncSession,
        original_timelog: Timelog,
        start_date: date,
        end_date: date,
        frequency: str,
    ) -> List[Timelog]:
        """
        Duplicate a timelog across multiple days.
        
        Args:
            session: Database session
            original_timelog: The timelog to duplicate
            start_date: Start date for duplication
            end_date: End date for duplication (inclusive)
            frequency: "daily", "weekdays", or "weekly"
        
        Returns:
            List of created timelogs
        """
        created_logs = []
        current_date = start_date
        
        # Get time difference from original
        time_diff = original_timelog.end_time - original_timelog.start_time
        
        while current_date <= end_date:
            # Check if we should duplicate on this date based on frequency
            should_duplicate = False
            
            if frequency == "daily":
                should_duplicate = True
            elif frequency == "weekdays":
                # weekday() returns 0 (Monday) to 6 (Sunday)
                should_duplicate = current_date.weekday() < 5
            elif frequency == "weekly":
                # Only duplicate on the same day of week as the original
                days_diff = (current_date - start_date).days
                should_duplicate = days_diff % 7 == 0 and current_date != original_timelog.start_time.date()
            
            if should_duplicate:
                # Check if there's already a task on this day that overlaps
                new_start = datetime.combine(current_date, original_timelog.start_time.time())
                new_end = new_start + time_diff
                
                # Query for overlapping timelogs
                stmt = select(Timelog).where(
                    Timelog.user_id == original_timelog.user_id,
                    Timelog.start_time < new_end,
                    Timelog.end_time > new_start,
                )
                result = await session.execute(stmt)
                overlapping = result.scalars().first()
                
                # Only create if no overlap
                if not overlapping:
                    new_log = Timelog(
                        user_id=original_timelog.user_id,
                        type=original_timelog.type,
                        project_id=original_timelog.project_id,
                        task_type_id=original_timelog.task_type_id,
                        description=original_timelog.description,
                        location=original_timelog.location,
                        start_time=new_start,
                        end_time=new_end,
                        duration_minutes=original_timelog.duration_minutes,
                        status=original_timelog.status,
                        exclude_lunch=getattr(original_timelog, "exclude_lunch", False),
                    )
                    session.add(new_log)
                    created_logs.append(new_log)
            
            current_date += timedelta(days=1)
        
        await session.commit()
        return created_logs
    
    async def duplicate_timelog_to_dates(
        self,
        session: AsyncSession,
        original_timelog: Timelog,
        dates: List[Union[str, date]],
    ) -> List[Timelog]:
        """
        Duplicate a timelog to specific dates.
        
        Args:
            session: Database session
            original_timelog: The timelog to duplicate
            dates: List of dates in YYYY-MM-DD format or date objects
        
        Returns:
            List of created timelogs
        """
        created_logs = []
        
        # Get time difference from original
        time_diff = original_timelog.end_time - original_timelog.start_time
        
        for date_item in dates:
            try:
                # Handle both string and date object inputs
                if isinstance(date_item, date):
                    target_date = date_item
                else:
                    target_date = datetime.strptime(date_item, "%Y-%m-%d").date()
                
                # Check if there's already a task on this day that overlaps
                new_start = datetime.combine(target_date, original_timelog.start_time.time())
                new_end = new_start + time_diff
                
                # Query for overlapping timelogs
                stmt = select(Timelog).where(
                    Timelog.user_id == original_timelog.user_id,
                    Timelog.start_time < new_end,
                    Timelog.end_time > new_start,
                )
                result = await session.execute(stmt)
                overlapping = result.scalars().first()
                
                # Only create if no overlap
                if not overlapping:
                    new_log = Timelog(
                        user_id=original_timelog.user_id,
                        type=original_timelog.type,
                        project_id=original_timelog.project_id,
                        task_type_id=original_timelog.task_type_id,
                        description=original_timelog.description,
                        location=original_timelog.location,
                        start_time=new_start,
                        end_time=new_end,
                        duration_minutes=original_timelog.duration_minutes,
                        status=original_timelog.status,
                        exclude_lunch=getattr(original_timelog, "exclude_lunch", False),
                    )
                    session.add(new_log)
                    created_logs.append(new_log)
            except ValueError:
                # Invalid date format, skip this one
                continue
        
        await session.commit()
        return created_logs


timelog_crud = TimelogCRUD(model=Timelog)
