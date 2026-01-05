"""
货币转换辅助模块 - 用于 LiteLLM 多货币支持

功能:
- 从实体（用户/团队/API Key）获取配置的货币
- 将 USD 成本转换为目标货币
- 构建包含货币信息的 spend 记录
"""

from typing import Optional, Tuple, Dict, Any
from datetime import datetime
import logging

from litellm.litellm_core_utils.currency import (
    CurrencyExchangeRateManager,
    convert_currency,
    get_exchange_rate,
)

logger = logging.getLogger("litellm.proxy.currency_helper")


class CurrencyHelper:
    """
    货币转换辅助类 - 用于 Proxy spend tracking

    所有 LiteLLM 内部计算仍然使用 USD，只在记录到数据库时转换
    """

    def __init__(self):
        self.manager = CurrencyExchangeRateManager()

    @staticmethod
    def get_entity_currency(
        entity_data: Optional[Dict[str, Any]],
        entity_type: str = "user"
    ) -> str:
        """
        获取实体配置的货币

        Args:
            entity_data: 实体数据（UserTable, TeamTable, VerificationToken等）
            entity_type: 实体类型

        Returns:
            货币代码，默认 USD
        """
        if entity_data is None:
            return "USD"

        # 优先级：spend_currency > budget_currency > USD
        currency = None

        if isinstance(entity_data, dict):
            currency = entity_data.get("spend_currency") or entity_data.get("budget_currency")
        else:
            currency = getattr(entity_data, "spend_currency", None) or getattr(
                entity_data, "budget_currency", None
            )

        return currency or "USD"

    def convert_spend_to_entity_currency(
        self,
        cost_usd: float,
        entity_currency: str,
    ) -> Tuple[float, float]:
        """
        将 USD 成本转换为实体货币

        Args:
            cost_usd: USD 金额
            entity_currency: 目标货币

        Returns:
            (converted_amount, exchange_rate)
        """
        if entity_currency == "USD":
            return cost_usd, 1.0

        try:
            rate = get_exchange_rate("USD", entity_currency)
            converted = convert_currency(cost_usd, "USD", entity_currency)
            return converted, rate
        except Exception as e:
            logger.warning(
                f"Currency conversion failed (USD -> {entity_currency}): {e}, using USD"
            )
            return cost_usd, 1.0

    def prepare_spend_log_with_currency(
        self,
        cost_usd: float,
        target_currency: str = "USD",
        model_currency: Optional[str] = None,
        model_original_cost: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        准备包含完整货币信息的 spend log 数据

        Args:
            cost_usd: USD 金额（LiteLLM 标准）
            target_currency: 目标记录货币
            model_currency: 模型提供商的原始货币
            model_original_cost: 模型提供商的原始金额

        Returns:
            包含货币信息的字典
        """
        converted_cost, exchange_rate = self.convert_spend_to_entity_currency(
            cost_usd, target_currency
        )

        result = {
            "spend": converted_cost,
            "spend_currency": target_currency,
            "exchange_rate": exchange_rate if target_currency != "USD" else None,
        }

        # 如果模型提供商使用了不同的货币（未来扩展）
        if model_currency and model_currency != "USD":
            result["model_currency"] = model_currency
            result["spend_original"] = model_original_cost or cost_usd

        return result

    def get_budget_in_usd(
        self,
        budget_amount: float,
        budget_currency: str = "USD"
    ) -> float:
        """
        将预算金额转换为 USD（用于预算检查）

        Args:
            budget_amount: 预算金额
            budget_currency: 预算货币

        Returns:
            USD 金额
        """
        if budget_currency == "USD":
            return budget_amount

        try:
            return convert_currency(budget_amount, budget_currency, "USD")
        except Exception as e:
            logger.error(
                f"Budget currency conversion failed ({budget_currency} -> USD): {e}"
            )
            return budget_amount  # Fallback

    def compare_spend_to_budget(
        self,
        spend_amount: float,
        spend_currency: str,
        budget_amount: float,
        budget_currency: str,
    ) -> Tuple[bool, float]:
        """
        比较 spend 和 budget（支持不同货币）

        Args:
            spend_amount: 消费金额
            spend_currency: 消费货币
            budget_amount: 预算金额
            budget_currency: 预算货币

        Returns:
            (is_over_budget, remaining_budget_in_usd)
        """
        # 统一转换为 USD 进行比较
        spend_usd = self.get_budget_in_usd(spend_amount, spend_currency)
        budget_usd = self.get_budget_in_usd(budget_amount, budget_currency)

        remaining = budget_usd - spend_usd
        is_over = spend_usd > budget_usd

        return is_over, remaining


# 全局单例
_currency_helper: Optional[CurrencyHelper] = None


def get_currency_helper() -> CurrencyHelper:
    """获取全局 CurrencyHelper 实例"""
    global _currency_helper
    if _currency_helper is None:
        _currency_helper = CurrencyHelper()
    return _currency_helper
