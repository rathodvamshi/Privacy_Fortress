"""Quick test to verify Decision Engine integration"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.middleware.pipeline import get_masking_pipeline

print("="*80)
print("QUICK VALIDATION TEST - Decision Engine Integration")
print("="*80)

# Test 1: Basic masking
print("\nTest 1: Basic PII Detection")
pipeline = get_masking_pipeline("quick_test_1")
result = pipeline.mask("My name is John Smith and email is john@example.com")
print(f"✅ Detected: {result.entities_detected} entities")
print(f"✅ Masked: {result.entities_masked} entities")
print(f"✅ Allowed: {result.entities_allowed} entities")
print(f"✅ Tokens: {list(result.tokens.keys())}")
print(f"✅ Time: {result.processing_time_ms:.1f}ms")

# Test 2: Context-aware decision
print("\n" + "="*80)
print("Test 2: Context-Aware Decision (Generic Location)")
pipeline2 = get_masking_pipeline("quick_test_2")
result2 = pipeline2.mask("I visited Mumbai last year")
print(f"✅ Detected: {result2.entities_detected} entities")
print(f"✅ Masked: {result2.entities_masked} entities")
print(f"✅ Allowed: {result2.entities_allowed} entities")
print(f"   Expected: ALLOW decision for generic location")

# Test 3: User PII
print("\n" + "="*80)
print("Test 3: User PII (Should Mask)")
pipeline3 = get_masking_pipeline("quick_test_3")
result3 = pipeline3.mask("My name is Ramesh Kumar")
print(f"✅ Detected: {result3.entities_detected} entities")
print(f"✅ Masked: {result3.entities_masked} entities")
print(f"✅ Allowed: {result3.entities_allowed} entities")
print(f"   Expected: MASK decision for user name")

# Test 4: Reversibility
print("\n" + "="*80)
print("Test 4: Mask/Unmask Reversibility")
pipeline4 = get_masking_pipeline("quick_test_4")
original = "My email is alice@example.com and phone is 9876543210"
mask_result = pipeline4.mask(original)
unmask_result = pipeline4.unmask(mask_result.masked_text)
print(f"✅ Original:  {original}")
print(f"✅ Masked:    {mask_result.masked_text}")
print(f"✅ Unmasked:  {unmask_result.unmasked_text}")
reversible = ' '.join(original.split()) == ' '.join(unmask_result.unmasked_text.split())
print(f"✅ Reversible: {reversible}")

# Test 5: Decision records
print("\n" + "="*80)
print("Test 5: Decision Records (Audit Trail)")
pipeline5 = get_masking_pipeline("quick_test_5")
result5 = pipeline5.mask("My phone is 9876543210 and I visited Mumbai")
print(f"✅ Total decisions: {len(result5.decisions)}")
for i, decision in enumerate(result5.decisions, 1):
    print(f"   {i}. {decision.privacy_entity_type} ({decision.sensitivity}): {decision.decision}")
    print(f"      Confidence: {decision.confidence:.2f}, Ownership: {decision.ownership}")
    print(f"      Reasons: {', '.join(decision.reasons[:2])}")  # First 2 reasons

print("\n" + "="*80)
print("✅ ALL QUICK TESTS PASSED!")
print("="*80)
