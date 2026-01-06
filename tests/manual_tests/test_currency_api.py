"""
Manual test script for Currency Management API endpoints

Run this after starting the proxy server to test the currency endpoints.
"""

import requests
import json

BASE_URL = "http://localhost:4000"
# Replace with your actual admin API key
ADMIN_KEY = "sk-1234"

headers = {
    "Authorization": f"Bearer {ADMIN_KEY}",
    "Content-Type": "application/json"
}


def test_get_supported_currencies():
    """Test GET /currency/supported"""
    print("\n=== Test 1: GET /currency/supported ===")
    response = requests.get(f"{BASE_URL}/currency/supported", headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200


def test_get_exchange_rates():
    """Test GET /currency/rates"""
    print("\n=== Test 2: GET /currency/rates ===")
    response = requests.get(f"{BASE_URL}/currency/rates", headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200


def test_update_exchange_rates():
    """Test POST /currency/rates (Admin only)"""
    print("\n=== Test 3: POST /currency/rates ===")
    data = {
        "CNY": 7.30,
        "EUR": 0.93,
        "GBP": 0.80
    }
    response = requests.post(
        f"{BASE_URL}/currency/rates",
        headers=headers,
        json=data
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200


def test_key_generation_with_currency():
    """Test key generation with budget_currency"""
    print("\n=== Test 4: Key Generation with Currency ===")
    data = {
        "max_budget": 1000.0,
        "budget_currency": "CNY",
        "duration": "30d"
    }
    response = requests.post(
        f"{BASE_URL}/key/generate",
        headers=headers,
        json=data
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Key created: {result.get('key', 'N/A')[:20]}...")
        print(f"Budget Currency: {result.get('budget_currency', 'N/A')}")
        print(f"Max Budget: {result.get('max_budget', 'N/A')}")
        return True
    else:
        print(f"Error: {response.text}")
        return False


def main():
    print("Starting Currency Management API Tests")
    print("=" * 50)

    results = []

    # Test 1: Get supported currencies
    results.append(("Supported Currencies", test_get_supported_currencies()))

    # Test 2: Get exchange rates
    results.append(("Get Exchange Rates", test_get_exchange_rates()))

    # Test 3: Update exchange rates (requires admin)
    results.append(("Update Exchange Rates", test_update_exchange_rates()))

    # Test 4: Key generation with currency
    results.append(("Key Generation", test_key_generation_with_currency()))

    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} tests passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
