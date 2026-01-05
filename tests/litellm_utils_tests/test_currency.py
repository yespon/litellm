"""
单元测试：货币和汇率管理模块

测试覆盖:
- CurrencyExchangeRateManager 单例模式
- Redis 模式和文件模式
- 汇率获取和转换
- 汇率更新
- 便捷函数
"""

import pytest
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from litellm.litellm_core_utils.currency import (
    CurrencyExchangeRateManager,
    convert_currency,
    get_exchange_rate,
    reload_exchange_rates,
    get_manager_stats,
)


class TestCurrencyManager:
    """汇率管理器测试"""

    def test_singleton(self):
        """测试单例模式"""
        manager1 = CurrencyExchangeRateManager()
        manager2 = CurrencyExchangeRateManager()
        assert manager1 is manager2

    def test_default_rates(self):
        """测试默认汇率"""
        manager = CurrencyExchangeRateManager()
        rates = manager.get_all_rates()

        # 验证默认货币存在
        assert "USD" in rates
        assert "CNY" in rates
        assert rates["USD"] == 1.0
        assert rates["CNY"] > 0

    def test_get_rate_same_currency(self):
        """测试相同货币汇率"""
        manager = CurrencyExchangeRateManager()
        rate = manager.get_rate("USD", "USD")
        assert rate == 1.0

    def test_get_rate_conversion(self):
        """测试汇率计算"""
        manager = CurrencyExchangeRateManager()

        # USD -> CNY
        rate = manager.get_rate("USD", "CNY")
        assert rate > 1.0  # CNY 应该比 USD 多

        # CNY -> USD (反向)
        reverse_rate = manager.get_rate("CNY", "USD")
        assert abs(rate * reverse_rate - 1.0) < 0.0001  # 往返应该接近 1

    def test_get_rate_unsupported_currency(self):
        """测试不支持的货币"""
        manager = CurrencyExchangeRateManager()

        with pytest.raises(ValueError, match="Unsupported currency"):
            manager.get_rate("USD", "XYZ")

        with pytest.raises(ValueError, match="Unsupported currency"):
            manager.get_rate("ABC", "USD")

    def test_convert_basic(self):
        """测试基本货币转换"""
        manager = CurrencyExchangeRateManager()

        # USD -> CNY
        result = manager.convert(100, "USD", "CNY")
        assert result > 100  # CNY 金额应该更大

        # CNY -> USD
        result_back = manager.convert(result, "CNY", "USD")
        assert abs(result_back - 100) < 0.01  # 往返误差应该很小

    def test_convert_same_currency(self):
        """测试相同货币转换"""
        manager = CurrencyExchangeRateManager()
        result = manager.convert(100, "USD", "USD")
        assert result == 100

    def test_update_rate_valid(self):
        """测试更新汇率（有效）"""
        manager = CurrencyExchangeRateManager()

        old_rate = manager.get_rate("USD", "CNY")
        new_rate_value = 7.5

        # 更新汇率（不保存）
        manager.update_rate("CNY", new_rate_value, save=False)

        # 验证更新成功
        updated_rate = manager.get_rate("USD", "CNY")
        assert updated_rate == new_rate_value
        assert updated_rate != old_rate

    def test_update_rate_invalid(self):
        """测试更新汇率（无效）"""
        manager = CurrencyExchangeRateManager()

        # 负数汇率
        with pytest.raises(ValueError, match="must be > 0"):
            manager.update_rate("CNY", -1.0)

        # 零汇率
        with pytest.raises(ValueError, match="must be > 0"):
            manager.update_rate("CNY", 0.0)

        # 不能修改 USD
        with pytest.raises(ValueError, match="Cannot modify USD"):
            manager.update_rate("USD", 2.0)

    def test_supported_currencies(self):
        """测试获取支持的货币列表"""
        manager = CurrencyExchangeRateManager()
        currencies = manager.get_supported_currencies()

        assert isinstance(currencies, list)
        assert len(currencies) >= 2  # 至少 USD 和 CNY
        assert "USD" in currencies
        assert "CNY" in currencies

    def test_get_stats(self):
        """测试获取管理器状态"""
        manager = CurrencyExchangeRateManager()
        stats = manager.get_stats()

        assert "mode" in stats
        assert "currencies" in stats
        assert stats["mode"] in ["redis", "file"]
        assert stats["currencies"] >= 2


class TestConvenienceFunctions:
    """便捷函数测试"""

    def test_convert_currency(self):
        """测试货币转换便捷函数"""
        result = convert_currency(100, "USD", "CNY")
        assert result > 100

        # 往返测试
        result_back = convert_currency(result, "CNY", "USD")
        assert abs(result_back - 100) < 0.01

    def test_get_exchange_rate(self):
        """测试获取汇率便捷函数"""
        rate = get_exchange_rate("USD", "CNY")
        assert rate > 1.0

        # 反向
        reverse_rate = get_exchange_rate("CNY", "USD")
        assert abs(rate * reverse_rate - 1.0) < 0.0001

    def test_get_manager_stats_function(self):
        """测试获取状态便捷函数"""
        stats = get_manager_stats()
        assert "mode" in stats
        assert "currencies" in stats


class TestFileMode:
    """文件模式测试"""

    def test_load_from_file(self, tmp_path):
        """测试从文件加载汇率"""
        # 创建临时配置文件
        config_file = tmp_path / "test_rates.json"
        config = {
            "version": "1.0",
            "base_currency": "USD",
            "rates": {
                "USD": 1.0,
                "CNY": 7.3,
                "EUR": 0.93
            }
        }

        with open(config_file, 'w') as f:
            json.dump(config, f)

        # 设置环境变量
        with patch.dict(os.environ, {"CURRENCY_EXCHANGE_RATE_FILE": str(config_file)}):
            # 创建新实例（绕过单例）
            manager = CurrencyExchangeRateManager.__new__(CurrencyExchangeRateManager)
            manager._initialized = False
            manager._use_redis = False
            manager._config_path = Path(config_file)

            rates = manager._load_from_file()

            assert rates["USD"] == 1.0
            assert rates["CNY"] == 7.3
            assert rates["EUR"] == 0.93

    def test_save_rates(self, tmp_path):
        """测试保存汇率到文件"""
        config_file = tmp_path / "test_rates.json"

        # 创建管理器实例
        manager = CurrencyExchangeRateManager()
        manager._config_path = Path(config_file)

        # 保存汇率
        test_rates = {
            "USD": 1.0,
            "CNY": 7.25,
            "EUR": 0.94
        }
        manager.save_rates(test_rates)

        # 验证文件内容
        assert config_file.exists()

        with open(config_file, 'r') as f:
            saved_config = json.load(f)

        assert saved_config["rates"]["USD"] == 1.0
        assert saved_config["rates"]["CNY"] == 7.25
        assert saved_config["rates"]["EUR"] == 0.94


class TestRedisMode:
    """Redis 模式测试"""

    @patch('litellm.utils.currency.redis')
    def test_redis_initialization_success(self, mock_redis_module):
        """测试 Redis 初始化成功"""
        # 模拟 Redis 客户端
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis_module.from_url.return_value = mock_client

        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0"}):
            manager = CurrencyExchangeRateManager.__new__(CurrencyExchangeRateManager)
            manager._initialized = False
            manager._redis_client = None
            manager._use_redis = False

            manager._init_redis()

            assert manager._use_redis is True
            assert manager._redis_client is not None

    @patch('litellm.utils.currency.redis')
    def test_redis_initialization_failure(self, mock_redis_module):
        """测试 Redis 初始化失败"""
        # 模拟连接失败
        mock_redis_module.from_url.side_effect = Exception("Connection failed")

        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0"}):
            manager = CurrencyExchangeRateManager.__new__(CurrencyExchangeRateManager)
            manager._initialized = False
            manager._redis_client = None
            manager._use_redis = False

            manager._init_redis()

            # 应该降级到文件模式
            assert manager._use_redis is False
            assert manager._redis_client is None

    @patch('litellm.utils.currency.redis')
    def test_get_from_redis(self, mock_redis_module):
        """测试从 Redis 获取汇率"""
        mock_client = MagicMock()
        mock_rates = {"USD": 1.0, "CNY": 7.2, "EUR": 0.92}
        mock_client.get.return_value = json.dumps(mock_rates)

        manager = CurrencyExchangeRateManager()
        manager._use_redis = True
        manager._redis_client = mock_client

        rates = manager._get_from_redis()

        assert rates == mock_rates
        mock_client.get.assert_called_once()

    @patch('litellm.utils.currency.redis')
    def test_update_rate_redis_mode(self, mock_redis_module):
        """测试 Redis 模式下更新汇率"""
        mock_client = MagicMock()

        manager = CurrencyExchangeRateManager()
        manager._use_redis = True
        manager._redis_client = mock_client

        # Mock 获取当前汇率
        with patch.object(manager, 'get_all_rates', return_value={"USD": 1.0, "CNY": 7.2}):
            manager.update_rate("CNY", 7.3, save=False)

            # 验证 Redis 更新被调用
            mock_client.setex.assert_called_once()


class TestPrecision:
    """精度测试"""

    def test_round_trip_precision(self):
        """测试往返转换精度"""
        amounts = [0.01, 1.0, 10.0, 100.0, 1000.0, 10000.0]

        manager = CurrencyExchangeRateManager()

        for amount in amounts:
            # USD -> CNY -> USD
            cny = manager.convert(amount, "USD", "CNY")
            usd_back = manager.convert(cny, "CNY", "USD")

            # 误差应该非常小（< 0.001%）
            relative_error = abs(usd_back - amount) / amount
            assert relative_error < 0.00001, f"Precision error for amount {amount}"

    def test_large_amounts(self):
        """测试大金额转换"""
        manager = CurrencyExchangeRateManager()

        # 测试 100 万
        result = manager.convert(1_000_000, "USD", "CNY")
        assert result > 1_000_000

        # 往返
        result_back = manager.convert(result, "CNY", "USD")
        assert abs(result_back - 1_000_000) < 10  # 允许小误差

    def test_small_amounts(self):
        """测试小金额转换"""
        manager = CurrencyExchangeRateManager()

        # 测试 1 分钱
        result = manager.convert(0.01, "USD", "CNY")
        assert result > 0

        # 往返
        result_back = manager.convert(result, "CNY", "USD")
        assert abs(result_back - 0.01) < 0.0001


class TestConcurrency:
    """并发测试"""

    def test_multiple_conversions(self):
        """测试多次并发转换"""
        import threading

        manager = CurrencyExchangeRateManager()
        results = []
        errors = []

        def convert_task():
            try:
                result = manager.convert(100, "USD", "CNY")
                results.append(result)
            except Exception as e:
                errors.append(e)

        # 创建 10 个线程
        threads = [threading.Thread(target=convert_task) for _ in range(10)]

        # 启动所有线程
        for thread in threads:
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

        # 验证
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 10
        # 所有结果应该相同（相同的汇率）
        assert all(abs(r - results[0]) < 0.0001 for r in results)


# 运行测试的示例命令：
# pytest tests/litellm_utils_tests/test_currency.py -v
# pytest tests/litellm_utils_tests/test_currency.py::TestCurrencyManager::test_singleton -v
