"""
Audit Logger - Logs all vault operations for compliance
"""
from datetime import datetime
from typing import Optional
import hashlib
import logging

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Audit logger for vault operations
    Logs actions without storing actual PII
    """
    
    def __init__(self):
        """Initialize audit logger"""
        self.logs = []  # In production, this would go to a database
    
    def log_store(self, session_id: str, token_count: int, ip_address: Optional[str] = None):
        """Log a store operation"""
        self._log('STORE', session_id, token_count, ip_address)
    
    def log_retrieve(self, session_id: str, token_count: int, ip_address: Optional[str] = None):
        """Log a retrieve operation"""
        self._log('RETRIEVE', session_id, token_count, ip_address)
    
    def log_delete(self, session_id: str, ip_address: Optional[str] = None):
        """Log a delete operation"""
        self._log('DELETE', session_id, 0, ip_address)
    
    def log_expire(self, session_id: str):
        """Log an expiration event"""
        self._log('EXPIRE', session_id, 0, None)

    def log_profile_save(self, user_id: str, ip_address: Optional[str] = None):
        """Log persistent profile save (Locker 2). No PII stored."""
        uid_hash = hashlib.sha256(user_id.encode()).hexdigest()[:16]
        ip_hash = hashlib.sha256(ip_address.encode()).hexdigest()[:16] if ip_address else None
        entry = {
            'action': 'PROFILE_SAVE',
            'user_id_hash': uid_hash,
            'timestamp': datetime.utcnow().isoformat(),
            'ip_hash': ip_hash,
        }
        self.logs.append(entry)
        logger.info(f"Audit: PROFILE_SAVE - user={uid_hash}")

    def log_profile_delete(self, user_id: str, ip_address: Optional[str] = None):
        """Log Forget me (profile + ephemeral clear). No PII stored."""
        uid_hash = hashlib.sha256(user_id.encode()).hexdigest()[:16]
        ip_hash = hashlib.sha256(ip_address.encode()).hexdigest()[:16] if ip_address else None
        entry = {
            'action': 'PROFILE_DELETE',
            'user_id_hash': uid_hash,
            'timestamp': datetime.utcnow().isoformat(),
            'ip_hash': ip_hash,
        }
        self.logs.append(entry)
        logger.info(f"Audit: PROFILE_DELETE (Forget me) - user={uid_hash}")
    
    def _log(self, action: str, session_id: str, token_count: int, ip_address: Optional[str]):
        """Internal logging method"""
        # Hash IP for privacy
        ip_hash = None
        if ip_address:
            ip_hash = hashlib.sha256(ip_address.encode()).hexdigest()[:16]
        
        entry = {
            'action': action,
            'session_id_hash': hashlib.sha256(session_id.encode()).hexdigest()[:16],
            'token_count': token_count,
            'timestamp': datetime.utcnow().isoformat(),
            'ip_hash': ip_hash
        }
        
        self.logs.append(entry)
        logger.info(f"Audit: {action} - session={entry['session_id_hash']}, tokens={token_count}")
    
    def get_recent_logs(self, limit: int = 100):
        """Get recent audit logs"""
        return self.logs[-limit:]


# Singleton
_audit_logger = None

def get_audit_logger() -> AuditLogger:
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
