"""
Simplified unit tests for currency_helper.py - with mocked dependencies

Tests the CurrencyHelper class without requiring Redis or external dependencies.
"""
import os
import sys
from typing import Dict
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add the parent directory to the path to import litellm
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


class TestCurrencyHelperBasic:
    """Basic test cases for CurrencyHelper with mocked dependencies"""

    @pytest.fixture
    def mock_manager(self):
        """Mock CurrencyExchangeRateManager"""
        manager = MagicMock()
        manager.get_rate.return_value = 7.2  # CNY rate
        return manager

    @pytest.fixture
    def mock_convert_currency(self):
        """Mock convert_currency function"""
        def _convert(amount, from_curr, to_curr):
            # Simple mock conversion logic
            rates = {
                ("USD", "CNY"): 7.2,
                ("CNY", "USD"): 1/7.2,
                ("USD", "USD"): 1.0,
            }
            rate = rates.get((from_curr, to_curr), 1.0)
            return amount * rate
        return _convert

    @pytest.fixture
    def mock_get_exchange_rate(self):
        """Mock get_exchange_rate function"""
        def _get_rate(from_curr, to_curr):
            rates = {
                ("USD", "CNY"): 7.2,
                ("CNY", "USD"): 1/7.2,
                ("USD", "USD"): 1.0,
            }
            return rates.get((from_curr, to_curr), 1.0)
        return _get_rate

    @patch('litellm.proxy.utils.currency_helper.CurrencyExchangeRateManager')
    @patch('litellm.proxy.utils.currency_helper.convert_currency')
    @patch('litellm.proxy.utils.currency_helper.get_exchange_rate')
    def test_get_entity_currency_from_dict(
        self,
        mock_get_rate,
        mock_convert,
        mock_manager_class,
    ):
        """Test extracting currency from dictionary entity data"""
        from litellm.proxy.currency_utils.currency_helper import CurrencyHelper

        helper = CurrencyHelper()

        # Test with budget_currency
        entity_data = {"budget_currency": "CNY"}
        currency = helper.get_entity_currency(entity_data, "user")
        assert currency == "CNY"

        # Test with spend_currency (higher priority)
        entity_data = {"spend_currency": "EUR", "budget_currency": "CNY"}
        currency = helper.get_entity_currency(entity_data, "user")
        assert currency == "EUR"

        # Test with missing currency
        entity_data = {}
        currency = helper.get_entity_currency(entity_data, "user")
        assert currency == "USD"

        # Test with None
        currency = helper.get_entity_currency(None, "user")
        assert currency == "USD"

    @patch('litellm.proxy.utils.currency_helper.CurrencyExchangeRateManager')
    @patch('litellm.proxy.utils.currency_helper.convert_currency')
    @patch('litellm.proxy.utils.currency_helper.get_exchange_rate')
    def test_convert_spend_to_entity_currency(
        self,
        mock_get_rate,
        mock_convert,
        mock_manager_class,
        mock_convert_currency,
        mock_get_exchange_rate
    ):
        """Test converting USD to entity currency"""
        from litellm.proxy.currency_utils.currency_helper import CurrencyHelper

        # Setup mocks
        mock_convert.side_effect = mock_convert_currency
        mock_get_rate.side_effect = mock_get_exchange_rate

        helper = CurrencyHelper()

        # Test USD to USD (no conversion)
        converted, rate = helper.convert_spend_to_entity_currency(100.0, "USD")
        assert converted == 100.0
        assert rate == 1.0

        # Test USD to CNY
        converted, rate = helper.convert_spend_to_entity_currency(100.0, "CNY")
        assert converted == 720.0
        assert rate == 7.2

    @patch('litellm.proxy.utils.currency_helper.CurrencyExchangeRateManager')
    @patch('litellm.proxy.utils.currency_helper.convert_currency')
    @patch('litellm.proxy.utils.currency_helper.get_exchange_rate')
    def test_prepare_spend_log_with_currency(
        self,
        mock_get_rate,
        mock_convert,
        mock_manager_class,
        mock_convert_currency,
        mock_get_exchange_rate
    ):
        """Test preparing spend log with currency information"""
        from litellm.proxy.currency_utils.currency_helper import CurrencyHelper

        # Setup mocks
        mock_convert.side_effect = mock_convert_currency
        mock_get_rate.side_effect = mock_get_exchange_rate

        helper = CurrencyHelper()

        # Test USD
        result = helper.prepare_spend_log_with_currency(100.0, "USD")
        assert result["spend"] == 100.0
        assert result["spend_currency"] == "USD"
        assert result["model_currency"] == "USD"
        assert result["spend_original"] == 100.0
        assert result["exchange_rate"] == 1.0

        # Test CNY
        result = helper.prepare_spend_log_with_currency(100.0, "CNY")
        assert result["spend"] == 720.0
        assert result["spend_currency"] == "CNY"
        assert result["model_currency"] == "USD"
        assert result["spend_original"] == 100.0
        assert result["exchange_rate"] == 7.2

    @patch('litellm.proxy.utils.currency_helper.CurrencyExchangeRateManager')
    def test_get_currency_helper_singleton(self, mock_manager_class):
        """Test that get_currency_helper returns singleton"""
        from litellm.proxy.currency_utils.currency_helper import get_currency_helper, _currency_helper

        # Reset singleton
        import litellm.proxy.utils.currency_helper as helper_module
        helper_module._currency_helper = None

        helper1 = get_currency_helper()
        helper2 = get_currency_helper()

        assert helper1 is helper2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
