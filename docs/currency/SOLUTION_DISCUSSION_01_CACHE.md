# 多货币支持 - 修复方案技术讨论

> **讨论日期**: 2026-01-04
> **参与者**: 技术团队
> **目标**: 确定三个严重问题的最佳修复方案

---

## 🔴 问题 #1: 汇率缓存一致性问题

### 问题描述

**场景**: LiteLLM Proxy 使用 Uvicorn 多进程模式运行

```bash
# 典型的生产部署
uvicorn litellm.proxy.proxy_server:app --workers 4 --host 0.0.0.0 --port 4001
```

**当前设计的问题**:
```python
class CurrencyExchangeRateManager:
    _instance = None
    _rates: Dict[str, float] = {}  # ❌ 类变量，每个进程独立

    # 进程 1: _rates = {"USD": 1.0, "CNY": 7.2}
    # 进程 2: _rates = {"USD": 1.0, "CNY": 7.2}
    # 进程 3: _rates = {"USD": 1.0, "CNY": 7.2}
    # 进程 4: _rates = {"USD": 1.0, "CNY": 7.2}

    # 管理员更新汇率（只更新了处理该请求的进程 1）
    # 进程 1: _rates = {"USD": 1.0, "CNY": 7.25} ✓ 已更新
    # 进程 2: _rates = {"USD": 1.0, "CNY": 7.2}  ✗ 未更新
    # 进程 3: _rates = {"USD": 1.0, "CNY": 7.2}  ✗ 未更新
    # 进程 4: _rates = {"USD": 1.0, "CNY": 7.2}  ✗ 未更新
```

**影响**:
- 同一时间，不同用户请求可能使用不同汇率
- 费用计算不一致
- 用户困惑（为什么我的费用和别人不一样？）

---

## 方案对比

### 方案 A: Redis 分布式缓存 ⭐ 推荐

#### 架构图

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Worker 1   │  │  Worker 2   │  │  Worker 3   │  │  Worker 4   │
│             │  │             │  │             │  │             │
│  Manager ───┼──┼─ Manager ───┼──┼─ Manager ───┼──┼─ Manager   │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │                │
       └────────────────┴────────────────┴────────────────┘
                               │
                               ▼
                      ┌─────────────────┐
                      │  Redis (共享)    │
                      │  exchange_rates │
                      │  {              │
                      │   "USD": 1.0,   │
                      │   "CNY": 7.25   │
                      │  }              │
                      └─────────────────┘
```

#### 实现代码

```python
"""
汇率管理器 - Redis 版本
"""
import json
import redis
from typing import Dict, Optional
from functools import wraps
import os

def with_redis_fallback(func):
    """Redis 故障时降级到文件"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except redis.RedisError as e:
            self._logger.warning(f"Redis error, using file fallback: {e}")
            return self._fallback_to_file(*args, **kwargs)
    return wrapper

class CurrencyExchangeRateManager:
    """汇率管理器 - Redis 分布式缓存版本"""

    _instance = None
    _redis_client: Optional[redis.Redis] = None
    _cache_key = "litellm:exchange_rates:v1"
    _cache_ttl = 3600  # 1小时

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化 Redis 连接"""
        if self._redis_client is None:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

            # 连接配置
            self._redis_client = redis.from_url(
                redis_url,
                decode_responses=True,  # 自动解码为字符串
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )

            # 测试连接
            try:
                self._redis_client.ping()
                print("[Currency] Redis connected successfully")
            except redis.RedisError as e:
                print(f"[Currency] Redis connection failed: {e}")
                print("[Currency] Will use file-based fallback")

    @with_redis_fallback
    def get_all_rates(self) -> Dict[str, float]:
        """获取所有汇率（优先从 Redis）"""
        # 1. 尝试从 Redis 读取
        cached = self._redis_client.get(self._cache_key)

        if cached:
            rates = json.loads(cached)
            print(f"[Currency] Loaded rates from Redis: {len(rates)} currencies")
            return rates

        # 2. Redis 未命中，从文件加载
        print("[Currency] Redis cache miss, loading from file")
        rates = self._load_from_file()

        # 3. 更新 Redis 缓存
        self._update_redis_cache(rates)

        return rates

    def _update_redis_cache(self, rates: Dict[str, float]):
        """更新 Redis 缓存"""
        try:
            # 使用 SETEX 原子设置值和过期时间
            self._redis_client.setex(
                self._cache_key,
                self._cache_ttl,
                json.dumps(rates)
            )
            print("[Currency] Updated Redis cache")
        except redis.RedisError as e:
            print(f"[Currency] Failed to update Redis: {e}")

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
            rate: 新汇率
            save: 是否保存到配置文件
        """
        if rate <= 0:
            raise ValueError(f"Invalid rate: {rate}")

        # 1. 获取当前汇率（用于审计）
        current_rates = self.get_all_rates()
        old_rate = current_rates.get(currency)

        # 2. 更新汇率
        current_rates[currency] = rate

        # 3. 原子更新 Redis（所有进程立即可见）
        try:
            # 使用 Redis 事务确保原子性
            pipe = self._redis_client.pipeline()
            pipe.setex(
                self._cache_key,
                self._cache_ttl,
                json.dumps(current_rates)
            )
            pipe.execute()

            print(f"[Currency] Updated {currency} rate: {old_rate} -> {rate}")

        except redis.RedisError as e:
            print(f"[Currency] Redis update failed: {e}")
            # Redis 失败不影响功能，继续保存到文件

        # 4. 保存到配置文件（持久化）
        if save:
            self.save_rates_to_file(current_rates)

        # 5. 发布更新事件（可选，用于实时通知）
        self._publish_rate_update(currency, old_rate, rate)

    def _publish_rate_update(self, currency: str, old_rate: float, new_rate: float):
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
        except redis.RedisError:
            pass  # 发布失败不影响主流程

    def _fallback_to_file(self) -> Dict[str, float]:
        """Redis 失败时的降级方案"""
        return self._load_from_file()

    def _load_from_file(self) -> Dict[str, float]:
        """从配置文件加载汇率"""
        config_path = self._get_config_path()

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config.get("rates", {"USD": 1.0, "CNY": 7.2})
        except FileNotFoundError:
            print("[Currency] Config file not found, using defaults")
            return {"USD": 1.0, "CNY": 7.2}
        except Exception as e:
            print(f"[Currency] Error loading file: {e}")
            return {"USD": 1.0, "CNY": 7.2}

    def save_rates_to_file(self, rates: Dict[str, float]):
        """保存汇率到配置文件"""
        config_path = self._get_config_path()

        config = {
            "version": "1.0",
            "base_currency": "USD",
            "last_updated": datetime.now().isoformat(),
            "rates": rates,
            "metadata": {
                "source": "manual",
                "auto_update_enabled": False
            }
        }

        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            print(f"[Currency] Saved rates to {config_path}")
        except Exception as e:
            print(f"[Currency] Error saving file: {e}")

    def _get_config_path(self):
        """获取配置文件路径"""
        from pathlib import Path
        env_path = os.getenv("CURRENCY_EXCHANGE_RATE_FILE")
        if env_path:
            return Path(env_path)
        return Path(__file__).parent.parent.parent / "currency_exchange_rates.json"

    # 其他方法（get_rate, convert 等）保持不变...
```

#### 优点

✅ **进程间一致性**: 所有进程共享同一份汇率数据
✅ **实时更新**: 更新立即对所有进程可见（<1ms）
✅ **高性能**: Redis 读取极快（~0.1ms）
✅ **可靠降级**: Redis 故障时自动降级到文件
✅ **支持 Pub/Sub**: 可实现实时通知

#### 缺点

❌ **依赖 Redis**: 需要额外的基础设施
❌ **复杂度增加**: 需要维护 Redis 连接
❌ **成本**: Redis 服务器资源

#### 适用场景

- ✅ 生产环境多进程部署
- ✅ 需要高性能和强一致性
- ✅ 已有 Redis 基础设施
- ✅ 团队熟悉 Redis

---

### 方案 B: 文件监控 + 信号通知

#### 架构图

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Worker 1   │  │  Worker 2   │  │  Worker 3   │  │  Worker 4   │
│             │  │             │  │             │  │             │
│  Manager    │  │  Manager    │  │  Manager    │  │  Manager    │
│  + Watcher  │  │  + Watcher  │  │  + Watcher  │  │  + Watcher  │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │                │
       └────────────────┴────────────────┴────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  currency_rates.json │
                    │  (文件系统)           │
                    └──────────────────────┘
```

#### 实现代码

```python
"""
汇率管理器 - 文件监控版本
"""
import json
import os
from pathlib import Path
from threading import Thread, Lock
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime, timedelta
from typing import Dict, Optional

class RateFileHandler(FileSystemEventHandler):
    """汇率配置文件监控器"""

    def __init__(self, manager):
        self.manager = manager
        self._debounce_timer = None
        self._lock = Lock()

    def on_modified(self, event):
        """文件修改时触发"""
        if event.src_path == str(self.manager._config_path):
            # 防抖：避免多次触发
            with self._lock:
                if self._debounce_timer:
                    self._debounce_timer.cancel()

                # 延迟 100ms 后重载
                self._debounce_timer = Timer(0.1, self._reload_rates)
                self._debounce_timer.start()

    def _reload_rates(self):
        """重新加载汇率"""
        print("[Currency] Config file changed, reloading...")
        self.manager.load_rates(force=True)

class CurrencyExchangeRateManager:
    """汇率管理器 - 文件监控版本"""

    _instance = None
    _rates: Dict[str, float] = {}
    _last_update: Optional[datetime] = None
    _cache_ttl: int = 60  # 缩短为 1 分钟（作为安全网）
    _config_path: Optional[Path] = None
    _observer: Optional[Observer] = None
    _lock = Lock()  # 线程锁

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化文件监控"""
        if self._observer is None:
            self._config_path = self._get_config_path()
            self._start_file_watcher()
            self._start_periodic_refresh()
            self.load_rates(force=True)

    def _start_file_watcher(self):
        """启动文件监控"""
        try:
            event_handler = RateFileHandler(self)
            self._observer = Observer()

            # 监控配置文件所在目录
            watch_path = self._config_path.parent
            self._observer.schedule(
                event_handler,
                str(watch_path),
                recursive=False
            )

            self._observer.start()
            print(f"[Currency] File watcher started on {watch_path}")

        except Exception as e:
            print(f"[Currency] Failed to start file watcher: {e}")
            # 文件监控失败不影响功能，依赖定期刷新

    def _start_periodic_refresh(self):
        """启动定期刷新（作为文件监控的备份）"""
        def refresh_loop():
            while True:
                time.sleep(300)  # 每 5 分钟刷新一次
                if not self._is_cache_valid():
                    print("[Currency] Periodic refresh triggered")
                    self.load_rates(force=True)

        refresh_thread = Thread(target=refresh_loop, daemon=True)
        refresh_thread.start()
        print("[Currency] Periodic refresh started (every 5 min)")

    def load_rates(self, force: bool = False) -> None:
        """加载汇率（线程安全）"""
        with self._lock:
            # 检查缓存
            if not force and self._is_cache_valid():
                return

            # 从文件加载
            try:
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                self._rates = config.get("rates", {"USD": 1.0, "CNY": 7.2})
                self._last_update = datetime.now()

                print(f"[Currency] Loaded {len(self._rates)} exchange rates")

            except FileNotFoundError:
                print("[Currency] Config file not found, using defaults")
                self._rates = {"USD": 1.0, "CNY": 7.2}
                self._last_update = datetime.now()

            except Exception as e:
                print(f"[Currency] Error loading rates: {e}")
                if not self._rates:
                    self._rates = {"USD": 1.0, "CNY": 7.2}

    def update_rate(
        self,
        currency: str,
        rate: float,
        save: bool = True
    ) -> None:
        """
        更新汇率（通过文件触发所有进程更新）

        注意：更新会有短暂延迟（100ms - 5min）
        """
        if rate <= 0:
            raise ValueError(f"Invalid rate: {rate}")

        with self._lock:
            # 更新内存
            old_rate = self._rates.get(currency)
            self._rates[currency] = rate

        # 保存到文件（触发文件监控）
        if save:
            self.save_rates_to_file(self._rates)
            # 文件监控会在 ~100ms 内触发其他进程重载

        print(f"[Currency] Updated {currency}: {old_rate} -> {rate}")

    def save_rates_to_file(self, rates: Dict[str, float]):
        """保存汇率到配置文件（原子写入）"""
        config = {
            "version": "1.0",
            "base_currency": "USD",
            "last_updated": datetime.now().isoformat(),
            "rates": rates,
            "metadata": {
                "source": "manual",
                "auto_update_enabled": False
            }
        }

        try:
            # 原子写入：先写临时文件，再重命名
            temp_path = self._config_path.with_suffix('.tmp')

            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            # 原子重命名（避免读到半写入的文件）
            temp_path.replace(self._config_path)

            print(f"[Currency] Saved rates to {self._config_path}")

        except Exception as e:
            print(f"[Currency] Error saving file: {e}")
            raise

    def __del__(self):
        """清理资源"""
        if self._observer:
            self._observer.stop()
            self._observer.join()

    # 其他方法保持不变...
```

#### 优点

✅ **无额外依赖**: 不需要 Redis 等外部服务
✅ **简单易维护**: 基于文件系统，容易理解
✅ **成本低**: 无额外基础设施成本
✅ **部署简单**: 无需配置外部服务

#### 缺点

❌ **延迟**: 更新传播有延迟（100ms - 5min）
❌ **依赖文件系统**: 在某些云环境可能不可靠
❌ **性能**: 文件 I/O 比 Redis 慢
❌ **并发**: 高并发下文件锁可能成为瓶颈

#### 适用场景

- ✅ 小规模部署（<10个进程）
- ✅ 汇率更新不频繁
- ✅ 对更新延迟不敏感
- ✅ 无 Redis 基础设施

---

### 方案 C: HTTP 轮询 + 内存缓存

#### 架构图

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Worker 1   │  │  Worker 2   │  │  Worker 3   │  │  Worker 4   │
│  (定时轮询) │  │  (定时轮询) │  │  (定时轮询) │  │  (定时轮询) │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │                │
       └────────────────┴────────────────┴────────────────┘
                               │
                    每 10 秒请求一次（stagger）
                               │
                               ▼
                    ┌──────────────────────┐
                    │ GET /internal/rates  │
                    │ (主进程或共享存储)    │
                    └──────────────────────┘
```

#### 实现代码

```python
"""
汇率管理器 - HTTP 轮询版本
"""
import httpx
import asyncio
from typing import Dict
from datetime import datetime

class CurrencyExchangeRateManager:
    """汇率管理器 - HTTP 轮询版本"""

    _instance = None
    _rates: Dict[str, float] = {}
    _poll_interval = 10  # 10秒轮询一次
    _poll_task = None

    def __init__(self):
        if self._poll_task is None:
            # 启动后台轮询任务
            asyncio.create_task(self._poll_rates())

    async def _poll_rates(self):
        """后台轮询汇率"""
        # 随机延迟启动（避免所有进程同时请求）
        await asyncio.sleep(random.uniform(0, self._poll_interval))

        while True:
            try:
                # 从主进程或共享存储获取汇率
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        "http://localhost:4001/internal/rates",
                        timeout=5.0
                    )

                    if response.status_code == 200:
                        data = response.json()
                        self._rates = data["rates"]
                        print(f"[Currency] Polled rates: {len(self._rates)} currencies")

            except Exception as e:
                print(f"[Currency] Poll error: {e}")

            # 等待下一次轮询
            await asyncio.sleep(self._poll_interval)

    # 其他方法...
```

#### 优点

✅ **无外部依赖**: 使用现有的 HTTP 服务
✅ **明确的同步机制**: 轮询逻辑清晰

#### 缺点

❌ **延迟高**: 最多 10 秒延迟
❌ **网络开销**: 频繁的 HTTP 请求
❌ **复杂**: 需要额外的内部 API
❌ **资源浪费**: 即使汇率不变也要轮询

---

## 方案对比矩阵

| 维度 | Redis (A) | 文件监控 (B) | HTTP 轮询 (C) |
|------|-----------|-------------|--------------|
| **一致性** | ⭐⭐⭐⭐⭐ 实时 | ⭐⭐⭐⭐ 100ms-5min | ⭐⭐⭐ 最多10秒 |
| **性能** | ⭐⭐⭐⭐⭐ ~0.1ms | ⭐⭐⭐ 文件I/O | ⭐⭐ HTTP开销 |
| **可靠性** | ⭐⭐⭐⭐ 可降级 | ⭐⭐⭐⭐⭐ 简单可靠 | ⭐⭐⭐ 依赖HTTP |
| **复杂度** | ⭐⭐⭐ 中等 | ⭐⭐⭐⭐ 较低 | ⭐⭐ 较高 |
| **成本** | ⭐⭐ 需要Redis | ⭐⭐⭐⭐⭐ 无额外成本 | ⭐⭐⭐⭐ 无额外成本 |
| **扩展性** | ⭐⭐⭐⭐⭐ 支持大规模 | ⭐⭐⭐ 中小规模 | ⭐⭐ 小规模 |
| **部署难度** | ⭐⭐⭐ 需配置Redis | ⭐⭐⭐⭐⭐ 最简单 | ⭐⭐⭐ 需要内部API |

---

## 🎯 推荐方案

### 综合推荐：**方案 A (Redis) + 方案 B (文件监控) 混合**

#### 实现策略

```python
class CurrencyExchangeRateManager:
    """混合方案：优先 Redis，降级到文件"""

    def __init__(self):
        # 尝试连接 Redis
        self.use_redis = self._init_redis()

        if not self.use_redis:
            print("[Currency] Redis unavailable, using file-based mode")
            self._init_file_watcher()

    def _init_redis(self) -> bool:
        """初始化 Redis（失败则返回 False）"""
        try:
            redis_url = os.getenv("REDIS_URL")
            if not redis_url:
                return False

            self._redis_client = redis.from_url(redis_url)
            self._redis_client.ping()
            return True
        except:
            return False

    def get_all_rates(self) -> Dict[str, float]:
        """获取汇率（自动选择最佳方案）"""
        if self.use_redis:
            return self._get_from_redis()
        else:
            return self._get_from_file()
```

#### 部署建议

**生产环境**:
```yaml
# docker-compose.yml
services:
  litellm:
    environment:
      REDIS_URL: redis://redis:6379/0  # 启用 Redis

  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data
```

**开发/小规模部署**:
```yaml
services:
  litellm:
    environment:
      # 不设置 REDIS_URL，自动使用文件模式
      CURRENCY_EXCHANGE_RATE_FILE: /app/currency_rates.json
```

---

## 决策建议

### 如果你...

**有 Redis 基础设施** → 选择**方案 A（Redis）**
- 最佳性能和一致性
- 生产环境推荐

**没有 Redis，小规模部署** → 选择**方案 B（文件监控）**
- 简单可靠
- 适合初期使用

**两者都可以** → 选择**混合方案**
- 灵活性最高
- 向后兼容最好

---

下一个问题的讨论准备好了吗？我们可以继续讨论：
- 问题 #2: 货币转换原子性
- 问题 #3: Budget 检查竞态

还是先确定汇率缓存方案？
