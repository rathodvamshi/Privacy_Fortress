
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from app.vault.redis_client import RedisVault
from app.vault.profile_vault import ProfileVault, CURRENT_SCHEMA_VERSION, SOFT_DELETE_RETENTION_DAYS
from app.core.exceptions import VaultException

# Mock settings
settings_mock = MagicMock()
settings_mock.REDIS_URL = "redis://localhost:6379/1"
settings_mock.VAULT_TTL_SECONDS = 300
settings_mock.ENCRYPTION_KEY = "test_key_must_be_32_bytes_long_!!" # 32 bytes

@pytest.fixture
def mock_encryption():
    with patch('app.vault.redis_client.get_encryption') as mock:
        enc = MagicMock()
        enc.encrypt_dict.return_value = "encrypted_data"
        enc.decrypt_dict.return_value = {"test": "data"}
        mock.return_value = enc
        yield enc

@pytest.fixture
def redis_vault(mock_encryption):
    with patch('app.vault.redis_client.settings', settings_mock):
        with patch('redis.from_url') as mock_redis:
            # Setup mock Redis client
            client = MagicMock()
            client.ping.return_value = True
            mock_redis.return_value = client
            
            vault = RedisVault()
            vault.client = client # Ensure client is set
            yield vault

@pytest.fixture
def profile_vault(mock_encryption):
    with patch('app.vault.profile_vault.get_encryption') as mock:
        mock.return_value = mock_encryption
        return ProfileVault(encryption=mock_encryption)

@pytest.mark.asyncio
async def test_redis_metrics(redis_vault):
    """Test standard Redis operations track metrics"""
    # 1. Test Write Metrics
    redis_vault.store_mappings("session_1", {"[TEST]": "data"})
    metrics = redis_vault.get_metrics()
    assert metrics['total_writes'] == 1
    assert metrics['avg_latency_ms'] > 0
    
    # 2. Test Read Metrics
    redis_vault.client.get.return_value = "encrypted_data"
    redis_vault.get_mappings("session_1")
    metrics = redis_vault.get_metrics()
    assert metrics['total_reads'] == 1
    
    # 3. Test Delete Metrics
    redis_vault.client.delete.return_value = 2 # keys deleted
    redis_vault.delete_mappings("session_1")
    metrics = redis_vault.get_metrics()
    assert metrics['total_deletes'] == 1

@pytest.mark.asyncio
async def test_redis_batch_delete(redis_vault):
    """Test batch delete operation"""
    session_ids = ["s1", "s2", "s3"]
    redis_vault.client.delete.return_value = 6 # 2 keys per session
    
    count = redis_vault.batch_delete_sessions(session_ids)
    
    assert count == 3
    # Verify client.delete called with all keys
    keys_arg = redis_vault.client.delete.call_args[0]
    assert len(keys_arg) == 6 # 2 keys * 3 sessions

@pytest.mark.asyncio
async def test_profile_integrity(profile_vault):
    """Test profile validation logic"""
    # Valid profile
    errors = profile_vault._validate_profile_integrity({
        "name": "Valid Name",
        "email": "test@example.com"
    })
    assert len(errors) == 0
    
    # Invalid keys
    errors = profile_vault._validate_profile_integrity({
        "bad_key": "value"
    })
    assert "Unexpected field: bad_key" in errors
    
    # Invalid email
    errors = profile_vault._validate_profile_integrity({
        "email": "bad-email"
    })
    assert "Invalid email format: bad-email" in errors[0]

@pytest.mark.asyncio
async def test_profile_storage(profile_vault):
    """Test profile storage with metadata"""
    db = AsyncMock()
    # Mock update_one result
    result = MagicMock()
    result.upserted_id = "user_1"
    db.encrypted_profiles.update_one.return_value = result
    
    success = await profile_vault.store_profile(
        db, "user_1", {"name": "Test"}, True, True
    )
    
    assert success is True
    assert profile_vault.get_metrics()['total_saves'] == 1
    
    # Verify update arguments included version and timestamps
    call_args = db.encrypted_profiles.update_one.call_args
    update_doc = call_args[0][1]
    assert "$set" in update_doc
    assert update_doc["$set"]["schema_version"] == CURRENT_SCHEMA_VERSION
    assert "updated_at" in update_doc["$set"]

@pytest.mark.asyncio
async def test_profile_soft_delete(profile_vault):
    """Test soft delete functionality"""
    db = AsyncMock()
    result = MagicMock()
    result.modified_count = 1
    db.encrypted_profiles.update_one.return_value = result
    
    # Test soft delete
    deleted = await profile_vault.delete_profile(db, "user_1", soft_delete=True)
    
    assert deleted is True
    # Verify update set deleted_at
    call_args = db.encrypted_profiles.update_one.call_args
    update_doc = call_args[0][1]
    assert "deleted_at" in update_doc["$set"]
    assert "deletion_scheduled_for" in update_doc["$set"]
    
@pytest.mark.asyncio
async def test_soft_delete_cleanup(profile_vault):
    """Test cleanup of expired profiles"""
    db = AsyncMock()
    result = MagicMock()
    result.deleted_count = 5
    db.encrypted_profiles.delete_many.return_value = result
    
    count = await profile_vault.cleanup_soft_deleted(db)
    
    assert count == 5
    # Verify query used lte (less than or equal) for timestamp
    call_args = db.encrypted_profiles.delete_many.call_args
    query = call_args[0][0]
    assert "deletion_scheduled_for" in query
    assert "$lte" in query["deletion_scheduled_for"]
