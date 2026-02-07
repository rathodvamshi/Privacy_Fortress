"""
Fuzzy Engine - Approximate matching to catch typos and variations
Uses RapidFuzz for fast fuzzy string matching
"""
from typing import List, Dict, Set, Optional
from dataclasses import dataclass
from rapidfuzz import fuzz, process
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


class FuzzyEngine:
    """
    Fuzzy matching engine to catch typos and variations
    Example: "Alicee" -> "Alice", "Gogle" -> "Google"
    """
    
    # Common company names that might be misspelled
    KNOWN_COMPANIES: Set[str] = {
        'Google', 'Microsoft', 'Apple', 'Amazon', 'Facebook', 'Meta',
        'Netflix', 'Twitter', 'LinkedIn', 'Instagram', 'WhatsApp',
        'TCS', 'Infosys', 'Wipro', 'HCL', 'Tech Mahindra', 'Cognizant',
        'Accenture', 'Deloitte', 'KPMG', 'EY', 'PwC',
        'IBM', 'Oracle', 'SAP', 'Salesforce', 'Adobe', 'Intel', 'Nvidia',
        'Tesla', 'SpaceX', 'Uber', 'Lyft', 'Airbnb', 'Stripe', 'Shopify',
    }
    
    # Common colleges/universities
    KNOWN_COLLEGES: Set[str] = {
        'MIT', 'Stanford', 'Harvard', 'Yale', 'Princeton', 'Columbia',
        'IIT', 'IIM', 'BITS', 'NIT', 'IIIT', 'VIT', 'SRM', 'Manipal',
        'CBIT', 'JNTU', 'Osmania', 'Anna University', 'Delhi University',
        'Oxford', 'Cambridge', 'Berkeley', 'UCLA', 'Caltech',
    }
    
    # Common first names (will match variations)
    COMMON_NAMES: Set[str] = {
        'John', 'Jane', 'Alice', 'Bob', 'Charlie', 'David', 'Emma',
        'James', 'Mary', 'Robert', 'Patricia', 'Michael', 'Jennifer',
        'William', 'Linda', 'Richard', 'Elizabeth', 'Joseph', 'Barbara',
        'Rahul', 'Priya', 'Amit', 'Anita', 'Raj', 'Pooja', 'Vikram',
        'Sneha', 'Arjun', 'Kavya', 'Rohan', 'Neha', 'Arun', 'Sanjay',
    }
    
    def __init__(self, threshold: int = 85):
        """
        Initialize the fuzzy engine
        
        Args:
            threshold: Minimum similarity score (0-100) to consider a match
        """
        self.threshold = threshold
        self.known_entities = self._build_entity_map()
    
    def _build_entity_map(self) -> Dict[str, str]:
        """Build a map of known entities to their types"""
        entity_map = {}
        
        for name in self.COMMON_NAMES:
            entity_map[name.lower()] = 'USER'
        
        for company in self.KNOWN_COMPANIES:
            entity_map[company.lower()] = 'ORG'
        
        for college in self.KNOWN_COLLEGES:
            entity_map[college.lower()] = 'COLLEGE'
        
        return entity_map
    
    def detect(self, text: str) -> List[DetectedEntity]:
        """
        Detect entities using fuzzy matching
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of DetectedEntity objects
        """
        if not text or not text.strip():
            return []
        
        entities = []
        words = text.split()
        
        for i, word in enumerate(words):
            # Skip very short words
            if len(word) < 3:
                continue
            
            # Clean the word
            clean_word = word.strip('.,!?;:\'"()[]{}')
            
            # Find the best match
            match = self._find_best_match(clean_word)
            
            if match:
                # Find position in original text
                start = text.find(word)
                if start >= 0:
                    entity = DetectedEntity(
                        text=word,
                        entity_type=match['type'],
                        start=start,
                        end=start + len(word),
                        confidence=match['score'] / 100,
                        source='fuzzy'
                    )
                    entities.append(entity)
        
        logger.debug(f"Fuzzy detected {len(entities)} entities in text")
        return entities
    
    def _find_best_match(self, word: str) -> Optional[Dict]:
        """
        Find the best fuzzy match for a word
        
        Args:
            word: Word to match
            
        Returns:
            Dict with 'match', 'type', and 'score', or None
        """
        word_lower = word.lower()
        
        # First, check for exact match
        if word_lower in self.known_entities:
            return {
                'match': word,
                'type': self.known_entities[word_lower],
                'score': 100
            }
        
        # Use fuzzy matching
        all_known = list(self.known_entities.keys())
        result = process.extractOne(
            word_lower,
            all_known,
            scorer=fuzz.ratio
        )
        
        if result and result[1] >= self.threshold:
            matched_word = result[0]
            return {
                'match': matched_word,
                'type': self.known_entities[matched_word],
                'score': result[1]
            }
        
        return None
    
    def add_known_entity(self, entity: str, entity_type: str):
        """
        Add a new known entity for fuzzy matching
        
        Args:
            entity: Entity name
            entity_type: Type (USER, ORG, COLLEGE)
        """
        self.known_entities[entity.lower()] = entity_type
    
    def detect_in_context(self, text: str, context_words: List[str]) -> List[DetectedEntity]:
        """
        Detect entities with context awareness
        Words near "name", "company", "works at" etc. are more likely to be entities
        
        Args:
            text: Input text
            context_words: List of context indicators
            
        Returns:
            List of DetectedEntity objects
        """
        entities = []
        words = text.split()
        
        # Context indicators
        name_indicators = {'name', 'called', 'am', 'i\'m', 'is', 'named'}
        org_indicators = {'at', 'from', 'company', 'works', 'employed', 'organization'}
        college_indicators = {'college', 'university', 'institute', 'school', 'studying'}
        
        for i, word in enumerate(words):
            clean_word = word.strip('.,!?;:\'"()[]{}')
            
            # Check context
            prev_words = [w.lower() for w in words[max(0, i-2):i]]
            
            # Increase confidence if context matches
            boost = 0
            if any(ind in prev_words for ind in name_indicators):
                boost = 10
            elif any(ind in prev_words for ind in org_indicators):
                boost = 10
            elif any(ind in prev_words for ind in college_indicators):
                boost = 10
            
            match = self._find_best_match(clean_word)
            
            if match and (match['score'] + boost) >= self.threshold:
                start = text.find(word)
                if start >= 0:
                    entity = DetectedEntity(
                        text=word,
                        entity_type=match['type'],
                        start=start,
                        end=start + len(word),
                        confidence=min((match['score'] + boost) / 100, 0.99),
                        source='fuzzy'
                    )
                    entities.append(entity)
        
        return entities


# Singleton instance
_fuzzy_engine = None

def get_fuzzy_engine() -> FuzzyEngine:
    """Get the singleton fuzzy engine instance"""
    global _fuzzy_engine
    if _fuzzy_engine is None:
        _fuzzy_engine = FuzzyEngine()
    return _fuzzy_engine
