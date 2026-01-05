from fastapi import HTTPException

from litellm import verbose_logger
from litellm._logging import verbose_proxy_logger
from litellm.caching.caching import DualCache
from litellm.integrations.custom_logger import CustomLogger
from litellm.proxy._types import UserAPIKeyAuth


class _PROXY_MaxBudgetLimiter(CustomLogger):
    # Class variables or attributes
    def __init__(self):
        pass

    async def async_pre_call_hook(
        self,
        user_api_key_dict: UserAPIKeyAuth,
        cache: DualCache,
        data: dict,
        call_type: str,
    ):
        try:
            verbose_proxy_logger.debug("Inside Max Budget Limiter Pre-Call Hook")
            cache_key = f"{user_api_key_dict.user_id}_user_api_key_user_id"
            user_row = await cache.async_get_cache(
                cache_key, parent_otel_span=user_api_key_dict.parent_otel_span
            )
            if user_row is None:  # value not yet cached
                return
            max_budget = user_row["max_budget"]
            curr_spend = user_row["spend"]

            if max_budget is None:
                return

            if curr_spend is None:
                return

            # Multi-currency budget check
            try:
                from litellm.proxy.utils.currency_helper import get_currency_helper
                currency_helper = get_currency_helper()

                spend_currency = user_row.get("spend_currency", "USD")
                budget_currency = user_row.get("budget_currency", "USD")

                is_over_budget, _ = currency_helper.compare_spend_to_budget(
                    spend_amount=curr_spend,
                    spend_currency=spend_currency,
                    budget_amount=max_budget,
                    budget_currency=budget_currency,
                )

                if is_over_budget:
                    raise HTTPException(
                        status_code=429,
                        detail=f"Max budget limit reached. Spend: {curr_spend} {spend_currency}, Budget: {max_budget} {budget_currency}",
                    )
            except ImportError:
                # Fallback to simple comparison if currency_helper not available
                if curr_spend >= max_budget:
                    raise HTTPException(status_code=429, detail="Max budget limit reached.")
        except HTTPException as e:
            raise e
        except Exception as e:
            verbose_logger.exception(
                "litellm.proxy.hooks.max_budget_limiter.py::async_pre_call_hook(): Exception occured - {}".format(
                    str(e)
                )
            )
