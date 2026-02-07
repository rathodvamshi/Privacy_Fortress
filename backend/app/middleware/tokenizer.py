"""
Tokenizer - Deterministic token generation and bidirectional mapping
Ensures consistent masking within a session
"""
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
import hashlib
import logging

logger = logging.getLogger(__name__)


@dataclass
class ScoredEntity:
    """Entity with aggregated confidence score"""
    text: str
    entity_type: str
    start: int
    end: int
    confidence: float
    sources: List[str]
    priority: int


@dataclass
class TokenMapping:
    """Bidirectional mapping between token and original value"""
    token: str
    original: str
    entity_type: str
    positions: List[Tuple[int, int]] = field(default_factory=list)


class Tokenizer:
    """
    Deterministic tokenizer that replaces PII with consistent tokens
    [USER_1], [ORG_1], [EMAIL_1], etc.
    """
    
    # Token prefix for each entity type
    TOKEN_PREFIXES = {
        'USER': 'USER',
        'ORG': 'ORG',
        'COLLEGE': 'COLLEGE',
        'LOCATION': 'LOCATION',
        'EMAIL': 'EMAIL',
        'PHONE': 'PHONE',
        'AADHAAR': 'AADHAAR',
        'PAN': 'PAN',
        'CREDIT_CARD': 'CARD',
        'SSN': 'SSN',
        'IP_ADDRESS': 'IP',
        'DOB': 'DOB',
        'BANK_ACCOUNT': 'BANK',
        'PASSPORT': 'PASSPORT',
        'VEHICLE_REG': 'VEHICLE',
        'ROLL_NUMBER': 'ROLL',
        'EMPLOYEE_ID': 'EMPID',
        'URL': 'URL',
        'ADDRESS': 'ADDRESS',
        'DATE': 'DATE',
        'MONEY': 'MONEY',
        'GROUP': 'GROUP',
        'FACILITY': 'FACILITY',
        'PRODUCT': 'PRODUCT',
        'EVENT': 'EVENT',
        'WORK': 'WORK',
        'LAW': 'LAW',
        'LANGUAGE': 'LANG',
        'TIME': 'TIME',
        'PERCENT': 'PERCENT',
        'QUANTITY': 'QTY',
        'NUMBER': 'NUM',
        'OTHER': 'OTHER',
    }
    
    def __init__(self, session_id: str):
        """
        Initialize tokenizer for a session
        
        Args:
            session_id: Unique session identifier
        """
        self.session_id = session_id
        
        # Counter for each entity type
        self.type_counters: Dict[str, int] = {}
        
        # Value to token mapping (for deterministic tokenization)
        self.value_to_token: Dict[str, str] = {}
        
        # Token to value mapping (for unmasking)
        self.token_to_value: Dict[str, TokenMapping] = {}
    
    def generate_token(self, entity_type: str, value: str) -> str:
        """
        Generate a deterministic token for a value
        If the value was seen before, return the same token
        
        Args:
            entity_type: Type of entity (USER, EMAIL, etc.)
            value: Original value to tokenize
            
        Returns:
            Token string like [USER_1]
        """
        # Normalize value for consistent matching
        normalized = value.strip().lower()
        
        # Check if we've seen this value before
        if normalized in self.value_to_token:
            return self.value_to_token[normalized]
        
        # Generate new token
        prefix = self.TOKEN_PREFIXES.get(entity_type, 'OTHER')
        
        if entity_type not in self.type_counters:
            self.type_counters[entity_type] = 0
        
        self.type_counters[entity_type] += 1
        counter = self.type_counters[entity_type]
        
        token = f"[{prefix}_{counter}]"
        
        # Store mappings
        self.value_to_token[normalized] = token
        self.token_to_value[token] = TokenMapping(
            token=token,
            original=value,  # Keep original case
            entity_type=entity_type,
            positions=[]
        )
        
        logger.debug(f"Generated token {token} for {entity_type}")
        return token
    
    def mask_text(self, text: str, entities: List[ScoredEntity]) -> Tuple[str, Dict[str, TokenMapping]]:
        """
        Replace all entities in text with tokens
        
        Args:
            text: Original text
            entities: List of detected entities (sorted by position)
            
        Returns:
            Tuple of (masked_text, token_mappings)
        """
        if not entities:
            return text, {}
        
        # Sort entities by start position (descending) for replacement
        sorted_entities = sorted(entities, key=lambda e: e.start, reverse=True)
        
        masked_text = text
        used_mappings: Dict[str, TokenMapping] = {}
        
        for entity in sorted_entities:
            token = self.generate_token(entity.entity_type, entity.text)
            
            # Replace in text
            masked_text = masked_text[:entity.start] + token + masked_text[entity.end:]
            
            # Track position
            if token in self.token_to_value:
                self.token_to_value[token].positions.append((entity.start, entity.end))
                used_mappings[token] = self.token_to_value[token]
        
        logger.info(f"Masked {len(entities)} entities in text")
        return masked_text, used_mappings
    
    def unmask_text(self, masked_text: str) -> str:
        """
        Replace all tokens in text with original values
        
        Args:
            masked_text: Text with tokens
            
        Returns:
            Original text with values restored
        """
        unmasked = masked_text
        
        # Sort tokens by length (longest first) to avoid partial replacements
        sorted_tokens = sorted(self.token_to_value.keys(), key=len, reverse=True)
        
        for token in sorted_tokens:
            if token in unmasked:
                mapping = self.token_to_value[token]
                unmasked = unmasked.replace(token, mapping.original)
        
        return unmasked
    
    def get_token_for_value(self, value: str) -> Optional[str]:
        """
        Get the token for a specific value if it exists
        
        Args:
            value: Original value
            
        Returns:
            Token if found, None otherwise
        """
        normalized = value.strip().lower()
        return self.value_to_token.get(normalized)
    
    def get_value_for_token(self, token: str) -> Optional[str]:
        """
        Get the original value for a token
        
        Args:
            token: Token string
            
        Returns:
            Original value if found, None otherwise
        """
        mapping = self.token_to_value.get(token)
        return mapping.original if mapping else None
    
    def get_all_mappings(self) -> Dict[str, TokenMapping]:
        """Get all token mappings"""
        return self.token_to_value.copy()
    
    def get_token_count(self) -> int:
        """Get the number of tokens generated"""
        return len(self.token_to_value)
    
    def get_tokens_by_type(self, entity_type: str) -> List[str]:
        """
        Get all tokens of a specific type
        
        Args:
            entity_type: Entity type to filter by
            
        Returns:
            List of tokens
        """
        return [
            token for token, mapping in self.token_to_value.items()
            if mapping.entity_type == entity_type
        ]
    
    def load_mappings(self, mappings: Dict[str, Dict]):
        """
        Load existing mappings (e.g., from Redis vault)
        
        Args:
            mappings: Dict of token -> {original, entity_type}
        """
        for token, data in mappings.items():
            self.token_to_value[token] = TokenMapping(
                token=token,
                original=data['original'],
                entity_type=data['entity_type'],
                positions=data.get('positions', [])
            )
            
            # Also update reverse mapping
            normalized = data['original'].strip().lower()
            self.value_to_token[normalized] = token
            
            # Update counter
            entity_type = data['entity_type']
            if entity_type not in self.type_counters:
                self.type_counters[entity_type] = 0
            
            # Extract counter from token
            try:
                counter = int(token.split('_')[-1].rstrip(']'))
                self.type_counters[entity_type] = max(
                    self.type_counters[entity_type],
                    counter
                )
            except (ValueError, IndexError):
                pass
        
        logger.info(f"Loaded {len(mappings)} token mappings")
    
    def export_mappings(self) -> Dict[str, Dict]:
        """
        Export mappings for storage in vault
        
        Returns:
            Dict suitable for JSON serialization
        """
        return {
            token: {
                'original': mapping.original,
                'entity_type': mapping.entity_type,
                'positions': mapping.positions
            }
            for token, mapping in self.token_to_value.items()
        }
    
    def get_masked_summary(self) -> Dict:
        """
        Get a summary of masked data for UI display
        (Shows token names but NOT the actual values for security)
        
        Returns:
            Summary dict with tokens and their types
        """
        return {
            'token_count': len(self.token_to_value),
            'tokens': [
                {
                    'token': token,
                    'type': mapping.entity_type,
                    'display': '●' * min(len(mapping.original), 10)
                }
                for token, mapping in self.token_to_value.items()
            ]
        }
