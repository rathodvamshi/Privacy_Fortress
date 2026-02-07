# Vault module — two lockers: ephemeral (Redis) + persistent profile (MongoDB)
from .redis_client import RedisVault, get_redis_vault
from .encryption import AESEncryption, get_encryption
from .audit import AuditLogger, get_audit_logger
from .profile_vault import (
    ProfileVault,
    get_profile_vault,
    profile_to_session_mappings,
    session_mappings_to_profile,
    normalize_profile,
    PROFILE_SCHEMA,
)
