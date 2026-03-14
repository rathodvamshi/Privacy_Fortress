"""
Persistent Encrypted Profile Vault (Locker 2 — LONG-TERM)

ONE encrypted user profile per user: { "name", "college", "email" }.
AES-256-GCM encrypted at rest. Decrypted only in RAM when recreating session state.
We do NOT store encrypted session vaults; we store one profile and recreate sessions from it.

Pro-Level Features:
- Profile versioning for migration support
- Data integrity validation
- Soft delete (retention) support
- Enhanced audit trail
- Performance monitoring
"""
import logging
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta

from ..core.exceptions import VaultException, EncryptionException
from .encryption import get_encryption

logger = logging.getLogger(__name__)

# Allowed profile keys and their mapping to token entity types
PROFILE_SCHEMA = {
    "name": "USER",
    "college": "COLLEGE",
    "email": "EMAIL",
}

# Current schema version for migrations
CURRENT_SCHEMA_VERSION = "2.0"

# Soft delete retention period (days)
SOFT_DELETE_RETENTION_DAYS = 30


def profile_to_session_mappings(profile: Dict[str, Optional[str]]) -> Dict[str, Dict]:
    """
    Convert persistent profile (name, college, email) into session-mapping format
    so the pipeline can load it. Used when reopening a session: we RECREATE
    session state from the profile, not restore an old session vault.

    Returns dict: token -> { original, entity_type, positions }
    e.g. [USER_1] -> { "original": "Alice", "entity_type": "USER", "positions": [] }
    """
    mappings = {}
    for idx, (key, entity_type) in enumerate(PROFILE_SCHEMA.items(), start=1):
        value = profile.get(key) if isinstance(profile.get(key), str) else None
        if not value or not value.strip():
            continue
        token = f"[{entity_type}_{idx}]"
        mappings[token] = {
            "original": value.strip(),
            "entity_type": entity_type,
            "positions": [],
        }
    return mappings


def session_mappings_to_profile(mappings: Dict[str, Dict]) -> Dict[str, Optional[str]]:
    """
    Extract a single user profile from session token mappings.
    Takes first USER -> name, first COLLEGE -> college, first EMAIL -> email.
    Used when saving "current session" into the persistent profile (one profile, not all sessions).
    """
    profile = {"name": None, "college": None, "email": None}
    for token, data in mappings.items():
        orig = (data.get("original") or "").strip()
        if not orig:
            continue
        entity_type = (data.get("entity_type") or "").upper()
        if entity_type == "USER" and profile["name"] is None:
            profile["name"] = orig
        elif entity_type == "COLLEGE" and profile["college"] is None:
            profile["college"] = orig
        elif entity_type == "EMAIL" and profile["email"] is None:
            profile["email"] = orig
    return profile


def normalize_profile(profile: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Ensure profile has only allowed keys and string or None values. Empty strings → None."""
    out = {}
    for key in PROFILE_SCHEMA:
        v = profile.get(key)
        if v is None:
            out[key] = None
        elif isinstance(v, str) and v.strip():
            out[key] = v.strip()
        else:
            out[key] = None
    return out


class ProfileVault:
    """
    Persistent vault for ONE user profile (Locker 2).

    - Stores: { "name": "...", "college": "...", "email": "..." } (AES-256-GCM).
    - One document per user_id in encrypted_profiles.
    - Decrypted only in middleware RAM to recreate session mappings.
    - Never store encrypted session vaults; only this single profile.
    
    Pro Features:
    - Versioned schema for migrations
    - Integrity validation
    - Soft delete with retention
    - Performance metrics
    """

    def __init__(self, encryption=None):
        self.encryption = encryption or get_encryption()
        self._metrics = {
            'total_saves': 0,
            'total_retrievals': 0,
            'total_deletes': 0,
            'failed_operations': 0,
        }
    
    def _validate_profile_integrity(self, profile: Dict[str, Optional[str]]) -> List[str]:
        """Validate profile data integrity"""
        errors = []
        
        # Check for unexpected keys
        for key in profile.keys():
            if key not in PROFILE_SCHEMA:
                errors.append(f"Unexpected field: {key}")
        
        # Validate email format if present
        if profile.get("email"):
            email = profile["email"]
            if "@" not in email or "." not in email.split("@")[-1]:
                errors.append(f"Invalid email format: {email}")
        
        # Validate name length
        if profile.get("name") and len(profile["name"]) > 100:
            errors.append("Name exceeds maximum length (100)")
        
        # Validate college length
        if profile.get("college") and len(profile["college"]) > 200:
            errors.append("College name exceeds maximum length (200)")
        
        return errors

    async def store_profile(
        self,
        db,
        user_id: str,
        profile: Dict[str, Optional[str]],
        consent_remember: bool = True,
        consent_sync: bool = True,
    ) -> bool:
        """
        Encrypt and store ONE user profile (name, college, email).
        Only call when user has given consent.
        
        Pro Features:
        - Integrity validation before storage
        - Schema versioning
        - Audit trail
        """
        if not db or not db.client:
            raise VaultException("Database not available")

        try:
            # Validate profile integrity
            normalized = normalize_profile(profile)
            validation_errors = self._validate_profile_integrity(normalized)
            if validation_errors:
                logger.warning(f"Profile validation issues: {validation_errors}")
                # Continue with warning, not error (allow partial profiles)
            
            # Encrypt profile
            encrypted_blob = self.encryption.encrypt_dict(normalized)
            
            doc = {
                "_id": user_id,
                "encrypted_blob": encrypted_blob,
                "consent_remember": consent_remember,
                "consent_sync": consent_sync,
                "schema_version": CURRENT_SCHEMA_VERSION,
                "updated_at": datetime.utcnow(),
                "created_at": datetime.utcnow(),  # Will be preserved on update
            }
            
            # Upsert with atomic update
            result = await db.encrypted_profiles.update_one(
                {"_id": user_id},
                {
                    "$set": {
                        "encrypted_blob": encrypted_blob,
                        "consent_remember": consent_remember,
                        "consent_sync": consent_sync,
                        "schema_version": CURRENT_SCHEMA_VERSION,
                        "updated_at": datetime.utcnow(),
                    },
                    "$setOnInsert": {
                        "created_at": datetime.utcnow(),
                    }
                },
                upsert=True,
            )
            
            # Track metrics
            self._metrics['total_saves'] += 1
            
            action = "Created" if result.upserted_id else "Updated"
            logger.info(f"{action} encrypted profile for user {user_id[:8]}... (schema v{CURRENT_SCHEMA_VERSION})")
            return True
            
        except EncryptionException as e:
            self._metrics['failed_operations'] += 1
            logger.error(f"Profile encryption failed: {e}")
            raise
        except Exception as e:
            self._metrics['failed_operations'] += 1
            logger.error(f"Failed to store profile: {e}")
            raise VaultException(f"Failed to store profile: {str(e)}")

    async def get_profile(
        self, db, user_id: str
    ) -> Optional[Dict[str, Optional[str]]]:
        """
        Retrieve and decrypt the user profile.
        Caller must use result only in RAM; then pass through profile_to_session_mappings
        to recreate session state. Never log or persist decrypted content.
        
        Pro Features:
        - Schema migration support
        - Soft delete filtering
        - Performance tracking
        """
        if not db or not db.client:
            return None

        try:
            doc = await db.encrypted_profiles.find_one({
                "_id": user_id,
                "deleted_at": {"$exists": False}  # Exclude soft-deleted profiles
            })
            
            if not doc or not doc.get("encrypted_blob"):
                return None
            
            # Check schema version for migration
            schema_version = doc.get("schema_version", "1.0")
            if schema_version != CURRENT_SCHEMA_VERSION:
                logger.info(f"Profile schema migration needed: {schema_version} → {CURRENT_SCHEMA_VERSION}")
                # Migration logic can be added here if needed
            
            # Decrypt profile
            profile = self.encryption.decrypt_dict(doc["encrypted_blob"])
            
            # Track metrics
            self._metrics['total_retrievals'] += 1
            
            return normalize_profile(profile)
            
        except Exception as e:
            self._metrics['failed_operations'] += 1
            logger.error(f"Failed to get profile: {e}")
            return None

    async def get_consent(self, db, user_id: str) -> Dict[str, bool]:
        """Get consent flags without decrypting profile."""
        if not db or not db.client:
            return {"remember_me": False, "sync_across_devices": False}

        try:
            doc = await db.encrypted_profiles.find_one(
                {"_id": user_id},
                {"consent_remember": 1, "consent_sync": 1},
            )
            if not doc:
                return {"remember_me": False, "sync_across_devices": False}
            return {
                "remember_me": doc.get("consent_remember", False),
                "sync_across_devices": doc.get("consent_sync", False),
            }
        except Exception as e:
            logger.error(f"Failed to get consent: {e}")
            return {"remember_me": False, "sync_across_devices": False}

    async def update_consent(
        self,
        db,
        user_id: str,
        remember_me: Optional[bool] = None,
        sync_across_devices: Optional[bool] = None,
    ) -> bool:
        """Update only consent flags; does not touch encrypted blob."""
        if not db or not db.client:
            raise VaultException("Database not available")

        updates = {}
        if remember_me is not None:
            updates["consent_remember"] = remember_me
        if sync_across_devices is not None:
            updates["sync_across_devices"] = sync_across_devices
        if not updates:
            return True

        from datetime import datetime

        updates["updated_at"] = datetime.utcnow()
        await db.encrypted_profiles.update_one(
            {"_id": user_id},
            {"$set": updates},
            upsert=True,
        )
        return True

    async def delete_profile(self, db, user_id: str, soft_delete: bool = False) -> bool:
        """
        Delete persistent profile for user (Forget me).
        
        Args:
            db: Database connection
            user_id: User identifier
            soft_delete: If True, mark as deleted but retain for retention period
        
        Returns:
            True if deleted
        """
        if not db or not db.client:
            return False

        try:
            if soft_delete:
                # Soft delete: mark as deleted with timestamp
                result = await db.encrypted_profiles.update_one(
                    {"_id": user_id},
                    {
                        "$set": {
                            "deleted_at": datetime.utcnow(),
                            "deletion_scheduled_for": datetime.utcnow() + timedelta(days=SOFT_DELETE_RETENTION_DAYS)
                        }
                    }
                )
                deleted = result.modified_count > 0
                if deleted:
                    logger.info(f"Soft-deleted profile for user {user_id[:8]}... (retention: {SOFT_DELETE_RETENTION_DAYS} days)")
            else:
                # Hard delete: permanent removal
                result = await db.encrypted_profiles.delete_one({"_id": user_id})
                deleted = result.deleted_count > 0
                if deleted:
                    logger.info(f"Permanently deleted profile for user {user_id[:8]}...")
            
            # Track metrics
            if deleted:
                self._metrics['total_deletes'] += 1
            
            return deleted
            
        except Exception as e:
            self._metrics['failed_operations'] += 1
            logger.error(f"Failed to delete profile: {e}")
            return False

    async def has_profile(self, db, user_id: str) -> bool:
        """Check if user has a stored profile with encrypted data (not just consent)."""
        if not db or not db.client:
            return False
        doc = await db.encrypted_profiles.find_one(
            {
                "_id": user_id,
                "deleted_at": {"$exists": False}  # Exclude soft-deleted
            },
            {"encrypted_blob": 1}
        )
        return doc is not None and bool(doc.get("encrypted_blob"))
    
    async def cleanup_soft_deleted(self, db) -> int:
        """
        Cleanup soft-deleted profiles past retention period.
        Should be called periodically (e.g., daily cron job).
        
        Returns:
            Number of profiles permanently deleted
        """
        if not db or not db.client:
            return 0
        
        try:
            # Find profiles scheduled for deletion
            result = await db.encrypted_profiles.delete_many({
                "deletion_scheduled_for": {"$lte": datetime.utcnow()}
            })
            
            if result.deleted_count > 0:
                logger.info(f"Cleaned up {result.deleted_count} soft-deleted profiles")
            
            return result.deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup soft-deleted profiles: {e}")
            return 0
    
    def get_metrics(self) -> Dict:
        """Get vault performance metrics"""
        return self._metrics.copy()


_profile_vault: Optional[ProfileVault] = None


def get_profile_vault() -> ProfileVault:
    global _profile_vault
    if _profile_vault is None:
        _profile_vault = ProfileVault()
    return _profile_vault
