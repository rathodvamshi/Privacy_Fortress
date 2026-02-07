"""
Masking Pipeline - Orchestrates all detection engines
The complete flow: Text -> Detect -> Merge -> Score -> Tokenize -> Masked Text
"""
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging

from .ner_engine import NEREngine, get_ner_engine, DetectedEntity as NEREntity
from .regex_engine import RegexEngine, get_regex_engine, DetectedEntity as RegexEntity
from .fuzzy_engine import FuzzyEngine, get_fuzzy_engine, DetectedEntity as FuzzyEntity
from .confidence import ConfidenceScorer, get_confidence_scorer, ScoredEntity
from .tokenizer import Tokenizer, TokenMapping

logger = logging.getLogger(__name__)


@dataclass
class MaskingResult:
    """Result of the masking pipeline"""
    original_text: str
    masked_text: str
    tokens: Dict[str, TokenMapping]
    entities_detected: int
    entity_breakdown: Dict[str, int]


@dataclass
class UnmaskingResult:
    """Result of the unmasking pipeline"""
    masked_text: str
    unmasked_text: str
    tokens_replaced: int


class MaskingPipeline:
    """
    Complete masking pipeline that orchestrates all detection engines
    
    Flow:
    1. Text cleaning and preprocessing
    2. NER detection (spaCy)
    3. Regex pattern matching
    4. Fuzzy matching for typos
    5. Entity merging and confidence scoring
    6. Tokenization
    7. Return masked text + mappings
    """
    
    def __init__(self, session_id: str):
        """
        Initialize the masking pipeline for a session
        
        Args:
            session_id: Unique session identifier
        """
        self.session_id = session_id
        
        # Initialize engines
        self.ner_engine = get_ner_engine()
        self.regex_engine = get_regex_engine()
        self.fuzzy_engine = get_fuzzy_engine()
        self.confidence_scorer = get_confidence_scorer()
        
        # Initialize tokenizer for this session
        self.tokenizer = Tokenizer(session_id)
    
    def mask(self, text: str) -> MaskingResult:
        """
        Complete masking pipeline
        
        Args:
            text: Original text with potential PII
            
        Returns:
            MaskingResult with masked text and mappings
        """
        if not text or not text.strip():
            return MaskingResult(
                original_text=text,
                masked_text=text,
                tokens={},
                entities_detected=0,
                entity_breakdown={}
            )
        
        logger.info(f"Starting masking pipeline for session {self.session_id}")
        
        # Step 1: Preprocess text
        cleaned_text = self._preprocess(text)
        
        # Step 2: Run all detection engines in parallel (conceptually)
        ner_entities = self._run_ner(cleaned_text)
        regex_entities = self._run_regex(cleaned_text)
        fuzzy_entities = self._run_fuzzy(cleaned_text)
        
        logger.debug(f"Detected: NER={len(ner_entities)}, Regex={len(regex_entities)}, Fuzzy={len(fuzzy_entities)}")
        
        # Step 3: Convert all to common format
        ner_common = self._convert_entities(ner_entities)
        regex_common = self._convert_entities(regex_entities)
        fuzzy_common = self._convert_entities(fuzzy_entities)
        
        # Step 4: Merge and score
        scored_entities = self.confidence_scorer.merge_and_score(
            ner_common, regex_common, fuzzy_common
        )
        
        logger.debug(f"Merged into {len(scored_entities)} scored entities")
        
        # Step 5: Tokenize
        masked_text, token_mappings = self.tokenizer.mask_text(text, scored_entities)
        
        # Step 6: Calculate breakdown
        breakdown = self._calculate_breakdown(scored_entities)
        
        logger.info(f"Masked {len(scored_entities)} entities, generated {len(token_mappings)} tokens")
        
        return MaskingResult(
            original_text=text,
            masked_text=masked_text,
            tokens=token_mappings,
            entities_detected=len(scored_entities),
            entity_breakdown=breakdown
        )
    
    def unmask(self, masked_text: str) -> UnmaskingResult:
        """
        Unmask text by replacing tokens with original values
        
        Args:
            masked_text: Text with tokens
            
        Returns:
            UnmaskingResult with original text restored
        """
        unmasked_text = self.tokenizer.unmask_text(masked_text)
        
        # Count how many tokens were replaced
        tokens_replaced = sum(1 for token in self.tokenizer.get_all_mappings() if token in masked_text)
        
        return UnmaskingResult(
            masked_text=masked_text,
            unmasked_text=unmasked_text,
            tokens_replaced=tokens_replaced
        )
    
    def _preprocess(self, text: str) -> str:
        """
        Preprocess text before detection
        
        Args:
            text: Raw input text
            
        Returns:
            Cleaned text
        """
        # Remove excessive whitespace but preserve structure
        cleaned = ' '.join(text.split())
        return cleaned
    
    def _run_ner(self, text: str) -> List[NEREntity]:
        """Run NER detection"""
        try:
            return self.ner_engine.detect(text)
        except Exception as e:
            logger.error(f"NER detection failed: {e}")
            return []
    
    def _run_regex(self, text: str) -> List[RegexEntity]:
        """Run regex detection"""
        try:
            return self.regex_engine.detect(text)
        except Exception as e:
            logger.error(f"Regex detection failed: {e}")
            return []
    
    def _run_fuzzy(self, text: str) -> List[FuzzyEntity]:
        """Run fuzzy detection"""
        try:
            return self.fuzzy_engine.detect(text)
        except Exception as e:
            logger.error(f"Fuzzy detection failed: {e}")
            return []
    
    def _convert_entities(self, entities) -> List:
        """Convert entities to common format for confidence scorer"""
        # Entities from all engines use the same DetectedEntity structure
        # so they can be passed directly
        return entities
    
    def _calculate_breakdown(self, entities: List[ScoredEntity]) -> Dict[str, int]:
        """Calculate entity type breakdown"""
        breakdown = {}
        for entity in entities:
            entity_type = entity.entity_type
            breakdown[entity_type] = breakdown.get(entity_type, 0) + 1
        return breakdown
    
    def load_session_mappings(self, mappings: Dict[str, Dict]):
        """
        Load existing token mappings from vault
        
        Args:
            mappings: Token mappings from Redis
        """
        self.tokenizer.load_mappings(mappings)
    
    def export_session_mappings(self) -> Dict[str, Dict]:
        """
        Export token mappings for vault storage
        
        Returns:
            Mappings suitable for Redis storage
        """
        return self.tokenizer.export_mappings()
    
    def get_token_count(self) -> int:
        """Get number of tokens in this session"""
        return self.tokenizer.get_token_count()
    
    def get_masked_summary(self) -> Dict:
        """Get summary for UI display (without revealing actual values)"""
        return self.tokenizer.get_masked_summary()


# Pipeline instances cache (per session)
_pipelines: Dict[str, MaskingPipeline] = {}


def get_masking_pipeline(session_id: str) -> MaskingPipeline:
    """
    Get or create a masking pipeline for a session
    
    Args:
        session_id: Session identifier
        
    Returns:
        MaskingPipeline instance
    """
    if session_id not in _pipelines:
        _pipelines[session_id] = MaskingPipeline(session_id)
    return _pipelines[session_id]


def clear_pipeline(session_id: str):
    """Remove a pipeline from cache"""
    if session_id in _pipelines:
        del _pipelines[session_id]
