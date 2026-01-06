"""
货币和汇率管理模块 - 生产级实现

功能:
- Redis 分布式缓存（多进程共享）
- 文件监控降级（无 Redis 时）
- 汇率转换和管理
- 自动故障恢复

支持部署模式:
- 单进程（文件模式）
- 多进程（文件监控模式）
- 分布式（Redis 模式）
"""

import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Literal
from pathlib import Path
from functools import wraps
from threading import Thread, Lock
import logging

# 配置日志
logger = logging.getLogger("litellm.currency")

# 支持的货币类型
SupportedCurrency = Literal["USD", "CNY", "EUR", "GBP", "JPY"]

# ==================== 装饰器 ====================

def with_redis_fallback(func):
    """Redis 故障时降级到文件"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            if self._use_redis and self._redis_client:
                return func(self, *args, **kwargs)
            else:
                return self._fallback_to_file(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Redis error in {func.__name__}: {e}, using file fallback")
            return self._fallback_to_file(*args, **kwargs)
    return wrapper

# ==================== 主类 ====================

class CurrencyExchangeRateManager:
    """
    汇率管理器 - Redis + 文件混合模式

    工作模式:
    1. Redis 模式（推荐）: 所有进程共享 Redis 缓存，实时同步
    2. 文件监控模式: 监控配置文件变化，自动重载
    3. 基础模式: 定期刷新配置文件
    """

    _instance = None
    _initialized = False
    _lock = Lock()

    # Redis 配置
    _redis_client: Optional[object] = None
    _use_redis: bool = False
    _redis_key = "litellm:exchange_rates:v1"
    _redis_ttl = 3600  # 1小时

    # 文件缓存配置
    _rates: Dict[str, float] = {}
    _last_update: Optional[datetime] = None
    _cache_ttl: int = 60  # 1分钟（作为安全网）
    _config_file: str = "currency_exchange_rates.json"
    _config_path: Optional[Path] = None
    _base_currency: str = "USD"

    # 文件监控
    _observer = None
    _watcher_thread = None

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化汇率管理器（只执行一次）"""
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            logger.info("[Currency] Initializing CurrencyExchangeRateManager...")

            # 1. 尝试连接 Redis
            self._init_redis()

            # 2. 如果 Redis 不可用，启动文件监控
            if not self._use_redis:
                logger.info("[Currency] Redis not available, using file-based mode")
                self._init_file_watcher()
                self._start_periodic_refresh()

            # 3. 初始加载汇率
            self.load_rates(force=True)

            self._initialized = True
            logger.info(f"[Currency] Initialization complete. Mode: {'Redis' if self._use_redis else 'File'}")

    def _init_redis(self) -> None:
        """初始化 Redis 连接"""
        redis_url = os.getenv("REDIS_URL")

        if not redis_url:
            logger.info("[Currency] REDIS_URL not set, skipping Redis")
            self._use_redis = False
            return

        try:
            import redis

            # 连接 Redis
            self._redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )

            # 测试连接
            self._redis_client.ping()
            self._use_redis = True
            logger.info(f"[Currency] Redis connected successfully: {redis_url}")

        except ImportError:
            logger.warning("[Currency] redis package not installed, using file mode")
            self._use_redis = False
            self._redis_client = None
        except Exception as e:
            logger.warning(f"[Currency] Failed to connect to Redis: {e}")
            self._use_redis = False
            self._redis_client = None

    def _init_file_watcher(self) -> None:
        """初始化文件监控（仅在无 Redis 时）"""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            class RateFileHandler(FileSystemEventHandler):
                def __init__(self, manager):
                    self.manager = manager
                    self._last_modified = 0

                def on_modified(self, event):
                    # 防抖：避免多次触发
                    if event.src_path == str(self.manager._config_path):
                        current_time = time.time()
                        if current_time - self._last_modified > 0.5:  # 500ms 防抖
                            self._last_modified = current_time
                            logger.info("[Currency] Config file changed, reloading...")
                            self.manager.load_rates(force=True)

            self._config_path = self._get_config_path()
            event_handler = RateFileHandler(self)
            self._observer = Observer()

            watch_path = self._config_path.parent
            self._observer.schedule(event_handler, str(watch_path), recursive=False)
            self._observer.start()

            logger.info(f"[Currency] File watcher started on {watch_path}")

        except ImportError:
            logger.warning("[Currency] watchdog not installed, file watcher disabled")
        except Exception as e:
            logger.warning(f"[Currency] Failed to start file watcher: {e}")

    def _start_periodic_refresh(self) -> None:
        """启动定期刷新（作为文件监控的备份）"""
        def refresh_loop():
            while True:
                time.sleep(300)  # 每 5 分钟刷新
                if not self._is_cache_valid():
                    logger.info("[Currency] Periodic refresh triggered")
                    self.load_rates(force=True)

        self._watcher_thread = Thread(target=refresh_loop, daemon=True)
        self._watcher_thread.start()
        logger.info("[Currency] Periodic refresh started (every 5 min)")

    # ==================== 汇率获取 ====================

    def get_all_rates(self) -> Dict[str, float]:
        """
        获取所有汇率

        优先级:
        1. Redis（如果可用）
        2. 内存缓存（如果有效）
        3. 配置文件
        """
        if self._use_redis:
            return self._get_from_redis()
        else:
            return self._get_from_file()

    def _get_from_redis(self) -> Dict[str, float]:
        """从 Redis 获取汇率"""
        try:
            # 从 Redis 读取
            cached = self._redis_client.get(self._redis_key)

            if cached:
                rates = json.loads(cached)
                logger.debug(f"[Currency] Loaded {len(rates)} rates from Redis")
                return rates

            # Redis 未命中，从文件加载并缓存
            logger.info("[Currency] Redis cache miss, loading from file")
            rates = self._load_from_file()
            self._update_redis_cache(rates)
            return rates

        except Exception as e:
            logger.error(f"[Currency] Redis error: {e}, falling back to file")
            return self._get_from_file()

    def _get_from_file(self) -> Dict[str, float]:
        """从文件获取汇率（带缓存）"""
        with self._lock:
            # 检查内存缓存
            if self._is_cache_valid():
                return self._rates.copy()

            # 从文件加载
            self._rates = self._load_from_file()
            self._last_update = datetime.now()
            return self._rates.copy()

    def _load_from_file(self) -> Dict[str, float]:
        """从配置文件加载汇率"""
        if not self._config_path:
            self._config_path = self._get_config_path()

        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            rates = config.get("rates", {"USD": 1.0, "CNY": 7.2})
            logger.info(f"[Currency] Loaded {len(rates)} rates from file")
            return rates

        except FileNotFoundError:
            logger.warning("[Currency] Config file not found, using defaults")
            return {"USD": 1.0, "CNY": 7.2, "EUR": 0.92, "GBP": 0.79, "JPY": 149.5}

        except Exception as e:
            logger.error(f"[Currency] Error loading file: {e}")
            return self._rates if self._rates else {"USD": 1.0, "CNY": 7.2}

    def _update_redis_cache(self, rates: Dict[str, float]) -> None:
        """更新 Redis 缓存"""
        try:
            self._redis_client.setex(
                self._redis_key,
                self._redis_ttl,
                json.dumps(rates)
            )
            logger.debug("[Currency] Updated Redis cache")
        except Exception as e:
            logger.warning(f"[Currency] Failed to update Redis: {e}")

    def _is_cache_valid(self) -> bool:
        """检查内存缓存是否有效"""
        if not self._last_update or not self._rates:
            return False

        elapsed = (datetime.now() - self._last_update).total_seconds()
        return elapsed < self._cache_ttl

    def _get_config_path(self) -> Path:
        """获取配置文件路径"""
        env_path = os.getenv("CURRENCY_EXCHANGE_RATE_FILE")
        if env_path:
            return Path(env_path)

        # 默认路径：项目根目录
        return Path(__file__).parent.parent.parent / self._config_file

    # ==================== 汇率计算 ====================

    def get_rate(
        self,
        from_currency: str,
        to_currency: str
    ) -> float:
        """
        获取汇率

        Args:
            from_currency: 源货币（如 "USD"）
            to_currency: 目标货币（如 "CNY"）

        Returns:
            汇率值

        Example:
            >>> manager = CurrencyExchangeRateManager()
            >>> rate = manager.get_rate("USD", "CNY")
            >>> print(rate)  # 7.2
        """
        # 相同货币
        if from_currency == to_currency:
            return 1.0

        # 获取汇率
        rates = self.get_all_rates()

        from_rate = rates.get(from_currency)
        to_rate = rates.get(to_currency)

        if from_rate is None:
            raise ValueError(f"Unsupported currency: {from_currency}")
        if to_rate is None:
            raise ValueError(f"Unsupported currency: {to_currency}")

        # 计算汇率: rate = to_rate / from_rate
        return to_rate / from_rate

    def convert(
        self,
        amount: float,
        from_currency: str,
        to_currency: str
    ) -> float:
        """
        货币转换

        Args:
            amount: 金额
            from_currency: 源货币
            to_currency: 目标货币

        Returns:
            转换后的金额

        Example:
            >>> manager = CurrencyExchangeRateManager()
            >>> result = manager.convert(100, "USD", "CNY")
            >>> print(result)  # 720.0
        """
        rate = self.get_rate(from_currency, to_currency)
        return amount * rate

    # ==================== 汇率更新 ====================

    def update_rate(
        self,
        currency: str,
        rate: float,
        save: bool = True
    ) -> None:
        """
        更新汇率（所有进程立即可见）

        Args:
            currency: 货币代码
            rate: 新汇率（相对于基准货币）
            save: 是否保存到配置文件

        Raises:
            ValueError: 汇率无效
        """
        if rate <= 0:
            raise ValueError(f"Invalid rate: {rate} (must be > 0)")

        if currency == "USD":
            raise ValueError("Cannot modify USD rate (always 1.0)")

        # 获取当前汇率（用于日志）
        current_rates = self.get_all_rates()
        old_rate = current_rates.get(currency)

        # 更新汇率
        current_rates[currency] = rate

        # 更新存储
        if self._use_redis:
            # Redis 模式：原子更新（所有进程立即可见）
            try:
                self._redis_client.setex(
                    self._redis_key,
                    self._redis_ttl,
                    json.dumps(current_rates)
                )
                logger.info(f"[Currency] Updated {currency} in Redis: {old_rate} -> {rate}")

                # 可选：发布更新事件
                self._publish_update_event(currency, old_rate, rate)

            except Exception as e:
                logger.error(f"[Currency] Failed to update Redis: {e}")
                # Redis 失败不影响文件保存
        else:
            # 文件模式：更新内存缓存
            with self._lock:
                self._rates = current_rates
                self._last_update = datetime.now()
            logger.info(f"[Currency] Updated {currency} in memory: {old_rate} -> {rate}")

        # 保存到配置文件（持久化）
        if save:
            self.save_rates(current_rates)

    def _publish_update_event(self, currency: str, old_rate: Optional[float], new_rate: float):
        """发布汇率更新事件（Redis Pub/Sub）"""
        try:
            event = {
                "currency": currency,
                "old_rate": old_rate,
                "new_rate": new_rate,
                "timestamp": datetime.now().isoformat()
            }
            self._redis_client.publish(
                "litellm:exchange_rate_updates",
                json.dumps(event)
            )
            logger.debug(f"[Currency] Published update event for {currency}")
        except Exception as e:
            logger.warning(f"[Currency] Failed to publish event: {e}")

    def save_rates(self, rates: Optional[Dict[str, float]] = None) -> None:
        """
        保存汇率到配置文件

        Args:
            rates: 要保存的汇率（None 则保存当前汇率）
        """
        if rates is None:
            rates = self.get_all_rates()

        if not self._config_path:
            self._config_path = self._get_config_path()

        config = {
            "version": "1.0",
            "base_currency": self._base_currency,
            "last_updated": datetime.now().isoformat(),
            "rates": rates,
            "metadata": {
                "source": "manual",
                "auto_update_enabled": False,
                "storage_mode": "redis" if self._use_redis else "file"
            }
        }

        try:
            # 原子写入：先写临时文件，再重命名
            temp_path = self._config_path.with_suffix('.tmp')

            self._config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            # 原子重命名（避免读到半写入的文件）
            temp_path.replace(self._config_path)

            logger.info(f"[Currency] Saved {len(rates)} rates to {self._config_path}")

        except Exception as e:
            logger.error(f"[Currency] Error saving rates: {e}")
            raise

    # ==================== 辅助方法 ====================

    def get_supported_currencies(self) -> list:
        """获取支持的货币列表"""
        rates = self.get_all_rates()
        return list(rates.keys())

    def reload(self) -> None:
        """强制重新加载汇率"""
        logger.info("[Currency] Manual reload triggered")
        self.load_rates(force=True)

    def reload_rates(self) -> None:
        """Alias for reload() - 用于API端点"""
        self.reload()

    def get_last_updated_time(self) -> Optional[datetime]:
        """获取最后更新时间"""
        if self._use_redis:
            # Redis 模式：尝试从 Redis 获取时间戳
            try:
                timestamp_key = f"{self._redis_key}:timestamp"
                timestamp_str = self._redis_client.get(timestamp_key)
                if timestamp_str:
                    return datetime.fromisoformat(timestamp_str)
            except Exception as e:
                logger.debug(f"[Currency] Failed to get Redis timestamp: {e}")

        # 返回内存中的最后更新时间
        return self._last_update

    def update_rates(self, rates: Dict[str, float]) -> None:
        """
        更新汇率到配置文件

        Args:
            rates: 货币代码到汇率的映射（相对于 USD）
        """
        if not self._config_path:
            self._config_path = self._get_config_path()

        try:
            # 1. 读取现有配置
            existing_config = {}
            if self._config_path.exists():
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    existing_config = json.load(f)

            # 2. 更新汇率
            if "rates" not in existing_config:
                existing_config["rates"] = {}

            existing_config["rates"].update(rates)
            existing_config["last_updated"] = datetime.now().isoformat()

            # 3. 写入文件
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(existing_config, f, indent=2, ensure_ascii=False)

            logger.info(f"[Currency] Updated {len(rates)} rates to file")

            # 4. 如果使用 Redis，更新 Redis 缓存
            if self._use_redis:
                self._update_redis_cache(existing_config["rates"])
                # 同时更新时间戳
                try:
                    timestamp_key = f"{self._redis_key}:timestamp"
                    self._redis_client.setex(
                        timestamp_key,
                        self._redis_ttl,
                        existing_config["last_updated"]
                    )
                except Exception as e:
                    logger.warning(f"[Currency] Failed to update Redis timestamp: {e}")

            # 5. 更新内存缓存
            with self._lock:
                self._rates = existing_config["rates"]
                self._last_update = datetime.now()

        except Exception as e:
            logger.error(f"[Currency] Failed to update rates: {e}")
            raise

    def load_rates(self, force: bool = False) -> None:
        """加载汇率（兼容旧接口）"""
        if force:
            if self._use_redis:
                # Redis 模式：清除缓存并重新加载
                rates = self._load_from_file()
                self._update_redis_cache(rates)
            else:
                # 文件模式：重新加载文件
                with self._lock:
                    self._rates = self._load_from_file()
                    self._last_update = datetime.now()

    def get_stats(self) -> dict:
        """获取管理器状态"""
        return {
            "mode": "redis" if self._use_redis else "file",
            "currencies": len(self.get_all_rates()),
            "last_update": self._last_update.isoformat() if self._last_update else None,
            "redis_connected": self._use_redis and self._redis_client is not None,
            "file_watcher_active": self._observer is not None
        }

    def __del__(self):
        """清理资源"""
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join()
            except:
                pass


# ==================== 便捷函数 ====================

def convert_currency(
    amount: float,
    from_currency: str = "USD",
    to_currency: str = "USD"
) -> float:
    """
    货币转换便捷函数

    Args:
        amount: 金额
        from_currency: 源货币
        to_currency: 目标货币

    Returns:
        转换后的金额

    Example:
        >>> from litellm.litellm_core_utils.currency import convert_currency
        >>> result = convert_currency(100, "USD", "CNY")
        >>> print(result)  # 720.0
    """
    manager = CurrencyExchangeRateManager()
    return manager.convert(amount, from_currency, to_currency)


def get_exchange_rate(
    from_currency: str,
    to_currency: str
) -> float:
    """
    获取汇率便捷函数

    Args:
        from_currency: 源货币
        to_currency: 目标货币

    Returns:
        汇率值
    """
    manager = CurrencyExchangeRateManager()
    return manager.get_rate(from_currency, to_currency)


def reload_exchange_rates() -> None:
    """重新加载汇率配置"""
    manager = CurrencyExchangeRateManager()
    manager.reload()


def get_manager_stats() -> dict:
    """获取管理器状态"""
    manager = CurrencyExchangeRateManager()
    return manager.get_stats()
