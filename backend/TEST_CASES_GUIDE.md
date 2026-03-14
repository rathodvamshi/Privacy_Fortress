# PRO-LEVEL TEST CASES - Quick Reference Guide

## Overview
**75+ Comprehensive Test Cases** covering all aspects of Privacy Fortress

## How to Run

### Run Complete Test Suite
```bash
cd backend
python PRO_TEST_CASES.py
```

### Expected Output
- Colorized output with detailed results
- For each test:
  - ✅ Input text
  - ✅ Detection results (entities detected, masked, allowed)
  - ✅ Masked output
  - ✅ Token mappings
  - ✅ Decision audit trail
  - ✅ Reversibility check
  - ✅ Performance metrics

---

## Test Sections

### SECTION 1: Basic PII Detection (Tests 1-20)
**All Entity Types**

| Test | Entity Type | Example |
|------|-------------|---------|
| 1-3 | Names | "My name is Ramesh Kumar" |
| 4-6 | Emails | "Email me at john@example.com" |
| 7-10 | Phone Numbers | "Call me at 9876543210" |
| 11-13 | Government IDs | "Aadhaar: 1234 5678 9012" |
| 14-15 | Financial | "Card: 4532-1234-5678-9010" |
| 16-18 | Locations | "Address: 123 MG Road" |
| 19-20 | Dates | "Born on 15/08/1990" |

**What to Check:**
- ✅ All entity types detected correctly
- ✅ Proper entity labeling (USER, EMAIL, PHONE, etc.)
- ✅ High confidence for structured data (regex patterns)

---

### SECTION 2: Context-Aware Decisions (Tests 21-34)
**ALLOW vs MASK Logic**

| Test | Scenario | Expected Decision |
|------|----------|-------------------|
| 21 | "I visited Mumbai" | ALLOW (generic location) |
| 22 | "My address is Mumbai" | MASK (personal location) |
| 24-25 | "Model with 9876543210 parameters" | ALLOW (technical number) |
| 26-27 | "Call me at 9876543210" | MASK (phone number) |
| 31-32 | "I work at Microsoft" | ALLOW (organization) |
| 33-34 | "Born on 15/08/1990" | MASK (DOB) |

**What to Check:**
- ✅ Generic entities are ALLOWED
- ✅ User PII is MASKED
- ✅ Context determines decision (not just entity type)
- ✅ Ownership classification (USER/THIRD_PARTY/GENERIC)

---

### SECTION 3: Ambiguity Resolution (Tests 35-42)
**Complex & Tricky Cases**

| Test | Ambiguity | Challenge |
|------|-----------|-----------|
| 35 | Phone vs Technical Number | Same number, different contexts |
| 36 | City vs Person | "Paris in Paris" |
| 39 | Nested Context | "delhi.office@company.com + Delhi project" |
| 40 | Mixed Numbers | "Call 9876543210 for model v9876543210" |
| 42 | Location Granularity | "Maharashtra, specifically Mumbai, near Bandra" |

**What to Check:**
- ✅ Correct disambiguation based on context
- ✅ No over-masking of generic content
- ✅ Proper handling of edge cases

---

### SECTION 4: High-Risk Blocking (Tests 43-46)
**OTP, Passwords, API Keys**

| Test | Secret Type | Input |
|------|-------------|-------|
| 43 | OTP | "Your OTP is 123456" |
| 44 | Password | "My password is SuperSecret123!" |
| 45 | API Key | "API key: sk_test_1234..." |
| 46 | Auth Token | "Bearer eyJhbGci..." |

**What to Check:**
- ✅ Request BLOCKED (403) when high-risk secrets detected
- ✅ Block reasons in response
- ⚠️ Note: Depends on pattern detection (might not block if patterns aren't implemented)

---

### SECTION 5: Edge Cases (Tests 47-62)
**Error Handling & Unusual Input**

| Category | Tests | Examples |
|----------|-------|----------|
| Empty/Minimal | 47-49 | "", "Hello", "     " |
| Special Chars | 50-52 | Unicode, Emojis, Special symbols |
| Long Input | 53 | 10,000+ characters |
| Dense PII | 54 | Multiple entities in one sentence |
| Overlapping | 55 | Same person with email + phone |
| Case Variations | 56-57 | Mixed case, ALL CAPS |
| Format Variations | 58-59 | Different phone/email formats |
| Boundaries | 60-62 | Entity at start/end, only entity |

**What to Check:**
- ✅ No crashes on edge cases
- ✅ Graceful handling of empty/invalid input
- ✅ Validation warnings for issues
- ✅ Consistent detection across format variations

---

### SECTION 6: Real-World Scenarios (Tests 63-70)
**Actual Conversation Examples**

| Test | Scenario | Example |
|------|----------|---------|
| 63 | Customer Support | Account help query with contact details |
| 64 | Job Application | Resume with full personal details |
| 65 | Medical Query | Patient info with DOB + health data |
| 66 | Banking Request | Transfer with account details |
| 67 | Hotel Booking | Reservation with guest details |
| 68 | Travel Itinerary | Flight + pickup with contact |
| 69 | Technical Discussion | Tech specs + team contact |
| 70 | Mixed Context | Personal + generic "Mumbai" |

**What to Check:**
- ✅ Handles complex multi-entity conversations
- ✅ Correct masking of multiple PII types
- ✅ Maintains readability after masking
- ✅ Perfect reversibility

---

### SECTION 7: Performance (Tests 71-75)
**Speed & Stress Testing**

| Test | Input Size | Expected Time |
|------|------------|---------------|
| 71 | Small (< 50 chars) | < 50ms |
| 72 | Medium (< 500 chars) | < 100ms |
| 73 | Large (< 2000 chars) | < 300ms |
| 74 | Many Entities (20+ emails) | < 500ms |
| 75 | Dense PII (10+ entities) | < 200ms |

**What to Check:**
- ✅ All tests < 1000ms (performance target)
- ✅ Average time < 100ms
- ✅ Linear scaling with input size
- ⚠️ Warnings if > 500ms

---

### SECTION 8: Consistency (Tests 76-77)
**Session Isolation & Token Consistency**

| Test | Check | Expected |
|------|-------|----------|
| 76 | Same input, different sessions | Consistent token generation |
| 77 | Different sessions | No token leakage |

**What to Check:**
- ✅ Same input → same masked output pattern
- ✅ Sessions don't share tokens
- ✅ Token counters isolated per session

---

## Success Criteria

### ✅ Production Ready If:
1. **All tests pass** (75/75)
2. **Reversibility: 100%** (all unmask correctly)
3. **Performance: < 1000ms** for all tests
4. **No crashes** on edge cases
5. **Context-aware decisions work** (ALLOW vs MASK)

### ⚠️ Needs Attention If:
1. Failed tests: 1-10 (check specific failures)
2. Reversibility: < 95%
3. Performance: > 1000ms for any test
4. Validation errors on normal input

### ❌ Critical Issues If:
1. Failed tests: > 10
2. Crashes on basic input
3. Reversibility: < 90%
4. Performance: > 2000ms average

---

## Common Test Failures & Fixes

### Failure: "Over-masking generic content"
**Symptom**: Mumbai, Microsoft, etc. are being masked
**Fix**: Decision Engine needs tuning - check ownership classification

### Failure: "Under-detecting PII"
**Symptom**: Emails, phones not detected
**Fix**: Check regex patterns, NER model loading

### Failure: "Reversibility failures"
**Symptom**: Unmask doesn't restore original
**Fix**: Check tokenizer boundary detection, special character handling

### Failure: "High-risk secrets not blocked"
**Symptom**: OTP, passwords allowed through
**Fix**: Add/improve regex patterns for secrets, check BLOCK logic

### Failure: "Performance issues"
**Symptom**: Tests > 1000ms
**Fix**: Check NER model initialization, optimize confidence scoring

---

## Quick Test Commands

### Run Specific Section
```python
# Edit PRO_TEST_CASES.py, comment out sections you don't want
# Example: only run Section 1
def main():
    all_results = []
    all_results.extend(section_1_basic_pii())  # Only this one
    # all_results.extend(section_2_context_aware())  # Commented out
    ...
```

### Run Single Test
```python
from PRO_TEST_CASES import run_test

# Test specific input
result = run_test(
    999,
    "My Custom Test",
    "My email is test@example.com"
)
```

### Check Specific Feature
```python
from app.middleware.pipeline import get_masking_pipeline

pipeline = get_masking_pipeline("test_session")
result = pipeline.mask("Your test input here")

print(f"Detected: {result.entities_detected}")
print(f"Masked: {result.entities_masked}")
print(f"Allowed: {result.entities_allowed}")
print(f"Decisions: {result.decisions}")
```

---

## Interpreting Results

### Color Coding
- 🟢 **GREEN** = Success, ALLOW decision, production ready
- 🟡 **YELLOW** = Warning, MASK decision, needs review
- 🔴 **RED** = Failure, BLOCK decision, critical issue
- 🔵 **BLUE** = Info, test headers
- 🟣 **PURPLE** = Section headers

### Decision Audit Trail
Each test shows detailed decision logs:
```
1. USER_NAME (HIGH): MASK
   Confidence: 0.92, Ownership: USER
   Sources: spacy, regex
   Reasons: Personal name in context, High confidence detection
```

**Interpretation:**
- **Entity Type**: Privacy taxonomy classification
- **Sensitivity**: HIGH/SEMI/SAFE
- **Decision**: ALLOW/MASK/BLOCK
- **Confidence**: Detection confidence (0.0-1.0)
- **Ownership**: USER/THIRD_PARTY/GENERIC/UNKNOWN
- **Sources**: Which engines detected it
- **Reasons**: Why this decision was made

---

## Example Output

```
================================================================================
  PRIVACY FORTRESS - PRO-LEVEL TEST SUITE
  Comprehensive Testing - All Entity Types & Edge Cases
================================================================================

================================================================================
  SECTION 1: Basic PII Detection - All Entity Types
================================================================================

[TEST 1] Simple Name
--------------------------------------------------------------------------------
INPUT:
  My name is Ramesh Kumar

✅ SUCCESS

RESULTS:
  📊 Entities Detected: 1
  ✅ Allowed: 0
  🎭 Masked: 1
  🛑 Blocked: 0
  ⏱️  Processing Time: 45.2ms

MASKED OUTPUT:
  My name is [USER_NAME_1]

TOKENS GENERATED:
  USER_NAME_1 ← 'Ramesh Kumar' (USER)

DECISIONS (Audit Trail):
  1. USER_NAME (HIGH): MASK
     Confidence: 0.92, Ownership: USER
     Sources: spacy
     Reasons: Personal name context, High confidence detection

REVERSIBILITY TEST:
  ✅ PASSED - Perfect unmask
```

---

## Tips for Testing

1. **Run full suite first** to get baseline
2. **Check summary statistics** for overview
3. **Review failures individually** for debugging
4. **Test with your own data** using custom tests
5. **Monitor performance** across different input sizes
6. **Verify decision logic** matches expectations
7. **Test session isolation** for multi-user scenarios

---

## Next Steps After Testing

### If All Pass ✅
1. Deploy to staging
2. Run integration tests
3. Performance benchmarking
4. Security audit
5. Production deployment

### If Some Fail ⚠️
1. Identify failure patterns
2. Fix specific issues
3. Re-run failed tests
4. Validate fixes
5. Run full suite again

### If Many Fail ❌
1. Check basic setup (models, dependencies)
2. Review recent changes
3. Debug systematically
4. Consider rollback
5. Full regression testing

---

**Last Updated**: 2026-02-11
**Total Tests**: 77
**Coverage**: All entity types, edge cases, real-world scenarios
**Performance Target**: < 1000ms per test
**Success Criteria**: 100% pass rate, 100% reversibility
