# Phase 4: API 端点实现代码

## 📋 目录
- [新增端点实现](#新增端点实现)
- [扩展端点实现](#扩展端点实现)
- [中间件和装饰器](#中间件和装饰器)
- [错误处理](#错误处理)

---

## 新增端点实现

### 文件: `/litellm/proxy/management_endpoints/currency_settings.py` (新建)

```python
"""
货币设置管理端点

提供汇率配置、更新和查询功能
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, List
from datetime import datetime

from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
from litellm.proxy._types import UserAPIKeyAuth
from litellm.utils.currency import (
    CurrencyExchangeRateManager,
    reload_exchange_rates
)
from pydantic import BaseModel, validator

router = APIRouter()

# ==================== 请求/响应模型 ====================

class ExchangeRateInfo(BaseModel):
    """汇率信息响应"""
    base_currency: str
    rates: Dict[str, float]
    last_updated: str
    source: str
    supported_currencies: List[str]


class UpdateExchangeRatesRequest(BaseModel):
    """更新汇率请求"""
    rates: Dict[str, float]

    @validator('rates')
    def validate_rates(cls, v):
        """验证汇率"""
        for currency, rate in v.items():
            if rate <= 0:
                raise ValueError(f"Rate for {currency} must be greater than 0")
            if currency == "USD":
                raise ValueError("Cannot modify USD rate (always 1.0)")
        return v


class UpdateExchangeRatesResponse(BaseModel):
    """更新汇率响应"""
    success: bool
    message: str
    data: Dict


class ReloadExchangeRatesResponse(BaseModel):
    """重新加载汇率响应"""
    success: bool
    message: str
    data: Dict


# ==================== 端点实现 ====================

@router.get(
    "/config/exchange_rates",
    tags=["currency", "config"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=Dict
)
async def get_exchange_rates(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)
):
    """
    获取当前汇率配置

    **权限**: 仅管理员

    **响应示例**:
    ```json
    {
        "success": true,
        "data": {
            "base_currency": "USD",
            "rates": {"USD": 1.0, "CNY": 7.2},
            "last_updated": "2026-01-03T10:00:00Z",
            "source": "manual",
            "supported_currencies": ["USD", "CNY"]
        }
    }
    ```
    """
    # 权限检查
    if user_api_key_dict.user_role != "proxy_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "message": "Only admins can view exchange rates",
                    "type": "auth_error",
                    "code": "403"
                }
            }
        )

    try:
        # 获取汇率管理器
        manager = CurrencyExchangeRateManager()

        # 构建响应
        response_data = {
            "base_currency": "USD",
            "rates": manager.get_all_rates(),
            "last_updated": manager._last_update.isoformat() if manager._last_update else None,
            "source": "manual",
            "supported_currencies": manager.get_supported_currencies()
        }

        return {
            "success": True,
            "data": response_data
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "message": f"Failed to retrieve exchange rates: {str(e)}",
                    "type": "internal_error",
                    "code": "500"
                }
            }
        )


@router.patch(
    "/config/exchange_rates",
    tags=["currency", "config"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=UpdateExchangeRatesResponse
)
async def update_exchange_rates(
    request: UpdateExchangeRatesRequest,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)
):
    """
    更新汇率

    **权限**: 仅管理员

    **请求示例**:
    ```json
    {
        "rates": {
            "CNY": 7.25,
            "EUR": 0.93
        }
    }
    ```

    **响应示例**:
    ```json
    {
        "success": true,
        "message": "Exchange rates updated successfully",
        "data": {
            "updated_rates": {"CNY": 7.25, "EUR": 0.93},
            "updated_at": "2026-01-03T12:30:00Z"
        }
    }
    ```
    """
    # 权限检查
    if user_api_key_dict.user_role != "proxy_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "message": "Only admins can modify exchange rates",
                    "type": "auth_error",
                    "code": "403"
                }
            }
        )

    try:
        # 获取汇率管理器
        manager = CurrencyExchangeRateManager()

        # 更新每个汇率
        for currency, rate in request.rates.items():
            # 验证货币是否支持
            supported = manager.get_supported_currencies()
            if currency not in supported:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": {
                            "message": f"Unsupported currency: {currency}",
                            "type": "validation_error",
                            "code": "400"
                        }
                    }
                )

            manager.update_rate(currency, rate, save=False)

        # 保存到文件
        manager.save_rates()

        # 记录日志
        print(f"[Currency] Admin {user_api_key_dict.get('user_id', 'unknown')} "
              f"updated rates: {request.rates}")

        return UpdateExchangeRatesResponse(
            success=True,
            message="Exchange rates updated successfully",
            data={
                "updated_rates": request.rates,
                "updated_at": datetime.now().isoformat()
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "message": f"Failed to update exchange rates: {str(e)}",
                    "type": "internal_error",
                    "code": "500"
                }
            }
        )


@router.post(
    "/config/exchange_rates/reload",
    tags=["currency", "config"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=ReloadExchangeRatesResponse
)
async def reload_exchange_rates_endpoint(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)
):
    """
    重新加载汇率配置

    **权限**: 仅管理员

    **用途**: 从配置文件重新加载汇率（用于手动修改配置文件后）

    **响应示例**:
    ```json
    {
        "success": true,
        "message": "Exchange rates reloaded successfully",
        "data": {
            "rates_loaded": 5,
            "source": "config_file",
            "loaded_at": "2026-01-03T13:00:00Z"
        }
    }
    ```
    """
    # 权限检查
    if user_api_key_dict.user_role != "proxy_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "message": "Only admins can reload exchange rates",
                    "type": "auth_error",
                    "code": "403"
                }
            }
        )

    try:
        # 强制重新加载
        manager = CurrencyExchangeRateManager()
        manager.load_rates(force=True)

        # 记录日志
        print(f"[Currency] Admin {user_api_key_dict.get('user_id', 'unknown')} "
              f"reloaded exchange rates")

        return ReloadExchangeRatesResponse(
            success=True,
            message="Exchange rates reloaded successfully",
            data={
                "rates_loaded": len(manager.get_all_rates()),
                "source": "config_file",
                "loaded_at": datetime.now().isoformat()
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "message": f"Failed to reload exchange rates: {str(e)}",
                    "type": "internal_error",
                    "code": "500"
                }
            }
        )


@router.get(
    "/config/exchange_rates/supported",
    tags=["currency", "config"],
    response_model=Dict
)
async def get_supported_currencies():
    """
    获取支持的货币列表

    **权限**: 公开（不需要认证）

    **响应示例**:
    ```json
    {
        "success": true,
        "data": {
            "currencies": ["USD", "CNY", "EUR", "GBP", "JPY"],
            "count": 5
        }
    }
    ```
    """
    try:
        manager = CurrencyExchangeRateManager()
        currencies = manager.get_supported_currencies()

        return {
            "success": True,
            "data": {
                "currencies": currencies,
                "count": len(currencies)
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "message": f"Failed to retrieve supported currencies: {str(e)}",
                    "type": "internal_error",
                    "code": "500"
                }
            }
        )
```

---

## 扩展端点实现

### 文件: `/litellm/proxy/management_endpoints/key_management.py` (改动)

#### 1. 扩展密钥生成端点

```python
from litellm.types.router import SupportedCurrency
from pydantic import Field

class GenerateKeyRequest(BaseModel):
    """生成密钥请求 - 扩展版"""
    # ... 现有字段 ...

    # 新增字段
    budget_currency: SupportedCurrency = Field(
        default="USD",
        description="预算货币类型 (USD, CNY, EUR, GBP, JPY)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "duration": "30d",
                "models": ["gpt-4", "gpt-3.5-turbo"],
                "max_budget": 10000.0,
                "budget_currency": "CNY",
                "key_alias": "my-cny-key"
            }
        }


@router.post(
    "/key/generate",
    tags=["key management"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=Dict
)
async def generate_key_fn(
    data: GenerateKeyRequest,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)
):
    """
    生成新密钥（支持多货币预算）

    **新增功能**: 支持设置预算货币
    """
    try:
        # 权限检查
        if user_api_key_dict.user_role != "proxy_admin":
            raise HTTPException(status_code=403)

        # 生成密钥
        from litellm.proxy.utils import generate_key_helper_fn

        new_key = generate_key_helper_fn()

        # 创建数据库记录
        from litellm.proxy.proxy_server import prisma_client

        key_data = {
            "token": new_key,
            "key_name": data.key_name,
            "key_alias": data.key_alias,
            "spend": 0.0,
            "max_budget": data.max_budget,
            "budget_currency": data.budget_currency,  # 新增
            "spend_currency": data.budget_currency,   # 新增
            "expires": data.expires,
            "models": data.models or [],
            "aliases": data.aliases or {},
            "config": data.config or {},
            "user_id": data.user_id,
            "team_id": data.team_id,
            "metadata": data.metadata or {}
        }

        created_key = await prisma_client.db.litellm_verificationtoken.create(
            data=key_data
        )

        # 返回结果
        return {
            "key": created_key.token,
            "key_alias": created_key.key_alias,
            "expires": created_key.expires,
            "max_budget": created_key.max_budget,
            "budget_currency": created_key.budget_currency,
            "spend": created_key.spend,
            "spend_currency": created_key.spend_currency
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate key: {str(e)}"
        )
```

#### 2. 扩展密钥信息端点

```python
@router.get(
    "/key/info",
    tags=["key management"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=Dict
)
async def key_info(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)
):
    """
    获取密钥信息（包含货币转换）

    **新增功能**:
    - 显示 budget_currency 和 spend_currency
    - 如果货币不同，显示转换后的费用
    """
    try:
        from litellm.utils.currency import convert_currency

        # 基本信息
        key_data = {
            "key": user_api_key_dict.token,
            "key_alias": user_api_key_dict.get("key_alias"),
            "spend": user_api_key_dict.spend,
            "spend_currency": user_api_key_dict.get("spend_currency", "USD"),
            "max_budget": user_api_key_dict.get("max_budget"),
            "budget_currency": user_api_key_dict.get("budget_currency", "USD"),
            "expires": user_api_key_dict.get("expires"),
            "models": user_api_key_dict.get("models", []),
            "user_id": user_api_key_dict.get("user_id"),
            "team_id": user_api_key_dict.get("team_id"),
            "metadata": user_api_key_dict.get("metadata", {})
        }

        # 如果 spend 和 budget 货币不同，添加转换后的值
        if key_data["spend_currency"] != key_data["budget_currency"]:
            key_data["spend_in_budget_currency"] = convert_currency(
                key_data["spend"],
                key_data["spend_currency"],
                key_data["budget_currency"]
            )
        else:
            key_data["spend_in_budget_currency"] = key_data["spend"]

        # 计算预算使用百分比
        if key_data["max_budget"]:
            usage_pct = (key_data["spend_in_budget_currency"] / key_data["max_budget"]) * 100
            key_data["budget_usage_percentage"] = round(usage_pct, 2)

        return key_data

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve key info: {str(e)}"
        )
```

#### 3. 扩展费用日志端点

```python
from typing import Optional

@router.get(
    "/spend/logs",
    tags=["spend tracking"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=Dict
)
async def get_spend_logs(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    display_currency: str = "USD",
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)
):
    """
    获取费用日志（支持货币转换）

    **新增参数**:
    - display_currency: 显示货币（可选，默认 USD）

    **响应示例**:
    ```json
    {
        "data": [
            {
                "request_id": "req_123",
                "model": "gpt-4",
                "spend": 0.05,
                "spend_currency": "USD",
                "spend_display": 0.36,
                "display_currency": "CNY",
                "startTime": "2026-01-03T10:00:00Z"
            }
        ],
        "metadata": {
            "exchange_rate": 7.2,
            "total_spend": 0.36,
            "currency": "CNY"
        }
    }
    ```
    """
    try:
        from litellm.proxy.proxy_server import prisma_client
        from litellm.utils.currency import convert_currency, get_exchange_rate
        from datetime import datetime

        # 构建查询条件
        where_clause = {"api_key": user_api_key_dict.token}

        if start_date:
            where_clause["startTime"] = {"gte": datetime.fromisoformat(start_date)}
        if end_date:
            if "startTime" in where_clause:
                where_clause["startTime"]["lte"] = datetime.fromisoformat(end_date)
            else:
                where_clause["startTime"] = {"lte": datetime.fromisoformat(end_date)}

        # 查询日志
        logs = await prisma_client.db.litellm_spendlogs.find_many(
            where=where_clause,
            take=100,
            order={"startTime": "desc"}
        )

        # 处理货币转换
        exchange_rate = 1.0
        total_spend_display = 0.0

        if display_currency != "USD":
            exchange_rate = get_exchange_rate("USD", display_currency)

        processed_logs = []
        for log in logs:
            log_dict = log.dict()

            # 转换货币
            if display_currency != log_dict.get("spend_currency", "USD"):
                spend_display = convert_currency(
                    log_dict["spend"],
                    log_dict.get("spend_currency", "USD"),
                    display_currency
                )
                log_dict["spend_display"] = spend_display
                log_dict["display_currency"] = display_currency
            else:
                log_dict["spend_display"] = log_dict["spend"]
                log_dict["display_currency"] = display_currency

            total_spend_display += log_dict["spend_display"]
            processed_logs.append(log_dict)

        # 返回结果
        return {
            "data": processed_logs,
            "metadata": {
                "exchange_rate": exchange_rate,
                "total_spend": round(total_spend_display, 4),
                "currency": display_currency,
                "count": len(processed_logs)
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve spend logs: {str(e)}"
        )
```

---

## 中间件和装饰器

### 文件: `/litellm/proxy/utils/currency_middleware.py` (新建)

```python
"""
货币处理中间件

自动处理请求/响应中的货币信息
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
from litellm.utils.currency import CurrencyExchangeRateManager

class CurrencyMiddleware(BaseHTTPMiddleware):
    """货币处理中间件"""

    async def dispatch(self, request: Request, call_next: Callable):
        """
        处理请求并注入货币信息

        功能:
        1. 预加载汇率（确保缓存可用）
        2. 在请求上下文中添加货币管理器
        """
        # 预加载汇率
        manager = CurrencyExchangeRateManager()
        manager.load_rates()

        # 将管理器添加到请求状态
        request.state.currency_manager = manager

        # 继续处理请求
        response = await call_next(request)

        # 添加货币相关响应头
        response.headers["X-Currency-Base"] = "USD"
        response.headers["X-Currency-Version"] = "1.0"

        return response


def with_currency_conversion(target_currency: str = "USD"):
    """
    装饰器：自动转换响应中的货币

    使用示例:
    @router.get("/cost")
    @with_currency_conversion(target_currency="CNY")
    async def get_cost():
        return {"cost": 100, "currency": "USD"}
        # 自动转换为: {"cost": 720, "currency": "CNY"}
    """
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            from litellm.utils.currency import convert_currency

            # 调用原函数
            result = await func(*args, **kwargs)

            # 如果结果包含 cost 和 currency，进行转换
            if isinstance(result, dict) and "cost" in result and "currency" in result:
                original_currency = result["currency"]
                if original_currency != target_currency:
                    result["cost"] = convert_currency(
                        result["cost"],
                        original_currency,
                        target_currency
                    )
                    result["currency"] = target_currency
                    result["original_cost"] = result.get("cost")
                    result["original_currency"] = original_currency

            return result

        return wrapper
    return decorator
```

---

## 错误处理

### 文件: `/litellm/proxy/utils/currency_errors.py` (新建)

```python
"""
货币相关错误定义
"""

from fastapi import HTTPException, status

class CurrencyError(Exception):
    """货币相关错误基类"""
    pass


class UnsupportedCurrencyError(CurrencyError):
    """不支持的货币"""

    def __init__(self, currency: str):
        self.currency = currency
        self.message = f"Unsupported currency: {currency}"
        super().__init__(self.message)

    def to_http_exception(self):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "message": self.message,
                    "type": "validation_error",
                    "code": "UNSUPPORTED_CURRENCY",
                    "currency": self.currency
                }
            }
        )


class CurrencyConversionError(CurrencyError):
    """货币转换错误"""

    def __init__(self, from_currency: str, to_currency: str, reason: str = ""):
        self.from_currency = from_currency
        self.to_currency = to_currency
        self.reason = reason
        self.message = f"Failed to convert {from_currency} to {to_currency}"
        if reason:
            self.message += f": {reason}"
        super().__init__(self.message)

    def to_http_exception(self):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "message": self.message,
                    "type": "conversion_error",
                    "code": "CURRENCY_CONVERSION_FAILED",
                    "from_currency": self.from_currency,
                    "to_currency": self.to_currency
                }
            }
        )


class ExchangeRateNotFoundError(CurrencyError):
    """汇率未找到"""

    def __init__(self, currency: str):
        self.currency = currency
        self.message = f"Exchange rate not found for currency: {currency}"
        super().__init__(self.message)

    def to_http_exception(self):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "message": self.message,
                    "type": "not_found_error",
                    "code": "EXCHANGE_RATE_NOT_FOUND",
                    "currency": self.currency
                }
            }
        )


class InvalidExchangeRateError(CurrencyError):
    """无效的汇率"""

    def __init__(self, currency: str, rate: float, reason: str = ""):
        self.currency = currency
        self.rate = rate
        self.reason = reason
        self.message = f"Invalid exchange rate for {currency}: {rate}"
        if reason:
            self.message += f" ({reason})"
        super().__init__(self.message)

    def to_http_exception(self):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "message": self.message,
                    "type": "validation_error",
                    "code": "INVALID_EXCHANGE_RATE",
                    "currency": self.currency,
                    "rate": self.rate
                }
            }
        )


def handle_currency_error(error: Exception) -> HTTPException:
    """
    统一处理货币相关错误

    Args:
        error: 错误对象

    Returns:
        HTTPException
    """
    if isinstance(error, CurrencyError):
        return error.to_http_exception()
    elif isinstance(error, ValueError):
        # 处理通用 ValueError
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "message": str(error),
                    "type": "validation_error",
                    "code": "INVALID_INPUT"
                }
            }
        )
    else:
        # 其他错误
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "message": "Internal server error",
                    "type": "internal_error",
                    "code": "INTERNAL_ERROR"
                }
            }
        )
```

---

## 路由注册

### 文件: `/litellm/proxy/proxy_server.py` (添加路由)

```python
# 在 app 初始化后添加
from litellm.proxy.management_endpoints.currency_settings import router as currency_router
from litellm.proxy.utils.currency_middleware import CurrencyMiddleware

# 添加货币路由
app.include_router(currency_router)

# 添加货币中间件
app.add_middleware(CurrencyMiddleware)
```

---

## 完整测试示例

### 文件: `/tests/proxy_unit_tests/test_currency_endpoints.py`

```python
"""
货币端点集成测试
"""

import pytest
from fastapi.testclient import TestClient
from litellm.proxy.proxy_server import app

client = TestClient(app)

# 管理员 token（需要在测试环境中设置）
ADMIN_TOKEN = "sk-1234"

class TestCurrencyEndpoints:
    """货币端点测试"""

    def test_get_exchange_rates(self):
        """测试获取汇率"""
        response = client.get(
            "/config/exchange_rates",
            headers={"Authorization": f"Bearer {ADMIN_TOKEN}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "rates" in data["data"]
        assert "USD" in data["data"]["rates"]

    def test_update_exchange_rates(self):
        """测试更新汇率"""
        response = client.patch(
            "/config/exchange_rates",
            headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            json={"rates": {"CNY": 7.25}}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["updated_rates"]["CNY"] == 7.25

    def test_reload_exchange_rates(self):
        """测试重新加载汇率"""
        response = client.post(
            "/config/exchange_rates/reload",
            headers={"Authorization": f"Bearer {ADMIN_TOKEN}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_get_supported_currencies(self):
        """测试获取支持的货币"""
        response = client.get("/config/exchange_rates/supported")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["currencies"]) > 0

    def test_generate_key_with_currency(self):
        """测试创建 CNY 预算的密钥"""
        response = client.post(
            "/key/generate",
            headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            json={
                "key_alias": "test-cny-key",
                "max_budget": 10000.0,
                "budget_currency": "CNY"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["budget_currency"] == "CNY"
        assert data["max_budget"] == 10000.0
```

---

## 下一步

1. ✅ Phase 4 API 端点实现完成
2. ⏭️ 创建 Phase 5: UI 组件设计
