"""
Response models for API endpoints
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime


class TokenInfo(BaseModel):
    """Token information for masked prompt viewer"""
    token: str
    type: str
    display: str  # Masked display like "●●●●●"
    original_value: Optional[str] = None  # Actual value (shown to data owner only)


class EntityInfo(BaseModel):
    """Detected entity information"""
    token: str
    type: str
    confidence: float
    sources: List[str]


class MaskResponse(BaseModel):
    """Response from masking endpoint"""
    original_text: str
    masked_text: str
    entities_detected: int
    entity_breakdown: Dict[str, int]
    tokens: List[EntityInfo]


class MessageResponse(BaseModel):
    """Single message in conversation"""
    id: str
    role: str  # "user" or "assistant"
    content: str  # UNMASKED for display - what user sees in UI
    masked_content: str  # What AI saw/generated (for MaskedViewer)
    tokens_used: List[str]
    timestamp: datetime


class ChatResponse(BaseModel):
    """Response from chat endpoint"""
    session_id: str
    message: MessageResponse
    token_count: int
    ttl_remaining: int


class MaskedPromptResponse(BaseModel):
    """Response showing masked prompt details"""
    original_message: str
    masked_message: str
    tokens: List[TokenInfo]
    ai_masked_response: str
    ai_unmasked_response: str
    encryption_status: Dict[str, Any]
    ttl_remaining: int


class SessionResponse(BaseModel):
    """Session information"""
    id: str
    title: str
    messages: List[MessageResponse]
    token_count: int
    created_at: datetime
    last_active: datetime
    ttl_remaining: int


class SessionListItem(BaseModel):
    """Session list item (minimal info)"""
    id: str
    title: str
    preview: str  # First message preview
    token_count: int
    created_at: datetime
    last_active: datetime


class SessionListResponse(BaseModel):
    """Response with list of sessions"""
    sessions: List[SessionListItem]
    total: int


class ProfileResponse(BaseModel):
    """User profile response"""
    email: str
    member_since: datetime
    total_sessions: int
    total_pii_protected: int
    total_tokens_generated: int
    data_encrypted_kb: float
    preferences: Dict[str, bool]


class PrivacyStatsResponse(BaseModel):
    """Privacy statistics response"""
    total_sessions: int
    total_messages: int
    pii_detected: int
    tokens_generated: int
    data_encrypted_kb: float
    by_type: Dict[str, int]


class SecurityStatusResponse(BaseModel):
    """Security status response"""
    encryption: Dict[str, Any]
    vault: Dict[str, Any]
    ttl_active: bool
    zero_knowledge: bool


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    redis: Dict[str, Any]
    mongodb: Dict[str, Any]
    groq: Dict[str, Any]
    version: str


class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    code: str
    detail: Optional[str] = None


class ConsentResponse(BaseModel):
    """Vault consent status"""
    remember_me: bool
    sync_across_devices: bool


class VaultProfileMetaResponse(BaseModel):
    """Encrypted profile metadata (no decrypted data)"""
    has_profile: bool
    consent: ConsentResponse
    encryption: str = "AES-256-GCM"


class ForgetMeResponse(BaseModel):
    """Response after Forget me"""
    status: str = "deleted"
    profile_deleted: bool
    ephemeral_vault_cleared: bool
