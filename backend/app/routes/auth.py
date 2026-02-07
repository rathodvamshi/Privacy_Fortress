"""
Auth Routes — Register, Login, Token Refresh, Current User
"""
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import logging
import uuid
import re

from ..core.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
)
from ..database.mongodb import get_mongodb

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── Request / Response models ────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)

class LoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict

class RefreshRequest(BaseModel):
    refresh_token: str

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    created_at: datetime


# ── Helpers ───────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

def _validate_email(email: str) -> str:
    email = email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    return email


def _sanitize_name(name: str) -> str:
    name = name.strip()
    name = re.sub(r'[<>"\'/;]', '', name)  # strip dangerous chars
    return name


def _build_user_response(user: dict) -> dict:
    return {
        "id": user["_id"],
        "name": user["name"],
        "email": user["email"],
        "created_at": user["created_at"].isoformat() if isinstance(user["created_at"], datetime) else user["created_at"],
    }


# ── Routes ────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(req: RegisterRequest):
    """
    Create a new user account.
    - Validates email uniqueness
    - Hashes password with bcrypt
    - Returns JWT access + refresh tokens
    """
    db = await get_mongodb()
    if not db.client:
        raise HTTPException(status_code=503, detail="Database not available")

    email = _validate_email(req.email)
    name = _sanitize_name(req.name)

    # Check duplicate
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user_id = str(uuid.uuid4())
    now = datetime.utcnow()

    user_doc = {
        "_id": user_id,
        "name": name,
        "email": email,
        "password_hash": hash_password(req.password),
        "created_at": now,
        "last_login": now,
    }
    await db.users.insert_one(user_doc)
    logger.info(f"[AUTH] New user registered: {email}")

    # Generate tokens
    token_data = {"user_id": user_id, "email": email}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=_build_user_response(user_doc),
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """
    Authenticate with email + password.
    Returns JWT access + refresh tokens.
    """
    db = await get_mongodb()
    if not db.client:
        raise HTTPException(status_code=503, detail="Database not available")

    email = _validate_email(req.email)
    user = await db.users.find_one({"email": email})

    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Update last login
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": datetime.utcnow()}},
    )

    token_data = {"user_id": user["_id"], "email": user["email"]}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    logger.info(f"[AUTH] User logged in: {email}")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=_build_user_response(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(req: RefreshRequest):
    """
    Exchange a refresh token for a new access + refresh token pair.
    """
    payload = decode_token(req.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    db = await get_mongodb()
    user = await db.users.find_one({"_id": payload["user_id"]})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    token_data = {"user_id": user["_id"], "email": user["email"]}
    new_access = create_access_token(token_data)
    new_refresh = create_refresh_token(token_data)

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        user=_build_user_response(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Return the currently authenticated user's profile.
    """
    db = await get_mongodb()
    user = await db.users.find_one({"_id": current_user["user_id"]})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(
        id=user["_id"],
        name=user["name"],
        email=user["email"],
        created_at=user["created_at"],
    )


# ── Profile management ────────────────────────────────────────────

class UpdateProfileRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)


@router.put("/profile")
async def update_profile(
    req: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Update profile fields (currently: name).
    """
    db = await get_mongodb()
    updates = {}
    if req.name is not None:
        updates["name"] = _sanitize_name(req.name)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    await db.users.update_one(
        {"_id": current_user["user_id"]},
        {"$set": updates},
    )
    logger.info(f"[AUTH] Profile updated for user {current_user['user_id']}")
    return {"status": "updated", **updates}


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Change password — requires current password for verification.
    """
    db = await get_mongodb()
    user = await db.users.find_one({"_id": current_user["user_id"]})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(req.current_password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    new_hash = hash_password(req.new_password)
    await db.users.update_one(
        {"_id": current_user["user_id"]},
        {"$set": {"password_hash": new_hash}},
    )
    logger.info(f"[AUTH] Password changed for user {current_user['user_id']}")
    return {"status": "password_changed"}


@router.delete("/account")
async def delete_account(
    current_user: dict = Depends(get_current_user),
):
    """
    Permanently delete the user account and all associated data.
    """
    db = await get_mongodb()
    user_id = current_user["user_id"]

    # Delete all user sessions and their messages
    sessions_cursor = db.sessions.find({"user_id": user_id}, {"_id": 1})
    async for session in sessions_cursor:
        await db.messages.delete_many({"session_id": session["_id"]})
    await db.sessions.delete_many({"user_id": user_id})

    # Delete stats
    await db.stats.delete_many({"user_id": user_id})

    # Delete user document
    await db.users.delete_one({"_id": user_id})

    logger.info(f"[AUTH] Account deleted: {user_id}")
    return {"status": "deleted"}
