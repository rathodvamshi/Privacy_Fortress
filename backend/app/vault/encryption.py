"""
AES-256-GCM Encryption for Vault Data
Military-grade encryption for token mappings
"""
import os
import base64
import hashlib
import secrets
from typing import Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

from ..core.config import settings
from ..core.exceptions import EncryptionException

logger = logging.getLogger(__name__)


class AESEncryption:
    """
    AES-256-GCM encryption for vault data
    
    Features:
    - AES-256 encryption (military-grade)
    - GCM mode for authenticated encryption
    - Random nonce for each encryption
    - Key derivation using PBKDF2
    """
    
    # Nonce size for AES-GCM (12 bytes recommended)
    NONCE_SIZE = 12
    
    # Salt size for key derivation
    SALT_SIZE = 16
    
    # Number of iterations for PBKDF2
    ITERATIONS = 100000
    
    def __init__(self, master_key: str = None):
        """
        Initialize encryption with master key
        
        Args:
            master_key: Master encryption key (defaults to env variable)
        """
        self.master_key = master_key or settings.ENCRYPTION_KEY
        
        if not self.master_key:
            raise EncryptionException("Encryption key not configured")
        
        # Derive a consistent salt from the master key
        self.salt = hashlib.sha256(self.master_key.encode()).digest()[:self.SALT_SIZE]
        
        # Derive the actual encryption key
        self.key = self._derive_key(self.master_key, self.salt)
        
        # Create AESGCM instance
        self.cipher = AESGCM(self.key)
        
        logger.info("AES-256-GCM encryption initialized")
    
    def _derive_key(self, master_key: str, salt: bytes) -> bytes:
        """
        Derive a 256-bit key from the master key using PBKDF2
        
        Args:
            master_key: Master key string
            salt: Salt bytes
            
        Returns:
            32-byte derived key
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits
            salt=salt,
            iterations=self.ITERATIONS,
        )
        return kdf.derive(master_key.encode())
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext using AES-256-GCM
        
        Args:
            plaintext: String to encrypt
            
        Returns:
            Base64-encoded ciphertext (nonce + encrypted data + tag)
        """
        try:
            # Generate random nonce
            nonce = secrets.token_bytes(self.NONCE_SIZE)
            
            # Encrypt
            ciphertext = self.cipher.encrypt(nonce, plaintext.encode(), None)
            
            # Combine nonce + ciphertext and encode as base64
            combined = nonce + ciphertext
            encoded = base64.b64encode(combined).decode()
            
            return encoded
            
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise EncryptionException(f"Failed to encrypt data: {str(e)}")
    
    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt ciphertext using AES-256-GCM
        
        Args:
            ciphertext: Base64-encoded encrypted data
            
        Returns:
            Decrypted plaintext string
        """
        try:
            # Decode from base64
            combined = base64.b64decode(ciphertext)
            
            # Extract nonce and ciphertext
            nonce = combined[:self.NONCE_SIZE]
            encrypted_data = combined[self.NONCE_SIZE:]
            
            # Decrypt
            plaintext = self.cipher.decrypt(nonce, encrypted_data, None)
            
            return plaintext.decode()
            
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise EncryptionException(f"Failed to decrypt data: {str(e)}")
    
    def encrypt_dict(self, data: dict) -> str:
        """
        Encrypt a dictionary as JSON
        
        Args:
            data: Dictionary to encrypt
            
        Returns:
            Encrypted string
        """
        import json
        json_str = json.dumps(data)
        return self.encrypt(json_str)
    
    def decrypt_dict(self, ciphertext: str) -> dict:
        """
        Decrypt JSON data to dictionary
        
        Args:
            ciphertext: Encrypted JSON string
            
        Returns:
            Decrypted dictionary
        """
        import json
        json_str = self.decrypt(ciphertext)
        return json.loads(json_str)
    
    def get_encryption_info(self) -> dict:
        """
        Get encryption configuration info (for UI display)
        
        Returns:
            Dict with encryption details
        """
        return {
            'algorithm': 'AES-256-GCM',
            'key_derivation': 'PBKDF2-SHA256',
            'iterations': self.ITERATIONS,
            'nonce_size': self.NONCE_SIZE,
            'key_size': 256,  # bits
        }


# Singleton instance
_encryption = None


def get_encryption() -> AESEncryption:
    """Get the singleton encryption instance"""
    global _encryption
    if _encryption is None:
        _encryption = AESEncryption()
    return _encryption
