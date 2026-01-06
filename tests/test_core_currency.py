#!/usr/bin/env python3
"""
Simple Core Currency Test - Only tests currency.py module
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

print("="*70)
print("CORE CURRENCY MODULE TEST")
print("="*70)

test_results = []

# Test 1: Import
print("\n[1] Testing imports...")
try:
    from litellm.litellm_core_utils.currency import (
        convert_currency,
        get_exchange_rate,
        reload_exchange_rates,
        CurrencyExchangeRateManager
    )
    print("✅ All imports successful")
    test_results.append(("Import", True))
except Exception as e:
    print(f"❌ Import failed: {e}")
    test_results.append(("Import", False))
    sys.exit(1)

# Test 2: Get exchange rate
print("\n[2] Testing get_exchange_rate...")
try:
    rate = get_exchange_rate("USD", "CNY")
    print(f"✅ 1 USD = {rate} CNY")
    test_results.append(("Get Exchange Rate", True))
except Exception as e:
    print(f"❌ Get rate failed: {e}")
    test_results.append(("Get Exchange Rate", False))

# Test 3: Convert currency
print("\n[3] Testing convert_currency...")
try:
    result = convert_currency(100, "USD", "CNY")
    print(f"✅ $100 USD = ¥{result:.2f} CNY")
    test_results.append(("Convert Currency", True))
except Exception as e:
    print(f"❌ Conversion failed: {e}")
    test_results.append(("Convert Currency", False))

# Test 4: Convert to EUR
print("\n[4] Testing EUR conversion...")
try:
    result = convert_currency(100, "USD", "EUR")
    print(f"✅ $100 USD = €{result:.2f} EUR")
    test_results.append(("EUR Conversion", True))
except Exception as e:
    print(f"❌ EUR conversion failed: {e}")
    test_results.append(("EUR Conversion", False))

# Test 5: Convert to JPY
print("\n[5] Testing JPY conversion...")
try:
    result = convert_currency(100, "USD", "JPY")
    print(f"✅ $100 USD = ¥{result:.2f} JPY")
    test_results.append(("JPY Conversion", True))
except Exception as e:
    print(f"❌ JPY conversion failed: {e}")
    test_results.append(("JPY Conversion", False))

# Test 6: Same currency
print("\n[6] Testing same currency...")
try:
    result = convert_currency(100, "USD", "USD")
    assert result == 100, f"Expected 100, got {result}"
    print(f"✅ $100 USD = ${result} USD")
    test_results.append(("Same Currency", True))
except Exception as e:
    print(f"❌ Same currency failed: {e}")
    test_results.append(("Same Currency", False))

# Test 7: Conversion symmetry
print("\n[7] Testing conversion symmetry...")
try:
    original = 100
    forward = convert_currency(original, "USD", "CNY")
    backward = convert_currency(forward, "CNY", "USD")
    diff = abs(backward - original)
    assert diff < 0.01, f"Too much difference: {diff}"
    print(f"✅ ${original} → ¥{forward:.2f} → ${backward:.2f} (diff: ${diff:.4f})")
    test_results.append(("Conversion Symmetry", True))
except Exception as e:
    print(f"❌ Symmetry test failed: {e}")
    test_results.append(("Conversion Symmetry", False))

# Test 8: Invalid currency
print("\n[8] Testing invalid currency handling...")
try:
    get_exchange_rate("USD", "INVALID")
    print(f"❌ Should have raised ValueError")
    test_results.append(("Invalid Currency", False))
except ValueError:
    print(f"✅ Correctly raised ValueError for invalid currency")
    test_results.append(("Invalid Currency", True))
except Exception as e:
    print(f"❌ Wrong exception: {e}")
    test_results.append(("Invalid Currency", False))

# Summary
print("\n" + "="*70)
print("TEST SUMMARY")
print("="*70)

passed = sum(1 for _, result in test_results if result)
total = len(test_results)

for name, result in test_results:
    status = "✅ PASS" if result else "❌ FAIL"
    print(f"{status}: {name}")

print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.1f}%)")

if passed == total:
    print("\n🎉 ALL TESTS PASSED!")
    sys.exit(0)
else:
    print(f"\n⚠️  {total - passed} test(s) failed")
    sys.exit(1)
