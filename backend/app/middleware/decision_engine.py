"""
Decision Engine — context-aware sensitivity + ALLOW/MASK/BLOCK

This module takes the merged/scored entities from the detection stack
and decides, **per entity**, whether it should be:

    - ALLOW  → pass through unchanged
    - MASK   → replaced by a token before sending to the AI
    - BLOCK  → hard-block the entire request (e.g. OTP / secrets)

It also:
    - Normalizes entity types into the locked taxonomy
    - Runs a ±5-token context window analysis
    - Performs simple ownership resolution (USER / THIRD_PARTY / GENERIC / UNKNOWN)
    - Assigns HIGH / SEMI / SAFE sensitivity
    - Emits structured, no-PII logs for explainability
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Literal, Tuple
import logging
import re

from .confidence import ScoredEntity

logger = logging.getLogger(__name__)

Ownership = Literal["USER", "THIRD_PARTY", "GENERIC", "UNKNOWN"]
Sensitivity = Literal["HIGH", "SEMI", "SAFE"]
DecisionAction = Literal["ALLOW", "MASK", "BLOCK"]


@dataclass
class DecisionRecord:
    """
    Explainable decision for a single detected entity.

    NOTE: This intentionally does NOT contain the raw text value, only:
      - taxonomy-level entity label
      - confidence / ownership / sensitivity
      - which engines contributed
      - the final decision + reasons
    """

    privacy_entity_type: str
    confidence: float
    ownership: Ownership
    sensitivity: Sensitivity
    decision: DecisionAction
    sources: List[str]
    reasons: List[str]


class DecisionEngine:
    """
    Context-aware decision engine sitting between detection and tokenization.

    Input:
        - original text
        - scored entities (merged across regex / spaCy / fuzzy)

    Output:
        - entities_to_mask: filtered list of entities that should be tokenized
        - decisions: list[DecisionRecord] for logging / inspection
        - blocked: bool flag if request must be blocked
        - block_reasons: high-level reasons for block
    """

    # --- Locked taxonomy (DO NOT CHANGE) -------------------------------

    HIGH_SENSITIVE_TYPES = {
        "USER_NAME",
        "USER_PHONE",
        "USER_EMAIL",
        "USER_GOV_ID",
        "BANK_ACCOUNT",
        "CREDIT_CARD",
        "OTP",
        "PASSWORD",
        "API_KEY",
        "AUTH_TOKEN",
        "SECRET",            # New generic secret
        "HEALTH_INFO",
        "USER_LOCATION_EXACT",
        "SUSPICIOUS_NUMBER", # High recall safety net
    }

    SEMI_SENSITIVE_TYPES = {
        "USER_LOCATION_CITY",
        "USER_LOCATION_STATE",
        "DOB_PARTIAL",
        "EMPLOYEE_ID",
    }

    SAFE_TYPES = {
        "PUBLIC_PERSON",
        "FICTIONAL_NAME",
        "TECH_NUMBER",
        "DATE_GENERIC",
        "LOCATION_GENERIC",
    }

    # Types that should HARD-BLOCK the entire request when they clearly
    # belong to the user (never safe to send to AI, even masked).
    GLOBAL_BLOCK_TYPES = {
        "OTP",
        "PASSWORD",
        "API_KEY",
        "AUTH_TOKEN",
        "SECRET",
    }

    # Keywords for simple context classification
    _TECH_NUMBER_KEYWORDS = {
        "parameter",
        "parameters",
        "params",
        "model",
        "version",
        "build",
        "epoch",
        "layer",
        "port",
        "code",
        "status",
        "http",
        "gpu",
        "cpu",
        "ram",
        "mb",
        "gb",
        "kb",
        "mbps",
        "kwh",
    }

    # Strong indicator that a numeric string is actually a phone/contact,
    # not a technical parameter.
    _PHONE_CONTEXT_HINTS = {
        "phone",
        "mobile",
        "whatsapp",
        "contact",
        "call",
        "sms",
    }

    _USER_OWNERSHIP_HINTS = {
        "my",
        "mine",
        "me",
        "i ",
        "i'm",
        "im ",
        "contact me",
        "reach me",
        "call me",
        "email me",
        "text me",
    }

    _THIRD_PARTY_HINTS = {
        "his",
        "her",
        "their",
        "them",
        "friend",
        "colleague",
        "boss",
        "manager",
        "customer",
        "client",
    }

    _GENERIC_HINTS = {
        "someone",
        "anyone",
        "example",
        "sample",
        "demo",
        "test",
        "dummy",
    }

    _NAME_CONTEXT_HINTS = {
        "my name is",
        "name is",
        "i'm",
        "im ",
        "i am",
        "call me",
        "they call me",
        "named",
    }

    _EXACT_LOCATION_HINTS = {
        "street",
        "st",
        "road",
        "rd",
        "lane",
        "ln",
        "avenue",
        "ave",
        "boulevard",
        "blvd",
        "colony",
        "phase",
        "sector",
        "block",
        "plot",
        "flat",
        "apartment",
        "apt",
        "house",
        "door no",
        "door number",
    }

    _CITY_STATE_HINTS = {
        "city",
        "town",
        "village",
        "district",
        "state",
    }

    # Personal location context: verbs/phrases indicating personal
    # connection to a place (triggers SEMI sensitivity for locations)
    _PERSONAL_LOCATION_HINTS = {
        "love", "like", "prefer", "miss", "enjoy",
        "live", "stay", "from", "born", "moved", "shifted",
        "visited", "visit", "going", "headed", "based",
        "relocated", "settled", "native", "hometown",
    }

    # Known location abbreviations (lowercase → full name)
    _LOCATION_ABBREVIATIONS = {
        'hyd', 'blr', 'bang', 'del', 'mum', 'chn', 'kol',
        'pune', 'ahmd', 'jpr', 'lko', 'noi', 'bombay',
        'calcutta', 'madras', 'nyc', 'sf', 'la', 'dc',
        'ldn', 'vizag', 'sec', 'ghy', 'nagpur', 'indore',
        'bhopal', 'cbe', 'tvm', 'ccj', 'cok', 'goa',
        'ggn', 'grg', 'vja', 'wgl',
    }

    # Known city names (lowercase) for direct matching
    _KNOWN_CITY_NAMES = {
        'hyderabad', 'bangalore', 'bengaluru', 'delhi', 'mumbai',
        'chennai', 'kolkata', 'pune', 'ahmedabad', 'jaipur',
        'lucknow', 'chandigarh', 'bhopal', 'indore', 'nagpur',
        'visakhapatnam', 'coimbatore', 'kochi', 'secunderabad',
        'noida', 'gurgaon', 'gurugram', 'faridabad', 'ghaziabad',
        'mysore', 'mysuru', 'vijayawada', 'warangal', 'tirupati',
        'guntur', 'london', 'paris', 'tokyo', 'singapore',
        'dubai', 'new york', 'san francisco', 'los angeles',
        'chicago', 'boston', 'seattle', 'austin', 'toronto',
        'sydney', 'melbourne', 'guwahati', 'patna', 'ranchi',
        'surat', 'vadodara', 'agra', 'varanasi',
    }

    # ─── PROXIMITY ANALYSIS ─────────────────────────────────────────
    # Danger words: when an entity appears near these, sensitivity
    # is automatically escalated (SAFE→SEMI, SEMI→HIGH).
    _DANGER_PROXIMITY_WORDS = {
        # Financial
        "password", "secret", "bank", "account", "credit",
        "debit", "transaction", "transfer", "payment", "salary",
        "loan", "emi", "upi", "ifsc", "swift",
        # Auth / Credential
        "login", "credential", "token", "otp", "pin", "verify",
        "authenticate", "2fa", "mfa",
        # Identity
        "ssn", "aadhaar", "passport", "pan", "license", "voter",
        # Medical / Legal
        "diagnosis", "prescribed", "treatment", "lawsuit",
        "arrest", "criminal", "court", "bail",
        # Location danger signals
        "hiding", "stalking", "following", "tracking", "locate",
        "address", "whereabouts", "fled", "escaped",
        # Secrecy intent
        "confidential", "classified", "private", "sensitive",
    }

    # ─── SECRET-SHARING INTENT DETECTION ────────────────────────────
    # Phrases that indicate the user is trying to share a secret.
    # Triggers maximum masking mode: ALL entities → MASK, SEMI→HIGH.
    _SECRET_INTENT_PHRASES = [
        r"\bdon'?t\s+tell\s+anyone",
        r"\bkeep\s+(?:it|this)\s+(?:a\s+)?secret",
        r"\bbetween\s+(?:you\s+and\s+me|us)",
        r"\boff\s+the\s+record",
        r"\bconfidential(?:ly)?",
        r"\bjust\s+between\s+us",
        r"\bdon'?t\s+share\s+(?:this|it)",
        r"\bnobody\s+(?:should|must|can)\s+know",
        r"\bprivate(?:ly)?\b",
        r"\bsecret(?:ly)?\b",
        r"\bin\s+confidence",
        r"\bplease\s+(?:don'?t|do\s+not)\s+(?:tell|share|reveal|disclose)",
    ]

    def decide(
        self, text: str, entities: List[ScoredEntity]
    ) -> Tuple[List[ScoredEntity], List[DecisionRecord], bool, List[str]]:
        if not entities:
            return [], [], False, []

        tokens_with_spans = self._tokenize_with_spans(text)
        entities_to_mask: List[ScoredEntity] = []
        decisions: List[DecisionRecord] = []
        blocked = False
        block_reasons: List[str] = []

        # Global ownership: infer from the FULL text so that first-person
        # indicators ("I", "my", etc.) aren't lost due to small context windows.
        global_ownership = self._infer_ownership(text.lower())

        # ─── SECRET-SHARING INTENT ──────────────────────────────────
        # If the user is signalling secrecy, escalate ALL entities.
        secret_intent = self._detect_secret_intent(text)
        if secret_intent:
            logger.info("🔐 Secret-sharing intent detected — maximum masking mode")

        for ent in entities:
            context = self._extract_context(text, tokens_with_spans, ent.start, ent.end)
            ownership = self._infer_ownership(context)
            # Fall back to global ownership when local context is ambiguous
            if ownership == "UNKNOWN" and global_ownership != "UNKNOWN":
                ownership = global_ownership
            privacy_type, sensitivity, reasons = self._map_to_privacy_type(
                ent, context, text
            )

            # ─── PROXIMITY ANALYSIS ─────────────────────────────────
            # Escalate sensitivity when entity is near danger words.
            proximity_hit = self._check_proximity(context)
            if proximity_hit:
                reasons.append(f"Proximity boost: near danger word(s)")
                if sensitivity == "SAFE":
                    sensitivity = "SEMI"
                elif sensitivity == "SEMI":
                    sensitivity = "HIGH"

            # ─── SECRET INTENT OVERRIDE ─────────────────────────────
            # If secret intent was detected, force everything to at least SEMI
            # and force ownership to USER (conservative).
            if secret_intent:
                reasons.append("Secret-sharing intent detected — escalated")
                if sensitivity == "SAFE":
                    sensitivity = "SEMI"
                if ownership == "UNKNOWN":
                    ownership = "USER"

            # Confidence adjustments based on ownership / source mix
            final_conf = self._adjust_confidence(ent, ownership, privacy_type)

            decision: DecisionAction
            decision_reasons = list(reasons)

            # --- Decision logic (final authority) --------------------
            if privacy_type in self.GLOBAL_BLOCK_TYPES and ownership == "USER":
                decision = "BLOCK"
                decision_reasons.append(
                    "High-risk secret (OTP/password/token) owned by user"
                )
                blocked = True
                if privacy_type not in block_reasons:
                    block_reasons.append(privacy_type)
            elif sensitivity == "HIGH":
                # By default: mask all HIGH sensitivity entities before AI
                decision = "MASK"
                decision_reasons.append("High sensitivity entity")
            elif sensitivity == "SEMI":
                # Context-dependent: mask when clearly personal, otherwise allow
                if ownership in ("USER", "THIRD_PARTY"):
                    decision = "MASK"
                    decision_reasons.append(
                        "Semi-sensitive entity with personal ownership"
                    )
                else:
                    decision = "ALLOW"
                    decision_reasons.append("Semi-sensitive but generic/unknown usage")
            else:  # SAFE
                decision = "ALLOW"
                decision_reasons.append("Classified as safe / non-sensitive")

            record = DecisionRecord(
                privacy_entity_type=privacy_type,
                confidence=min(max(final_conf, 0.0), 0.99),
                ownership=ownership,
                sensitivity=sensitivity,
                decision=decision,
                sources=list(sorted(ent.sources)) if hasattr(ent, "sources") else [],
                reasons=decision_reasons,
            )
            decisions.append(record)

            # Only pass entities that must be masked to the tokenizer
            if decision == "MASK":
                entities_to_mask.append(ent)

            # Emit structured, no-PII log for this entity
            logger.info(
                "entity_decision",
                extra={
                    "privacy_entity_type": record.privacy_entity_type,
                    "confidence": record.confidence,
                    "ownership": record.ownership,
                    "sensitivity": record.sensitivity,
                    "decision": record.decision,
                    "sources": record.sources,
                    "reasons": record.reasons,
                },
            )

        return entities_to_mask, decisions, blocked, block_reasons

    # ------------------------------------------------------------------ #
    # INTERNAL HELPERS
    # ------------------------------------------------------------------ #

    def _tokenize_with_spans(self, text: str) -> List[Tuple[str, int, int]]:
        """
        Very lightweight tokenizer that returns (token, start, end) spans.
        Used only for context-window extraction; does NOT leave process
        or call any external NLP APIs.
        """
        tokens: List[Tuple[str, int, int]] = []
        if not text:
            return tokens

        idx = 0
        for raw in text.split():
            start = text.find(raw, idx)
            if start == -1:
                continue
            end = start + len(raw)
            tokens.append((raw, start, end))
            idx = end
        return tokens

    def _extract_context(
        self,
        text: str,
        tokens_with_spans: List[Tuple[str, int, int]],
        start: int,
        end: int,
        window: int = 5,
    ) -> str:
        """
        Extract a ±N token window around an entity.
        """
        if not tokens_with_spans:
            return ""

        center_idx = 0
        for i, (_, s, e) in enumerate(tokens_with_spans):
            if s <= start < e or (start <= s < end):
                center_idx = i
                break

        lo = max(0, center_idx - window)
        hi = min(len(tokens_with_spans), center_idx + window + 1)
        ctx_tokens = [t for (t, _, _) in tokens_with_spans[lo:hi]]
        return " ".join(ctx_tokens)

    def _infer_ownership(self, context: str) -> Ownership:
        ctxt = context.lower()
        if any(hint in ctxt for hint in self._USER_OWNERSHIP_HINTS):
            return "USER"
        if any(hint in ctxt for hint in self._THIRD_PARTY_HINTS):
            return "THIRD_PARTY"
        if any(hint in ctxt for hint in self._GENERIC_HINTS):
            return "GENERIC"
        return "UNKNOWN"

    def _map_to_privacy_type(
        self, ent: ScoredEntity, context: str, original_text: str = ""
    ) -> Tuple[str, Sensitivity, List[str]]:
        """
        Map a scored entity (using internal canonical types) into the locked
        privacy taxonomy. Returns (privacy_type, sensitivity, reasons).
        """
        base_type = (ent.entity_type or "OTHER").upper()
        txt = getattr(ent, "text", "") or ""
        txt_lower = txt.lower()
        ctx_lower = context.lower()
        reasons: List[str] = []

        # 1) Phone-specific override: if context clearly indicates "phone/mobile",
        #    always treat long numbers as USER_PHONE, even if engines called it NUMBER.
        if (base_type in {"PHONE", "NUMBER"} or re.fullmatch(r"\d{6,}", txt.strip())) and any(
            kw in ctx_lower for kw in self._PHONE_CONTEXT_HINTS
        ):
            reasons.append("Numeric entity in phone/contact context")
            return "USER_PHONE", "HIGH", reasons

        # 2) Special case: technical numbers (Example 2 in spec)
        if base_type in {"PHONE", "NUMBER"} or re.fullmatch(r"\d{6,}", txt.strip()):
            if any(kw in ctx_lower for kw in self._TECH_NUMBER_KEYWORDS):
                reasons.append("Numeric entity in technical context (treated as TECH_NUMBER)")
                return "TECH_NUMBER", "SAFE", reasons

        # 3) Name-context override: ONLY if a name-context phrase
        #    IMMEDIATELY precedes the entity (not just anywhere in the context window).
        #    E.g. "my name is Delhi" -> reclassify as USER_NAME.
        #    But  "I am Ravi and I live in Delhi" -> Delhi stays LOCATION.
        if base_type in {"LOCATION", "ADDRESS"} and original_text:
            prefix = original_text[:ent.start].lower().rstrip()
            has_immediate_name_ctx = any(
                prefix.endswith(hint.rstrip())
                for hint in self._NAME_CONTEXT_HINTS
            )
            if has_immediate_name_ctx:
                reasons.append("LOCATION entity immediately after name-context -> USER_NAME")
                return "USER_NAME", "HIGH", reasons

        # 4) Location granularity
        if base_type in {"LOCATION", "ADDRESS"}:
            has_digit = any(ch.isdigit() for ch in txt)
            if has_digit or any(h in txt_lower for h in self._EXACT_LOCATION_HINTS):
                reasons.append("Exact address or street-level location")
                return "USER_LOCATION_EXACT", "HIGH", reasons
            
            # Check if entity is a known city name or abbreviation
            is_known_city = (
                txt_lower in self._KNOWN_CITY_NAMES
                or txt_lower in self._LOCATION_ABBREVIATIONS
                or any(h in ctx_lower for h in self._CITY_STATE_HINTS)
            )
            # Check for personal location context (love, like, from, etc.)
            has_personal_ctx = any(
                h in ctx_lower for h in self._PERSONAL_LOCATION_HINTS
            )
            
            if is_known_city or has_personal_ctx:
                reasons.append("City-level location or personal location context")
                return "USER_LOCATION_CITY", "SEMI", reasons
            
            reasons.append("Generic location")
            return "LOCATION_GENERIC", "SAFE", reasons

        # 5) Secrets and high-risk identifiers (OTP / passwords / tokens / secrets)
        if base_type in {"OTP", "PASSWORD", "API_KEY", "AUTH_TOKEN", "SECRET"}:
            reasons.append(f"{base_type} pattern (high-risk secret)")
            # Map 1:1 into privacy taxonomy; Decision logic will BLOCK when owned by user.
            return base_type, "HIGH", reasons

        # 6) Health information (medical / mental health)
        if base_type in {"HEALTH_INFO", "HEALTH"}:
            reasons.append("Health / medical information")
            return "HEALTH_INFO", "HIGH", reasons

        # 6.5) Suspicious Number (High Recall Safety Net)
        if base_type == "SUSPICIOUS_NUMBER":
            reasons.append("Unidentified long numeric string (safety net)")
            return "SUSPICIOUS_NUMBER", "HIGH", reasons

        # 7) Core identifiers
        if base_type == "EMAIL":
            reasons.append("Email address pattern")
            return "USER_EMAIL", "HIGH", reasons
        if base_type == "PHONE":
            reasons.append("Phone number pattern")
            return "USER_PHONE", "HIGH", reasons
        if base_type in {"AADHAAR", "PAN", "SSN", "PASSPORT"}:
            reasons.append("Government identifier pattern")
            return "USER_GOV_ID", "HIGH", reasons
        if base_type == "BANK_ACCOUNT":
            reasons.append("Bank account / IFSC pattern")
            return "BANK_ACCOUNT", "HIGH", reasons
        if base_type == "CREDIT_CARD":
            reasons.append("Credit card pattern")
            return "CREDIT_CARD", "HIGH", reasons
        if base_type == "EMPLOYEE_ID":
            reasons.append("Employee ID")
            return "EMPLOYEE_ID", "SEMI", reasons
        if base_type == "DOB":
            reasons.append("Date-of-birth like date")
            return "DOB_PARTIAL", "SEMI", reasons

        # 8) Names / organisations
        if base_type == "USER":
            reasons.append("Personal name (USER)")
            return "USER_NAME", "HIGH", reasons
        if base_type in {"ORG", "COLLEGE"}:
            reasons.append("Organisation / college name")
            return "PUBLIC_PERSON", "SAFE", reasons

        # 9) IPs, URLs and misc IDs → treat as technical / generic
        if base_type in {"IP_ADDRESS", "URL", "ROLL_NUMBER"}:
            reasons.append(f"{base_type} treated as technical identifier")
            return "TECH_NUMBER", "SAFE", reasons

        # 10) Fallbacks
        if base_type in {
            "DATE",
            "TIME",
            "MONEY",
            "PERCENT",
            "QUANTITY",
            "NUMBER",
            "OTHER",
        }:
            reasons.append(f"{base_type} treated as generic non-PII")
            if base_type == "DATE":
                return "DATE_GENERIC", "SAFE", reasons
            return "LOCATION_GENERIC", "SAFE", reasons

        # Unknown types → safe generic
        reasons.append(f"Unmapped type {base_type} → LOCATION_GENERIC/SAFE")
        return "LOCATION_GENERIC", "SAFE", reasons

    def _adjust_confidence(
        self, ent: ScoredEntity, ownership: Ownership, privacy_type: str
    ) -> float:
        """
        Adjust confidence using simple heuristics:
            - boost for clear ownership
            - slight boost for HIGH sensitivity categories
        """
        conf = float(getattr(ent, "confidence", 0.7) or 0.7)

        if ownership == "USER":
            conf *= 1.05
        elif ownership == "UNKNOWN":
            conf *= 0.97

        if privacy_type in self.HIGH_SENSITIVE_TYPES:
            conf *= 1.03

        return conf

    def _check_proximity(self, context: str) -> bool:
        """
        Proximity Analysis: check whether the context window around
        an entity contains any danger words that should boost sensitivity.
        Returns True if at least one danger word is found.
        """
        ctx_lower = context.lower()
        return any(w in ctx_lower for w in self._DANGER_PROXIMITY_WORDS)

    def _detect_secret_intent(self, text: str) -> bool:
        """
        Detect whether the user's message signals secret-sharing intent.
        E.g. "don't tell anyone but...", "this is confidential", etc.
        Returns True if intent is detected.
        """
        text_lower = text.lower()
        for pattern in self._SECRET_INTENT_PHRASES:
            if re.search(pattern, text_lower):
                return True
        return False


_decision_engine: DecisionEngine | None = None


def get_decision_engine() -> DecisionEngine:
    global _decision_engine
    if _decision_engine is None:
        _decision_engine = DecisionEngine()
    return _decision_engine

