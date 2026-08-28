import jwt
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from typing import Optional
from app.schemas import AdminLoginRequest, AdminLoginResponse
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Admin Auth"])

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.ADMIN_JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_admin(token: str = Depends(oauth2_scheme)) -> str:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.ADMIN_JWT_SECRET, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None or email.lower() != settings.ADMIN_EMAIL.lower():
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    return email

@router.post("/login", response_model=AdminLoginResponse)
def admin_login(req: AdminLoginRequest):
    clean_email = req.email.strip().lower()

    if clean_email != settings.ADMIN_EMAIL.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Unauthorized email."
        )

    if req.password != settings.ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid administrator password."
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": clean_email}, expires_delta=access_token_expires
    )

    return AdminLoginResponse(
        success=True,
        email=clean_email,
        role="Super Admin",
        token=access_token,
        message=f"Welcome back, Administrator ({clean_email})!"
    )

@router.get("/profile")
def get_admin_profile(admin_email: str = Depends(get_current_admin)):
    return {
        "admin_email": admin_email,
        "role": "Super Admin",
        "status": "Active"
    }
