"""
Custom exceptions for Privacy Fortress
"""
from fastapi import HTTPException, status


class PrivacyFortressException(Exception):
    """Base exception for Privacy Fortress"""
    def __init__(self, message: str, code: str = "UNKNOWN_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class VaultException(PrivacyFortressException):
    """Raised when vault operations fail"""
    def __init__(self, message: str):
        super().__init__(message, "VAULT_ERROR")


class EncryptionException(PrivacyFortressException):
    """Raised when encryption/decryption fails"""
    def __init__(self, message: str):
        super().__init__(message, "ENCRYPTION_ERROR")


class TokenizationException(PrivacyFortressException):
    """Raised when tokenization fails"""
    def __init__(self, message: str):
        super().__init__(message, "TOKENIZATION_ERROR")


class LLMException(PrivacyFortressException):
    """Raised when LLM operations fail"""
    def __init__(self, message: str):
        super().__init__(message, "LLM_ERROR")


class SessionNotFoundException(HTTPException):
    """Raised when session is not found"""
    def __init__(self, session_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )


class RateLimitExceededException(HTTPException):
    """Raised when rate limit is exceeded"""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )


class InvalidInputException(HTTPException):
    """Raised when input validation fails"""
    def __init__(self, message: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
