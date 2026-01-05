# API 端点设计 - 多货币支持

## 📋 目录
- [新增端点](#新增端点)
- [扩展端点](#扩展端点)
- [请求/响应示例](#请求响应示例)

---

## 新增端点

### 1. GET /config/exchange_rates

获取当前汇率配置

**权限**: Admin only

**请求**:
```http
GET /config/exchange_rates HTTP/1.1
Host: localhost:4001
Authorization: Bearer sk-1234
```

**响应**:
```json
{
  "success": true,
  "data": {
    "base_currency": "USD",
    "rates": {
      "USD": 1.0,
      "CNY": 7.2,
      "EUR": 0.92,
      "GBP": 0.79,
      "JPY": 149.5
    },
    "last_updated": "2026-01-03T10:00:00Z",
    "source": "manual",
    "supported_currencies": ["USD", "CNY", "EUR", "GBP", "JPY"]
  }
}
```

**错误响应**:
```json
{
  "error": {
    "message": "Unauthorized",
    "type": "auth_error",
    "code": "401"
  }
}
```

**实现位置**: `/litellm/proxy/management_endpoints/currency_settings.py`

```python
@router.get(
    "/config/exchange_rates",
    tags=["currency", "config"],
    dependencies=[Depends(user_api_key_auth)],
)
async def get_exchange_rates(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)
):
    """获取汇率配置"""
    from litellm.proxy.proxy_server import general_settings

    # 权限检查
    if user_api_key_dict.user_role != "proxy_admin":
        raise HTTPException(
            status_code=403,
            detail="Only admins can view exchange rates"
        )

    # 获取汇率
    from litellm.utils.currency import CurrencyExchangeRateManager
    manager = CurrencyExchangeRateManager()

    return {
        "success": True,
        "data": {
            "base_currency": "USD",
            "rates": manager.get_all_rates(),
            "last_updated": manager._last_update.isoformat() if manager._last_update else None,
            "source": "manual",
            "supported_currencies": manager.get_supported_currencies()
        }
    }
```

---

### 2. PATCH /config/exchange_rates

更新汇率

**权限**: Admin only

**请求**:
```http
PATCH /config/exchange_rates HTTP/1.1
Host: localhost:4001
Authorization: Bearer sk-1234
Content-Type: application/json

{
  "rates": {
    "CNY": 7.25,
    "EUR": 0.93
  }
}
```

**响应**:
```json
{
  "success": true,
  "message": "Exchange rates updated successfully",
  "data": {
    "updated_rates": {
      "CNY": 7.25,
      "EUR": 0.93
    },
    "updated_at": "2026-01-03T12:30:00Z"
  }
}
```

**验证规则**:
- 汇率必须 > 0
- 货币代码必须是支持的货币
- USD 汇率不能修改（始终为 1.0）

**错误响应**:
```json
{
  "error": {
    "message": "Invalid rate: CNY rate must be greater than 0",
    "type": "validation_error",
    "code": "400"
  }
}
```

**实现**:
```python
from pydantic import BaseModel, validator

class UpdateExchangeRatesRequest(BaseModel):
    rates: Dict[str, float]

    @validator('rates')
    def validate_rates(cls, v):
        for currency, rate in v.items():
            if rate <= 0:
                raise ValueError(f"Rate for {currency} must be > 0")
            if currency == "USD":
                raise ValueError("Cannot modify USD rate")
        return v

@router.patch(
    "/config/exchange_rates",
    tags=["currency", "config"],
    dependencies=[Depends(user_api_key_auth)],
)
async def update_exchange_rates(
    request: UpdateExchangeRatesRequest,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)
):
    """更新汇率"""
    # 权限检查
    if user_api_key_dict.user_role != "proxy_admin":
        raise HTTPException(status_code=403)

    # 更新汇率
    from litellm.utils.currency import CurrencyExchangeRateManager
    manager = CurrencyExchangeRateManager()

    for currency, rate in request.rates.items():
        manager.update_rate(currency, rate, save=False)

    # 保存到文件
    manager.save_rates()

    return {
        "success": True,
        "message": "Exchange rates updated successfully",
        "data": {
            "updated_rates": request.rates,
            "updated_at": datetime.now().isoformat()
        }
    }
```

---

### 3. POST /config/exchange_rates/reload

重新加载汇率配置

**权限**: Admin only

**请求**:
```http
POST /config/exchange_rates/reload HTTP/1.1
Host: localhost:4001
Authorization: Bearer sk-1234
```

**响应**:
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

**实现**:
```python
@router.post(
    "/config/exchange_rates/reload",
    tags=["currency", "config"],
    dependencies=[Depends(user_api_key_auth)],
)
async def reload_exchange_rates(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)
):
    """重新加载汇率"""
    # 权限检查
    if user_api_key_dict.user_role != "proxy_admin":
        raise HTTPException(status_code=403)

    # 强制重新加载
    from litellm.utils.currency import CurrencyExchangeRateManager
    manager = CurrencyExchangeRateManager()
    manager.load_rates(force=True)

    return {
        "success": True,
        "message": "Exchange rates reloaded successfully",
        "data": {
            "rates_loaded": len(manager.get_all_rates()),
            "source": "config_file",
            "loaded_at": datetime.now().isoformat()
        }
    }
```

---

## 扩展端点

### 4. GET /public/litellm_model_cost_map

扩展模型价格映射，添加货币信息

**改动前**:
```json
{
  "gpt-4": {
    "input_cost_per_token": 0.00003,
    "output_cost_per_token": 0.00006
  }
}
```

**改动后**:
```json
{
  "gpt-4": {
    "input_cost_per_token": 0.00003,
    "output_cost_per_token": 0.00006,
    "currency": "USD",
    "litellm_provider": "openai"
  },
  "qwen-max": {
    "input_cost_per_token": 0.0008,
    "output_cost_per_token": 0.002,
    "currency": "CNY",
    "litellm_provider": "openai"
  }
}
```

**实现**:
```python
@router.get(
    "/public/litellm_model_cost_map",
    tags=["public", "model management"],
)
async def get_litellm_model_cost_map():
    """获取模型价格映射（包含货币信息）"""
    import litellm
    _model_cost_map = litellm.model_cost

    # 确保每个模型都有 currency 字段
    for model, info in _model_cost_map.items():
        if "currency" not in info:
            info["currency"] = "USD"  # 默认 USD

    return _model_cost_map
```

---

### 5. GET /spend/logs

添加货币显示支持

**新增查询参数**:
- `display_currency`: 显示货币（可选，如 "CNY"）

**请求**:
```http
GET /spend/logs?display_currency=CNY HTTP/1.1
Host: localhost:4001
Authorization: Bearer sk-xxxxx
```

**响应**:
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
      "prompt_tokens": 100,
      "completion_tokens": 50,
      "startTime": "2026-01-03T10:00:00Z"
    }
  ],
  "metadata": {
    "exchange_rate": 7.2,
    "rate_updated_at": "2026-01-03T09:00:00Z"
  }
}
```

**实现**:
```python
@router.get(
    "/spend/logs",
    tags=["spend tracking"],
    dependencies=[Depends(user_api_key_auth)],
)
async def get_spend_logs(
    display_currency: Optional[str] = "USD",
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)
):
    """获取费用日志（支持货币转换）"""
    # 查询数据库
    logs = await prisma_client.db.litellm_spendlogs.find_many(
        where={"api_key": user_api_key_dict.token},
        take=100
    )

    # 如果需要转换货币
    if display_currency != "USD":
        from litellm.utils.currency import convert_currency, get_exchange_rate

        rate = get_exchange_rate("USD", display_currency)

        for log in logs:
            log["spend_display"] = convert_currency(
                log["spend"],
                "USD",
                display_currency
            )
            log["display_currency"] = display_currency

    return {
        "data": logs,
        "metadata": {
            "exchange_rate": rate if display_currency != "USD" else 1.0,
            "rate_updated_at": datetime.now().isoformat()
        }
    }
```

---

### 6. GET /key/info

扩展密钥信息，显示货币

**改动前**:
```json
{
  "key": "sk-xxxxx",
  "spend": 100.5,
  "max_budget": 1000.0
}
```

**改动后**:
```json
{
  "key": "sk-xxxxx",
  "spend": 100.5,
  "spend_currency": "USD",
  "max_budget": 1000.0,
  "budget_currency": "USD",
  "spend_in_budget_currency": 100.5
}
```

**实现**:
```python
@router.get(
    "/key/info",
    tags=["key management"],
    dependencies=[Depends(user_api_key_auth)],
)
async def key_info(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)
):
    """获取密钥信息（包含货币）"""
    key_data = {
        "key": user_api_key_dict.token,
        "spend": user_api_key_dict.spend,
        "spend_currency": user_api_key_dict.get("spend_currency", "USD"),
        "max_budget": user_api_key_dict.max_budget,
        "budget_currency": user_api_key_dict.get("budget_currency", "USD"),
    }

    # 如果货币不同，显示转换后的费用
    if key_data["spend_currency"] != key_data["budget_currency"]:
        from litellm.utils.currency import convert_currency
        key_data["spend_in_budget_currency"] = convert_currency(
            key_data["spend"],
            key_data["spend_currency"],
            key_data["budget_currency"]
        )
    else:
        key_data["spend_in_budget_currency"] = key_data["spend"]

    return key_data
```

---

### 7. POST /key/generate

创建密钥时支持货币设置

**新增字段**:
- `budget_currency`: 预算货币

**请求**:
```http
POST /key/generate HTTP/1.1
Host: localhost:4001
Authorization: Bearer sk-1234
Content-Type: application/json

{
  "max_budget": 10000.0,
  "budget_currency": "CNY",
  "key_alias": "test-cny-key"
}
```

**响应**:
```json
{
  "key": "sk-xxxxxxxxxxxxxxxx",
  "key_alias": "test-cny-key",
  "max_budget": 10000.0,
  "budget_currency": "CNY",
  "spend": 0.0,
  "spend_currency": "CNY"
}
```

**实现**:
```python
from pydantic import BaseModel

class GenerateKeyRequest(BaseModel):
    max_budget: Optional[float] = None
    budget_currency: str = "USD"  # 新增字段
    key_alias: Optional[str] = None
    # ... 其他字段

@router.post(
    "/key/generate",
    tags=["key management"],
    dependencies=[Depends(user_api_key_auth)],
)
async def generate_key(
    request: GenerateKeyRequest,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)
):
    """生成密钥（支持货币设置）"""
    # 权限检查
    if user_api_key_dict.user_role != "proxy_admin":
        raise HTTPException(status_code=403)

    # 生成密钥
    new_key = generate_random_key()

    # 创建数据库记录
    await prisma_client.db.litellm_verificationtoken.create(
        data={
            "token": new_key,
            "key_alias": request.key_alias,
            "max_budget": request.max_budget,
            "budget_currency": request.budget_currency,  # 新增
            "spend_currency": request.budget_currency,   # 新增
            "spend": 0.0
        }
    )

    return {
        "key": new_key,
        "key_alias": request.key_alias,
        "max_budget": request.max_budget,
        "budget_currency": request.budget_currency,
        "spend": 0.0,
        "spend_currency": request.budget_currency
    }
```

---

## 请求/响应示例

### 完整流程示例

#### 1. 管理员设置汇率

```bash
curl -X PATCH http://localhost:4001/config/exchange_rates \
  -H "Authorization: Bearer sk-1234" \
  -H "Content-Type: application/json" \
  -d '{
    "rates": {
      "CNY": 7.25
    }
  }'
```

#### 2. 创建 CNY 预算的密钥

```bash
curl -X POST http://localhost:4001/key/generate \
  -H "Authorization: Bearer sk-1234" \
  -H "Content-Type: application/json" \
  -d '{
    "max_budget": 10000.0,
    "budget_currency": "CNY",
    "key_alias": "cny-test-key"
  }'
```

**响应**:
```json
{
  "key": "sk-proj-abc123...",
  "key_alias": "cny-test-key",
  "max_budget": 10000.0,
  "budget_currency": "CNY",
  "spend": 0.0,
  "spend_currency": "CNY"
}
```

#### 3. 使用密钥调用 API

```bash
curl -X POST http://localhost:4001/v1/chat/completions \
  -H "Authorization: Bearer sk-proj-abc123..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

**系统行为**:
1. GPT-4 使用 USD 定价：$0.05
2. 转换为 CNY：¥0.05 × 7.25 = ¥0.3625
3. 累计费用：spend = ¥0.3625
4. 检查预算：¥0.3625 < ¥10000 ✅

#### 4. 查看费用

```bash
curl http://localhost:4001/key/info \
  -H "Authorization: Bearer sk-proj-abc123..."
```

**响应**:
```json
{
  "key": "sk-proj-abc123...",
  "spend": 0.3625,
  "spend_currency": "CNY",
  "max_budget": 10000.0,
  "budget_currency": "CNY",
  "spend_in_budget_currency": 0.3625
}
```

---

## 错误处理

### 常见错误

#### 1. 汇率无效

```json
{
  "error": {
    "message": "Invalid exchange rate: CNY rate must be greater than 0",
    "type": "validation_error",
    "code": "400"
  }
}
```

#### 2. 不支持的货币

```json
{
  "error": {
    "message": "Unsupported currency: XXX",
    "type": "validation_error",
    "code": "400"
  }
}
```

#### 3. 权限不足

```json
{
  "error": {
    "message": "Only admins can modify exchange rates",
    "type": "auth_error",
    "code": "403"
  }
}
```

---

## 下一步

1. ✅ API 设计完成
2. ⏭️ 创建测试计划文档
3. ⏭️ 创建用户文档
