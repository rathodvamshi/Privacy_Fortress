"""
Masking Pipeline - Orchestrates all detection engines
The complete flow: Text -> Detect -> Merge -> Score -> Decide -> Tokenize -> Masked Text

Advanced features:
  - Proximity-based sensitivity boosting
  - Secret-sharing intent detection (max-masking mode)
  - Synthetic data injection (optional)
  - Basic coreference resolution (pronoun → entity tracking)
"""
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging
import re as _re

from .ner_engine import NEREngine, get_ner_engine, DetectedEntity as NEREntity
from .regex_engine import RegexEngine, get_regex_engine, DetectedEntity as RegexEntity
from .fuzzy_engine import FuzzyEngine, get_fuzzy_engine, DetectedEntity as FuzzyEntity
from .confidence import ConfidenceScorer, get_confidence_scorer, ScoredEntity
from .decision_engine import DecisionEngine, get_decision_engine, DecisionRecord
from .tokenizer import Tokenizer, TokenMapping

logger = logging.getLogger(__name__)


# ─── Coreference Resolution ──────────────────────────────────────────────
# Maps pronouns to the gender-hint or plurality of the last masked entity.
# When the user says "My name is Vijay, he lives in Hyd", we know "he"
# refers to the already-masked entity and should NOT leak information.
_PRONOUN_MAP = {
    # Subject pronouns
    "he": "USER", "she": "USER", "they": "USER",
    # Object pronouns
    "him": "USER", "her": "USER", "them": "USER",
    # Possessive
    "his": "USER", "hers": "USER", "their": "USER", "theirs": "USER",
    # Reflexive
    "himself": "USER", "herself": "USER", "themselves": "USER",
}

# Phrases that indicate a pronoun is referring to a previously mentioned person
_COREF_CONTEXT_PATTERNS = [
    r"\b(he|she|they)\s+(?:is|was|lives?|works?|stays?|moved?|went|called|named|located)\b",
    r"\b(his|her|their)\s+(?:name|phone|email|number|address|account|password|id)\b",
    r"\bcontact\s+(him|her|them)\b",
    r"\bcall\s+(him|her|them)\b",
    r"\breach\s+(him|her|them)\b",
]



@dataclass
class MaskingResult:
    """Result of the masking pipeline"""
    original_text: str
    masked_text: str
    tokens: Dict[str, TokenMapping]
    entities_detected: int
    entity_breakdown: Dict[str, int]
    # NEW: Decision tracking
    decisions: List[DecisionRecord]
    entities_allowed: int
    entities_masked: int
    entities_blocked: int
    # NEW: Validation metadata
    validation_errors: List[str]
    processing_time_ms: float



@dataclass
class UnmaskingResult:
    """Result of the unmasking pipeline"""
    masked_text: str
    unmasked_text: str
    tokens_replaced: int

    def __str__(self) -> str:
        """Return unmasked_text so str(result) is always safe for Pydantic / f-strings."""
        return self.unmasked_text


class MaskingPipeline:
    """
    Complete masking pipeline that orchestrates all detection engines
    
    Flow:
    1. Text cleaning and preprocessing
    2. NER detection (spaCy)
    3. Regex pattern matching
    4. Fuzzy matching for typos
    5. Entity merging and confidence scoring
    6. 🆕 Context-aware decision making (ALLOW/MASK/BLOCK)
    7. Tokenization (only for MASK decisions)
    8. 🆕 Coreference resolution (pronoun tracking)
    9. Validation and audit
    10. Return masked text + mappings + decisions
    """
    
    def __init__(self, session_id: str, synthetic_mode: bool = False):
        """
        Initialize the masking pipeline for a session
        
        Args:
            session_id: Unique session identifier
            synthetic_mode: If True, use realistic fake data instead of bracket tokens
        """
        self.session_id = session_id
        self.synthetic_mode = synthetic_mode
        
        # Initialize detection engines
        self.ner_engine = get_ner_engine()
        self.regex_engine = get_regex_engine()
        self.fuzzy_engine = get_fuzzy_engine()
        self.confidence_scorer = get_confidence_scorer()
        
        # 🆕 Initialize decision engine for context-aware filtering
        self.decision_engine = get_decision_engine()
        
        # Initialize tokenizer for this session (with optional synthetic mode)
        self.tokenizer = Tokenizer(session_id, synthetic_mode=synthetic_mode)
        
        # Coreference tracking: maps masked person tokens → pronoun occurrences
        self._coref_chain: Dict[str, List[str]] = {}
        # Track the last masked PERSON token for pronoun resolution
        self._last_person_token: Optional[str] = None
        
        # Validation & error tracking
        self._last_errors: List[str] = []
    
    def mask(self, text: str) -> MaskingResult:
        """
        Complete masking pipeline with context-aware decisions
        
        Args:
            text: Original text with potential PII
            
        Returns:
            MaskingResult with masked text, mappings, and decision records
            
        Raises:
            ValueError: If text is invalid or contains blocked content
        """
        import time
        start_time = time.time()
        self._last_errors = []
        
        # Validation: Empty or None input
        if not text or not text.strip():
            return MaskingResult(
                original_text=text or "",
                masked_text=text or "",
                tokens={},
                entities_detected=0,
                entity_breakdown={},
                decisions=[],
                entities_allowed=0,
                entities_masked=0,
                entities_blocked=0,
                validation_errors=[],
                processing_time_ms=0.0
            )
        
        # Validation: Input length
        if len(text) > 50000:  # 50K character limit
            self._last_errors.append(f"Input too long: {len(text)} chars (max 50000)")
            logger.warning(f"Input exceeds max length: {len(text)} chars")
        
        logger.info(f"🔒 Starting masking pipeline for session {self.session_id}")
        
        # Step 1: Preprocess text
        try:
            cleaned_text = self._preprocess(text)
        except Exception as e:
            logger.error(f"Preprocessing failed: {e}")
            self._last_errors.append(f"Preprocessing error: {str(e)}")
            cleaned_text = text  # Fallback to original
        
        # Step 2: Run all detection engines in parallel (conceptually)
        ner_entities = self._run_ner(cleaned_text)
        regex_entities = self._run_regex(cleaned_text)
        fuzzy_entities = self._run_fuzzy(cleaned_text)
        
        total_raw_detections = len(ner_entities) + len(regex_entities) + len(fuzzy_entities)
        logger.debug(f"📊 Raw detections: NER={len(ner_entities)}, Regex={len(regex_entities)}, Fuzzy={len(fuzzy_entities)}")
        
        # Step 3: Convert all to common format
        ner_common = self._convert_entities(ner_entities)
        regex_common = self._convert_entities(regex_entities)
        fuzzy_common = self._convert_entities(fuzzy_entities)
        
        # Step 4: Merge and score
        try:
            scored_entities = self.confidence_scorer.merge_and_score(
                ner_common, regex_common, fuzzy_common
            )
        except Exception as e:
            logger.error(f"Confidence scoring failed: {e}")
            self._last_errors.append(f"Scoring error: {str(e)}")
            scored_entities = []
        
        logger.debug(f"✅ Merged {total_raw_detections} raw detections → {len(scored_entities)} scored entities")
        
        # 🆕 Step 5: DECISION ENGINE - Context-aware filtering
        try:
            entities_to_mask, decisions, blocked, block_reasons = self.decision_engine.decide(
                text, scored_entities
            )
        except Exception as e:
            logger.error(f"Decision engine failed: {e}")
            self._last_errors.append(f"Decision error: {str(e)}")
            # Fallback: mask everything (safe default)
            entities_to_mask = scored_entities
            decisions = []
            blocked = False
            block_reasons = []
        
        # Count decisions
        entities_allowed = sum(1 for d in decisions if d.decision == "ALLOW")
        entities_masked = sum(1 for d in decisions if d.decision == "MASK")
        entities_blocked = sum(1 for d in decisions if d.decision == "BLOCK")
        
        logger.info(f"📋 Decisions: ALLOW={entities_allowed}, MASK={entities_masked}, BLOCK={entities_blocked}")
        
        # Log decisions for audit
        for decision in decisions:
            logger.debug(
                f"  • {decision.privacy_entity_type} ({decision.sensitivity}): "
                f"{decision.decision} [conf={decision.confidence:.2f}, owner={decision.ownership}] "
                f"- {', '.join(decision.reasons)}"
            )
        
        # 🛑 CRITICAL: Block request if high-risk secrets detected
        if blocked:
            error_msg = f"Request blocked - contains high-risk secrets: {', '.join(block_reasons)}"
            logger.warning(f"🛑 {error_msg}")
            raise ValueError(error_msg)
        
        # Step 6: Tokenize ONLY entities marked for MASK
        try:
            masked_text, token_mappings = self.tokenizer.mask_text(text, entities_to_mask)
        except Exception as e:
            logger.error(f"Tokenization failed: {e}")
            self._last_errors.append(f"Tokenization error: {str(e)}")
            # Fallback: return original text
            masked_text = text
            token_mappings = {}
        
        # 🆕 Step 6.5: Coreference Resolution — detect pronouns referring to masked persons
        try:
            masked_text, coref_annotations = self._resolve_coreferences(
                masked_text, token_mappings, entities_to_mask
            )
            if coref_annotations:
                logger.info(f"🔗 Coreference: resolved {len(coref_annotations)} pronoun(s)")
        except Exception as e:
            logger.error(f"Coreference resolution failed: {e}")
            coref_annotations = []
        
        # Step 7: Calculate breakdown (from original scored entities, not just masked ones)
        breakdown = self._calculate_breakdown(scored_entities)
        
        # Step 8: Validation
        validation_errors = self._validate_masking(text, masked_text, token_mappings)
        if validation_errors:
            self._last_errors.extend(validation_errors)
            logger.warning(f"⚠️ Validation warnings: {len(validation_errors)}")
        
        processing_time = (time.time() - start_time) * 1000  # Convert to ms
        
        logger.info(
            f"✅ Masking complete: {len(scored_entities)} entities detected, "
            f"{entities_masked} masked, {entities_allowed} allowed, "
            f"{len(token_mappings)} tokens generated in {processing_time:.1f}ms"
        )
        
        return MaskingResult(
            original_text=text,
            masked_text=masked_text,
            tokens=token_mappings,
            entities_detected=len(scored_entities),
            entity_breakdown=breakdown,
            decisions=decisions,
            entities_allowed=entities_allowed,
            entities_masked=entities_masked,
            entities_blocked=entities_blocked,
            validation_errors=self._last_errors,
            processing_time_ms=processing_time
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
    
    # ─── Coreference Resolution ───────────────────────────────────────────
    def _resolve_coreferences(
        self,
        masked_text: str,
        token_mappings: Dict[str, TokenMapping],
        masked_entities: List[ScoredEntity],
    ) -> Tuple[str, List[Dict]]:
        """
        Basic coreference resolution: detect pronouns that refer to masked entities.
        
        Strategy:
        1. Identify which masked entities are PERSON-type (USER_NAME, PERSON).
        2. Walk through the *masked* text. When we find a pronoun (he, she, him, her …)
           in a context that suggests it refers to a previously masked person, we
           annotate it so the LLM (and the user) know it carries PII-by-reference.
        3. Optionally replace the pronoun with the same token, e.g.
           "[USER_1] went to school. He scored well" → "[USER_1] went to school. [USER_1] scored well"
        
        We are conservative: pronouns are only resolved when:
          - A PERSON entity was masked earlier in the text.
          - The pronoun appears in a sentence AFTER the masked entity.
          - The pronoun matches a known coreference-context pattern.
        
        Args:
            masked_text: Text after initial masking pass.
            token_mappings: Current token→original mappings.
            masked_entities: Entities that were masked.
            
        Returns:
            (updated_masked_text, coref_annotations list)
        """
        # 1. Find person tokens in the masked text
        person_types = {"USER_NAME", "PERSON", "NAME"}
        person_tokens = []
        for tok_name, mapping in token_mappings.items():
            canon = getattr(mapping, "canonical_type", "")
            if canon in person_types or tok_name.startswith("[USER_"):
                person_tokens.append(tok_name)
        
        if not person_tokens:
            return masked_text, []
        
        # 2. The most-recently-masked person token (appears first / is the primary subject)
        #    We pick the one that appears earliest in the text.
        first_person_token = None
        earliest_pos = len(masked_text)
        for pt in person_tokens:
            pos = masked_text.find(pt)
            if pos != -1 and pos < earliest_pos:
                earliest_pos = pos
                first_person_token = pt
        
        if first_person_token is None:
            return masked_text, []
        
        # 3. Find pronouns AFTER the first person token that match coreference patterns
        after_entity = masked_text[earliest_pos + len(first_person_token):]
        annotations = []
        replacements = []  # (start_in_after, end_in_after, replacement)
        
        for pattern_str in _COREF_CONTEXT_PATTERNS:
            for m in _re.finditer(pattern_str, after_entity, _re.IGNORECASE):
                pronoun_group = 1  # group(1) is the pronoun
                pronoun = m.group(pronoun_group)
                # Position in full masked_text
                abs_start = earliest_pos + len(first_person_token) + m.start(pronoun_group)
                abs_end = earliest_pos + len(first_person_token) + m.end(pronoun_group)
                
                annotations.append({
                    "pronoun": pronoun,
                    "refers_to": first_person_token,
                    "position": abs_start,
                    "context_pattern": pattern_str,
                })
                replacements.append((abs_start, abs_end, first_person_token))
        
        if not replacements:
            return masked_text, annotations
        
        # 4. Apply replacements in reverse order to keep positions stable
        replacements.sort(key=lambda r: r[0], reverse=True)
        updated = masked_text
        for start, end, replacement in replacements:
            updated = updated[:start] + replacement + updated[end:]
        
        # Update the coreference chain tracker
        self._coref_chain.setdefault(first_person_token, []).extend(
            [a["pronoun"] for a in annotations]
        )
        self._last_person_token = first_person_token
        
        logger.debug(
            f"🔗 Coreference: {len(annotations)} pronoun(s) → {first_person_token}"
        )
        
        return updated, annotations
    
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
    
    def _validate_masking(
        self,
        original: str,
        masked: str,
        tokens: Dict[str, TokenMapping]
    ) -> List[str]:
        """
        Validate masking results to catch errors
        
        Args:
            original: Original text
            masked: Masked text
            tokens: Token mappings
            
        Returns:
            List of validation error messages (empty if all good)
        """
        errors = []
        
        # 1. Check if masking actually happened when tokens exist
        if tokens and original == masked:
            errors.append("Masking produced no changes despite having tokens")
        
        # 2. Check for orphaned tokens (tokens without mappings)
        import re
        # Pattern to find tokens in text: matches [USER_1]
        token_pattern = r'(\[[A-Z]+_\d+\])'
        tokens_in_text = set(re.findall(token_pattern, masked))
        mapped_tokens = set(tokens.keys())  # Keys include brackets: [USER_1]
        
        orphaned = tokens_in_text - mapped_tokens
        if orphaned:
            errors.append(f"Found orphaned tokens in masked text: {orphaned}")
        
        # 3. Check for incomplete token removal (original values still present)
        for token_name, mapping in tokens.items():
            original_value = mapping.original
            if original_value and len(original_value) > 3:  # Skip very short values
                # Case-insensitive check
                if original_value.lower() in masked.lower() and original_value.lower() not in original.lower():
                    errors.append(
                        f"Original value '{original_value}' found in masked text "
                        f"(should be {token_name})"
                    )
        
        # 4. Check for excessive masking (masked text much shorter than original)
        len_ratio = len(masked) / len(original) if len(original) > 0 else 1.0
        if len_ratio < 0.3 and len(tokens) > 5:
            errors.append(
                f"Excessive masking: masked text is {len_ratio*100:.1f}% of original "
                f"({len(masked)} vs {len(original)} chars)"
            )
        
        # 5. Check for malformed tokens
        for token_name in tokens.keys():
            # Tokens must look like [TYPE_ID]
            if not re.match(r'^\[[A-Z]+_\d+\]$', token_name):
                errors.append(f"Malformed token name: {token_name}")
        
        return errors
    
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


def get_masking_pipeline(session_id: str, synthetic_mode: bool = False) -> MaskingPipeline:
    """
    Get or create a masking pipeline for a session
    
    Args:
        session_id: Session identifier
        synthetic_mode: If True, use realistic synthetic data instead of bracket tokens
        
    Returns:
        MaskingPipeline instance
    """
    if session_id not in _pipelines:
        _pipelines[session_id] = MaskingPipeline(session_id, synthetic_mode=synthetic_mode)
    return _pipelines[session_id]


def clear_pipeline(session_id: str):
    """Remove a pipeline from cache"""
    if session_id in _pipelines:
        del _pipelines[session_id]
