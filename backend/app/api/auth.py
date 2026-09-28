from fastapi import Depends, APIRouter, HTTPException,status, Security
from fastapi.security import OAuth2PasswordRequestForm, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta, date
from app.security import ACCESS_TOKEN_EXPIRE_MINUTES,ALGORITHM,create_access_token
from app.crud.users import user_crud
from app.database import get_async_session
from app.schemas.auth import Token
from app.api.dependencies import authenticate_user, get_current_user
from app.models.users import User
from app.utils.user_utils import is_user_account_active, get_user_status

router = APIRouter(prefix="/auth", tags=["Auth"])
security = HTTPBearer()




@router.post("/login", response_model=Token, summary="Login for access token")
async def login_for_access_token(
    session: AsyncSession = Depends(get_async_session), form_data: OAuth2PasswordRequestForm = Depends()
) -> Token:
    """
    Authenticate user and return JWT access token.
    
    - **username**: Your username
    - **password**: Your password
    
    Returns a JWT token that should be used in the Authorization header for protected endpoints.
    """
    #print(f"Login attempt for username: {form_data.username}")  # Debug log
    try:
        user = await authenticate_user(
            session, username=form_data.username, password=form_data.password
        )
        if not user:
            #print("Authentication failed - user not found or invalid password")  # Debug log
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="INCORRECT USERNAME OR PASSWORD!",
            )
        
        # Blocked account check
        if getattr(user, "blocked", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ACCOUNT BLOCKED — Contact admin",
            )
        
        # Contract enforcement: deny login if account is out of contract or not started
        if not is_user_account_active(user.emp_start_date, user.emp_end_date):
            status_value = get_user_status(user.emp_start_date, user.emp_end_date)
            if status_value == "Inactive (Contract Not Started)":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="CONTRACT NOT STARTED — Contact admin",
                )
            elif status_value == "Inactive (Contract Ended)":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="OUT OF CONTRACT — Contact admin",
                )
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            subject=user.id, expires_delta=access_token_expires, role=user.role
        )
        token = Token(access_token=access_token,token_type="bearer")
        #print(f"Authentication successful for user: {user.username}")  # Debug log
        return token
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        #print(f"Error during authentication: {str(e)}")
        #print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="INCORRECT USERNAME OR PASSWORD!",
        )

@router.get("/verify", summary="Verify token")
async def verify_token(current_user: User = Depends(get_current_user)):
    """
    Verify that the current token is valid and return user info.
    This is a protected endpoint that requires authentication.
    """
    return {
        "message": "Token is valid",
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "role": current_user.role
        }
    }
