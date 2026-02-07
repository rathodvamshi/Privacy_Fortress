"""
Confidence Scorer - Merges and scores entities from multiple detection engines
"""
from typing import List, Dict, Tuple
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


class ConfidenceScorer:
    """
    Merges entities from multiple engines and calculates final confidence
    Resolves overlapping entities and deduplicates
    """
    
    # Source weights for confidence calculation
    SOURCE_WEIGHTS = {
        'regex': 1.0,      # Regex is most reliable for structured data
        'spacy': 0.9,      # spaCy is reliable for names/orgs
        'fuzzy': 0.7,      # Fuzzy is less reliable
    }
    
    # Entity type priorities (higher = more important to mask)
    TYPE_PRIORITIES = {
        'USER': 10,
        'EMAIL': 10,
        'PHONE': 9,
        'AADHAAR': 10,
        'PAN': 10,
        'CREDIT_CARD': 10,
        'SSN': 10,
        'ORG': 7,
        'COLLEGE': 7,
        'LOCATION': 6,
        'ADDRESS': 8,
        'IP_ADDRESS': 7,
        'DOB': 8,
        'BANK_ACCOUNT': 9,
        'PASSPORT': 9,
        'VEHICLE_REG': 7,
        'ROLL_NUMBER': 6,
        'EMPLOYEE_ID': 6,
        'URL': 5,
        'DATE': 4,
        'MONEY': 3,
        'NUMBER': 2,
        'OTHER': 1,
    }
    
    # Minimum confidence threshold to consider an entity
    MIN_CONFIDENCE = 0.5
    
    def __init__(self):
        """Initialize the confidence scorer"""
        pass
    
    def merge_and_score(
        self,
        ner_entities: List[DetectedEntity],
        regex_entities: List[DetectedEntity],
        fuzzy_entities: List[DetectedEntity]
    ) -> List[ScoredEntity]:
        """
        Merge entities from all engines, resolve overlaps, and score
        
        Args:
            ner_entities: Entities from spaCy NER
            regex_entities: Entities from regex patterns
            fuzzy_entities: Entities from fuzzy matching
            
        Returns:
            List of scored and deduplicated entities
        """
        all_entities = ner_entities + regex_entities + fuzzy_entities
        
        if not all_entities:
            return []
        
        # Group overlapping entities
        groups = self._group_overlapping(all_entities)
        
        # Score each group and select best
        scored_entities = []
        for group in groups:
            best = self._score_group(group)
            if best and best.confidence >= self.MIN_CONFIDENCE:
                scored_entities.append(best)
        
        # Sort by position
        scored_entities.sort(key=lambda e: e.start)
        
        logger.debug(f"Merged {len(all_entities)} entities into {len(scored_entities)} final entities")
        return scored_entities
    
    def _group_overlapping(self, entities: List[DetectedEntity]) -> List[List[DetectedEntity]]:
        """
        Group entities that overlap in position
        
        Args:
            entities: All detected entities
            
        Returns:
            List of entity groups
        """
        if not entities:
            return []
        
        # Sort by start position
        sorted_entities = sorted(entities, key=lambda e: (e.start, -e.end))
        
        groups = []
        current_group = [sorted_entities[0]]
        current_end = sorted_entities[0].end
        
        for entity in sorted_entities[1:]:
            # Check if overlapping with current group
            if entity.start < current_end:
                current_group.append(entity)
                current_end = max(current_end, entity.end)
            else:
                groups.append(current_group)
                current_group = [entity]
                current_end = entity.end
        
        groups.append(current_group)
        return groups
    
    def _score_group(self, group: List[DetectedEntity]) -> ScoredEntity:
        """
        Score a group of overlapping entities and return the best one
        
        Args:
            group: List of overlapping entities
            
        Returns:
            Best scored entity from the group
        """
        if not group:
            return None
        
        if len(group) == 1:
            entity = group[0]
            return ScoredEntity(
                text=entity.text,
                entity_type=entity.entity_type,
                start=entity.start,
                end=entity.end,
                confidence=entity.confidence * self.SOURCE_WEIGHTS.get(entity.source, 0.5),
                sources=[entity.source],
                priority=self.TYPE_PRIORITIES.get(entity.entity_type, 1)
            )
        
        # Calculate aggregated scores
        type_scores: Dict[str, Dict] = {}
        
        for entity in group:
            key = entity.entity_type
            weight = self.SOURCE_WEIGHTS.get(entity.source, 0.5)
            weighted_confidence = entity.confidence * weight
            
            if key not in type_scores:
                type_scores[key] = {
                    'text': entity.text,
                    'start': entity.start,
                    'end': entity.end,
                    'confidence_sum': weighted_confidence,
                    'count': 1,
                    'sources': [entity.source],
                    'max_text_len': len(entity.text),
                }
            else:
                type_scores[key]['confidence_sum'] += weighted_confidence
                type_scores[key]['count'] += 1
                if entity.source not in type_scores[key]['sources']:
                    type_scores[key]['sources'].append(entity.source)
                # Keep the longest text
                if len(entity.text) > type_scores[key]['max_text_len']:
                    type_scores[key]['text'] = entity.text
                    type_scores[key]['start'] = entity.start
                    type_scores[key]['end'] = entity.end
                    type_scores[key]['max_text_len'] = len(entity.text)
        
        # Find the best type
        best_type = None
        best_score = 0
        
        for entity_type, scores in type_scores.items():
            # Multi-source boost: if multiple engines agree, boost confidence
            multi_source_boost = 1 + (0.1 * (scores['count'] - 1))
            priority_weight = self.TYPE_PRIORITIES.get(entity_type, 1) / 10
            
            final_score = (scores['confidence_sum'] / scores['count']) * multi_source_boost * (1 + priority_weight)
            
            if final_score > best_score:
                best_score = final_score
                best_type = entity_type
        
        if best_type:
            scores = type_scores[best_type]
            return ScoredEntity(
                text=scores['text'],
                entity_type=best_type,
                start=scores['start'],
                end=scores['end'],
                confidence=min(best_score, 0.99),
                sources=scores['sources'],
                priority=self.TYPE_PRIORITIES.get(best_type, 1)
            )
        
        return None
    
    def filter_by_priority(
        self,
        entities: List[ScoredEntity],
        min_priority: int = 5
    ) -> List[ScoredEntity]:
        """
        Filter entities by minimum priority
        
        Args:
            entities: Scored entities
            min_priority: Minimum priority to include
            
        Returns:
            Filtered list of entities
        """
        return [e for e in entities if e.priority >= min_priority]


# Singleton instance
_confidence_scorer = None

def get_confidence_scorer() -> ConfidenceScorer:
    """Get the singleton confidence scorer instance"""
    global _confidence_scorer
    if _confidence_scorer is None:
        _confidence_scorer = ConfidenceScorer()
    return _confidence_scorer
