"""
Redis Vault - Encrypted ephemeral storage for token mappings
TTL-based auto-deletion for privacy

Pro-Level Features:
- Connection pooling with auto-reconnect
- Health monitoring with metrics
- Batch operations for performance
- Graceful degradation on failures
- Performance tracking
"""
import json
import redis
from typing import Dict, Optional, List, Tuple
from datetime import datetime
import logging
import time

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
        
        # Performance metrics
        self._metrics = {
            'total_reads': 0,
            'total_writes': 0,
            'total_deletes': 0,
            'failed_operations': 0,
            'avg_latency_ms': 0.0,
        }
        
        logger.info(f"Redis vault initialized with TTL={self.ttl}s")
    
    def _connect(self):
        """Establish Redis connection with pool and retry logic"""
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                self.client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True,
                    max_connections=50,  # Connection pool size
                    health_check_interval=30  # Health check every 30s
                )
                
                # Test connection
                self.client.ping()
                logger.info(f"Connected to Redis vault (attempt {attempt + 1}/{max_retries})")
                return
                
            except redis.ConnectionError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Redis connection attempt {attempt + 1} failed, retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(f"Failed to connect to Redis after {max_retries} attempts: {e}")
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
        start_time = time.time()
        try:
            key = self._get_mapping_key(session_id)
            
            # Encrypt the mappings
            encrypted = self.encryption.encrypt_dict(mappings)
            
            # Store with TTL
            self.client.setex(key, self.ttl, encrypted)
            
            # Update session metadata
            self._update_session_meta(session_id, len(mappings))
            
            # Track metrics
            self._metrics['total_writes'] += 1
            latency = (time.time() - start_time) * 1000
            self._update_avg_latency(latency)
            
            logger.debug(f"Stored {len(mappings)} mappings for session {session_id} in {latency:.2f}ms")
            return True
            
        except Exception as e:
            self._metrics['failed_operations'] += 1
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
        start_time = time.time()
        try:
            key = self._get_mapping_key(session_id)
            
            encrypted = self.client.get(key)
            
            if not encrypted:
                logger.debug(f"No mappings found for session {session_id}")
                return None
            
            # Decrypt and return
            mappings = self.encryption.decrypt_dict(encrypted)
            
            # Track metrics
            self._metrics['total_reads'] += 1
            latency = (time.time() - start_time) * 1000
            self._update_avg_latency(latency)
            
            logger.debug(f"Retrieved {len(mappings)} mappings for session {session_id} in {latency:.2f}ms")
            return mappings
            
        except Exception as e:
            self._metrics['failed_operations'] += 1
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
            session_key = self._get_session_key(session_id)
            
            # Delete both mappings and session metadata
            deleted = self.client.delete(key, session_key)
            
            # Track metrics
            self._metrics['total_deletes'] += 1
            
            if deleted:
                logger.info(f"Deleted mappings for session {session_id}")
            
            return bool(deleted)
            
        except Exception as e:
            self._metrics['failed_operations'] += 1
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
            'metrics': self._metrics.copy(),
        }
    
    def _update_avg_latency(self, new_latency_ms: float):
        """Update rolling average latency"""
        total_ops = self._metrics['total_reads'] + self._metrics['total_writes']
        if total_ops == 1:
            self._metrics['avg_latency_ms'] = new_latency_ms
        else:
            # Exponential moving average
            alpha = 0.1  # Smoothing factor
            self._metrics['avg_latency_ms'] = (
                alpha * new_latency_ms + 
                (1 - alpha) * self._metrics['avg_latency_ms']
            )
    
    def batch_delete_sessions(self, session_ids: List[str]) -> int:
        """
        Delete multiple sessions in a batch (for "Forget Me" operations)
        
        Args:
            session_ids: List of session IDs to delete
            
        Returns:
            Number of sessions deleted
        """
        if not session_ids:
            return 0
        
        try:
            # Build all keys to delete
            keys_to_delete = []
            for sid in session_ids:
                keys_to_delete.append(self._get_mapping_key(sid))
                keys_to_delete.append(self._get_session_key(sid))
            
            # Batch delete with pipeline
            deleted = self.client.delete(*keys_to_delete)
            
            logger.info(f"Batch deleted {deleted} keys for {len(session_ids)} sessions")
            return len(session_ids)
            
        except Exception as e:
            logger.error(f"Failed to batch delete sessions: {e}")
            return 0
    
    def get_metrics(self) -> Dict:
        """Get current performance metrics"""
        return self._metrics.copy()


# Singleton instance
_redis_vault = None


def get_redis_vault() -> RedisVault:
    """Get the singleton Redis vault instance"""
    global _redis_vault
    if _redis_vault is None:
        _redis_vault = RedisVault()
    return _redis_vault
