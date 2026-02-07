"""
Redis Vault - Encrypted ephemeral storage for token mappings
TTL-based auto-deletion for privacy
"""
import json
import redis
from typing import Dict, Optional, List
from datetime import datetime
import logging

from ..core.config import settings
from ..core.exceptions import VaultException
from .encryption import AESEncryption, get_encryption

logger = logging.getLogger(__name__)


class RedisVault:
    """
    Redis-based vault for storing encrypted token mappings
    
    Features:
    - AES-256-GCM encryption at rest
    - TTL-based auto-deletion (30 minutes)
    - Session-scoped storage
    - Connection pooling
    """
    
    # Key prefixes
    PREFIX_MAPPINGS = "pf:mappings"
    PREFIX_SESSION = "pf:session"
    PREFIX_AUDIT = "pf:audit"
    
    def __init__(self, redis_url: str = None, ttl: int = None):
        """
        Initialize Redis vault connection
        
        Args:
            redis_url: Redis connection URL (defaults to env variable)
            ttl: Time-to-live in seconds (defaults to 30 minutes)
        """
        self.redis_url = redis_url or settings.REDIS_URL
        self.ttl = ttl or settings.VAULT_TTL_SECONDS
        
        if not self.redis_url:
            raise VaultException("Redis URL not configured")
        
        # Initialize connection
        self.client = None
        self._connect()
        
        # Initialize encryption
        self.encryption = get_encryption()
        
        logger.info(f"Redis vault initialized with TTL={self.ttl}s")
    
    def _connect(self):
        """Establish Redis connection with pool"""
        try:
            self.client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )
            
            # Test connection
            self.client.ping()
            logger.info("Connected to Redis vault")
            
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise VaultException(f"Redis connection failed: {str(e)}")
    
    def _get_mapping_key(self, session_id: str) -> str:
        """Get Redis key for session mappings"""
        return f"{self.PREFIX_MAPPINGS}:{session_id}"
    
    def _get_session_key(self, session_id: str) -> str:
        """Get Redis key for session metadata"""
        return f"{self.PREFIX_SESSION}:{session_id}"
    
    def store_mappings(self, session_id: str, mappings: Dict[str, Dict]) -> bool:
        """
        Store encrypted token mappings for a session
        
        Args:
            session_id: Session identifier
            mappings: Token mappings to store
            
        Returns:
            True if successful
        """
        try:
            key = self._get_mapping_key(session_id)
            
            # Encrypt the mappings
            encrypted = self.encryption.encrypt_dict(mappings)
            
            # Store with TTL
            self.client.setex(key, self.ttl, encrypted)
            
            # Update session metadata
            self._update_session_meta(session_id, len(mappings))
            
            logger.debug(f"Stored {len(mappings)} mappings for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store mappings: {e}")
            raise VaultException(f"Failed to store mappings: {str(e)}")
    
    def get_mappings(self, session_id: str) -> Optional[Dict[str, Dict]]:
        """
        Retrieve and decrypt token mappings for a session
        
        Args:
            session_id: Session identifier
            
        Returns:
            Decrypted mappings or None if not found/expired
        """
        try:
            key = self._get_mapping_key(session_id)
            
            encrypted = self.client.get(key)
            
            if not encrypted:
                logger.debug(f"No mappings found for session {session_id}")
                return None
            
            # Decrypt and return
            mappings = self.encryption.decrypt_dict(encrypted)
            
            logger.debug(f"Retrieved {len(mappings)} mappings for session {session_id}")
            return mappings
            
        except Exception as e:
            logger.error(f"Failed to retrieve mappings: {e}")
            return None
    
    def delete_mappings(self, session_id: str) -> bool:
        """
        Delete token mappings for a session
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if deleted
        """
        try:
            key = self._get_mapping_key(session_id)
            deleted = self.client.delete(key)
            
            if deleted:
                logger.info(f"Deleted mappings for session {session_id}")
            
            return bool(deleted)
            
        except Exception as e:
            logger.error(f"Failed to delete mappings: {e}")
            return False
    
    def refresh_ttl(self, session_id: str) -> int:
        """
        Refresh TTL for a session (extends the expiration)
        
        Args:
            session_id: Session identifier
            
        Returns:
            New TTL in seconds
        """
        try:
            key = self._get_mapping_key(session_id)
            
            if self.client.exists(key):
                self.client.expire(key, self.ttl)
                logger.debug(f"Refreshed TTL for session {session_id}")
                return self.ttl
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to refresh TTL: {e}")
            return 0
    
    def get_ttl(self, session_id: str) -> int:
        """
        Get remaining TTL for a session
        
        Args:
            session_id: Session identifier
            
        Returns:
            TTL in seconds (-1 if no expiry, -2 if key doesn't exist)
        """
        try:
            key = self._get_mapping_key(session_id)
            return self.client.ttl(key)
        except Exception as e:
            logger.error(f"Failed to get TTL: {e}")
            return -2
    
    def _update_session_meta(self, session_id: str, token_count: int):
        """Update session metadata"""
        try:
            key = self._get_session_key(session_id)
            meta = {
                'token_count': token_count,
                'last_updated': datetime.utcnow().isoformat(),
            }
            self.client.setex(key, self.ttl, json.dumps(meta))
        except Exception as e:
            logger.warning(f"Failed to update session meta: {e}")
    
    def get_session_meta(self, session_id: str) -> Optional[Dict]:
        """Get session metadata"""
        try:
            key = self._get_session_key(session_id)
            data = self.client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.warning(f"Failed to get session meta: {e}")
            return None
    
    def health_check(self) -> Dict:
        """
        Check Redis connection health
        
        Returns:
            Health status dict
        """
        try:
            start = datetime.now()
            self.client.ping()
            latency = (datetime.now() - start).total_seconds() * 1000
            
            return {
                'status': 'healthy',
                'latency_ms': round(latency, 2),
                'connected': True
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'connected': False
            }
    
    def get_vault_info(self) -> Dict:
        """
        Get vault configuration info (for UI display)
        
        Returns:
            Vault info dict
        """
        encryption_info = self.encryption.get_encryption_info()
        
        return {
            'ttl_seconds': self.ttl,
            'ttl_display': f"{self.ttl // 60} minutes",
            'encryption': encryption_info,
            'auto_delete': True,
        }


# Singleton instance
_redis_vault = None


def get_redis_vault() -> RedisVault:
    """Get the singleton Redis vault instance"""
    global _redis_vault
    if _redis_vault is None:
        _redis_vault = RedisVault()
    return _redis_vault
