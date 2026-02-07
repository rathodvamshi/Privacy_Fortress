"""
Response models for API endpoints
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional, Any
from datetime import datetime


class TokenInfo(BaseModel):
    """Single detected PII token for masked prompt viewer — label and (optional) value for data owner."""
    token: str  # e.g. [NAME_1], [COLLEGE_1]
    type: str   # Entity label: USER, COLLEGE, EMAIL, etc.
    display: str  # Masked display e.g. "●●●●●"
    original_value: Optional[str] = None  # Actual value (shown only to data owner)


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
    """Message-level transparency for the Masked Prompt Viewer: user prompt (original + masked), detected tokens with labels, and AI response (masked + unmasked)."""
    original_message: str = Field(
        ...,
        description="Full user input exactly as they typed it (unmasked, before any PII replacement).",
    )
    masked_message: str = Field(
        ...,
        description="Full user input as sent to the AI (PII replaced by placeholders e.g. [NAME_1], [COLLEGE_1]).",
    )
    tokens: List[TokenInfo] = Field(
        default_factory=list,
        description="All PII tokens detected in this exchange: token id, entity type, and original value (for data owner).",
    )
    ai_masked_response: str = Field(
        ...,
        description="AI reply as stored and as the model produced it (placeholders only; zero PII).",
    )
    ai_unmasked_response: str = Field(
        ...,
        description="AI reply as shown to the user (placeholders resolved to real values in backend RAM only).",
    )
    encryption_status: Dict[str, Any] = Field(
        default_factory=dict,
        description="Encryption algorithm and vault status (e.g. AES-256-GCM).",
    )
    ttl_remaining: int = Field(
        ...,
        description="Seconds until ephemeral session vault expires.",
    )

    # ── Safety net: auto-convert UnmaskingResult → str so Pydantic never chokes ──
    @field_validator("original_message", "ai_masked_response", "ai_unmasked_response", mode="before")
    @classmethod
    def _coerce_to_str(cls, v):
        if isinstance(v, str):
            return v
        # If someone passes an UnmaskingResult (or anything with .unmasked_text), extract it
        unmasked = getattr(v, "unmasked_text", None)
        if isinstance(unmasked, str):
            return unmasked
        return str(v) if v is not None else ""


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
