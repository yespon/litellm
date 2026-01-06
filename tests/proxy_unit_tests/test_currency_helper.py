"""
Unit tests for currency_helper.py

Tests the CurrencyHelper class and its currency conversion functionality.
"""
import os
import sys
import tempfile
from typing import Dict
from unittest.mock import MagicMock, patch

import pytest

# Add the parent directory to the path to import litellm
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from litellm.proxy.utils.currency_helper import CurrencyHelper, get_currency_helper


class TestCurrencyHelper:
    """Test cases for CurrencyHelper class"""

    @pytest.fixture
    def sample_rates(self) -> Dict[str, float]:
        """Sample exchange rates for testing"""
        return {
            "USD": 1.0,
            "CNY": 7.2,
            "EUR": 0.92,
            "GBP": 0.79,
            "JPY": 149.5,
        }

    @pytest.fixture
    def currency_helper(self, sample_rates):
        """Create a CurrencyHelper instance with sample rates"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            import json

            json.dump(sample_rates, f)
            temp_file = f.name

        try:
            helper = CurrencyHelper(exchange_rates_file=temp_file)
            yield helper
        finally:
            # Cleanup
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_singleton_pattern(self):
        """Test that get_currency_helper returns the same instance"""
        helper1 = get_currency_helper()
        helper2 = get_currency_helper()
        assert helper1 is helper2, "get_currency_helper should return singleton instance"

    def test_load_exchange_rates(self, currency_helper, sample_rates):
        """Test loading exchange rates from file"""
        assert currency_helper.exchange_rates == sample_rates
        assert currency_helper.exchange_rates["USD"] == 1.0
        assert currency_helper.exchange_rates["CNY"] == 7.2

    def test_convert_basic(self, currency_helper):
        """Test basic currency conversion"""
        # USD to CNY
        result = currency_helper.convert(100.0, "USD", "CNY")
        assert result == 720.0, "100 USD should be 720 CNY"

        # CNY to USD
        result = currency_helper.convert(720.0, "CNY", "USD")
        assert abs(result - 100.0) < 0.01, "720 CNY should be ~100 USD"

        # Same currency
        result = currency_helper.convert(100.0, "USD", "USD")
        assert result == 100.0, "Same currency conversion should return same amount"

    def test_convert_zero_amount(self, currency_helper):
        """Test converting zero amount"""
        result = currency_helper.convert(0.0, "USD", "CNY")
        assert result == 0.0, "Zero amount should return zero"

    def test_convert_negative_amount(self, currency_helper):
        """Test converting negative amount"""
        result = currency_helper.convert(-100.0, "USD", "CNY")
        assert result == -720.0, "Negative amounts should work"

    def test_convert_unsupported_currency(self, currency_helper):
        """Test converting with unsupported currency"""
        # Should fall back to original amount
        result = currency_helper.convert(100.0, "USD", "XXX")
        assert result == 100.0, "Unsupported target currency should return original amount"

        result = currency_helper.convert(100.0, "XXX", "USD")
        assert result == 100.0, "Unsupported source currency should return original amount"

    def test_get_budget_in_usd(self, currency_helper):
        """Test converting various currencies to USD"""
        # USD to USD
        result = currency_helper.get_budget_in_usd(100.0, "USD")
        assert result == 100.0

        # CNY to USD
        result = currency_helper.get_budget_in_usd(720.0, "CNY")
        assert abs(result - 100.0) < 0.01

        # EUR to USD
        result = currency_helper.get_budget_in_usd(92.0, "EUR")
        assert abs(result - 100.0) < 0.01

    def test_compare_spend_to_budget_same_currency(self, currency_helper):
        """Test comparing spend and budget in same currency"""
        # Under budget
        is_over, remaining = currency_helper.compare_spend_to_budget(
            spend_amount=50.0,
            spend_currency="USD",
            budget_amount=100.0,
            budget_currency="USD",
        )
        assert is_over is False
        assert abs(remaining - 50.0) < 0.01

        # Over budget
        is_over, remaining = currency_helper.compare_spend_to_budget(
            spend_amount=150.0,
            spend_currency="USD",
            budget_amount=100.0,
            budget_currency="USD",
        )
        assert is_over is True
        assert remaining < 0

        # Exactly at budget
        is_over, remaining = currency_helper.compare_spend_to_budget(
            spend_amount=100.0,
            spend_currency="USD",
            budget_amount=100.0,
            budget_currency="USD",
        )
        assert is_over is False
        assert abs(remaining) < 0.01

    def test_compare_spend_to_budget_different_currencies(self, currency_helper):
        """Test comparing spend and budget in different currencies"""
        # 50 USD vs 100 CNY budget (100 CNY = ~13.89 USD)
        is_over, remaining = currency_helper.compare_spend_to_budget(
            spend_amount=50.0,
            spend_currency="USD",
            budget_amount=100.0,
            budget_currency="CNY",
        )
        assert is_over is True  # 50 USD > 13.89 USD

        # 10 USD vs 100 CNY budget
        is_over, remaining = currency_helper.compare_spend_to_budget(
            spend_amount=10.0,
            spend_currency="USD",
            budget_amount=100.0,
            budget_currency="CNY",
        )
        assert is_over is False  # 10 USD < 13.89 USD

    def test_get_entity_currency_token(self, currency_helper):
        """Test extracting currency from token entity"""
        token_data = {
            "token": "sk-test",
            "budget_currency": "CNY",
        }
        currency = currency_helper.get_entity_currency(token_data, entity_type="token")
        assert currency == "CNY"

    def test_get_entity_currency_user(self, currency_helper):
        """Test extracting currency from user entity"""
        user_data = {
            "user_id": "user-1",
            "budget_currency": "EUR",
        }
        currency = currency_helper.get_entity_currency(user_data, entity_type="user")
        assert currency == "EUR"

    def test_get_entity_currency_team(self, currency_helper):
        """Test extracting currency from team entity"""
        team_data = {
            "team_id": "team-1",
            "budget_currency": "GBP",
        }
        currency = currency_helper.get_entity_currency(team_data, entity_type="team")
        assert currency == "GBP"

    def test_get_entity_currency_missing(self, currency_helper):
        """Test extracting currency when field is missing"""
        entity_data = {
            "user_id": "user-1",
            # No budget_currency field
        }
        currency = currency_helper.get_entity_currency(entity_data, entity_type="user")
        assert currency == "USD", "Should default to USD when field is missing"

    def test_get_entity_currency_none_value(self, currency_helper):
        """Test extracting currency when field is None"""
        entity_data = {
            "user_id": "user-1",
            "budget_currency": None,
        }
        currency = currency_helper.get_entity_currency(entity_data, entity_type="user")
        assert currency == "USD", "Should default to USD when field is None"

    def test_convert_spend_to_entity_currency_no_conversion(self, currency_helper):
        """Test converting spend when entity uses USD"""
        entity_data = {
            "budget_currency": "USD",
        }
        result = currency_helper.convert_spend_to_entity_currency(
            cost_usd=100.0, entity_data=entity_data, entity_type="user"
        )
        assert result == 100.0

    def test_convert_spend_to_entity_currency_with_conversion(self, currency_helper):
        """Test converting spend to entity's currency"""
        entity_data = {
            "budget_currency": "CNY",
        }
        result = currency_helper.convert_spend_to_entity_currency(
            cost_usd=100.0, entity_data=entity_data, entity_type="user"
        )
        assert result == 720.0

    def test_prepare_spend_log_with_currency_usd(self, currency_helper):
        """Test preparing spend log for USD"""
        result = currency_helper.prepare_spend_log_with_currency(
            cost_usd=100.0, target_currency="USD"
        )

        assert result["spend"] == 100.0
        assert result["spend_currency"] == "USD"
        assert result["model_currency"] == "USD"
        assert result["spend_original"] == 100.0
        assert result["exchange_rate"] == 1.0

    def test_prepare_spend_log_with_currency_cny(self, currency_helper):
        """Test preparing spend log for CNY"""
        result = currency_helper.prepare_spend_log_with_currency(
            cost_usd=100.0, target_currency="CNY"
        )

        assert result["spend"] == 720.0
        assert result["spend_currency"] == "CNY"
        assert result["model_currency"] == "USD"
        assert result["spend_original"] == 100.0
        assert result["exchange_rate"] == 7.2

    def test_prepare_spend_log_with_currency_unsupported(self, currency_helper):
        """Test preparing spend log for unsupported currency"""
        result = currency_helper.prepare_spend_log_with_currency(
            cost_usd=100.0, target_currency="XXX"
        )

        # Should fall back to USD
        assert result["spend"] == 100.0
        assert result["spend_currency"] == "USD"
        assert result["model_currency"] == "USD"
        assert result["spend_original"] == 100.0
        assert result["exchange_rate"] == 1.0

    def test_precision_handling(self, currency_helper):
        """Test handling of floating point precision"""
        # Very small amounts
        result = currency_helper.convert(0.0001, "USD", "CNY")
        assert result > 0, "Should handle very small amounts"

        # Large amounts
        result = currency_helper.convert(1000000.0, "USD", "CNY")
        assert result == 7200000.0, "Should handle large amounts"

    def test_thread_safety(self, currency_helper):
        """Test basic thread safety (exchange rates don't change during conversion)"""
        import threading

        results = []

        def convert_worker():
            for _ in range(100):
                result = currency_helper.convert(100.0, "USD", "CNY")
                results.append(result)

        threads = [threading.Thread(target=convert_worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All results should be the same
        assert all(r == 720.0 for r in results), "Conversions should be consistent"

    def test_invalid_rates_file(self):
        """Test handling of invalid rates file"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            f.write("invalid json content {{{")
            temp_file = f.name

        try:
            # Should fall back to defaults
            helper = CurrencyHelper(exchange_rates_file=temp_file)
            assert "USD" in helper.exchange_rates
            assert helper.exchange_rates["USD"] == 1.0
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_missing_rates_file(self):
        """Test handling of missing rates file"""
        helper = CurrencyHelper(exchange_rates_file="/nonexistent/path/rates.json")
        # Should use defaults
        assert "USD" in helper.exchange_rates
        assert helper.exchange_rates["USD"] == 1.0

    @pytest.mark.parametrize(
        "from_currency,to_currency,amount,expected",
        [
            ("USD", "CNY", 100, 720),
            ("CNY", "USD", 720, 100),
            ("EUR", "USD", 92, 100),
            ("USD", "EUR", 100, 92),
            ("USD", "GBP", 100, 79),
            ("JPY", "USD", 14950, 100),
        ],
    )
    def test_conversion_parametrized(
        self, currency_helper, from_currency, to_currency, amount, expected
    ):
        """Parametrized test for various currency conversions"""
        result = currency_helper.convert(amount, from_currency, to_currency)
        assert abs(result - expected) < 0.1, f"{amount} {from_currency} should be ~{expected} {to_currency}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
