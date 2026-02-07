"""
Privacy Fortress Backend
========================

Zero-Knowledge AI Chat with PII Protection

This is the main entry point for the FastAPI application.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
import os
import sys

from app.core.config import settings
from app.routes import chat_router, sessions_router, health_router, auth_router, vault_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create FastAPI app
app = FastAPI(
    title="Privacy Fortress API",
    description="""
🏛️ **Privacy Fortress** - Zero-Knowledge AI Chat with PII Protection

## Features

- 🎭 **PII Detection & Masking**: Automatically detects and masks personal information
- 🔐 **AES-256-GCM Encryption**: Military-grade encryption for all stored data
- ⏱️ **TTL Auto-Delete**: Tokens automatically expire after 30 minutes
- 🛡️ **Prompt Injection Shield**: Protection against LLM jailbreak attempts
- 🧠 **Zero-Knowledge LLM**: AI never sees real user identities

## Two Lockers

- **Locker 1 (Ephemeral)**: Per-session vault in Redis; TTL; wiped when session ends. Not restored in future.
- **Locker 2 (Persistent)**: One encrypted user profile (name, college, email) per user; recreated into session when you open a session. Until "Forget me".

## Security Layers

1. **Layer 1 - Frontend**: RAM-only state, no localStorage
2. **Layer 2 - Mask-Maker**: NER + Regex + Fuzzy detection
3. **Layer 3 - Ephemeral Vault**: Session mappings (Redis, TTL)
4. **Layer 4 - Persistent Vault**: AES-256 encrypted profile (one per user; consent required)
5. **Layer 5 - LLM**: Prompt shield + response validation; AI never sees PII

## Vault API

- `GET/PUT /api/vault/consent` — Remember me / sync across devices
- `GET /api/vault/profile` — Profile metadata (has_profile, consent)
- `PUT /api/vault/profile` — Save profile: body `{ name?, college?, email? }` or `?session_id=...` to extract from session
- `DELETE /api/vault/profile` — Forget me (delete persistent profile + clear ephemeral vault for user)
    """,
    version="1.0.0",
    docs_url="/docs" if settings.APP_ENV == "development" else None,
    redoc_url="/redoc" if settings.APP_ENV == "development" else None,
)

# Rate limiter state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# GZip middleware — compress responses > 500 bytes for faster transfer
app.add_middleware(GZipMiddleware, minimum_size=500)

# CORS middleware — uses CORS_ORIGINS env var for production flexibility
# Default localhost origins + any from CORS_ORIGINS env var
_default_origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
    "http://127.0.0.1:3000",
]
_env_origins = settings.cors_origins_list if settings.CORS_ORIGINS else []
_all_origins = list(set(_default_origins + _env_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_all_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "code": "INTERNAL_ERROR",
            "detail": str(exc) if settings.APP_ENV == "development" else None
        }
    )


# Include routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(sessions_router)
app.include_router(vault_router)

# Serve static files (logo, etc.)
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info("[STARTUP] Initializing Privacy Fortress...")
    
    # ── Eager-load spaCy model so first request is instant ──
    try:
        from app.middleware.ner_engine import NEREngine
        _ner = NEREngine()
        # Warm it with a test sentence to JIT-compile pipelines
        _ner.detect("Test warmup for Privacy Fortress startup.")
        logger.info("[OK] spaCy NER model preloaded and warmed")
    except Exception as e:
        logger.warning(f"[WARN] NER preload failed (will load on first request): {e}")
    
    # Initialize database + create indexes
    try:
        from app.database.mongodb import get_mongodb
        db = await get_mongodb()
        logger.info(f"[OK] MongoDB connected: {settings.MONGODB_DB_NAME}")
    except Exception as e:
        logger.warning(f"[WARN] MongoDB not available: {e}")
    
    # Test Redis connection
    try:
        from app.vault.redis_client import get_redis_vault
        vault = get_redis_vault()
        health = vault.health_check()
        if health["status"] == "healthy":
            logger.info(f"[OK] Redis vault connected, TTL={settings.VAULT_TTL_SECONDS}s")
        else:
            logger.warning(f"[WARN] Redis issue: {health}")
    except Exception as e:
        logger.warning(f"[WARN] Redis not available: {e}")
    
    # Test Groq connection
    try:
        from app.llm.groq_client import get_groq_client
        groq = get_groq_client()
        logger.info(f"[OK] Groq LLM ready: {groq.model}")
    except Exception as e:
        logger.warning(f"[WARN] Groq not available: {e}")
    
    port = os.environ.get('PORT', '8000')
    env = settings.APP_ENV
    logger.info(f"[READY] Privacy Fortress running on :{port} ({env})")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    print("\n" + "="*60)
    print("  SHUTTING DOWN PRIVACY FORTRESS...")
    print("="*60 + "\n")
    logger.info("[SHUTDOWN] Privacy Fortress shutting down...")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=settings.APP_ENV == "development"
    )
