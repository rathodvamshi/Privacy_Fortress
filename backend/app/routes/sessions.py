"""
Session Routes - Session management endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List
import logging

from ..core.auth import get_current_user, get_optional_user
from ..models.requests import SessionCreate
from ..models.responses import (
    SessionResponse, SessionListResponse, SessionListItem,
    MessageResponse, ProfileResponse, PrivacyStatsResponse
)
from ..database.mongodb import get_mongodb
from ..vault.redis_client import get_redis_vault
from ..vault.profile_vault import (
    get_profile_vault,
    profile_to_session_mappings,
)
from ..middleware.pipeline import get_masking_pipeline, clear_pipeline
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["sessions"])


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    limit: int = 50,
    skip: int = 0,
    current_user: dict = Depends(get_optional_user),
):
    """
    List all sessions for the authenticated user (returns empty for guests)
    """
    try:
        if not current_user:
            return SessionListResponse(sessions=[], total=0)
        user_id = current_user["user_id"]
        db = await get_mongodb()
        
        if not db.client:
            return SessionListResponse(sessions=[], total=0)
        
        sessions = await db.get_user_sessions(user_id, limit=limit, skip=skip)
        
        items = []
        for session in sessions:
            # Get first message as preview
            messages = await db.get_session_messages(session["_id"], limit=1)
            preview = messages[0]["masked_content"][:50] if messages else "Empty chat"
            
            items.append(SessionListItem(
                id=session["_id"],
                title=session.get("title", "Untitled"),
                preview=preview,
                token_count=session.get("token_count", 0),
                created_at=session["created_at"],
                last_active=session["last_active"]
            ))
        
        return SessionListResponse(sessions=items, total=len(items))
        
    except Exception as e:
        logger.error(f"List sessions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: SessionCreate = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new chat session for the authenticated user
    """
    try:
        user_id = current_user["user_id"]
        db = await get_mongodb()
        
        title = request.title if request else "New Chat"
        session_id = await db.create_session(user_id, title)
        
        return SessionResponse(
            id=session_id,
            title=title,
            messages=[],
            token_count=0,
            created_at=datetime.utcnow(),
            last_active=datetime.utcnow(),
            ttl_remaining=1800
        )
        
    except Exception as e:
        logger.error(f"Create session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Get a specific session with all messages (must belong to current user)
    """
    try:
        user_id = current_user["user_id"]
        db = await get_mongodb()
        vault = get_redis_vault()
        
        if not db.client:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = await db.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Verify ownership
        if session.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get messages
        messages = await db.get_session_messages(session_id)

        # Get pipeline to unmask - content MUST be unmasked for frontend display
        pipeline = get_masking_pipeline(session_id)
        # Two lockers: ephemeral first; if empty, recreate session state from persistent profile
        mappings = vault.get_mappings(session_id)
        profile_vault = get_profile_vault()
        consent = await profile_vault.get_consent(db, user_id)
        has_consent = consent.get("sync_across_devices") or consent.get("remember_me")

        if mappings:
            pipeline.load_session_mappings(mappings)
        elif has_consent:
            profile = await profile_vault.get_profile(db, user_id)
            if profile:
                recreated = profile_to_session_mappings(profile)
                if recreated:
                    pipeline.load_session_mappings(recreated)
                    vault.store_mappings(session_id, pipeline.export_session_mappings())
        else:
            pass

        # Build message responses - content = unmasked for UI, masked_content = what AI saw
        message_responses = []
        for msg in messages:
            result = pipeline.unmask(msg["masked_content"])
            display_content = result.unmasked_text

            message_responses.append(MessageResponse(
                id=msg["_id"],
                role=msg["role"],
                content=display_content,  # UNMASKED - what user sees in UI
                masked_content=msg["masked_content"],
                tokens_used=msg.get("tokens_used", []),
                timestamp=msg["timestamp"]
            ))
        
        # Get TTL
        ttl = vault.get_ttl(session_id)
        
        return SessionResponse(
            id=session_id,
            title=session.get("title", "Untitled"),
            messages=message_responses,
            token_count=session.get("token_count", 0),
            created_at=session["created_at"],
            last_active=session["last_active"],
            ttl_remaining=max(ttl, 0)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Delete a session and all its data (must belong to current user)
    """
    try:
        user_id = current_user["user_id"]
        db = await get_mongodb()
        vault = get_redis_vault()
        
        # Verify ownership
        session = await db.get_session(session_id)
        if session and session.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Delete from vault
        vault.delete_mappings(session_id)
        
        # Delete from MongoDB
        if db.client:
            await db.delete_session(session_id)
        
        # Clear pipeline cache
        clear_pipeline(session_id)
        
        return {"status": "deleted", "session_id": session_id}
        
    except Exception as e:
        logger.error(f"Delete session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(current_user: dict = Depends(get_current_user)):
    """
    Get user profile and privacy statistics
    """
    try:
        user_id = current_user["user_id"]
        db = await get_mongodb()
        
        if db.client:
            stats = await db.get_user_stats(user_id)
            # Fetch actual pii/token stats from the stats collection
            actual_stats = await db.stats.find_one({"user_id": user_id}) or {}
            user_doc = await db.users.find_one({"_id": user_id})
        else:
            stats = {"total_sessions": 0, "total_messages": 0, "total_tokens": 0}
            actual_stats = {}
            user_doc = None
        
        pii_protected = actual_stats.get("pii_detected", stats.get("total_tokens", 0) * 2)
        tokens_generated = actual_stats.get("tokens_generated", stats.get("total_tokens", 0))
        member_since = user_doc["created_at"] if user_doc and "created_at" in user_doc else datetime.utcnow()
        
        return ProfileResponse(
            email=current_user.get("email", f"{user_id}@privacy.fortress"),
            member_since=member_since,
            total_sessions=stats.get("total_sessions", 0),
            total_pii_protected=pii_protected,
            total_tokens_generated=tokens_generated,
            data_encrypted_kb=tokens_generated * 0.1,
            preferences={
                "show_masked_by_default": False,
                "enable_notifications": True,
            }
        )
        
    except Exception as e:
        logger.error(f"Get profile error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profile/stats", response_model=PrivacyStatsResponse)
async def get_privacy_stats(current_user: dict = Depends(get_current_user)):
    """
    Get detailed privacy statistics
    """
    try:
        user_id = current_user["user_id"]
        db = await get_mongodb()
        
        if db.client:
            stats = await db.get_user_stats(user_id)
            actual_stats = await db.stats.find_one({"user_id": user_id}) or {}
        else:
            stats = {}
            actual_stats = {}
        
        pii_detected = actual_stats.get("pii_detected", stats.get("total_tokens", 0) * 2)
        tokens_generated = actual_stats.get("tokens_generated", stats.get("total_tokens", 0))
        
        return PrivacyStatsResponse(
            total_sessions=stats.get("total_sessions", 0),
            total_messages=stats.get("total_messages", 0),
            pii_detected=pii_detected,
            tokens_generated=tokens_generated,
            data_encrypted_kb=tokens_generated * 0.1,
            by_type={
                "USER": tokens_generated // 3 if tokens_generated else 0,
                "EMAIL": tokens_generated // 4 if tokens_generated else 0,
                "PHONE": tokens_generated // 5 if tokens_generated else 0,
                "ORG": tokens_generated // 6 if tokens_generated else 0,
            }
        )
        
    except Exception as e:
        logger.error(f"Get stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/sessions/{session_id}")
async def rename_session(
    session_id: str,
    request: SessionCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    Rename a session (must belong to current user)
    """
    try:
        user_id = current_user["user_id"]
        db = await get_mongodb()

        if not db.client:
            raise HTTPException(status_code=503, detail="Database not available")

        session = await db.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        new_title = (request.title or "Untitled").strip()[:200]
        await db.update_session(session_id, {"title": new_title})

        return {"status": "renamed", "session_id": session_id, "title": new_title}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rename session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
