#!/usr/bin/env python3
"""
Ultra-simple currency test - using only convenience functions
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath('.'))

print("Starting currency test...")
print("Importing modules...")

# Just import, don't initialize
from litellm.litellm_core_utils import currency

print("Import successful!")
print("\n" + "="*60)
print("Testing convenience functions (no initialization needed)")
print("="*60)

# Test convert_currency function
print("\n[TEST 1] convert_currency(100, 'USD', 'CNY')...")
try:
    result = currency.convert_currency(100, "USD", "CNY")
    print(f"✅ Result: ${100} USD = ¥{result:.2f} CNY")
except Exception as e:
    print(f"❌ Failed: {e}")
    import traceback
    traceback.print_exc()

# Test get_exchange_rate function
print("\n[TEST 2] get_exchange_rate('USD', 'EUR')...")
try:
    rate = currency.get_exchange_rate("USD", "EUR")
    print(f"✅ Result: 1 USD = {rate} EUR")
except Exception as e:
    print(f"❌ Failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("Test completed!")
print("="*60)
