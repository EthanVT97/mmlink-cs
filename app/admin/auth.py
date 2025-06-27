from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional
from app.config import Settings
import logging

logger = logging.getLogger(__name__)

# Initialize security
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = Settings()

class AuthService:
    def __init__(self):
        self.settings = Settings()
        self.secret_key = self.settings.jwt_secret
        self.algorithm = self.settings.jwt_algorithm
        self.access_token_expire_minutes = self.settings.jwt_expiration // 60

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """Hash password"""
        return pwd_context.hash(password)

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire})
        
        try:
            encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
            return encoded_jwt
        except Exception as e:
            logger.error(f"Error creating access token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not create access token"
            )

    def verify_token(self, token: str) -> Optional[dict]:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            username: str = payload.get("sub")
            
            if username is None:
                return None
                
            return {"username": username, "role": payload.get("role", "admin")}
            
        except JWTError as e:
            logger.error(f"JWT verification error: {str(e)}")
            return None

    def authenticate_admin(self, username: str, password: str) -> Optional[dict]:
        """Authenticate admin user"""
        try:
            # Simple authentication against environment variables
            # In production, this should be against a database
            if (username == self.settings.admin_username and 
                password == self.settings.admin_password):
                
                return {
                    "username": username,
                    "role": "admin",
                    "permissions": ["read", "write", "delete"]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return None

# Initialize auth service
auth_service = AuthService()

async def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Get current authenticated admin user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        payload = auth_service.verify_token(token)
        
        if payload is None:
            raise credentials_exception
            
        return payload
        
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise credentials_exception

async def get_current_active_admin(current_admin: dict = Depends(get_current_admin)) -> dict:
    """Get current active admin (additional checks can be added here)"""
    # Additional checks for admin status can be added here
    # For example, checking if admin is still active in database
    return current_admin

def create_admin_token(username: str, role: str = "admin") -> str:
    """Create admin access token"""
    access_token_expires = timedelta(minutes=auth_service.access_token_expire_minutes)
    
    access_token = auth_service.create_access_token(
        data={"sub": username, "role": role},
        expires_delta=access_token_expires
    )
    
    return access_token

# Optional: Decorator for role-based access
def require_role(required_role: str):
    """Decorator to require specific role"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Get admin from kwargs (assumes get_current_admin is used)
            admin = kwargs.get('admin') or kwargs.get('current_admin')
            
            if not admin or admin.get('role') != required_role:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required role: {required_role}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator
