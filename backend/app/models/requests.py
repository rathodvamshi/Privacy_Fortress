"""
Request models for API endpoints
"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional
import re


class ChatRequest(BaseModel):
    """Request for chat endpoint"""
    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="User message"
    )
    session_id: Optional[str] = Field(
        None,
        description="Session ID for conversation continuity"
    )
    
    @validator('message')
    def sanitize_message(cls, v):
        # Remove null bytes and control characters
        v = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', v)
        return v.strip()


class MaskRequest(BaseModel):
    """Request for masking endpoint"""
    text: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Text to mask"
    )
    session_id: Optional[str] = Field(
        None,
        description="Session ID for consistent tokenization"
    )


class SessionCreate(BaseModel):
    """Request to create a new session"""
    title: Optional[str] = Field(
        None,
        max_length=200,
        description="Optional session title"
    )


class ProfileUpdate(BaseModel):
    """Request to update user profile"""
    show_masked_by_default: Optional[bool] = None
    enable_notifications: Optional[bool] = None


class ConversationHistoryRequest(BaseModel):
    """Request for conversation history"""
    session_id: str = Field(
        ...,
        description="Session ID"
    )
    message_id: Optional[str] = Field(
        None,
        description="Specific message ID to get masked data for"
    )


class ConsentUpdateRequest(BaseModel):
    """Request to update vault/profile consent"""
    remember_me: Optional[bool] = Field(
        None,
        description="Allow remembering PII for next time"
    )
    sync_across_devices: Optional[bool] = Field(
        None,
        description="Allow syncing encrypted profile across devices"
    )


_EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class ProfileSaveRequest(BaseModel):
    """Request to save persistent profile (Locker 2). One profile per user: name, college, email."""
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="Display name")
    college: Optional[str] = Field(None, min_length=1, max_length=200, description="College or organization")
    email: Optional[str] = Field(None, max_length=255, description="Email address")

    @validator("email")
    def email_format_if_present(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("Invalid email format")
        return v
