"""
Regex Engine - Pattern-based PII detection
Detects: Emails, Phones, Aadhaar, PAN, Credit Cards, IPs, etc.
"""
import re
from typing import List, Dict, Pattern
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class DetectedEntity:
    """Represents a detected entity"""
    text: str
    entity_type: str
    start: int
    end: int
    confidence: float
    source: str


class RegexEngine:
    """
    Pattern-based PII detection using regex
    High precision for structured data
    """
    
    # Comprehensive PII patterns
    PATTERNS: Dict[str, Dict] = {
        # Email patterns
        'EMAIL': {
            'pattern': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'confidence': 0.98,
            'description': 'Email addresses'
        },
        
        # Phone patterns
        'PHONE': {
            'pattern': r'''
                (?:
                    # Indian format: +91-9876543210 or 9876543210
                    (?:\+91[-.\s]?)?[6-9]\d{9}
                    |
                    # US format: (555) 123-4567 or 555-123-4567
                    (?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}
                    |
                    # International format: +44 20 7123 4567
                    \+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}
                )
            ''',
            'confidence': 0.95,
            'description': 'Phone numbers (Indian, US, International)'
        },
        
        # Indian Aadhaar Number (12 digits with optional separators)
        'AADHAAR': {
            'pattern': r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
            'confidence': 0.97,
            'description': 'Aadhaar numbers'
        },
        
        # Indian PAN Card (5 letters, 4 digits, 1 letter)
        'PAN': {
            'pattern': r'\b[A-Z]{5}\d{4}[A-Z]\b',
            'confidence': 0.98,
            'description': 'PAN card numbers'
        },
        
        # Credit Card Numbers (13-19 digits with optional separators)
        'CREDIT_CARD': {
            'pattern': r'''
                \b(?:
                    # Visa: starts with 4, 16 digits
                    4\d{3}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}
                    |
                    # MasterCard: starts with 51-55, 16 digits
                    5[1-5]\d{2}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}
                    |
                    # American Express: starts with 34/37, 15 digits
                    3[47]\d{2}[-\s]?\d{6}[-\s]?\d{5}
                )\b
            ''',
            'confidence': 0.96,
            'description': 'Credit card numbers'
        },
        
        # US Social Security Number
        'SSN': {
            'pattern': r'\b(?!000|666|9\d{2})\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0000)\d{4}\b',
            'confidence': 0.95,
            'description': 'US Social Security Numbers'
        },
        
        # IP Addresses
        'IP_ADDRESS': {
            'pattern': r'\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d{1,2})\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d{1,2})\b',
            'confidence': 0.99,
            'description': 'IPv4 addresses'
        },
        
        # Date of Birth (various formats)
        'DOB': {
            'pattern': r'''
                \b(?:
                    # DD/MM/YYYY or DD-MM-YYYY
                    (?:0?[1-9]|[12]\d|3[01])[/-](?:0?[1-9]|1[0-2])[/-](?:19|20)\d{2}
                    |
                    # YYYY/MM/DD or YYYY-MM-DD
                    (?:19|20)\d{2}[/-](?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])
                    |
                    # Month DD, YYYY (e.g., January 15, 1990)
                    (?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}
                )\b
            ''',
            'confidence': 0.90,
            'description': 'Dates of birth'
        },
        
        # Passport Numbers (generic patterns)
        'PASSPORT': {
            'pattern': r'\b[A-Z]{1,2}\d{6,9}\b',
            'confidence': 0.75,
            'description': 'Passport numbers'
        },
        
        # Indian Vehicle Registration
        'VEHICLE_REG': {
            'pattern': r'\b[A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{4}\b',
            'confidence': 0.92,
            'description': 'Indian vehicle registration numbers'
        },
        
        # Bank Account Numbers (Indian IFSC + Account)
        'BANK_ACCOUNT': {
            'pattern': r'\b[A-Z]{4}0[A-Z0-9]{6}\b',  # IFSC code
            'confidence': 0.88,
            'description': 'Bank IFSC codes'
        },
        
        # URLs (can contain usernames, tracking info)
        'URL': {
            'pattern': r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?:/[^\s]*)?',
            'confidence': 0.85,
            'description': 'URLs'
        },
        
        # Physical Addresses (basic pattern)
        'ADDRESS': {
            'pattern': r'\b\d{1,5}\s+[\w\s]{1,50}(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Way|Place|Pl)\.?\b',
            'confidence': 0.70,
            'description': 'Physical addresses'
        },
        
        # College/University Roll Numbers (common patterns)
        'ROLL_NUMBER': {
            'pattern': r'\b(?:\d{2}[A-Z]{2,4}\d{3,5}|[A-Z]{2,4}\d{4,8})\b',
            'confidence': 0.80,
            'description': 'College roll numbers'
        },
        
        # Employee IDs (generic)
        'EMPLOYEE_ID': {
            'pattern': r'\b(?:EMP|ID|EMPLOYEE)[-_]?\d{4,10}\b',
            'confidence': 0.85,
            'description': 'Employee IDs'
        },
    }
    
    def __init__(self):
        """Initialize the regex engine with compiled patterns"""
        self.compiled_patterns: Dict[str, Pattern] = {}
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile all regex patterns for efficiency"""
        for entity_type, config in self.PATTERNS.items():
            try:
                self.compiled_patterns[entity_type] = re.compile(
                    config['pattern'],
                    re.IGNORECASE | re.VERBOSE
                )
                logger.debug(f"Compiled pattern for {entity_type}")
            except re.error as e:
                logger.error(f"Failed to compile pattern for {entity_type}: {e}")
    
    def detect(self, text: str) -> List[DetectedEntity]:
        """
        Detect PII patterns in the text
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of DetectedEntity objects
        """
        if not text or not text.strip():
            return []
        
        entities = []
        
        for entity_type, pattern in self.compiled_patterns.items():
            for match in pattern.finditer(text):
                entity = DetectedEntity(
                    text=match.group(),
                    entity_type=entity_type,
                    start=match.start(),
                    end=match.end(),
                    confidence=self.PATTERNS[entity_type]['confidence'],
                    source='regex'
                )
                entities.append(entity)
        
        logger.debug(f"Regex detected {len(entities)} patterns in text")
        return entities
    
    def detect_specific(self, text: str, entity_types: List[str]) -> List[DetectedEntity]:
        """
        Detect only specific types of PII
        
        Args:
            text: Input text to analyze
            entity_types: List of entity types to detect
            
        Returns:
            List of DetectedEntity objects
        """
        entities = []
        
        for entity_type in entity_types:
            if entity_type not in self.compiled_patterns:
                continue
            
            pattern = self.compiled_patterns[entity_type]
            for match in pattern.finditer(text):
                entity = DetectedEntity(
                    text=match.group(),
                    entity_type=entity_type,
                    start=match.start(),
                    end=match.end(),
                    confidence=self.PATTERNS[entity_type]['confidence'],
                    source='regex'
                )
                entities.append(entity)
        
        return entities
    
    def get_supported_types(self) -> List[str]:
        """Get list of supported entity types"""
        return list(self.PATTERNS.keys())


# Singleton instance
_regex_engine = None

def get_regex_engine() -> RegexEngine:
    """Get the singleton regex engine instance"""
    global _regex_engine
    if _regex_engine is None:
        _regex_engine = RegexEngine()
    return _regex_engine
