"""
Vault Routes — Two lockers

- GET/PUT consent (remember_me, sync_across_devices)
- GET profile metadata (has_profile, consent; no decrypted data)
- PUT profile: save ONE user profile (name, college, email) to Locker 2:
  - Body { name?, college?, email? } to set explicitly (merge with existing)
  - Or ?session_id=... to extract from that session's mappings and save
- DELETE profile: Forget me — delete persistent profile + clear ephemeral vault for all user sessions
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from typing import Optional
import logging

from ..core.auth import get_current_user
from ..models.requests import ConsentUpdateRequest, ProfileSaveRequest
from ..models.responses import (
    ConsentResponse,
    VaultProfileMetaResponse,
    ForgetMeResponse,
)
from ..database.mongodb import get_mongodb
from ..vault.redis_client import get_redis_vault
from ..vault.profile_vault import (
    get_profile_vault,
    session_mappings_to_profile,
    normalize_profile,
)
from ..middleware.pipeline import clear_pipeline
from ..vault.audit import get_audit_logger

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vault", tags=["vault"])


@router.get("/consent", response_model=ConsentResponse)
async def get_consent(current_user: dict = Depends(get_current_user)):
    """Get user's consent flags for persistent profile (Locker 2) and cross-device sync."""
    user_id = current_user["user_id"]
    db = await get_mongodb()
    profile_vault = get_profile_vault()
    consent = await profile_vault.get_consent(db, user_id)
    return ConsentResponse(
        remember_me=consent["remember_me"],
        sync_across_devices=consent["sync_across_devices"],
    )


@router.put("/consent", response_model=ConsentResponse)
async def update_consent(
    request: ConsentUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update consent. Does not store or decrypt profile data."""
    user_id = current_user["user_id"]
    db = await get_mongodb()
    if not db.client:
        raise HTTPException(status_code=503, detail="Database not available")

    profile_vault = get_profile_vault()
    await profile_vault.update_consent(
        db,
        user_id,
        remember_me=request.remember_me,
        sync_across_devices=request.sync_across_devices,
    )
    consent = await profile_vault.get_consent(db, user_id)
    return ConsentResponse(
        remember_me=consent["remember_me"],
        sync_across_devices=consent["sync_across_devices"],
    )


@router.get("/profile", response_model=VaultProfileMetaResponse)
async def get_profile_meta(current_user: dict = Depends(get_current_user)):
    """Get profile metadata only (has_profile, consent). No decrypted data."""
    user_id = current_user["user_id"]
    db = await get_mongodb()
    profile_vault = get_profile_vault()
    consent = await profile_vault.get_consent(db, user_id)
    has_profile = await profile_vault.has_profile(db, user_id)
    return VaultProfileMetaResponse(
        has_profile=has_profile,
        consent=ConsentResponse(
            remember_me=consent["remember_me"],
            sync_across_devices=consent["sync_across_devices"],
        ),
    )


@router.put("/profile")
async def save_profile(
    req: Request,
    request: Optional[ProfileSaveRequest] = None,
    session_id: Optional[str] = Query(None, description="Extract profile from this session's mappings and save"),
    current_user: dict = Depends(get_current_user),
):
    """
    Save ONE user profile to the persistent encrypted vault (Locker 2).
    Requires consent (remember_me or sync_across_devices).

    - Body { name?, college?, email? }: set fields explicitly (merge with existing).
    - Query ?session_id=...: extract name/college/email from that session's current mappings and save.
    - If both: session extraction is base, then body fields overwrite.
    """
    user_id = current_user["user_id"]
    db = await get_mongodb()
    if not db.client:
        raise HTTPException(status_code=503, detail="Database not available")

    profile_vault = get_profile_vault()
    consent = await profile_vault.get_consent(db, user_id)
    if not consent["remember_me"] and not consent["sync_across_devices"]:
        raise HTTPException(
            status_code=403,
            detail="Consent required. Set remember_me or sync_across_devices first (PUT /api/vault/consent).",
        )

    # Require either session_id (extract from session) or at least one body field
    if not session_id:
        if not request or (request.name is None and request.college is None and request.email is None):
            raise HTTPException(
                status_code=400,
                detail="Provide session_id to extract from session, or body with at least one of name, college, email.",
            )

    # Base profile: from session extraction or existing stored profile
    if session_id:
        session = await db.get_session(session_id)
        if not session or session.get("user_id") != user_id:
            raise HTTPException(status_code=404, detail="Session not found")
        redis_vault = get_redis_vault()
        mappings = redis_vault.get_mappings(session_id)
        if not mappings:
            raise HTTPException(
                status_code=400,
                detail="No mappings for this session (empty or TTL expired). Chat first to detect name/college/email, then save.",
            )
        profile = session_mappings_to_profile(mappings)
    else:
        profile = await profile_vault.get_profile(db, user_id) or {"name": None, "college": None, "email": None}
        profile = normalize_profile(profile)

    # Merge body over profile
    if request:
        if request.name is not None:
            profile["name"] = request.name.strip() if request.name else None
        if request.college is not None:
            profile["college"] = request.college.strip() if request.college else None
        if request.email is not None:
            profile["email"] = request.email.strip() if request.email else None

    profile = normalize_profile(profile)
    # Do not store an all-empty profile (would overwrite with nothing)
    if not any(profile.get(k) for k in ("name", "college", "email")):
        raise HTTPException(
            status_code=400,
            detail="Profile would be empty. Provide at least one of name, college, or email.",
        )
    await profile_vault.store_profile(
        db,
        user_id,
        profile,
        consent_remember=consent["remember_me"],
        consent_sync=consent["sync_across_devices"],
    )
    audit = get_audit_logger()
    ip = req.client.host if req.client else None
    audit.log_profile_save(user_id, ip)
    return {
        "status": "saved",
        "message": "Profile saved to persistent vault (AES-256). One profile per user; session state is recreated from it when you open a session.",
    }


@router.delete("/profile", response_model=ForgetMeResponse)
async def forget_me(req: Request, current_user: dict = Depends(get_current_user)):
    """
    Forget me: delete persistent profile (Locker 2) and clear ephemeral vault (Locker 1)
    for all of this user's sessions.
    """
    user_id = current_user["user_id"]
    db = await get_mongodb()
    profile_vault = get_profile_vault()
    redis_vault = get_redis_vault()

    profile_deleted = False
    if db.client:
        profile_deleted = await profile_vault.delete_profile(db, user_id)

    ephemeral_cleared = 0
    if db.client:
        cursor = db.sessions.find({"user_id": user_id}, {"_id": 1})
        async for session in cursor:
            sid = session["_id"]
            if redis_vault.delete_mappings(sid):
                ephemeral_cleared += 1
            clear_pipeline(sid)

    audit = get_audit_logger()
    ip = req.client.host if req.client else None
    audit.log_profile_delete(user_id, ip)

    return ForgetMeResponse(
        status="deleted",
        profile_deleted=profile_deleted,
        ephemeral_vault_cleared=ephemeral_cleared > 0,
    )
