"""
NER Engine - Named Entity Recognition using spaCy
Detects: PERSON, ORG, GPE (locations), DATE, MONEY, etc.
"""
import spacy
from typing import List, Tuple
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
        """Load the spaCy model"""
        try:
            self.nlp = spacy.load(self.model_name)
            logger.info(f"Loaded spaCy model: {self.model_name}")
        except OSError:
            logger.warning(f"Model {self.model_name} not found. Downloading...")
            spacy.cli.download(self.model_name)
            self.nlp = spacy.load(self.model_name)
            logger.info(f"Downloaded and loaded spaCy model: {self.model_name}")
    
    def detect(self, text: str) -> List[DetectedEntity]:
        """
        Detect named entities in the text
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of DetectedEntity objects
        """
        if not text or not text.strip():
            return []
        
        doc = self.nlp(text)
        entities = []
        
        for ent in doc.ents:
            # Skip excluded terms
            if ent.text.lower() in self.EXCLUDED_TERMS:
                continue
            
            # Skip very short entities (likely false positives)
            if len(ent.text) < 2:
                continue
            
            # NEW: Skip generic multi-word phrases (e.g., "summer season")
            words = ent.text.lower().split()
            if len(words) > 1:
                # If ALL words are in excluded list, skip the entire phrase
                if all(word in self.EXCLUDED_TERMS for word in words):
                    logger.debug(f"Skipping generic phrase: '{ent.text}'")
                    continue
            
            # NEW: Skip if entity is too generic based on type
            if not self._is_valid_entity(ent):
                logger.debug(f"Skipping invalid entity: '{ent.text}' ({ent.label_})")
                continue
            
            # Map spaCy label to our type
            entity_type = self.ENTITY_MAPPING.get(ent.label_, 'OTHER')
            
            # Calculate confidence based on entity type priority
            confidence = self._calculate_confidence(ent, entity_type)
            
            entity = DetectedEntity(
                text=ent.text,
                entity_type=entity_type,
                start=ent.start_char,
                end=ent.end_char,
                confidence=confidence,
                source='spacy'
            )
            entities.append(entity)
        
        logger.debug(f"NER detected {len(entities)} entities in text")
        return entities
    
    def _is_valid_entity(self, ent) -> bool:
        """
        Validate if an entity is truly PII-sensitive or just a false positive.
        Reject common nouns, generic terms, and low-confidence detections.
        """
        text = ent.text.lower()
        label = ent.label_
        
        # ONLY mask these specific entity types (strict allowlist)
        SENSITIVE_LABELS = {'PERSON', 'ORG', 'GPE'}
        
        # For non-sensitive types, require minimum length
        if label not in SENSITIVE_LABELS:
            if len(text) < 3:
                return False
        
        # For PERSON entities, require proper capitalization (names are capitalized)
        if label == 'PERSON':
            # If text is all lowercase, it's probably not a real name
            if text == text.lower():
                return False
        
        # For ORG/GPE, reject if it's a single common word
        if label in {'ORG', 'GPE'}:
            if text in self.EXCLUDED_TERMS:
                return False
        
        return True
    
    def _calculate_confidence(self, ent, entity_type: str) -> float:
        """
        Calculate confidence score for an entity
        
        Higher confidence for:
        - Priority entities (names, orgs, locations)
        - Longer entity text
        - Entities that match expected patterns
        """
        base_confidence = 0.7
        
        # Priority entities get higher confidence
        if entity_type in self.PRIORITY_ENTITIES:
            base_confidence = 0.85
        
        # Longer entities are usually more reliable
        if len(ent.text) > 5:
            base_confidence += 0.05
        
        # Names starting with capital letters
        if entity_type == 'USER' and ent.text[0].isupper():
            base_confidence += 0.05
        
        return min(base_confidence, 0.99)
    
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
                confidence = self._calculate_confidence(ent, entity_type)
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
