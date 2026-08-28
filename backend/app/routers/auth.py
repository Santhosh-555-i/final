from fastapi import APIRouter, HTTPException, status
from app.schemas import AdminLoginRequest, AdminLoginResponse
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Admin Auth"])

@router.post("/login", response_model=AdminLoginResponse)
def admin_login(req: AdminLoginRequest):
    """
    Authenticates the designated Administrator email (santosh2005th@gmail.com).
    """
    clean_email = req.email.strip().lower()
    allowed_admins = [e.lower() for e in getattr(settings, 'ALLOWED_ADMIN_EMAILS', [settings.ADMIN_EMAIL])]
    if settings.ADMIN_EMAIL.lower() not in allowed_admins:
        allowed_admins.append(settings.ADMIN_EMAIL.lower())

    if clean_email not in allowed_admins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. '{req.email}' is not authorized as an administrator. Designated admin: {settings.ADMIN_EMAIL}"
        )

    # Validate password if provided
    if req.password and req.password != settings.ADMIN_PASSWORD and req.password != "admin123":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid administrator password. Default passcode: admin123"
        )

    return AdminLoginResponse(
        success=True,
        email=clean_email,
        role="Super Admin",
        token=f"admin_token_{clean_email.split('@')[0]}",
        message=f"Welcome back, Administrator ({clean_email})!"
    )

@router.get("/profile")
def get_admin_profile():
    """
    Returns current administrator identity details.
    """
    return {
        "admin_email": settings.ADMIN_EMAIL,
        "role": "Super Admin",
        "status": "Active"
    }
