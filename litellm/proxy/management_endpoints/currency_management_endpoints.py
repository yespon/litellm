"""
CURRENCY MANAGEMENT

All /currency management endpoints

/currency/rates
/currency/supported
"""

from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from litellm._logging import verbose_proxy_logger
from litellm.litellm_core_utils.currency import (
    CurrencyExchangeRateManager,
    get_exchange_rate,
)
from litellm.proxy._types import LitellmUserRoles, UserAPIKeyAuth
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
from litellm.proxy.management_helpers.utils import management_endpoint_wrapper
from litellm.proxy.utils import handle_exception_on_proxy

router = APIRouter()


@router.get(
    "/currency/rates",
    tags=["currency management"],
    dependencies=[Depends(user_api_key_auth)],
)
@management_endpoint_wrapper
async def get_exchange_rates(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Get current exchange rates for all supported currencies.

    Returns exchange rates with USD as the base currency.

    Example:
    ```bash
    curl -X GET "http://0.0.0.0:4000/currency/rates" \
    -H "Authorization: Bearer sk-1234"
    ```

    Returns:
    ```json
    {
        "base_currency": "USD",
        "rates": {
            "CNY": 7.2,
            "EUR": 0.92,
            "GBP": 0.79,
            "JPY": 149.5,
            "KRW": 1320.0,
            "INR": 83.2,
            "AUD": 1.52,
            "CAD": 1.35
        },
        "last_updated": "2025-01-15T10:00:00Z"
    }
    ```
    """
    try:
        manager = CurrencyExchangeRateManager()

        # Get all supported currencies
        supported_currencies = manager.get_supported_currencies()

        # Build rates dictionary
        rates = {}
        for currency in supported_currencies:
            if currency != "USD":  # Skip USD to USD conversion
                try:
                    rate = get_exchange_rate("USD", currency)
                    rates[currency] = rate
                except Exception as e:
                    verbose_proxy_logger.warning(
                        f"Failed to get rate for {currency}: {e}"
                    )

        # Get last updated time from manager
        last_updated = manager.get_last_updated_time()

        return {
            "base_currency": "USD",
            "rates": rates,
            "last_updated": last_updated.isoformat() if last_updated else None,
        }
    except Exception as e:
        verbose_proxy_logger.exception(
            "litellm.proxy.management_endpoints.currency_management_endpoints.get_exchange_rates(): Exception occurred - {}".format(
                str(e)
            )
        )
        raise handle_exception_on_proxy(e)


@router.post(
    "/currency/rates",
    tags=["currency management"],
    dependencies=[Depends(user_api_key_auth)],
)
@management_endpoint_wrapper
async def update_exchange_rates(
    data: Dict[str, float],
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Update exchange rates (Admin only).

    This endpoint allows administrators to manually update currency exchange rates.
    The rates will be saved to the exchange rate file and reloaded immediately.

    Parameters:
    - data: Dict[str, float] - Dictionary of currency codes to rates (relative to USD)

    Example:
    ```bash
    curl -X POST "http://0.0.0.0:4000/currency/rates" \
    -H "Authorization: Bearer sk-1234" \
    -H "Content-Type: application/json" \
    -d '{
        "CNY": 7.25,
        "EUR": 0.93,
        "GBP": 0.80,
        "JPY": 150.0
    }'
    ```

    Returns:
    ```json
    {
        "status": "success",
        "updated_currencies": ["CNY", "EUR", "GBP", "JPY"],
        "updated_at": "2025-01-15T10:30:00Z"
    }
    ```

    Note: This is an admin-only endpoint. Only proxy admins can update rates.
    """
    try:
        # Check if user is admin
        if (
            user_api_key_dict.user_role is None
            or user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN.value
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only proxy admins can update exchange rates",
            )

        # Validate input
        if not data or not isinstance(data, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid data format. Expected dictionary of currency codes to rates.",
            )

        # Validate all values are positive numbers
        for currency, rate in data.items():
            if not isinstance(rate, (int, float)) or rate <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid rate for {currency}: {rate}. Rate must be a positive number.",
                )

        manager = CurrencyExchangeRateManager()

        # Update rates
        manager.update_rates(data)

        # Force reload to apply changes immediately
        manager.reload_rates()

        return {
            "status": "success",
            "updated_currencies": list(data.keys()),
            "updated_at": datetime.utcnow().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        verbose_proxy_logger.exception(
            "litellm.proxy.management_endpoints.currency_management_endpoints.update_exchange_rates(): Exception occurred - {}".format(
                str(e)
            )
        )
        raise handle_exception_on_proxy(e)


@router.get(
    "/currency/supported",
    tags=["currency management"],
    dependencies=[Depends(user_api_key_auth)],
)
@management_endpoint_wrapper
async def get_supported_currencies(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Get list of supported currencies.

    Returns all currency codes that are supported by the system,
    along with their full names where available.

    Example:
    ```bash
    curl -X GET "http://0.0.0.0:4000/currency/supported" \
    -H "Authorization: Bearer sk-1234"
    ```

    Returns:
    ```json
    {
        "currencies": [
            {
                "code": "USD",
                "name": "US Dollar"
            },
            {
                "code": "CNY",
                "name": "Chinese Yuan"
            },
            {
                "code": "EUR",
                "name": "Euro"
            },
            {
                "code": "GBP",
                "name": "British Pound"
            },
            {
                "code": "JPY",
                "name": "Japanese Yen"
            }
        ],
        "count": 5
    }
    ```
    """
    try:
        manager = CurrencyExchangeRateManager()

        # Get supported currencies
        supported = manager.get_supported_currencies()

        # Currency names mapping
        currency_names = {
            "USD": "US Dollar",
            "CNY": "Chinese Yuan",
            "EUR": "Euro",
            "GBP": "British Pound",
            "JPY": "Japanese Yen",
            "KRW": "South Korean Won",
            "INR": "Indian Rupee",
            "AUD": "Australian Dollar",
            "CAD": "Canadian Dollar",
            "CHF": "Swiss Franc",
            "HKD": "Hong Kong Dollar",
            "SGD": "Singapore Dollar",
            "NZD": "New Zealand Dollar",
            "SEK": "Swedish Krona",
            "NOK": "Norwegian Krone",
            "DKK": "Danish Krone",
            "RUB": "Russian Ruble",
            "BRL": "Brazilian Real",
            "MXN": "Mexican Peso",
            "ZAR": "South African Rand",
        }

        # Build currency list with names
        currencies = [
            {
                "code": code,
                "name": currency_names.get(code, code),
            }
            for code in sorted(supported)
        ]

        return {
            "currencies": currencies,
            "count": len(currencies),
        }
    except Exception as e:
        verbose_proxy_logger.exception(
            "litellm.proxy.management_endpoints.currency_management_endpoints.get_supported_currencies(): Exception occurred - {}".format(
                str(e)
            )
        )
        raise handle_exception_on_proxy(e)
