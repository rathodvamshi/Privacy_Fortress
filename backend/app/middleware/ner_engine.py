"""
NER Engine - Named Entity Recognition using spaCy
Detects: PERSON, ORG, GPE (locations), DATE, MONEY, etc.
"""
import spacy
from typing import List, Tuple
from dataclasses import dataclass
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


@dataclass
class DetectedEntity:
    """Represents a detected entity"""
    text: str
    entity_type: str
    start: int
    end: int
    confidence: float
    source: str  # 'spacy', 'regex', 'fuzzy'


class NEREngine:
    """
    Named Entity Recognition Engine using spaCy
    Runs locally - no data leaves the server
    """
    
    # Mapping spaCy labels to our token types
    ENTITY_MAPPING = {
        'PERSON': 'USER',
        'ORG': 'ORG',
        'GPE': 'LOCATION',      # Geo-Political Entity (cities, countries)
        'LOC': 'LOCATION',      # Non-GPE locations
        'DATE': 'DATE',
        'MONEY': 'MONEY',
        'NORP': 'GROUP',        # Nationalities, religious/political groups
        'FAC': 'FACILITY',      # Buildings, airports, etc.
        'PRODUCT': 'PRODUCT',
        'EVENT': 'EVENT',
        'WORK_OF_ART': 'WORK',
        'LAW': 'LAW',
        'LANGUAGE': 'LANGUAGE',
        'TIME': 'TIME',
        'PERCENT': 'PERCENT',
        'QUANTITY': 'QUANTITY',
        'ORDINAL': 'ORDINAL',
        'CARDINAL': 'NUMBER',
    }
    
    
    # Terms to exclude from masking (common words that NER may incorrectly detect)
    EXCLUDED_TERMS = {
        # Common abbreviations
        'ip', 'ssn', 'dob', 'pan', 'id', 'aadhaar', 'aadhar',
        'email', 'phone', 'mobile', 'address', 'name', 'age',
        # Common tech terms
        'ai', 'ml', 'api', 'url', 'http', 'https', 'www',
        # Common words
        'hello', 'hi', 'hey', 'thanks', 'thank', 'please', 'help',
        'python', 'java', 'javascript', 'code', 'programming',
        # Days and months
        'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
        'january', 'february', 'march', 'april', 'may', 'june',
        'july', 'august', 'september', 'october', 'november', 'december',
        # ===== NEW: Prevent false positives =====
        # Seasons and time periods (commonly misdetected as DATES)
        'summer', 'winter', 'spring', 'fall', 'autumn', 'season', 'seasons',
        'morning', 'afternoon', 'evening', 'night', 'today', 'tomorrow', 'yesterday',
        # Generic location/org terms (prevent over-masking)
        'college', 'school', 'university', 'company', 'office', 'home',
        'city', 'state', 'country', 'place', 'location',
        # Common verbs/adjectives that spaCy sometimes flags
        'related', 'associated', 'connected', 'based', 'located',
        # Generic nouns
        'fruits', 'vegetables', 'food', 'drink', 'water',
        'book', 'movie', 'song', 'music', 'art',
        # Question words
        'what', 'when', 'where', 'who', 'why', 'how',
    }

    
    # Priority entities (these are most important for privacy)
    PRIORITY_ENTITIES = {'USER', 'ORG', 'LOCATION', 'DATE'}
    
    # Context patterns that strongly indicate the following word(s) are a person's name
    # Context patterns that strongly indicate the following word(s) are a person's name
    NAME_CONTEXT_PATTERNS = [
        r'\bmy\s+name\s+is\s+',
        r'\bi[\'\'\u2019]?m\s+',
        r'\bi\s+am\s+',
        r'\bcall\s+me\s+',
        r'\bthey\s+call\s+me\s+',
        r'\bnamed\s+',
        r'\bname\s*:\s*',
        r'\bname\s+is\s+',
    ]

    # Context patterns that indicate a LOCATION
    LOCATION_CONTEXT_PATTERNS = [
        r'\blive\s+(?:in|at|near)\s+',
        r'\bstay\s+(?:in|at|near)\s+',
        r'\bfrom\s+',
        r'\bvisit(?:ed|ing)?\s+',
        r'\btravel(?:ed|ling|ing)?\s+to\s+',
        r'\blocated\s+(?:in|at)\s+',
        r'\baddress\s+(?:is|:)\s+',
        r'\born\s+in\s+',
        r'\bmoved?\s+to\s+',
        r'\bgoing\s+to\s+',
        r'\bheaded\s+to\s+',
        r'\bbased\s+(?:in|at|out\s+of)\s+',
        r'\bnear\s+',
        r'\bsettle[d]?\s+(?:in|at)\s+',
        r'\brelocate[d]?\s+to\s+',
        r'\bshift(?:ed|ing)?\s+to\s+',
    ]

    # Weaker location context patterns — only trust when followed by
    # a known location / abbreviation / capitalized proper noun
    WEAK_LOCATION_CONTEXT_PATTERNS = [
        r'\blove\s+',
        r'\blike\s+',
        r'\bprefer\s+',
        r'\bmiss(?:ing)?\s+',
        r'\bexplor(?:e|ed|ing)\s+',
        r'\benjoy\s+',
    ]

    # Context patterns for CONTACT info (Phone, Email) - "Semantic Intent"
    CONTACT_CONTEXT_PATTERNS = [
        r'\breach\s+(?:me|us)\s+(?:at|on)\s+',
        r'\bcontact\s+(?:me|us)\s+(?:at|on)\s+',
        r'\bcall\s+(?:me|us|him|her)\s+(?:at|on)?\s+',
        r'\bdial\s+',
        r'\bphone\s*:\s+',
        r'\bemail\s*:\s+',
        r'\bping\s+me\s+on\s+',
    ]

    # Context patterns for AUTHENTICATION / SECRETS
    AUTH_CONTEXT_PATTERNS = [
        r'\blogin\s+(?:is|with)\s+',
        r'\bpassword\s+(?:is|:)\s+',
        r'\bcredential[s]?\s+(?:are|is|:)\s+',
        r'\bverification\s+code\s+(?:is|:)\s+',
        r'\botp\s+(?:is|:)\s+',
        r'\bsecret\s+(?:is|:)\s+',
        r'\bkey\s+(?:is|:)\s+',
    ]

    # Context patterns for HEALTH / MEDICAL
    HEALTH_CONTEXT_PATTERNS = [
        r'\bdiagnosed\s+(?:with|of)\s+',
        r'\bsuffering\s+(?:from)\s+',
        r'\bprescribed\s+',
        r'\btreatment\s+for\s+',
        r'\bsymptoms?\s+(?:of|include)\s+',
        r'\bmedication\s+(?:for)\s+',
        r'\bpain\s+in\s+',
    ]

    # Controlled Vocabulary for Health (High sensitivity)
    HEALTH_KEYWORDS = {
        'diabetes', 'cancer', 'hiv', 'aids', 'depression', 'anxiety',
        'hypertension', 'covid', 'asthma', 'arthritis', 'allergy',
        'pregnant', 'pregnancy', 'surgery', 'operation', 'therapy',
        'mental health', 'disorder', 'syndrome', 'disease', 'infection',
        'tumor', 'cardiac', 'stroke', 'seizure', 'autism', 'adhd'
    }

    # Known location abbreviations → full name (for direct detection)
    LOCATION_ABBREVIATIONS = {
        'hyd': 'Hyderabad', 'blr': 'Bangalore', 'bang': 'Bangalore',
        'del': 'Delhi', 'mum': 'Mumbai', 'chn': 'Chennai',
        'kol': 'Kolkata', 'pune': 'Pune', 'ahmd': 'Ahmedabad',
        'jpr': 'Jaipur', 'lko': 'Lucknow', 'noi': 'Noida',
        'bombay': 'Mumbai', 'calcutta': 'Kolkata', 'madras': 'Chennai',
        'nyc': 'New York', 'sf': 'San Francisco',
        'la': 'Los Angeles', 'dc': 'Washington DC',
        'ldn': 'London', 'vizag': 'Visakhapatnam',
        'sec': 'Secunderabad', 'ghy': 'Guwahati',
        'nagpur': 'Nagpur', 'indore': 'Indore', 'bhopal': 'Bhopal',
        'cbe': 'Coimbatore', 'tvm': 'Thiruvananthapuram',
        'ccj': 'Calicut', 'cok': 'Kochi',
        'goa': 'Goa', 'ggn': 'Gurgaon', 'grg': 'Gurgaon',
        'vja': 'Vijayawada', 'wgl': 'Warangal',
    }

    # Known cities and places for direct detection (lowercase)
    KNOWN_CITIES = {
        'hyderabad', 'bangalore', 'bengaluru', 'delhi', 'mumbai',
        'chennai', 'kolkata', 'pune', 'ahmedabad', 'jaipur',
        'lucknow', 'chandigarh', 'bhopal', 'indore', 'nagpur',
        'visakhapatnam', 'coimbatore', 'kochi', 'thiruvananthapuram',
        'guwahati', 'patna', 'ranchi', 'bhubaneswar', 'surat',
        'vadodara', 'agra', 'varanasi', 'noida', 'gurgaon', 'gurugram',
        'faridabad', 'ghaziabad', 'mysore', 'mysuru', 'mangalore',
        'mangaluru', 'hubli', 'dharwad', 'belgaum', 'belagavi',
        'vijayawada', 'guntur', 'tirupati', 'warangal', 'karimnagar',
        'nizamabad', 'khammam', 'rajahmundry', 'kakinada', 'nellore',
        'secunderabad', 'new york', 'london', 'paris', 'tokyo',
        'singapore', 'san francisco', 'los angeles', 'chicago',
        'boston', 'seattle', 'austin', 'denver', 'toronto',
        'vancouver', 'sydney', 'melbourne', 'dubai', 'hong kong',
        'berlin', 'amsterdam', 'barcelona', 'rome', 'moscow',
    }

    # Common non-location words that look like names (to filter false positives)
    _NON_NAME_WORDS = {
        'the', 'a', 'an', 'is', 'was', 'are', 'am', 'be', 'been',
        'and', 'or', 'but', 'so', 'if', 'then', 'that', 'this',
        'it', 'not', 'very', 'really', 'just', 'also', 'too',
        'here', 'there', 'now', 'well', 'going', 'doing', 'working',
        'looking', 'trying', 'happy', 'sad', 'good', 'bad', 'new',
        'old', 'big', 'small', 'sure', 'okay', 'yes', 'no',
        'fine', 'great', 'nice', 'cool', 'awesome', 'right',
        'sorry', 'glad', 'with', 'for', 'from', 'about', 'like',
        'have', 'has', 'had', 'will', 'would', 'could', 'should',
        'can', 'may', 'might', 'do', 'does', 'did', 'get', 'got',
        'let', 'make', 'take', 'give', 'know', 'think', 'say',
        'tell', 'ask', 'use', 'find', 'want', 'need', 'try',
        'come', 'go', 'see', 'look', 'read', 'write', 'run',
        'much', 'many', 'some', 'any', 'all', 'each', 'every',
    }

    # ... (init and load methods remain same) ...



    def _has_location_context(self, text: str, entity_start: int) -> bool:
        """Check if text before entity matches location context"""
        prefix = text[:entity_start].lower()
        import re as _re
        for pattern in self.LOCATION_CONTEXT_PATTERNS:
            if _re.search(pattern + r'$', prefix, _re.IGNORECASE):
                return True
        return False
    
    def __init__(self, model_name: str = "en_core_web_sm"):
        """
        Initialize the NER engine
        
        Args:
            model_name: spaCy model to use. Options:
                - en_core_web_sm (small, fast)
                - en_core_web_md (medium, balanced) 
                - en_core_web_lg (large, accurate)
        """
        self.model_name = model_name
        self.nlp = None
        self._load_model()
    
    def _load_model(self):
        """
        Load spaCy model with INTELLIGENCE ENABLED (v3.0).
        
        Change: Re-ENABLED 'tagger', 'parser', 'lemmatizer'.
        Reason: We need grammatical structure (POS tags, dependencies) to understand 
        CONTEXT and INTENT, not just pattern matching.
        """
        try:
            # v3.0: Enable full pipeline for "Deep Context" understanding
            self.nlp = spacy.load(self.model_name)
            logger.info(f"Loaded spaCy model: {self.model_name} (Full Intelligence Enabled)")
            
        except OSError:
            logger.warning(f"Model {self.model_name} not found. Downloading...")
            from spacy.cli import download
            download(self.model_name)
            self.nlp = spacy.load(self.model_name)
            logger.info(f"Downloaded and loaded spaCy model: {self.model_name}")
            
    """
    LRU CACHE (Least Recently Used)
    -------------------------------
    Professional optimization: If the same text comes in twice (e.g. "Hi"),
    we return the result from RAM instantly (0ms) instead of re-processing.
    """
    from functools import lru_cache

    @lru_cache(maxsize=1024)
    def _cached_spacy_detect(self, text: str) -> List[Tuple[str, str, int, int]]:
        """Cached wrapper for spaCy detection"""
        doc = self.nlp(text)
        # Return tuple of primitive types (hashable/cachable)
        return [(ent.text, ent.label_, ent.start_char, ent.end_char) for ent in doc.ents]
    
    def detect(self, text: str) -> List[DetectedEntity]:
        """
        Detect named entities in the text using Optimized Caching.
        """
        if not text or not text.strip():
            return []
        
        # USE CACHED DETECTION (Super Fast 0ms for repeats)
        # Returns list of (text, label, start, end) tuples
        raw_entities = self._cached_spacy_detect(text)
        entities = []
        
        for (ent_text, ent_label, start_char, end_char) in raw_entities:
            # Skip excluded terms
            if ent_text.lower() in self.EXCLUDED_TERMS:
                continue
            
            # Skip very short entities
            if len(ent_text) < 2:
                continue
            
            # Skip generic multi-word phrases
            words = ent_text.lower().split()
            if len(words) > 1:
                if all(word in self.EXCLUDED_TERMS for word in words):
                    continue
            
            # Skip generic entities
            if not self._is_valid_entity(ent_text, ent_label):
                continue
            
            # Map spaCy label to our type
            entity_type = self.ENTITY_MAPPING.get(ent_label, 'OTHER')
            
            # CONTEXT OVERRIDE 1: Name Context
            # If spaCy tagged as GPE/LOC/ORG but context implies name -> USER
            if ent_label in ('GPE', 'LOC', 'ORG', 'NORP', 'PERSON', 'OTHER'):
                if self._has_name_context(text, start_char):
                    entity_type = 'USER'
            # CONTEXT OVERRIDE 3: Health / Medical (Highest Sensitivity)
            # Detects "diabetes", "cancer" OR "diagnosed with..."
            if ent_text.lower() in self.HEALTH_KEYWORDS:
                entity_type = 'HEALTH'
                confidence = 0.95
            elif self._has_health_context(text, start_char):
                entity_type = 'HEALTH'
                confidence = 0.90
            
            # CONTEXT OVERRIDE 4: Auth / Secret (Highest Sensitivity)
            # Detects "password is...", "login with..."
            if self._has_auth_context(text, start_char):
                entity_type = 'SECRET'
                confidence = 0.99
            
            # CONTEXT OVERRIDE 5: Contact Intent
            # Detects "reach me at...", "call me on..."
            if self._has_contact_context(text, start_char):
                # If vague entity (like a number), assume PHONE
                if entity_type in ('OTHER', 'CARDINAL', 'DATE'):  # Sometimes phones detected as DATE
                    entity_type = 'PHONE'
                    confidence = 0.90
            
            # Calculate confidence
            confidence = self._calculate_confidence(ent_text, entity_type)
            
            entity = DetectedEntity(
                text=ent_text,
                entity_type=entity_type,
                start=start_char,
                end=end_char,
                confidence=confidence,
                source='spacy'
            )
            entities.append(entity)
        
        # POST-PROCESSING: Correct spaCy misclassifications
        # If a PERSON/ORG entity is actually a known city/abbreviation,
        # reclassify as LOCATION (unless name-context immediately precedes it)
        for entity in entities:
            if entity.entity_type in ('USER', 'ORG'):
                is_known_loc = (
                    entity.text.lower() in self.KNOWN_CITIES
                    or entity.text.lower() in self.LOCATION_ABBREVIATIONS
                )
                has_name_ctx = self._has_name_context(text, entity.start)
                if is_known_loc and not has_name_ctx:
                    logger.debug(
                        f"Correcting {entity.entity_type} → LOCATION for known city: '{entity.text}'"
                    )
                    entity.entity_type = 'LOCATION'
        
        # POST-PROCESSING 2: Split compound entities like "Arjun from Chennai"
        # When spaCy lumps a name + preposition + city into one PERSON entity,
        # split it into separate NAME and LOCATION entities.
        _SPLIT_PREPS = {'from', 'in', 'at', 'near', 'of'}
        split_additions = []
        entities_to_remove = []
        for entity in entities:
            if entity.entity_type in ('USER', 'PERSON'):
                words = entity.text.split()
                if len(words) >= 3:
                    # Check for "Name prep City" pattern
                    for i, w in enumerate(words):
                        if w.lower() in _SPLIT_PREPS and i > 0 and i < len(words) - 1:
                            name_part = ' '.join(words[:i])
                            city_part = ' '.join(words[i+1:])
                            city_lower = city_part.lower()
                            if (city_lower in self.KNOWN_CITIES or
                                city_lower in self.LOCATION_ABBREVIATIONS or
                                city_part[0].isupper()):
                                # Split: create name entity and location entity
                                name_end = entity.start + len(name_part)
                                city_start = entity.start + entity.text.index(city_part)
                                city_end = city_start + len(city_part)
                                split_additions.append(DetectedEntity(
                                    text=name_part,
                                    entity_type='USER',
                                    start=entity.start,
                                    end=name_end,
                                    confidence=entity.confidence,
                                    source='spacy_split'
                                ))
                                split_additions.append(DetectedEntity(
                                    text=city_part,
                                    entity_type='LOCATION',
                                    start=city_start,
                                    end=city_end,
                                    confidence=entity.confidence * 0.95,
                                    source='spacy_split'
                                ))
                                entities_to_remove.append(entity)
                                logger.debug(
                                    f"Split compound entity '{entity.text}' → "
                                    f"USER:'{name_part}' + LOCATION:'{city_part}'"
                                )
                                break
        for e in entities_to_remove:
            entities.remove(e)
        entities.extend(split_additions)
        
        # Contextual name detection (fallback)
        context_names = self._detect_contextual_names(text, entities)
        entities.extend(context_names)
        
        # Known location detection (abbreviations + city names)
        known_locations = self._detect_known_locations(text, entities)
        entities.extend(known_locations)
        
        # Contextual location detection (capitalized words after location context)
        context_locations = self._detect_contextual_locations(text, entities)
        entities.extend(context_locations)
        
        # Standalone health keyword detection (catches health terms
        # even when spaCy doesn't recognize them as named entities)
        health_entities = self._detect_health_keywords(text, entities)
        entities.extend(health_entities)
        
        return entities
    
    def _is_valid_entity(self, text: str, label: str) -> bool:
        """Validate if entity is truly PII-sensitive"""
        text_lower = text.lower()
        
        # ONLY mask these specific entity types
        SENSITIVE_LABELS = {'PERSON', 'ORG', 'GPE'}
        
        if label not in SENSITIVE_LABELS:
            if len(text) < 3:
                return False
        
        if label == 'PERSON':
            # Allow lowercase names — users often type casually in chat
            # Context-based detection and confidence scoring handle quality
            if len(text) < 2:
                return False
        
        if label in {'ORG', 'GPE'}:
            if text_lower in self.EXCLUDED_TERMS:
                return False
        
        return True

    
    def _calculate_confidence(self, text: str, entity_type: str) -> float:
        """Calculate confidence score"""
        base_confidence = 0.7
        
        if entity_type in self.PRIORITY_ENTITIES:
            base_confidence = 0.85
        
        if len(text) > 5:
            base_confidence += 0.05
        
        if entity_type == 'USER' and text[0].isupper():
            base_confidence += 0.05
        
        return min(base_confidence, 0.99)
    
    def _has_name_context(self, text: str, entity_start: int) -> bool:
        """
        Check if the text immediately before `entity_start` matches
        a name-context phrase (e.g. 'my name is', 'I am', 'I\'m').
        """
        prefix = text[:entity_start].lower()
        import re as _re
        for pattern in self.NAME_CONTEXT_PATTERNS:
            if _re.search(pattern + r'$', prefix, _re.IGNORECASE):
                return True
        return False
    
    def _detect_contextual_names(self, text: str, existing_entities: List[DetectedEntity]) -> List[DetectedEntity]:
        """
        Detect names that spaCy missed by looking for words
        right after name-context phrases.
        
        Now handles BOTH capitalized AND lowercase names (users often
        type casually in chat: "my name is vijay").
        """
        import re as _re
        new_entities = []
        existing_spans = {(e.start, e.end) for e in existing_entities}
        
        for pattern in self.NAME_CONTEXT_PATTERNS:
            for ctx_match in _re.finditer(pattern, text, _re.IGNORECASE):
                rest_start = ctx_match.end()
                rest = text[rest_start:]
                
                # Try 1: Capitalized name(s) — highest confidence
                name_match = _re.match(r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)', rest)
                confidence = 0.92
                
                # Try 2: Lowercase / mixed-case single word — strong context
                #         compensates for lack of capitalisation
                if not name_match:
                    name_match = _re.match(r'([a-zA-Z]{2,})', rest)
                    confidence = 0.88
                    if name_match:
                        candidate = name_match.group(1).lower()
                        # Reject common non-name words
                        if candidate in self._NON_NAME_WORDS or candidate in self.EXCLUDED_TERMS:
                            name_match = None
                
                if not name_match:
                    continue
                
                name_text = name_match.group(1)
                # Stop at commas, periods, or other punctuation
                name_text = _re.split(r'[,;.!?\-]', name_text)[0].strip()
                if len(name_text) < 2:
                    continue
                
                name_start = rest_start + name_match.start(1)
                name_end = name_start + len(name_text)
                
                # Skip if already detected
                if any(s <= name_start and name_end <= e for (s, e) in existing_spans):
                    continue
                
                # Skip excluded terms
                if name_text.lower() in self.EXCLUDED_TERMS:
                    continue
                
                logger.debug(f"Context-detected name: '{name_text}' from pattern")
                new_entities.append(DetectedEntity(
                    text=name_text,
                    entity_type='USER',
                    start=name_start,
                    end=name_end,
                    confidence=confidence,
                    source='spacy'
                ))
                existing_spans.add((name_start, name_end))
        
        return new_entities

    def _detect_known_locations(self, text: str, existing_entities: List[DetectedEntity]) -> List[DetectedEntity]:
        """
        Scan text for known location abbreviations and city names,
        regardless of context. E.g. "Hyd" → Hyderabad, "Mumbai" → Mumbai.
        """
        import re as _re
        new_entities = []
        existing_spans = {(e.start, e.end) for e in existing_entities}
        text_lower = text.lower()
        
        # 1) Detect known abbreviations (word-boundary match)
        for abbr, full_name in self.LOCATION_ABBREVIATIONS.items():
            # Match abbreviation as a whole word (case-insensitive)
            for m in _re.finditer(r'\b' + _re.escape(abbr) + r'\b', text_lower):
                start, end = m.start(), m.end()
                # Use the original-case text
                original_text = text[start:end]
                
                # Skip if already covered by an existing entity
                if any(s <= start and end <= e for (s, e) in existing_spans):
                    continue
                # Skip if it's in excluded terms
                if original_text.lower() in self.EXCLUDED_TERMS:
                    continue
                
                logger.debug(f"Known abbreviation detected: '{original_text}' → {full_name}")
                new_entities.append(DetectedEntity(
                    text=original_text,
                    entity_type='LOCATION',
                    start=start,
                    end=end,
                    confidence=0.90,
                    source='spacy'
                ))
                existing_spans.add((start, end))
        
        # 2) Detect known city names (multi-word aware)
        for city in self.KNOWN_CITIES:
            for m in _re.finditer(r'\b' + _re.escape(city) + r'\b', text_lower):
                start, end = m.start(), m.end()
                original_text = text[start:end]
                
                if any(s <= start and end <= e for (s, e) in existing_spans):
                    continue
                if original_text.lower() in self.EXCLUDED_TERMS:
                    continue
                
                logger.debug(f"Known city detected: '{original_text}'")
                new_entities.append(DetectedEntity(
                    text=original_text,
                    entity_type='LOCATION',
                    start=start,
                    end=end,
                    confidence=0.90,
                    source='spacy'
                ))
                existing_spans.add((start, end))
        
        return new_entities

    def _detect_contextual_locations(self, text: str, existing_entities: List[DetectedEntity]) -> List[DetectedEntity]:
        """
        Detect locations after context patterns:
          - Strong patterns ("live in", "from", "moved to") → accept any capitalized word
          - Weak patterns ("love", "like") → only accept if the word is a known
            location / abbreviation / already capitalized proper noun
        """
        import re as _re
        new_entities = []
        existing_spans = {(e.start, e.end) for e in existing_entities}
        
        # Strong context → accept any capitalized word as location
        for pattern in self.LOCATION_CONTEXT_PATTERNS:
            for ctx_match in _re.finditer(pattern, text, _re.IGNORECASE):
                rest_start = ctx_match.end()
                rest = text[rest_start:]
                loc_match = _re.match(r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)', rest)
                if not loc_match:
                    # Also try lowercase known city / abbreviation
                    loc_match = _re.match(r'([a-zA-Z]{2,})', rest)
                    if loc_match:
                        candidate = loc_match.group(1).lower()
                        if candidate not in self.KNOWN_CITIES and candidate not in self.LOCATION_ABBREVIATIONS:
                            loc_match = None
                
                if not loc_match:
                    continue
                
                loc_text = loc_match.group(1)
                loc_text = _re.split(r'[,;.!?\-]', loc_text)[0].strip()
                if len(loc_text) < 2 or loc_text.lower() in self.EXCLUDED_TERMS:
                    continue
                
                loc_start = rest_start + loc_match.start(1)
                loc_end = loc_start + len(loc_text)
                
                if any(s <= loc_start and loc_end <= e for (s, e) in existing_spans):
                    continue
                
                logger.debug(f"Context-detected location: '{loc_text}'")
                new_entities.append(DetectedEntity(
                    text=loc_text,
                    entity_type='LOCATION',
                    start=loc_start,
                    end=loc_end,
                    confidence=0.88,
                    source='spacy'
                ))
                existing_spans.add((loc_start, loc_end))
        
        # Weak context → only known locations / abbreviations
        for pattern in self.WEAK_LOCATION_CONTEXT_PATTERNS:
            for ctx_match in _re.finditer(pattern, text, _re.IGNORECASE):
                rest_start = ctx_match.end()
                rest = text[rest_start:]
                loc_match = _re.match(r'([a-zA-Z]{2,}(?:\s+[a-zA-Z]{2,})*)', rest)
                if not loc_match:
                    continue
                
                loc_text = _re.split(r'[,;.!?\-]', loc_match.group(1))[0].strip()
                candidate = loc_text.lower()
                
                # Only accept known cities / abbreviations for weak patterns
                if candidate not in self.KNOWN_CITIES and candidate not in self.LOCATION_ABBREVIATIONS:
                    continue
                
                if len(loc_text) < 2 or candidate in self.EXCLUDED_TERMS:
                    continue
                
                loc_start = rest_start + loc_match.start(1)
                loc_end = loc_start + len(loc_text)
                
                if any(s <= loc_start and loc_end <= e for (s, e) in existing_spans):
                    continue
                
                logger.debug(f"Weak-context location: '{loc_text}'")
                new_entities.append(DetectedEntity(
                    text=loc_text,
                    entity_type='LOCATION',
                    start=loc_start,
                    end=loc_end,
                    confidence=0.85,
                    source='spacy'
                ))
                existing_spans.add((loc_start, loc_end))
        
        return new_entities

    def _detect_health_keywords(self, text: str, existing_entities: List[DetectedEntity]) -> List[DetectedEntity]:
        """
        Standalone health keyword detection — catches health terms
        even when spaCy doesn't recognize them as named entities.
        Scans for HEALTH_KEYWORDS and HEALTH_CONTEXT_PATTERNS independently.
        """
        import re as _re
        new_entities = []
        existing_spans = {(e.start, e.end) for e in existing_entities}
        text_lower = text.lower()

        # 1) Direct keyword match
        for keyword in self.HEALTH_KEYWORDS:
            for m in _re.finditer(r'\b' + _re.escape(keyword) + r'\b', text_lower):
                start, end = m.start(), m.end()
                original_text = text[start:end]

                if any(s <= start and end <= e for (s, e) in existing_spans):
                    continue

                logger.debug(f"Health keyword detected: '{original_text}'")
                new_entities.append(DetectedEntity(
                    text=original_text,
                    entity_type='HEALTH',
                    start=start,
                    end=end,
                    confidence=0.95,
                    source='spacy'
                ))
                existing_spans.add((start, end))

        # 2) Health context patterns ("diagnosed with X", "suffering from X")
        for pattern in self.HEALTH_CONTEXT_PATTERNS:
            for ctx_match in _re.finditer(pattern, text, _re.IGNORECASE):
                rest_start = ctx_match.end()
                rest = text[rest_start:]
                # Only take the first 1–2 words (avoid bridging to unrelated entities)
                word_match = _re.match(r'([a-zA-Z]{3,}(?:\s+[a-zA-Z]{3,})?)', rest)
                if not word_match:
                    continue

                health_text = word_match.group(1)
                # Stop at prepositions / stop words to avoid oversized spans
                stop_words = {'in', 'at', 'on', 'to', 'of', 'and', 'or', 'the',
                              'is', 'my', 'for', 'with', 'from', 'by', 'a', 'an'}
                words = health_text.split()
                trimmed = []
                for w in words:
                    if w.lower() in stop_words:
                        break
                    trimmed.append(w)
                health_text = ' '.join(trimmed) if trimmed else ''
                if len(health_text) < 3 or health_text.lower() in self.EXCLUDED_TERMS:
                    continue

                h_start = rest_start + word_match.start(1)
                h_end = h_start + len(health_text)

                if any(s <= h_start and h_end <= e for (s, e) in existing_spans):
                    continue

                logger.debug(f"Health-context entity: '{health_text}'")
                new_entities.append(DetectedEntity(
                    text=health_text,
                    entity_type='HEALTH',
                    start=h_start,
                    end=h_end,
                    confidence=0.90,
                    source='spacy'
                ))
                existing_spans.add((h_start, h_end))

        return new_entities

    def _has_contact_context(self, text: str, entity_start: int) -> bool:
        """Check if text before entity matches contact context"""
        prefix = text[:entity_start].lower()
        import re as _re
        for pattern in self.CONTACT_CONTEXT_PATTERNS:
            if _re.search(pattern + r'$', prefix, _re.IGNORECASE):
                return True
        return False

    def _has_auth_context(self, text: str, entity_start: int) -> bool:
        """Check if text before entity matches auth context"""
        prefix = text[:entity_start].lower()
        import re as _re
        for pattern in self.AUTH_CONTEXT_PATTERNS:
            if _re.search(pattern + r'$', prefix, _re.IGNORECASE):
                return True
        return False

    def _has_health_context(self, text: str, entity_start: int) -> bool:
        """Check if text before entity matches health context"""
        prefix = text[:entity_start].lower()
        import re as _re
        for pattern in self.HEALTH_CONTEXT_PATTERNS:
            if _re.search(pattern + r'$', prefix, _re.IGNORECASE):
                return True
        return False

    def detect_batch(self, texts: List[str]) -> List[List[DetectedEntity]]:
        """
        Detect entities in multiple texts efficiently
        
        Args:
            texts: List of input texts
            
        Returns:
            List of entity lists for each text
        """
        results = []
        for doc in self.nlp.pipe(texts, batch_size=50):
            entities = []
            for ent in doc.ents:
                entity_type = self.ENTITY_MAPPING.get(ent.label_, 'OTHER')
                # Updated to match new signature: pass text string, not object
                confidence = self._calculate_confidence(ent.text, entity_type)
                entity = DetectedEntity(
                    text=ent.text,
                    entity_type=entity_type,
                    start=ent.start_char,
                    end=ent.end_char,
                    confidence=confidence,
                    source='spacy'
                )
                entities.append(entity)
            results.append(entities)
        return results


# Singleton instance
_ner_engine = None

def get_ner_engine() -> NEREngine:
    """Get the singleton NER engine instance"""
    global _ner_engine
    if _ner_engine is None:
        _ner_engine = NEREngine()
    return _ner_engine
