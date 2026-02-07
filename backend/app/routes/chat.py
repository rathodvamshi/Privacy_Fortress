"""
Chat Routes - Main chat and masking endpoints
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from typing import Optional
import uuid
import logging

from ..models.requests import ChatRequest, MaskRequest
from ..models.responses import (
    ChatResponse, MaskResponse, MessageResponse,
    MaskedPromptResponse, EntityInfo, TokenInfo
)
from ..core.auth import get_current_user, get_optional_user
from ..middleware.pipeline import MaskingPipeline, get_masking_pipeline
from ..vault.redis_client import RedisVault, get_redis_vault
from ..vault.audit import get_audit_logger
from ..vault.profile_vault import (
    get_profile_vault,
    profile_to_session_mappings,
)
from ..llm.groq_client import GroqClient, get_groq_client
from ..database.mongodb import get_mongodb
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


def _extract_unmasked_text(result) -> str:
    """
    Extract the plain unmasked-text string from an UnmaskingResult.

    This MUST be called on every return value of ``pipeline.unmask()``
    before the value is stored in a Pydantic model — Pydantic expects a
    plain ``str``, not a dataclass.
    """
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    text = getattr(result, "unmasked_text", None)
    if isinstance(text, str):
        return text
    # Last resort: str() now calls UnmaskingResult.__str__ → unmasked_text
    return str(result) if result is not None else ""


def _detect_pii_leak_in_response(response: str, pipeline) -> bool:
    """
    Detect if the AI's response contains actual PII values instead of tokens.
    
    Returns True if PII leak detected (AI exposed original values).
    """
    if not response:
        return False
    
    # Get all token mappings (token -> original value)
    mappings = pipeline.export_session_mappings()
    
    # Check if ANY original value appears in the response
    # The AI should ONLY have tokens like [USER_1], not "Alice Smith"
    for token_name, mapping_data in mappings.items():
        original_value = mapping_data.get('original', '')
        if original_value and len(original_value) > 2:  # Skip very short values
            # Case-insensitive search
            if original_value.lower() in response.lower():
                logger.warning(f"PII LEAK: Found '{original_value}' in AI response (should be {token_name})")
                return True
    
    return False


def _sanitize_response(response: str, pipeline) -> str:
    """
    Sanitize AI response by replacing any leaked PII values with their tokens.
    
    This is a safety net in case the AI somehow echoes actual values.
    """
    mappings = pipeline.export_session_mappings()
    sanitized = response
    
    # Replace each original value with its token
    # Sort by length (longest first) to avoid partial replacements
    sorted_mappings = sorted(
        mappings.items(),
        key=lambda x: len(x[1].get('original', '')),
        reverse=True
    )
    
    for token_name, mapping_data in sorted_mappings:
        original_value = mapping_data.get('original', '')
        if original_value and len(original_value) > 2:
            # Case-insensitive replace
            import re
            pattern = re.compile(re.escape(original_value), re.IGNORECASE)
            sanitized = pattern.sub(token_name, sanitized)
    
    return sanitized


# CORS preflight handler
@router.options("/chat")
async def chat_options():
    """Handle CORS preflight for /api/chat"""
    return {"message": "OK"}


@router.options("/mask")
async def mask_options():
    """Handle CORS preflight for /api/mask"""
    return {"message": "OK"}


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    req: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Main chat endpoint with full privacy pipeline (authenticated)
    
    Flow:
    1. Get or create session
    2. Mask user message (detect PII, tokenize)
    3. Store tokens in encrypted vault
    4. Send masked message to LLM
    5. Unmask LLM response
    6. Store masked history in MongoDB
    7. Return unmasked response to user
    """
    try:
        user_id = current_user["user_id"]
        print("\n" + "="*60)
        print(f"  NEW CHAT REQUEST (user: {user_id[:8]}...)")
        print("="*60)
        
        # Get or create session
        session_id = request.session_id
        is_new_session = False
        if not session_id:
            session_id = str(uuid.uuid4())
            is_new_session = True
        print(f"\n[1] SESSION: {session_id[:8]}... {'(NEW)' if is_new_session else ''}")
        
        # Initialize components
        vault = get_redis_vault()
        groq = get_groq_client()
        db = await get_mongodb()
        audit = get_audit_logger()

        # Create session in DB for new conversations
        if is_new_session and db.client:
            await db.sessions.insert_one({
                "_id": session_id,
                "user_id": user_id,
                "title": "New Chat",
                "created_at": datetime.utcnow(),
                "last_active": datetime.utcnow(),
                "message_count": 0,
                "token_count": 0,
            })
        elif not is_new_session and db.client:
            # Verify user owns this session
            session = await db.get_session(session_id)
            if session and session.get("user_id") != user_id:
                raise HTTPException(status_code=403, detail="Access denied")
        
        # Get or create masking pipeline for this session
        pipeline = get_masking_pipeline(session_id)

        # CRITICAL: Load ONLY this session's mappings from Redis vault
        # DO NOT load profile mappings - this causes cross-session contamination
        # Each session MUST have isolated token mappings for zero-knowledge guarantee
        existing_mappings = vault.get_mappings(session_id)
        if existing_mappings:
            pipeline.load_session_mappings(existing_mappings)
            logger.info(f"Loaded {len(existing_mappings)} existing tokens for session")
        
        # Step 1: Show original message
        print(f"\n[2] ORIGINAL MESSAGE:")
        print(f"    \"{request.message}\"")
        
        # Step 2: Mask user message
        mask_result = pipeline.mask(request.message)
        
        print(f"\n[3] ENTITIES DETECTED: {mask_result.entities_detected}")
        for token, mapping in mask_result.tokens.items():
            print(f"    {token} <- \"{mapping.original}\" ({mapping.entity_type})")
        
        print(f"\n[4] MASKED MESSAGE (sent to AI):")
        print(f"    \"{mask_result.masked_text}\"")
        
        # Step 3: Store tokens in encrypted vault
        vault.store_mappings(session_id, pipeline.export_session_mappings())
        print(f"\n[5] VAULT: Stored {len(mask_result.tokens)} tokens (AES-256-GCM encrypted)")
        
        # Audit log
        ip = req.client.host if req.client else None
        audit.log_store(session_id, pipeline.get_token_count(), ip)
        
        # Step 4: Get conversation history (masked)
        history = []
        if db.client:
            messages = await db.get_session_messages(session_id, limit=10)
            for msg in messages:
                history.append({
                    "role": msg["role"],
                    "content": msg["masked_content"]
                })
        
        # Step 5: Send masked message to LLM
        print(f"\n[6] SENDING TO GROQ LLM ({groq.model})...")
        masked_response = await groq.chat_async(
            mask_result.masked_text,
            history=history
        )
        
        print(f"\n[7] AI RESPONSE (masked):")
        print(f"    \"{masked_response[:100]}{'...' if len(masked_response) > 100 else ''}\"")
        
        # Step 6: Validate AI response for PII leakage
        # CRITICAL: The AI should ONLY see/use tokens like [USER_1], not actual values
        # If the masked_response contains actual PII values, it means the AI leaked data
        pii_leak_detected = _detect_pii_leak_in_response(masked_response, pipeline)
        if pii_leak_detected:
            logger.warning(f"[SECURITY] AI response contains PII! Sanitizing...")
            print(f"\n[⚠️  WARNING] AI response leaked PII. Auto-sanitizing...")
            # Replace leaked values with tokens in the response
            masked_response = _sanitize_response(masked_response, pipeline)
        
        # Step 7: Unmask LLM response
        unmask_result = pipeline.unmask(masked_response)
        
        print(f"\n[8] UNMASKED RESPONSE (shown to user):")
        print(f"    \"{unmask_result.unmasked_text[:100]}{'...' if len(unmask_result.unmasked_text) > 100 else ''}\"")
        
        # Step 7: Store in MongoDB (masked only!)
        user_msg_id = None
        assistant_msg_id = None
        
        if db.client:
            # Store user message (masked)
            tokens_used = list(mask_result.tokens.keys())
            user_msg_id = await db.add_message(
                session_id,
                "user",
                mask_result.masked_text,
                tokens_used
            )
            
            # Store assistant message (masked)
            assistant_msg_id = await db.add_message(
                session_id,
                "assistant",
                masked_response,
                tokens_used
            )
            
            # Update session
            await db.update_session(session_id, {
                "token_count": pipeline.get_token_count(),
                "title": mask_result.masked_text[:50] + "..." if len(mask_result.masked_text) > 50 else mask_result.masked_text
            })
            
            # Update stats
            await db.increment_stats(
                user_id,
                pii_detected=mask_result.entities_detected,
                tokens_generated=len(mask_result.tokens)
            )
        
        # Get TTL
        ttl = vault.get_ttl(session_id)
        
        print(f"\n[9] SAVED TO MONGODB (masked only)")
        print(f"[10] TTL REMAINING: {ttl} seconds")
        
        # CRITICAL: Ensure unmasked text is used for user display
        display_content = unmask_result.unmasked_text
        if display_content != unmask_result.masked_text:
            print(f"[11] ✓ Returning UNMASKED content to frontend ({len(display_content)} chars)")
        else:
            print(f"[11] ⚠ WARNING: Unmasked same as masked - no tokens replaced!")
        
        print("\n" + "="*60)
        print("  REQUEST COMPLETE - Privacy Protected!")
        print("="*60 + "\n")
        
        # Build response — content MUST be unmasked for frontend display
        msg_id = str(assistant_msg_id) if assistant_msg_id else str(uuid.uuid4())
        return ChatResponse(
            session_id=session_id,
            message=MessageResponse(
                id=msg_id,
                role="assistant",
                content=display_content,
                masked_content=masked_response,
                tokens_used=list(mask_result.tokens.keys()),
                timestamp=datetime.utcnow()
            ),
            token_count=pipeline.get_token_count(),
            ttl_remaining=max(ttl, 0)
        )
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mask", response_model=MaskResponse)
async def mask_text(request: MaskRequest):
    """
    Mask text endpoint (for testing/debugging)
    
    Returns masked text with entity information
    """
    try:
        session_id = request.session_id or str(uuid.uuid4())
        pipeline = get_masking_pipeline(session_id)
        
        result = pipeline.mask(request.text)
        
        # Build entity info list
        entities = [
            EntityInfo(
                token=token,
                type=mapping.entity_type,
                confidence=0.95,  # Average confidence
                sources=["spacy", "regex"]
            )
            for token, mapping in result.tokens.items()
        ]
        
        return MaskResponse(
            original_text=result.original_text,
            masked_text=result.masked_text,
            entities_detected=result.entities_detected,
            entity_breakdown=result.entity_breakdown,
            tokens=entities
        )
        
    except Exception as e:
        logger.error(f"Mask error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/{session_id}/masked/{message_id}", response_model=MaskedPromptResponse)
async def get_masked_prompt(
    session_id: str,
    message_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Masked Prompt Viewer: message-level transparency for one exchange.
    Returns the full user prompt (original + masked), all detected PII tokens with labels and values,
    and the AI response (masked as stored / unmasked as shown to the user).
    Works whether you pass the user message id or the assistant message id.
    """
    try:
        user_id = current_user["user_id"]
        vault = get_redis_vault()
        db = await get_mongodb()
        pipeline = get_masking_pipeline(session_id)

        # Two lockers: ephemeral first; if empty, recreate from profile
        mappings = vault.get_mappings(session_id)
        if mappings:
            pipeline.load_session_mappings(mappings)
        elif db.client:
            profile_vault = get_profile_vault()
            consent = await profile_vault.get_consent(db, user_id)
            has_consent = consent.get("sync_across_devices") or consent.get("remember_me")
            if has_consent:
                profile = await profile_vault.get_profile(db, user_id)
                if profile:
                    recreated = profile_to_session_mappings(profile)
                    if recreated:
                        pipeline.load_session_mappings(recreated)

        # Get message from MongoDB
        message = await db.get_message(message_id) if db.client else None
        
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Get the user message (previous message)
        messages = await db.get_session_messages(session_id, limit=100)
        
        # Find user message and assistant response pair (works for both user and assistant message_id)
        user_msg = None
        assistant_msg = None
        for i, msg in enumerate(messages):
            if msg["_id"] == message_id:
                if msg["role"] == "assistant":
                    assistant_msg = msg
                    if i > 0 and messages[i - 1]["role"] == "user":
                        user_msg = messages[i - 1]
                else:
                    user_msg = msg
                    if i + 1 < len(messages) and messages[i + 1]["role"] == "assistant":
                        assistant_msg = messages[i + 1]
                break

        # Collect all token names used in this pair (user + assistant) for full transparency
        msg_tokens_used = set()
        if user_msg:
            msg_tokens_used.update(user_msg.get("tokens_used") or [])
        if assistant_msg:
            msg_tokens_used.update(assistant_msg.get("tokens_used") or [])

        # Build token info with labels and data (token, type, display, original_value)
        all_mappings = pipeline.export_session_mappings()
        tokens = []
        for token_name in sorted(msg_tokens_used):
            mapping = all_mappings.get(token_name, {})
            original = mapping.get("original", "")
            entity_type = mapping.get("entity_type", "UNKNOWN")
            tokens.append(TokenInfo(
                token=token_name,
                type=entity_type,
                display="●" * min(len(original), 10) if original else "●●●●●",
                original_value=original if original else None,
            ))

        vault_info = vault.get_vault_info()
        ttl = vault.get_ttl(session_id)

        # Full user input: original (unmasked) and masked
        user_message_original = "N/A"
        user_message_masked = "N/A"
        if user_msg:
            user_message_masked = user_msg.get("masked_content") or "N/A"
            _ures = pipeline.unmask(user_message_masked)
            user_message_original = _extract_unmasked_text(_ures) if _ures else "N/A"

        # AI response: masked (what AI saw/sent) and unmasked (what user sees) — always string
        ai_masked = assistant_msg.get("masked_content", "") if assistant_msg else ""
        ai_unmasked_str = ""
        if assistant_msg and ai_masked:
            _res = pipeline.unmask(ai_masked)
            ai_unmasked_str = _extract_unmasked_text(_res) if _res else ""

        return MaskedPromptResponse(
            original_message=user_message_original,
            masked_message=user_message_masked,
            tokens=tokens,
            ai_masked_response=ai_masked,
            ai_unmasked_response=ai_unmasked_str,
            encryption_status=vault_info["encryption"],
            ttl_remaining=max(ttl, 0),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get masked prompt error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    req: Request,
    current_user: dict = Depends(get_optional_user),
):
    """
    Streaming chat endpoint. Uses two lockers: ephemeral first; if empty and user has consent, recreate from persistent profile.
    Returns Server-Sent Events with response chunks.
    """
    try:
        session_id = request.session_id or str(uuid.uuid4())
        user_id = current_user["user_id"] if current_user else None

        vault = get_redis_vault()
        groq = get_groq_client()
        db = await get_mongodb()

        pipeline = get_masking_pipeline(session_id)

        # Two lockers: ephemeral first; if empty, recreate from profile when user has consent
        existing_mappings = vault.get_mappings(session_id)
        if existing_mappings:
            pipeline.load_session_mappings(existing_mappings)
        elif user_id and db.client:
            profile_vault = get_profile_vault()
            consent = await profile_vault.get_consent(db, user_id)
            has_consent = consent.get("sync_across_devices") or consent.get("remember_me")
            if has_consent:
                profile = await profile_vault.get_profile(db, user_id)
                if profile:
                    recreated = profile_to_session_mappings(profile)
                    if recreated:
                        pipeline.load_session_mappings(recreated)
                        vault.store_mappings(session_id, pipeline.export_session_mappings())

        # Mask user message
        mask_result = pipeline.mask(request.message)
        
        # Store in vault
        vault.store_mappings(session_id, pipeline.export_session_mappings())
        
        async def generate():
            full_response = ""
            async for chunk in groq.chat_stream(mask_result.masked_text):
                full_response += chunk
                # Unmask on-the-fly — always extract the text string
                unmasked_chunk = _extract_unmasked_text(pipeline.unmask(chunk))
                yield f"data: {unmasked_chunk}\n\n"
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream"
        )
        
    except Exception as e:
        logger.error(f"Stream error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
