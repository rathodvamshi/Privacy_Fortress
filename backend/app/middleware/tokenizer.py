"""
Tokenizer — Deterministic token generation with 9-type canonical system
and cross-session consistency via profile seeding.

Entity types: USER, EMAIL, PHONE, COLLEGE, ORG, LOCATION, ID, HEALTH, SECRET
Token format: [ENTITY_TYPE_INDEX]  e.g. [USER_1], [EMAIL_1]

Modes:
  - BRACKET mode (default): [USER_1], [LOCATION_1] — for debugging / transparent masking
  - SYNTHETIC mode: replaces entities with realistic fake data so the LLM
    reasons naturally (e.g. "Vijay" → "John", "Hyderabad" → "Springfield").
    Synthetic values are deterministic per session so unmasking is exact.

Rules:
  - Profile defines token identity; sessions reuse and extend it.
  - Normalization: lowercase, trim, collapse whitespace before every lookup.
  - Type locking: once value→TYPE is assigned, it never changes.
  - Longest match: overlapping entities resolved by longest span.
"""
import re
import random
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

# ─── Canonical 9-type system ──────────────────────────────────────────────
CANONICAL_TYPES = {"USER", "EMAIL", "PHONE", "COLLEGE", "ORG", "LOCATION", "ID", "HEALTH", "SECRET"}

# ─── Synthetic data pools ─────────────────────────────────────────────────
# Deterministic fake replacements so the LLM sees "real-looking" data
# instead of bracket tokens, keeping its reasoning quality high.
SYNTHETIC_NAMES = [
    "Alex", "Jordan", "Morgan", "Casey", "Taylor", "Riley",
    "Quinn", "Harper", "Avery", "Dakota", "Reese", "Skyler",
    "Jamie", "Charlie", "Robin", "Drew", "Sage", "Finley",
    "Emerson", "Devon", "Parker", "Blair", "Lane", "Rowan",
    "Hayden", "Cameron", "Logan", "Ellis", "Brooks", "Peyton",
]

SYNTHETIC_LOCATIONS = [
    "Springfield", "Riverside", "Lakewood", "Greenville", "Fairview",
    "Madison", "Georgetown", "Franklin", "Arlington", "Oakville",
    "Westfield", "Clearwater", "Brookhaven", "Sunnyvale", "Maplewood",
    "Edgewood", "Woodbridge", "Ridgewood", "Hillcrest", "Meadowbrook",
]

SYNTHETIC_ORGS = [
    "Acme Corp", "Bluebird Inc", "Summit Tech", "Pinnacle Labs",
    "Cascade Solutions", "Trident Systems", "Nova Digital", "Vertex AI",
    "Helix Dynamics", "Prism Analytics",
]

SYNTHETIC_COLLEGES = [
    "Ivy Technical Institute", "Maple Valley University",
    "Pacific Coast College", "Sunrise Academy",
    "Northern Star University", "Crystal Lake Institute",
]

SYNTHETIC_EMAILS_DOMAINS = [
    "example.com", "test.org", "sample.net", "demo.io", "placeholder.edu",
]

SYNTHETIC_PHONES = [
    "555-0101", "555-0142", "555-0173", "555-0199", "555-0123",
    "555-0156", "555-0188", "555-0134", "555-0167", "555-0145",
]

# Map legacy / spaCy / regex types → canonical type
TYPE_CONSOLIDATION: Dict[str, str] = {
    # Direct canonical
    "USER": "USER", "EMAIL": "EMAIL", "PHONE": "PHONE",
    "COLLEGE": "COLLEGE", "ORG": "ORG", "LOCATION": "LOCATION", "ID": "ID",
    "HEALTH": "HEALTH", "SECRET": "SECRET",
    
    # Mapped types
    "HEALTH_INFO": "HEALTH",
    "OTP": "SECRET", "PASSWORD": "SECRET", "API_KEY": "SECRET", "AUTH_TOKEN": "SECRET",
            
    # spaCy label aliases
    "PERSON": "USER", "GPE": "LOCATION", "LOC": "LOCATION",
    # Regex / legacy ID-class types
    "AADHAAR": "ID", "PAN": "ID", "CREDIT_CARD": "ID", "SSN": "ID",
    "PASSPORT": "ID", "ROLL_NUMBER": "ID", "EMPLOYEE_ID": "ID",
    "BANK_ACCOUNT": "ID", "VEHICLE_REG": "ID", "IP_ADDRESS": "ID",
    "DOB": "ID", "URL": "ID", "DATE": "ID", "TIME": "ID",
    "MONEY": "ID", "NUMBER": "ID", "PERCENT": "ID", "QUANTITY": "ID",
    "LANGUAGE": "ID", "ORDINAL": "ID", "CARDINAL": "ID",
    "SUSPICIOUS_NUMBER": "ID",
    
    # spaCy misc → nearest canonical
    "ADDRESS": "LOCATION", "FACILITY": "LOCATION",
    "GROUP": "ORG", "NORP": "ORG",
    "PRODUCT": "ORG", "EVENT": "ORG", "WORK": "ORG", "LAW": "ORG",
    "OTHER": "ID",
}


def normalize(value: str) -> str:
    """Normalize a value: lowercase → trim → collapse whitespace."""
    return re.sub(r"\s+", " ", value.strip().lower())


def consolidate_type(raw_type: str) -> str:
    """Map any entity type string to one of the 7 canonical types."""
    return TYPE_CONSOLIDATION.get(raw_type.upper(), "ID")


# ─── Data classes ─────────────────────────────────────────────────────────
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


# ─── Tokenizer ────────────────────────────────────────────────────────────
class Tokenizer:
    """
    Deterministic tokenizer with 9 canonical types.

    Supports two modes:
    - BRACKET (default): [USER_1], [LOCATION_1] - transparent, debuggable.
    - SYNTHETIC: replaces with realistic fake data ("Alex", "Springfield")
      so the LLM reasons naturally. Unmasking still works exactly.

    Invariants
    ----------
    1. Same normalized value -> same token (within and across sessions via profile).
    2. Type lock: once value->TYPE is set, detection can never reclassify it.
    3. Token index is per-type: USER_1, USER_2 ... EMAIL_1, EMAIL_2 ...
    4. Profile seeds the tokenizer BEFORE detection runs.
    """
    
    def __init__(self, session_id: str, synthetic_mode: bool = False):
        self.session_id = session_id
        self.synthetic_mode = synthetic_mode
        # Per-type counters: {"USER": 2, "EMAIL": 1, ...}
        self.type_counters: Dict[str, int] = {}
        # normalized_value → token string
        self.value_to_token: Dict[str, str] = {}
        # token string → TokenMapping
        self.token_to_value: Dict[str, TokenMapping] = {}
        # TYPE LOCK: normalized_value → canonical type (never changes once set)
        self._type_lock: Dict[str, str] = {}
        # Synthetic display text: token → fake visible string
        self._synthetic_display: Dict[str, str] = {}
        # Seed RNG deterministically from session_id for reproducibility
        self._rng = random.Random(hash(session_id))
    
    def generate_token(self, entity_type: str, value: str) -> str:
        """
        Return a deterministic token for *value*.
        If the normalized value was seen before → return existing token.
        Otherwise mint a new [TYPE_N] token and lock the type.
        """
        canon_type = consolidate_type(entity_type)
        norm = normalize(value)

        # Already tokenized?
        if norm in self.value_to_token:
            return self.value_to_token[norm]

        # Type lock: honour previously locked type
        if norm in self._type_lock:
            canon_type = self._type_lock[norm]
        else:
            self._type_lock[norm] = canon_type

        # Mint new token
        self.type_counters[canon_type] = self.type_counters.get(canon_type, 0) + 1
        idx = self.type_counters[canon_type]
        token = f"[{canon_type}_{idx}]"

        self.value_to_token[norm] = token
        self.token_to_value[token] = TokenMapping(
            token=token,
            original=value,   # preserve original casing for unmask
            entity_type=canon_type,
            positions=[],
        )

        # Generate synthetic display text if in synthetic mode
        if self.synthetic_mode:
            self._synthetic_display[token] = self._generate_synthetic(canon_type, idx)

        logger.debug(f"Generated {token} for {canon_type}")
        return token

    def _generate_synthetic(self, canon_type: str, idx: int) -> str:
        """
        Generate a realistic-looking fake value for a given entity type.
        Deterministic per session (uses seeded RNG).
        """
        pool_map = {
            "USER": SYNTHETIC_NAMES,
            "LOCATION": SYNTHETIC_LOCATIONS,
            "ORG": SYNTHETIC_ORGS,
            "COLLEGE": SYNTHETIC_COLLEGES,
        }

        pool = pool_map.get(canon_type)
        if pool:
            return pool[(idx - 1) % len(pool)]

        if canon_type == "EMAIL":
            name = SYNTHETIC_NAMES[(idx - 1) % len(SYNTHETIC_NAMES)].lower()
            domain = SYNTHETIC_EMAILS_DOMAINS[(idx - 1) % len(SYNTHETIC_EMAILS_DOMAINS)]
            return f"{name}@{domain}"

        if canon_type == "PHONE":
            return SYNTHETIC_PHONES[(idx - 1) % len(SYNTHETIC_PHONES)]

        if canon_type == "HEALTH":
            return "[medical condition]"

        if canon_type == "SECRET":
            return "[REDACTED]"

        # ID and other types stay as bracket tokens
        return f"[{canon_type}_{idx}]"

    def get_display_token(self, token: str) -> str:
        """
        Return the display string for a token.
        In synthetic mode, returns the fake value; otherwise the bracket token.
        """
        if self.synthetic_mode and token in self._synthetic_display:
            return self._synthetic_display[token]
        return token
    
    def mask_text(
        self, text: str, entities: List[ScoredEntity]
    ) -> Tuple[str, Dict[str, TokenMapping]]:
        """
        Replace detected entities in *text* with tokens (or synthetic data).

        Overlap rules:
          • Prefer longest span.
          • On tie, prefer higher confidence.
          • On tie, prefer earlier start position.
        """
        if not entities:
            return text, {}

        # Deduplicate & prefer longest
        entities = self._resolve_overlaps(entities)

        # Sort descending by start for safe in-place replacement
        entities.sort(key=lambda e: e.start, reverse=True)

        masked = text
        used: Dict[str, TokenMapping] = {}

        for ent in entities:
            token = self.generate_token(ent.entity_type, ent.text)
            # Use synthetic display text if available, otherwise bracket token
            display = self.get_display_token(token)
            masked = masked[: ent.start] + display + masked[ent.end :]
            if token in self.token_to_value:
                self.token_to_value[token].positions.append((ent.start, ent.end))
                used[token] = self.token_to_value[token]

        logger.info(f"Masked {len(entities)} entities (synthetic={self.synthetic_mode})")
        return masked, used

    @staticmethod
    def _resolve_overlaps(entities: List[ScoredEntity]) -> List[ScoredEntity]:
        """
        Remove overlapping entities, keeping longest span (then highest confidence).
        """
        # Sort by: longest span desc, confidence desc, earliest start
        entities = sorted(
            entities,
            key=lambda e: (-(e.end - e.start), -e.confidence, e.start),
        )
        kept: List[ScoredEntity] = []
        occupied: List[Tuple[int, int]] = []

        for ent in entities:
            if any(ent.start < oend and ent.end > ostart for ostart, oend in occupied):
                continue  # overlaps with a longer/better entity
            kept.append(ent)
            occupied.append((ent.start, ent.end))

        return kept
    
    def unmask_text(self, masked_text: str) -> str:
        """
        Replace all tokens (bracket or synthetic) in text with original values.
        
        In BRACKET mode: replaces [USER_1] → original value.
        In SYNTHETIC mode: replaces e.g. 'Alex' -> original value.
        
        Args:
            masked_text: Text with tokens or synthetic data
            
        Returns:
            Original text with values restored
        """
        unmasked = masked_text

        if self.synthetic_mode:
            # Build synthetic → original mapping, sorted longest-first
            synthetic_to_original: List[Tuple[str, str]] = []
            for token, mapping in self.token_to_value.items():
                display = self._synthetic_display.get(token, token)
                synthetic_to_original.append((display, mapping.original))
            # Sort by display length descending to avoid partial replacements
            synthetic_to_original.sort(key=lambda x: len(x[0]), reverse=True)
            for display, original in synthetic_to_original:
                if display in unmasked:
                    unmasked = unmasked.replace(display, original)
        else:
            # Standard bracket token replacement
            sorted_tokens = sorted(self.token_to_value.keys(), key=len, reverse=True)
            for token in sorted_tokens:
                if token in unmasked:
                    mapping = self.token_to_value[token]
                    unmasked = unmasked.replace(token, mapping.original)
        
        return unmasked
    
    def get_token_for_value(self, value: str) -> Optional[str]:
        """Get the token for a specific value if it exists."""
        return self.value_to_token.get(normalize(value))
    
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
            if mapping.entity_type == consolidate_type(entity_type)
        ]
    
    def load_mappings(self, mappings: Dict[str, Dict]):
        """
        Load existing mappings (e.g., from Redis vault or profile).
        Consolidates types and sets type locks.
        """
        for token, data in mappings.items():
            original = data.get('original', '')
            raw_type = data.get('entity_type', 'ID')
            canon = consolidate_type(raw_type)
            norm = normalize(original)

            self.token_to_value[token] = TokenMapping(
                token=token,
                original=original,
                entity_type=canon,
                positions=data.get('positions', [])
            )
            self.value_to_token[norm] = token
            self._type_lock[norm] = canon

            # Keep counter in sync
            try:
                idx = int(token.split('_')[-1].rstrip(']'))
                self.type_counters[canon] = max(
                    self.type_counters.get(canon, 0), idx
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

    def get_known_values(self) -> Dict[str, str]:
        """
        Return {normalized_value: canonical_type} for all known entities.
        Used to feed the fuzzy engine with profile + session entities.
        """
        return dict(self._type_lock)
