"""
Response Validator - Validates LLM responses for PII leakage
"""
import re
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class ResponseValidator:
    """
    Validates LLM responses to ensure no PII leakage
    
    Features:
    - Pattern matching for common PII formats
    - Token leakage detection
    - Response sanitization
    """
    
    # Patterns that might indicate PII leakage in responses
    PII_PATTERNS = [
        # Email pattern
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        # Phone patterns
        r'(?:\+91[-.\s]?)?[6-9]\d{9}',
        r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        # Aadhaar
        r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
        # PAN
        r'\b[A-Z]{5}\d{4}[A-Z]\b',
        # Credit card (basic)
        r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
        # SSN
        r'\b\d{3}-\d{2}-\d{4}\b',
    ]
    
    def __init__(self):
        """Initialize response validator"""
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.PII_PATTERNS
        ]
    
    def validate(self, response: str, original_pii: List[str] = None) -> Tuple[bool, List[str]]:
        """
        Validate LLM response for PII leakage
        
        Args:
            response: LLM response text
            original_pii: List of original PII values to check for
            
        Returns:
            Tuple of (is_valid, list of detected leaks)
        """
        leaks = []
        
        # Check for pattern-based PII
        for pattern in self.compiled_patterns:
            matches = pattern.findall(response)
            leaks.extend(matches)
        
        # Check for specific original PII values
        if original_pii:
            for pii in original_pii:
                if pii.lower() in response.lower():
                    leaks.append(pii)
        
        is_valid = len(leaks) == 0
        
        if not is_valid:
            logger.warning(f"PII leakage detected in response: {len(leaks)} items")
        
        return is_valid, leaks
    
    def sanitize(self, response: str, pii_to_remove: List[str]) -> str:
        """
        Remove leaked PII from response
        
        Args:
            response: LLM response with potential leaks
            pii_to_remove: List of PII values to remove
            
        Returns:
            Sanitized response
        """
        sanitized = response
        
        # Remove specific PII
        for pii in pii_to_remove:
            sanitized = re.sub(
                re.escape(pii),
                '[REDACTED]',
                sanitized,
                flags=re.IGNORECASE
            )
        
        return sanitized
    
    def check_token_consistency(self, response: str, valid_tokens: List[str]) -> List[str]:
        """
        Check if response contains only valid tokens
        
        Args:
            response: LLM response
            valid_tokens: List of valid tokens from the session
            
        Returns:
            List of invalid/unknown tokens found
        """
        # Find all token-like patterns in response
        token_pattern = r'\[[A-Z]+_\d+\]'
        found_tokens = re.findall(token_pattern, response)
        
        invalid = [t for t in found_tokens if t not in valid_tokens]
        
        if invalid:
            logger.warning(f"Unknown tokens in response: {invalid}")
        
        return invalid


# Singleton
_validator = None

def get_response_validator() -> ResponseValidator:
    global _validator
    if _validator is None:
        _validator = ResponseValidator()
    return _validator
