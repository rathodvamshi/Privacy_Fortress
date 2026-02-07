"""
Persistent Encrypted Profile Vault (Locker 2 — LONG-TERM)

ONE encrypted user profile per user: { "name", "college", "email" }.
AES-256-GCM encrypted at rest. Decrypted only in RAM when recreating session state.
We do NOT store encrypted session vaults; we store one profile and recreate sessions from it.
"""
import logging
from typing import Dict, Optional, Any

from ..core.exceptions import VaultException, EncryptionException
from .encryption import get_encryption

logger = logging.getLogger(__name__)

# Allowed profile keys and their mapping to token entity types
PROFILE_SCHEMA = {
    "name": "USER",
    "college": "COLLEGE",
    "email": "EMAIL",
}


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
    """

    def __init__(self, encryption=None):
        self.encryption = encryption or get_encryption()

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
        """
        if not db or not db.client:
            raise VaultException("Database not available")

        try:
            normalized = normalize_profile(profile)
            encrypted_blob = self.encryption.encrypt_dict(normalized)
            from datetime import datetime

            doc = {
                "_id": user_id,
                "encrypted_blob": encrypted_blob,
                "consent_remember": consent_remember,
                "consent_sync": consent_sync,
                "updated_at": datetime.utcnow(),
            }
            await db.encrypted_profiles.update_one(
                {"_id": user_id},
                {"$set": doc},
                upsert=True,
            )
            logger.info(f"Stored encrypted profile for user {user_id[:8]}...")
            return True
        except EncryptionException as e:
            logger.error(f"Profile encryption failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to store profile: {e}")
            raise VaultException(f"Failed to store profile: {str(e)}")

    async def get_profile(
        self, db, user_id: str
    ) -> Optional[Dict[str, Optional[str]]]:
        """
        Retrieve and decrypt the user profile.
        Caller must use result only in RAM; then pass through profile_to_session_mappings
        to recreate session state. Never log or persist decrypted content.
        """
        if not db or not db.client:
            return None

        try:
            doc = await db.encrypted_profiles.find_one({"_id": user_id})
            if not doc or not doc.get("encrypted_blob"):
                return None
            profile = self.encryption.decrypt_dict(doc["encrypted_blob"])
            return normalize_profile(profile)
        except Exception as e:
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

    async def delete_profile(self, db, user_id: str) -> bool:
        """Permanently delete persistent profile for user (Forget me)."""
        if not db or not db.client:
            return False

        try:
            result = await db.encrypted_profiles.delete_one({"_id": user_id})
            if result.deleted_count:
                logger.info(f"Deleted persistent profile for user {user_id[:8]}...")
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete profile: {e}")
            return False

    async def has_profile(self, db, user_id: str) -> bool:
        """Check if user has a stored profile with encrypted data (not just consent)."""
        if not db or not db.client:
            return False
        doc = await db.encrypted_profiles.find_one(
            {"_id": user_id}, {"encrypted_blob": 1}
        )
        return doc is not None and bool(doc.get("encrypted_blob"))


_profile_vault: Optional[ProfileVault] = None


def get_profile_vault() -> ProfileVault:
    global _profile_vault
    if _profile_vault is None:
        _profile_vault = ProfileVault()
    return _profile_vault
