import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from data.database import (
    create_user,
    create_user_profile,
    delete_user,
    get_all_users,
    get_user_by_username,
    get_user_profile,
    log_activity,
)

# ── Config ──────────────────────────────────────────────────────────────────────

from config import settings  # noqa: E402

SECRET_KEY = settings.OASIS_SECRET_KEY
ALGORITHM = settings.OASIS_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.OASIS_TOKEN_EXPIRY_HOURS * 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

router = APIRouter(prefix="/auth", tags=["Auth"])


# ── Schemas ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "user"
    display_name: str | None = None
    email: str | None = None
    email2: str | None = None
    company_link: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    created_at: str


# ── Helpers ─────────────────────────────────────────────────────────────────────

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """FastAPI dependency — returns the authenticated user dict."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = get_user_by_username(username)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_role(role: str):
    """Factory: returns a dependency that checks for a specific role."""
    def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user
    return role_checker


def seed_default_users():
    """Create default accounts on first startup."""
    for username, password, role in [
        ("admin", "admin123", "superadmin"),
        ("user", "user123", "user"),
    ]:
        existing = get_user_by_username(username)
        if existing is None:
            user = create_user(username, hash_password(password), role)
        else:
            user = existing
        # Ensure profile exists for every default user
        existing_profile = get_user_profile(user["id"])
        if existing_profile is None:
            create_user_profile(user["id"], username)


# ── Endpoints ───────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request = None):
    """Authenticate and return a JWT access token."""
    user = get_user_by_username(body.username)
    if not user or not verify_password(body.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token({"sub": user["username"], "role": user["role"]})
    ua = request.headers.get("user-agent", "unknown") if request else "unknown"
    log_activity(
        act_type="login",
        message=f"User '{user['username']}' logged in",
        html=f'User <strong>{user["username"]}</strong> logged in',
        user_id=user["id"],
        username=user["username"],
        user_agent=ua,
    )
    return TokenResponse(
        access_token=token,
        username=user["username"],
        role=user["role"],
    )


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    """Return the currently authenticated user (without password hash)."""
    profile = get_user_profile(current_user["id"])
    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "role": current_user["role"],
        "created_at": current_user["created_at"],
        "profile": {
            "display_name": profile["display_name"] if profile else current_user["username"],
            "avatar_color": profile["avatar_color"] if profile else "#FF9E00",
            "theme": profile["theme"] if profile else "dark",
            "settings": profile["settings"] if profile and profile.get("settings") else {},
        } if profile else {},
    }


@router.post("/register")
def register(
    body: RegisterRequest,
    _: dict = Depends(require_role("superadmin")),
):
    """Create a new user. Superadmin only (admin panel)."""
    existing = get_user_by_username(body.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    user = create_user(body.username, hash_password(body.password), body.role)
    create_user_profile(user["id"], user["username"])
    return {"id": user["id"], "username": user["username"], "role": user["role"]}


@router.post("/signup", response_model=TokenResponse)
def signup(body: RegisterRequest, request: Request = None):
    """Public self-registration. Creates account and returns JWT."""
    existing = get_user_by_username(body.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    # Verify email if provided
    if body.email:
        from data.database import is_email_verified
        if not is_email_verified(body.email):
            raise HTTPException(status_code=400, detail="Please verify your email address before signing up")

    user = create_user(body.username, hash_password(body.password), body.role)
    
    # Build settings with additional signup data
    settings = {}
    if body.display_name:
        settings["display_name"] = body.display_name
    if body.email:
        settings["email"] = body.email
    if body.email2:
        settings["email2"] = body.email2
    if body.company_link:
        settings["company_link"] = body.company_link
    
    create_user_profile(user["id"], body.display_name or user["username"])
    
    # Update settings if we have additional data
    if settings:
        from data.database import update_user_profile
        update_user_profile(user["id"], settings=settings)
    
    token = create_access_token({"sub": user["username"], "role": user["role"]})
    ua = request.headers.get("user-agent", "unknown") if request else "unknown"
    log_activity(
        act_type="signup",
        message=f"User '{user['username']}' signed up",
        html=f'User <strong>{user["username"]}</strong> signed up',
        user_id=user["id"],
        username=user["username"],
        user_agent=ua,
    )
    return TokenResponse(
        access_token=token,
        username=user["username"],
        role=user["role"],
    )


@router.get("/users")
def list_users(_: dict = Depends(require_role("superadmin"))):
    """List all users. Superadmin only."""
    return {"users": get_all_users()}


@router.delete("/users/{user_id}")
def remove_user(
    user_id: int,
    current_user: dict = Depends(require_role("superadmin")),
):
    """Delete a user. Superadmin only. Cannot delete yourself."""
    if current_user["id"] == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    if not delete_user(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return {"deleted": True, "user_id": user_id}


# ── Email OTP ──────────────────────────────────────────────────────────────

class SendOTPRequest(BaseModel):
    email: str

class VerifyOTPRequest(BaseModel):
    email: str
    code: str


def _send_email(to: str, subject: str, body: str) -> bool:
    """Send email via SMTP. Returns True on success."""
    import smtplib
    from email.mime.text import MIMEText
    host = settings.SMTP_HOST
    port = settings.SMTP_PORT
    user = settings.SMTP_USER
    passwd = settings.SMTP_PASS
    from_addr = settings.SMTP_FROM or user
    if not all([host, user, passwd]):
        return False
    try:
        msg = MIMEText(body, "html")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            server.login(user, passwd)
            server.sendmail(from_addr, [to], msg.as_string())
        return True
    except Exception:
        return False


@router.post("/send-otp")
def send_otp(body: SendOTPRequest):
    """Send a 6-digit OTP to the given email address."""
    from data.database import create_otp
    code = create_otp(body.email)
    html = f"""
    <div style="font-family:system-ui,sans-serif;max-width:400px;margin:0 auto;padding:32px;background:#081420;border-radius:12px;color:#e8f0f8">
      <h2 style="color:#00ff88;margin:0 0 16px">OASIS-X Email Verification</h2>
      <p style="font-size:14px;color:#6b8aa8">Your one-time verification code is:</p>
      <div style="font-size:32px;font-weight:700;letter-spacing:8px;color:#00ff88;text-align:center;padding:20px;background:rgba(0,255,136,0.08);border-radius:8px;margin:16px 0">{code}</div>
      <p style="font-size:12px;color:#3d5a7a">This code expires in 10 minutes. If you didn't request this, ignore this email.</p>
    </div>
    """
    sent = _send_email(body.email, "OASIS-X — Verify Your Email", html)
    if not sent:
        raise HTTPException(status_code=500, detail="Failed to send verification email. Please try again.")
    return {"sent": True}


@router.post("/verify-otp")
def verify_otp_endpoint(body: VerifyOTPRequest):
    """Verify the OTP code for an email address."""
    from data.database import verify_otp as _verify_otp
    if _verify_otp(body.email, body.code):
        return {"verified": True}
    raise HTTPException(status_code=400, detail="Invalid or expired verification code")


@router.post("/check-otp")
def check_otp(body: SendOTPRequest):
    """Check if an email has been recently verified."""
    from data.database import is_email_verified
    return {"verified": is_email_verified(body.email)}
