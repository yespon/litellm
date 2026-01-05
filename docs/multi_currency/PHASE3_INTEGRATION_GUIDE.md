# Phase 3 集成指南：货币感知计费系统

## 日期：2026-01-04

## 概述

Phase 3 为 LiteLLM Proxy 的计费系统添加了多货币支持，保持向后兼容的同时支持用户自定义货币。

**关键原则**:
- ✅ 所有内部计算保持 USD（不修改 `cost_calculator.py`）
- ✅ 在记录到数据库时进行货币转换
- ✅ 完整的审计追踪（记录原始金额、汇率等）
- ✅ 向后兼容（默认所有实体使用 USD）

## 已完成的工作

### 1. 货币辅助模块

**文件**: `litellm/proxy/utils/currency_helper.py`

**核心类**: `CurrencyHelper`

**功能**:
- `get_entity_currency()` - 从用户/团队/API Key 获取配置的货币
- `convert_spend_to_entity_currency()` - USD → 目标货币转换
- `prepare_spend_log_with_currency()` - 构建完整货币信息的 spend 记录
- `get_budget_in_usd()` - 将预算转换为 USD（用于预算检查）
- `compare_spend_to_budget()` - 跨货币预算比较

## 集成点（待实现）

### 集成点 1: 数据库 Spend 写入

**文件**: `litellm/proxy/db/db_spend_update_writer.py`

**函数**: `DBSpendUpdateWriter.update_database()`

**修改位置**: 第 76-90 行

**修改前**:
```python
async def update_database(
    self,
    token: Optional[str],
    user_id: Optional[str],
    end_user_id: Optional[str],
    team_id: Optional[str],
    org_id: Optional[str],
    kwargs: Optional[dict],
    completion_response: Optional[Union[litellm.ModelResponse, Any, Exception]],
    start_time: Optional[datetime],
    end_time: Optional[datetime],
    response_cost: Optional[float],  # 这是 USD 金额
):
    # ... 现有代码 ...
```

**修改后（集成货币支持）**:
```python
from litellm.proxy.utils.currency_helper import get_currency_helper

async def update_database(
    self,
    token: Optional[str],
    user_id: Optional[str],
    end_user_id: Optional[str],
    team_id: Optional[str],
    org_id: Optional[str],
    kwargs: Optional[dict],
    completion_response: Optional[Union[litellm.ModelResponse, Any, Exception]],
    start_time: Optional[datetime],
    end_time: Optional[datetime],
    response_cost: Optional[float],  # USD 金额
):
    currency_helper = get_currency_helper()

    # 1. 获取实体配置的货币
    # 需要从数据库查询 user/team/token 的货币配置
    # 优先级: token.spend_currency > team.spend_currency > user.spend_currency > USD

    entity_currency = "USD"  # 默认
    entity_data = None

    # 获取实体数据（示例）
    if token and prisma_client:
        from litellm.proxy.utils import hash_token
        hashed_token = hash_token(token)
        token_data = user_api_key_cache.get_cache(key=hashed_token)
        if token_data:
            entity_currency = currency_helper.get_entity_currency(
                token_data, entity_type="token"
            )
            entity_data = token_data

    # 2. 转换成本到实体货币
    currency_info = currency_helper.prepare_spend_log_with_currency(
        cost_usd=response_cost or 0.0,
        target_currency=entity_currency,
    )

    # 3. 使用转换后的金额和货币信息
    converted_cost = currency_info["spend"]
    spend_currency = currency_info["spend_currency"]
    exchange_rate = currency_info.get("exchange_rate")

    # ... 继续使用 converted_cost 进行数据库更新 ...
```

### 集成点 2: SpendLogs 记录

**文件**: `litellm/proxy/db/db_spend_update_writer.py`

**函数**: 构建 `SpendLogsPayload`（大约第 150-200 行）

**修改说明**: 在创建 spend log 时添加货币字段

**示例代码**:
```python
# 构建 spend log payload
spend_log_payload = SpendLogsPayload(
    request_id=request_id,
    call_type=call_type,
    api_key=hashed_token,
    spend=converted_cost,  # 使用转换后的金额
    spend_currency=spend_currency,  # 新增：记录货币
    model_currency=None,  # 新增：模型提供商原始货币（未来扩展）
    spend_original=response_cost,  # 新增：USD 原始金额
    exchange_rate=exchange_rate,  # 新增：使用的汇率
    # ... 其他字段 ...
)
```

### 集成点 3: 每日 Spend 统计更新

**文件**: `litellm/proxy/db/db_spend_update_writer.py`

**涉及的数据结构**:
- `DailyUserSpendTransaction`
- `DailyTeamSpendTransaction`
- `DailyEndUserSpendTransaction`
- `DailyAgentSpendTransaction`
- `DailyOrganizationSpendTransaction`
- `DailyTagSpendTransaction`

**修改位置**: 创建这些 transaction 对象时

**修改示例**:
```python
# 原始代码（简化）
daily_spend_transaction = DailyUserSpendTransaction(
    user_id=user_id,
    date=today_str,
    spend=response_cost,  # 原本直接使用 USD
    # ...
)

# 修改后
daily_spend_transaction = DailyUserSpendTransaction(
    user_id=user_id,
    date=today_str,
    spend=converted_cost,  # 使用转换后的金额
    spend_currency=spend_currency,  # 新增字段
    # ...
)
```

### 集成点 4: 预算检查

**文件**: `litellm/proxy/auth/route_checks.py`

**函数**: `RouteChecks.check_budget()` 等预算检查函数

**修改说明**: 比较 spend 和 budget 时需要处理不同货币

**示例代码**:
```python
from litellm.proxy.utils.currency_helper import get_currency_helper

def check_budget(
    user_max_budget: float,
    user_budget_currency: str,
    user_current_spend: float,
    user_spend_currency: str,
):
    currency_helper = get_currency_helper()

    is_over, remaining = currency_helper.compare_spend_to_budget(
        spend_amount=user_current_spend,
        spend_currency=user_spend_currency,
        budget_amount=user_max_budget,
        budget_currency=user_budget_currency,
    )

    if is_over:
        raise Exception(f"Budget exceeded. Remaining: ${remaining:.2f} USD")
```

### 集成点 5: API Key/User/Team 创建时设置默认货币

**文件**:
- `litellm/proxy/management_endpoints/key_management_endpoints.py`
- `litellm/proxy/management_endpoints/team_endpoints.py`
- `litellm/proxy/management_endpoints/internal_user_endpoints.py`

**修改说明**: 创建新实体时，允许指定 `budget_currency` 和 `spend_currency`

**示例**:
```python
# 创建 API Key
async def create_key(
    data: GenerateKeyRequest,
):
    # ... 现有代码 ...

    # 新增：允许设置货币
    budget_currency = data.budget_currency or "USD"
    spend_currency = data.spend_currency or "USD"

    await prisma_client.litellm_verificationtoken.create(
        data={
            "token": token,
            "max_budget": max_budget,
            "budget_currency": budget_currency,  # 新增
            "spend_currency": spend_currency,   # 新增
            # ... 其他字段 ...
        }
    )
```

## 数据类型修改

### 更新 _types.py 中的数据结构

**文件**: `litellm/proxy/_types.py`

**需要添加货币字段**:

```python
class SpendLogsPayload(TypedDict, total=False):
    # 现有字段 ...
    spend: float

    # 新增字段
    spend_currency: str
    model_currency: Optional[str]
    spend_original: Optional[float]
    exchange_rate: Optional[float]

class DailyUserSpendTransaction(BaseDailySpendTransaction):
    # 现有字段 ...
    spend: float

    # 新增字段
    spend_currency: str  # 默认 "USD"
```

## 向后兼容策略

1. **默认值**: 所有新增货币字段默认为 `"USD"`
2. **渐进迁移**: 现有数据无需修改，新记录自动使用 USD
3. **降级处理**: 如果货币转换失败，自动回退到 USD
4. **可选特性**: 用户可以选择是否启用多货币功能

## 测试策略

### 单元测试

创建 `tests/proxy_tests/test_currency_helper.py`:

```python
import pytest
from litellm.proxy.utils.currency_helper import CurrencyHelper

def test_get_entity_currency():
    helper = CurrencyHelper()

    # 测试默认 USD
    assert helper.get_entity_currency(None) == "USD"

    # 测试从字典获取
    entity = {"spend_currency": "CNY"}
    assert helper.get_entity_currency(entity) == "CNY"

def test_convert_spend():
    helper = CurrencyHelper()

    # USD -> CNY
    converted, rate = helper.convert_spend_to_entity_currency(100.0, "CNY")
    assert converted > 100  # CNY 应该比 USD 多
    assert rate > 1.0

    # USD -> USD（无转换）
    converted, rate = helper.convert_spend_to_entity_currency(100.0, "USD")
    assert converted == 100.0
    assert rate == 1.0

def test_prepare_spend_log():
    helper = CurrencyHelper()

    log_data = helper.prepare_spend_log_with_currency(
        cost_usd=50.0,
        target_currency="EUR",
    )

    assert "spend" in log_data
    assert "spend_currency" in log_data
    assert log_data["spend_currency"] == "EUR"
    assert "exchange_rate" in log_data
```

### 集成测试

创建 `tests/proxy_tests/test_multi_currency_integration.py`:

```python
import pytest
from litellm.proxy.proxy_server import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_create_key_with_currency():
    """测试创建带有自定义货币的 API Key"""
    response = client.post(
        "/key/generate",
        json={
            "max_budget": 100.0,
            "budget_currency": "CNY",
            "spend_currency": "CNY",
        },
        headers={"Authorization": "Bearer sk-master-key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["budget_currency"] == "CNY"
    assert data["spend_currency"] == "CNY"

def test_spend_tracking_with_currency():
    """测试消费追踪使用正确的货币"""
    # 1. 创建 CNY 货币的 key
    # 2. 使用该 key 完成请求
    # 3. 检查 spend log 中的货币字段
    pass
```

## 迁移清单

- [ ] 执行数据库迁移 (`migrations/add_currency_support.sql`)
- [ ] 运行 `poetry run prisma generate` 更新 Prisma Client
- [ ] 集成 `currency_helper.py` 到 `db_spend_update_writer.py`
- [ ] 更新 `_types.py` 添加货币字段
- [ ] 修改 API Key/User/Team 创建端点支持货币参数
- [ ] 更新预算检查逻辑支持多货币比较
- [ ] 编写单元测试和集成测试
- [ ] 更新 API 文档说明货币字段

## 风险和注意事项

### 高风险区域
1. **`db_spend_update_writer.py`**: 核心计费逻辑，修改需谨慎
2. **预算检查**: 错误的货币比较可能导致预算控制失效
3. **性能**: 每次写入都需要查询实体货币配置

### 缓解措施
1. **完整测试**: 覆盖所有货币组合场景
2. **日志记录**: 详细记录所有货币转换操作
3. **降级机制**: 转换失败时自动回退到 USD
4. **缓存优化**: 缓存实体的货币配置
5. **分阶段发布**: 先在小范围测试环境验证

## 性能优化

### 缓存策略
```python
# 在 user_api_key_cache 中缓存货币信息
# 避免每次请求都查询数据库

def get_cached_entity_currency(token: str) -> str:
    cached_data = user_api_key_cache.get_cache(key=hash_token(token))
    if cached_data and "spend_currency" in cached_data:
        return cached_data["spend_currency"]
    return "USD"
```

## 下一步：Phase 4

Phase 4 将实现 Management API 端点：
- `POST /key/generate` - 支持 `budget_currency`、`spend_currency` 参数
- `GET /key/info` - 返回货币信息
- `PUT /team/update` - 更新团队货币配置
- `GET /spend/logs` - 按货币筛选和聚合
- `POST /currency/rates` - 管理员更新汇率

## 参考资料

- Phase 1: `litellm/litellm_core_utils/currency.py`
- Phase 2: `docs/multi_currency/PHASE2_SUMMARY.md`
- 设计文档: `docs/multi_currency/06_PHASE2_DATA_MODEL_DESIGN.md`
