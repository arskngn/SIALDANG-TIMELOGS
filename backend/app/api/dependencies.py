from typing import Tuple
from fastapi import Depends, status,HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from pydantic import ValidationError
from app.security import ACCESS_TOKEN_EXPIRE_MINUTES,ALGORITHM
from app.secrets import JWT_SECRET_KEY
from app.database import get_async_session
from app.schemas.auth import Token,TokenData
from app.crud.users import user_crud
from app.models.users import User
from app.exceptions import _get_credential_exception
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.security import verify_password

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


async def get_user_from_token_body(
    token: str,
    session: AsyncSession,
) -> User:

    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOKEN NOT PROVIDED!"
        )

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        token_data = TokenData(**payload)
    except (jwt.JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="INVALID TOKEN!"
        )

    user = await user_crud.get_one(session, User.id == token_data.sub)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="USER NOT FOUND!"
        )

    return user

def get_token(token: str = Depends(oauth2_scheme)) -> TokenData:
    """
    Retrieve the token payload from the provided JWT token.

    Parameters:
        token (str, optional): The JWT token. Defaults to the value returned by the `oauth2_scheme` dependency.

    Returns:
        TokenPayload: The decoded token payload.

    Raises:
        HTTPException: If there is an error decoding the token or validating the payload.
    """
    #print(f"DEBUG get_token: token = {token[:20] if token else None}...")
    try:
        payload = jwt.decode(
            token, JWT_SECRET_KEY, algorithms=[ALGORITHM]
        )
        token_data = TokenData(**payload)
        #print(f"DEBUG: Token decoded successfully, sub = {token_data.sub}")
    except (jwt.JWTError, ValidationError) as e:
        #print(f"DEBUG: Token decode failed: {e}")
        raise _get_credential_exception(status_code=status.HTTP_403_FORBIDDEN) from e
    return token_data


async def get_current_user(
    session: AsyncSession = Depends(get_async_session), token: TokenData = Depends(get_token)
) -> User:
    """
    Retrieves the current user based on the provided database session and authentication token.

    Parameters:
        session (Session): The database session to use for querying the user information.
        token (TokenPayload): The authentication token containing the user's identification.

    Returns:
        User: The user object representing the current authenticated user.

    Raises:
        HTTPException: If the user is not found in the database.
    """
    #print(f"DEBUG get_current_user: token.sub = {token.sub}")
    current_user = await user_crud.get_one(session, User.id == token.sub)
    if current_user is None:
        #print(f"DEBUG: User not found for ID {token.sub}")
        raise _get_credential_exception(
            status_code=status.HTTP_404_NOT_FOUND, details="USER NOT FOUND!"
        )
    return current_user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Returns the current user if they have admin role.

    Parameters:
        current_user (User): The current user.

    Returns:
        User: The current admin user.

    Raises:
        HTTPException: If the user does not have admin role
    """
    if not current_user.role or current_user.role.lower() != "admin":
        raise _get_credential_exception(
            status_code=status.HTTP_403_FORBIDDEN,
            details="USER DOES NOT HAVE ADMIN PRIVILEGES!",
        )
    return current_user


async def get_current_manager(
    current_user: User = Depends(get_current_user),
) -> User:
    """Returns the current user if they have manager or admin role.

    Parameters:
        current_user (User): The current user.

    Returns:
        User: The current user with manager/admin role.
        
    Access rules:
    - Admin: Full access
    - Manager: Full access to all projects and timelogs
    - User: Access denied
    """
    role = (current_user.role or "").lower()
    #print(f"DEBUG get_current_manager: user_id={current_user.id}, role={current_user.role}, role_lower={role}")
    if role not in ("admin", "manager"):
        #print(f"DEBUG: User {current_user.id} does not have manager role, rejecting")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="USER DOES NOT HAVE MANAGER PRIVILEGES!",
        )
    #print(f"DEBUG: User {current_user.id} has manager role, allowing")
    return current_user


async def get_current_project_manager(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> User:
    """Returns the current user if they are a project manager (assigned to at least one project).
    
    A project manager is someone with:
    - Admin role, OR
    - Manager role, OR
    - Assigned to a project as 'Project Manager' or 'manager'
    """
    from sqlalchemy import select, func
    from app.models.user_projects import UserProject
    
    role = (current_user.role or "").lower()
    
    # Admin and Manager roles automatically qualify
    if role in ("admin", "manager"):
        return current_user
    
    # Check if user is assigned as project manager to any project
    project_mgr_query = select(func.count(UserProject.id)).where(
        UserProject.user_id == current_user.id,
        UserProject.role_in_project.in_(["project_manager", "manager", "admin"]),
    )
    result = await session.execute(project_mgr_query)
    count = result.scalar_one()
    
    if count > 0:
        return current_user
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="USER IS NOT A PROJECT MANAGER",
    )





async def authenticate_user(
        session: AsyncSession, username: str, password: str
) -> Optional[User]:
        #print(f"Attempting to authenticate user: {username}")  # Debug log
        user:User = await user_crud.get_one(session,User.username==username)
        if not user:
            #print(f"User not found: {username}")  # Debug log
            return None
        if not verify_password(password, user.password):
            #print(f"Invalid password for user: {username}")  # Debug log
            return None
        #print(f"Authentication successful for user: {username}")  # Debug log
        return user
