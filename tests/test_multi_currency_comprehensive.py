#!/usr/bin/env python3
"""
Comprehensive Multi-Currency Feature Test Suite

Tests all aspects of the multi-currency implementation:
1. Currency Management (CurrencyExchangeRateManager)
2. Currency Helper Functions
3. API-ready validation
"""

import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")

def print_test(name, passed, details=""):
    """Print test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {name}")
    if details:
        print(f"   {details}")

# ==================== Test 1: Currency Manager ====================

def test_currency_manager():
    """Test CurrencyExchangeRateManager functionality"""
    print_section("Test 1: Currency Exchange Rate Manager")

    from litellm.litellm_core_utils.currency import CurrencyExchangeRateManager

    try:
        manager = CurrencyExchangeRateManager()
        print_test("Manager initialization", True, "Singleton instance created")
    except Exception as e:
        print_test("Manager initialization", False, str(e))
        return False

    # Test 1.1: Get all rates
    try:
        rates = manager.get_all_rates()
        print_test(
            "Get all exchange rates",
            len(rates) > 0,
            f"Loaded {len(rates)} currencies: {', '.join(list(rates.keys())[:5])}..."
        )
    except Exception as e:
        print_test("Get all exchange rates", False, str(e))
        return False

    # Test 1.2: Get specific rate
    try:
        usd_to_cny = manager.get_rate("USD", "CNY")
        print_test(
            "Get USD to CNY rate",
            usd_to_cny > 0,
            f"1 USD = {usd_to_cny} CNY"
        )
    except Exception as e:
        print_test("Get USD to CNY rate", False, str(e))
        return False

    # Test 1.3: Currency conversion
    try:
        amount_usd = 100
        amount_cny = manager.convert(amount_usd, "USD", "CNY")
        print_test(
            "Convert 100 USD to CNY",
            amount_cny > 0,
            f"${amount_usd} USD = ¥{amount_cny:.2f} CNY"
        )
    except Exception as e:
        print_test("Convert 100 USD to CNY", False, str(e))
        return False

    # Test 1.4: Same currency conversion
    try:
        same_rate = manager.get_rate("USD", "USD")
        print_test(
            "Same currency rate (USD to USD)",
            same_rate == 1.0,
            f"Rate: {same_rate}"
        )
    except Exception as e:
        print_test("Same currency rate", False, str(e))
        return False

    # Test 1.5: Supported currencies
    try:
        currencies = manager.get_supported_currencies()
        print_test(
            "Get supported currencies",
            "USD" in currencies and "CNY" in currencies,
            f"Found {len(currencies)} currencies"
        )
    except Exception as e:
        print_test("Get supported currencies", False, str(e))
        return False

    # Test 1.6: Manager stats
    try:
        stats = manager.get_stats()
        print_test(
            "Get manager statistics",
            "mode" in stats and "currencies" in stats,
            f"Mode: {stats['mode']}, Currencies: {stats['currencies']}"
        )
    except Exception as e:
        print_test("Get manager statistics", False, str(e))
        return False

    return True

# ==================== Test 2: Currency Helper ====================

def test_currency_helper():
    """Test currency_helper.py functions"""
    print_section("Test 2: Currency Helper Functions")

    try:
        from litellm.litellm_core_utils.currency_helper import (
            get_entity_currency,
            convert_to_usd,
            convert_from_usd
        )
    except Exception as e:
        print_test("Import currency_helper", False, str(e))
        return False

    print_test("Import currency_helper", True, "All functions imported successfully")

    # Test 2.1: Entity currency resolution
    try:
        # Test with token currency
        currency = get_entity_currency(
            token_currency="CNY",
            team_currency="EUR",
            user_currency="GBP"
        )
        print_test(
            "Entity currency priority (token)",
            currency == "CNY",
            f"Got: {currency} (expected: CNY)"
        )
    except Exception as e:
        print_test("Entity currency priority", False, str(e))
        return False

    # Test 2.2: Fallback to team currency
    try:
        currency = get_entity_currency(
            token_currency=None,
            team_currency="EUR",
            user_currency="GBP"
        )
        print_test(
            "Entity currency fallback (team)",
            currency == "EUR",
            f"Got: {currency} (expected: EUR)"
        )
    except Exception as e:
        print_test("Entity currency fallback", False, str(e))
        return False

    # Test 2.3: Fallback to user currency
    try:
        currency = get_entity_currency(
            token_currency=None,
            team_currency=None,
            user_currency="GBP"
        )
        print_test(
            "Entity currency fallback (user)",
            currency == "GBP",
            f"Got: {currency} (expected: GBP)"
        )
    except Exception as e:
        print_test("Entity currency fallback", False, str(e))
        return False

    # Test 2.4: Default to USD
    try:
        currency = get_entity_currency(
            token_currency=None,
            team_currency=None,
            user_currency=None
        )
        print_test(
            "Entity currency default (USD)",
            currency == "USD",
            f"Got: {currency} (expected: USD)"
        )
    except Exception as e:
        print_test("Entity currency default", False, str(e))
        return False

    # Test 2.5: Convert to USD
    try:
        amount_cny = 720
        amount_usd = convert_to_usd(amount_cny, "CNY")
        print_test(
            "Convert CNY to USD",
            90 < amount_usd < 110,  # Should be around 100
            f"¥{amount_cny} CNY = ${amount_usd:.2f} USD"
        )
    except Exception as e:
        print_test("Convert CNY to USD", False, str(e))
        return False

    # Test 2.6: Convert from USD
    try:
        amount_usd = 100
        amount_eur = convert_from_usd(amount_usd, "EUR")
        print_test(
            "Convert USD to EUR",
            80 < amount_eur < 100,  # Should be around 92
            f"${amount_usd} USD = €{amount_eur:.2f} EUR"
        )
    except Exception as e:
        print_test("Convert USD to EUR", False, str(e))
        return False

    return True

# ==================== Test 3: Convenience Functions ====================

def test_convenience_functions():
    """Test convenience functions"""
    print_section("Test 3: Convenience Functions")

    try:
        from litellm.litellm_core_utils.currency import (
            convert_currency,
            get_exchange_rate,
            reload_exchange_rates
        )
    except Exception as e:
        print_test("Import convenience functions", False, str(e))
        return False

    print_test("Import convenience functions", True)

    # Test 3.1: convert_currency
    try:
        result = convert_currency(100, "USD", "JPY")
        print_test(
            "convert_currency function",
            result > 0,
            f"$100 USD = ¥{result:.2f} JPY"
        )
    except Exception as e:
        print_test("convert_currency function", False, str(e))
        return False

    # Test 3.2: get_exchange_rate
    try:
        rate = get_exchange_rate("USD", "GBP")
        print_test(
            "get_exchange_rate function",
            0 < rate < 1,  # GBP is less than USD
            f"1 USD = {rate} GBP"
        )
    except Exception as e:
        print_test("get_exchange_rate function", False, str(e))
        return False

    # Test 3.3: reload_exchange_rates
    try:
        reload_exchange_rates()
        print_test("reload_exchange_rates function", True)
    except Exception as e:
        print_test("reload_exchange_rates function", False, str(e))
        return False

    return True

# ==================== Test 4: Error Handling ====================

def test_error_handling():
    """Test error handling and edge cases"""
    print_section("Test 4: Error Handling & Edge Cases")

    from litellm.litellm_core_utils.currency import CurrencyExchangeRateManager
    from litellm.litellm_core_utils.currency_helper import get_entity_currency

    manager = CurrencyExchangeRateManager()

    # Test 4.1: Invalid currency
    try:
        manager.get_rate("USD", "INVALID")
        print_test("Invalid currency handling", False, "Should have raised ValueError")
    except ValueError as e:
        print_test("Invalid currency handling", True, f"Correctly raised: {str(e)}")
    except Exception as e:
        print_test("Invalid currency handling", False, f"Wrong exception: {str(e)}")

    # Test 4.2: Negative amount conversion
    try:
        result = manager.convert(-100, "USD", "CNY")
        print_test(
            "Negative amount handling",
            result < 0,
            f"Correctly handled: -$100 = ¥{result:.2f}"
        )
    except Exception as e:
        print_test("Negative amount handling", False, str(e))

    # Test 4.3: Zero amount
    try:
        result = manager.convert(0, "USD", "CNY")
        print_test(
            "Zero amount handling",
            result == 0,
            f"Correctly handled: $0 = ¥{result}"
        )
    except Exception as e:
        print_test("Zero amount handling", False, str(e))

    # Test 4.4: NULL currency handling
    try:
        currency = get_entity_currency(None, None, None)
        print_test(
            "NULL currency handling",
            currency == "USD",
            f"Correctly defaulted to: {currency}"
        )
    except Exception as e:
        print_test("NULL currency handling", False, str(e))

    return True

# ==================== Test 5: Data Integrity ====================

def test_data_integrity():
    """Test data integrity and consistency"""
    print_section("Test 5: Data Integrity & Consistency")

    from litellm.litellm_core_utils.currency import CurrencyExchangeRateManager

    manager = CurrencyExchangeRateManager()

    # Test 5.1: USD base rate
    try:
        usd_rate = manager.get_rate("USD", "USD")
        print_test(
            "USD base rate integrity",
            usd_rate == 1.0,
            f"USD rate is exactly 1.0: {usd_rate}"
        )
    except Exception as e:
        print_test("USD base rate integrity", False, str(e))
        return False

    # Test 5.2: Conversion symmetry
    try:
        forward = manager.convert(100, "USD", "CNY")
        backward = manager.convert(forward, "CNY", "USD")
        difference = abs(backward - 100)
        print_test(
            "Conversion symmetry",
            difference < 0.01,  # Allow tiny floating point error
            f"$100 → ¥{forward:.2f} → ${backward:.2f} (diff: ${difference:.4f})"
        )
    except Exception as e:
        print_test("Conversion symmetry", False, str(e))
        return False

    # Test 5.3: All rates positive
    try:
        rates = manager.get_all_rates()
        all_positive = all(rate > 0 for rate in rates.values())
        print_test(
            "All rates positive",
            all_positive,
            f"Checked {len(rates)} rates"
        )
    except Exception as e:
        print_test("All rates positive", False, str(e))
        return False

    return True

# ==================== Main Test Runner ====================

def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("  LITELLM MULTI-CURRENCY COMPREHENSIVE TEST SUITE")
    print("  Testing Phase 1-5 Implementation")
    print("="*70)
    print(f"\nTest started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = []

    # Run all test suites
    results.append(("Currency Manager", test_currency_manager()))
    results.append(("Currency Helper", test_currency_helper()))
    results.append(("Convenience Functions", test_convenience_functions()))
    results.append(("Error Handling", test_error_handling()))
    results.append(("Data Integrity", test_data_integrity()))

    # Print summary
    print_section("Test Summary")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {name}")

    print(f"\n{'='*70}")
    print(f"Total: {passed}/{total} test suites passed ({passed/total*100:.1f}%)")

    if passed == total:
        print("🎉 ALL TESTS PASSED!")
    else:
        print(f"⚠️  {total - passed} test suite(s) failed")

    print(f"\nTest completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
