"""
Health Routes - Health check and security status endpoints
"""
from fastapi import APIRouter
from datetime import datetime
import logging

from ..models.responses import HealthResponse, SecurityStatusResponse
from ..vault.redis_client import get_redis_vault
from ..vault.encryption import get_encryption
from ..llm.groq_client import get_groq_client
from ..database.mongodb import get_mongodb
from .. import __version__

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Comprehensive health check for all services
    """
    try:
        # Check Redis
        vault = get_redis_vault()
        redis_health = vault.health_check()
    except Exception as e:
        redis_health = {"status": "error", "error": str(e)}
    
    try:
        # Check MongoDB
        db = await get_mongodb()
        mongodb_health = await db.health_check()
    except Exception as e:
        mongodb_health = {"status": "error", "error": str(e)}
    
    try:
        # Check Groq
        groq = get_groq_client()
        groq_health = await groq.health_check()
    except Exception as e:
        groq_health = {"status": "error", "error": str(e)}
    
    # Overall status
    all_healthy = all([
        redis_health.get("status") == "healthy",
        mongodb_health.get("status") == "healthy",
        groq_health.get("status") == "healthy"
    ])
    
    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        timestamp=datetime.utcnow(),
        redis=redis_health,
        mongodb=mongodb_health,
        groq=groq_health,
        version=__version__
    )


@router.get("/health/security", response_model=SecurityStatusResponse)
async def security_status():
    """
    Get security configuration status
    """
    try:
        vault = get_redis_vault()
        encryption = get_encryption()
        
        return SecurityStatusResponse(
            encryption=encryption.get_encryption_info(),
            vault=vault.get_vault_info(),
            ttl_active=True,
            zero_knowledge=True
        )
    except Exception as e:
        logger.error(f"Security status error: {e}")
        return SecurityStatusResponse(
            encryption={"error": str(e)},
            vault={"error": str(e)},
            ttl_active=False,
            zero_knowledge=True
        )


@router.get("/")
async def root():
    """
    Root endpoint
    """
    return {
        "name": "Privacy Fortress API",
        "version": __version__,
        "description": "Zero-Knowledge AI Chat with PII Protection",
        "docs": "/docs"
    }
