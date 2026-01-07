#!/usr/bin/env python3
"""
Quick Multi-Currency Test - No external dependencies
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

print("="*70)
print("QUICK MULTI-CURRENCY TEST")
print("="*70)

# Test 1: Import
print("\n[1] Testing imports...")
try:
    from litellm.litellm_core_utils.currency import (
        convert_currency,
        get_exchange_rate
    )
    from litellm.proxy.currency_utils.currency_helper import (
        get_entity_currency,
        convert_to_usd,
        convert_from_usd
    )
    print("✅ All imports successful")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

# Test 2: Basic conversion
print("\n[2] Testing basic currency conversion...")
try:
    result = convert_currency(100, "USD", "CNY")
    print(f"✅ $100 USD = ¥{result:.2f} CNY")
except Exception as e:
    print(f"❌ Conversion failed: {e}")
    sys.exit(1)

# Test 3: Get exchange rate
print("\n[3] Testing get_exchange_rate...")
try:
    rate = get_exchange_rate("USD", "EUR")
    print(f"✅ 1 USD = {rate} EUR")
except Exception as e:
    print(f"❌ Get rate failed: {e}")
    sys.exit(1)

# Test 4: Entity currency resolution
print("\n[4] Testing entity currency resolution...")
try:
    # Priority: token > team > user > USD
    currency = get_entity_currency("CNY", "EUR", "GBP")
    assert currency == "CNY", f"Expected CNY, got {currency}"
    print(f"✅ Priority works: token currency (CNY) selected")

    currency = get_entity_currency(None, "EUR", "GBP")
    assert currency == "EUR", f"Expected EUR, got {currency}"
    print(f"✅ Fallback works: team currency (EUR) selected")

    currency = get_entity_currency(None, None, None)
    assert currency == "USD", f"Expected USD, got {currency}"
    print(f"✅ Default works: USD selected")
except Exception as e:
    print(f"❌ Entity currency failed: {e}")
    sys.exit(1)

# Test 5: Convert to/from USD
print("\n[5] Testing USD conversions...")
try:
    amount_cny = 720
    amount_usd = convert_to_usd(amount_cny, "CNY")
    print(f"✅ ¥{amount_cny} CNY = ${amount_usd:.2f} USD")

    amount_usd = 100
    amount_eur = convert_from_usd(amount_usd, "EUR")
    print(f"✅ ${amount_usd} USD = €{amount_eur:.2f} EUR")
except Exception as e:
    print(f"❌ USD conversion failed: {e}")
    sys.exit(1)

# Test 6: Conversion symmetry
print("\n[6] Testing conversion symmetry...")
try:
    original = 100
    forward = convert_currency(original, "USD", "JPY")
    backward = convert_currency(forward, "JPY", "USD")
    diff = abs(backward - original)
    assert diff < 0.01, f"Too much difference: {diff}"
    print(f"✅ ${original} → ¥{forward:.2f} → ${backward:.2f} (diff: ${diff:.4f})")
except Exception as e:
    print(f"❌ Symmetry test failed: {e}")
    sys.exit(1)

print("\n" + "="*70)
print("🎉 ALL TESTS PASSED!")
print("="*70)
