import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from data.database import (
    create_user,
    delete_user,
    get_all_users,
    get_user_by_username,
)

# ── Config ──────────────────────────────────────────────────────────────────────

SECRET_KEY = os.environ.get(
    "OASIS_SECRET_KEY",
    "oasis-x-dev-secret-key-do-not-use-in-production",
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours

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
            create_user(username, hash_password(password), role)


# ── Endpoints ───────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    """Authenticate and return a JWT access token."""
    user = get_user_by_username(body.username)
    if not user or not verify_password(body.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token({"sub": user["username"], "role": user["role"]})
    return TokenResponse(
        access_token=token,
        username=user["username"],
        role=user["role"],
    )


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    """Return the currently authenticated user (without password hash)."""
    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "role": current_user["role"],
        "created_at": current_user["created_at"],
    }


@router.post("/register")
def register(
    body: RegisterRequest,
    _: dict = Depends(require_role("superadmin")),
):
    """Create a new user. Superadmin only."""
    existing = get_user_by_username(body.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    user = create_user(body.username, hash_password(body.password), body.role)
    return {"id": user["id"], "username": user["username"], "role": user["role"]}


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
