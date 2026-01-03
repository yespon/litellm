# 多货币支持 - 精度和 Budget 兼容性分析

## 1. 精度测试结果 ✅

**测试结论**: Python Float 精度足够，CNY ↔ USD 转换无精度损失
- 15位十进制精度
- 1000次累计误差：0%
- Budget 转换误差：0%

---

## 2. Budget 系统的真正问题 ⚠️

### 2.1 问题场景

**用户设置 CNY 预算**:
```
用户操作：设置 ¥10,000 预算
汇率：1 USD = 7.2 CNY

方案A（强制转USD存储）：
  存储：max_budget = 1388.89 (USD)

1周后汇率变化：1 USD = 7.5 CNY
  用户看到：¥10,000 预算 → 显示为 ¥10,416 ❌

问题：用户困惑 - "我设置了 ¥10,000，为什么变成 ¥10,416了？"
```

**跨货币模型使用**:
```
用户：¥10,000 预算
- 调用 GPT-4 (USD 定价): $100
- 调用 Qwen-Max (CNY 定价): ¥500

方案A（统一USD）：
  总花费 = $100 + (¥500 ÷ 7.2) = $169.44
  剩余预算 = $1388.89 - $169.44 = $1219.45
  显示：¥1219.45 × 7.2 = ¥8780 ✅ (如果汇率不变)

但汇率变化后：
  显示：¥1219.45 × 7.5 = ¥9146 ❌ (预算"变多了"？)
```

### 2.2 当前 Schema 的局限

```prisma
model LiteLLM_VerificationToken {
  max_budget: Float  // 只有数字，没有货币类型！
  spend: Float       // 只有数字，没有货币类型！
  model_spend: Json  // {"gpt-4": 100.5} - 也没有货币类型
  model_max_budget: Json
}
```

**核心问题**:
- ✅ 可以存储数字
- ❌ 不知道这个数字是什么货币
- ❌ 汇率变化时，预算的实际价值会变化

---

## 3. 改进方案：原生货币存储

### 3.1 设计原则

```
核心思想：
1. 预算用什么货币设置，就用什么货币存储
2. 费用用什么货币产生，就用什么货币累计
3. 比较时才进行实时转换
```

### 3.2 Schema 改进（推荐方案）

```prisma
model LiteLLM_VerificationToken {
  // 原有字段
  spend: Float @default(0.0)
  max_budget: Float?
  model_spend: Json @default("{}")
  model_max_budget: Json @default("{}")

  // 新增字段 - 货币类型
  budget_currency: String @default("USD")  // 预算设置的货币
  spend_currency: String @default("USD")   // 费用累计的货币（通常与budget_currency相同）

  // 多币种支持（可选）
  spend_by_currency: Json @default("{}")
  // 格式: {"USD": 100.5, "CNY": 720.0}
  // 分别记录不同货币的花费
}

model LiteLLM_TeamTable {
  // 类似的改动
  max_budget: Float?
  spend: Float @default(0.0)
  budget_currency: String @default("USD")
  spend_by_currency: Json @default("{}")
  model_spend: Json @default("{}")
  model_max_budget: Json @default("{}")
}

model LiteLLM_BudgetTable {
  max_budget: Float?
  soft_budget: Float?
  budget_currency: String @default("USD")
  // ...
}
```

### 3.3 数据结构示例

#### 选项 1: 单一货币模式（简单）

```json
{
  "max_budget": 10000.0,
  "budget_currency": "CNY",
  "spend": 1500.0,
  "spend_currency": "CNY",
  "model_spend": {
    "qwen-max": 800.0,    // CNY
    "gpt-4": 700.0        // 自动转换为 CNY
  }
}
```

**逻辑**:
- 用户设置 CNY 预算
- 所有花费都转换为 CNY 累计
- USD 模型的花费实时转换为 CNY
- 预算检查：`spend >= max_budget`

**优点**:
- 简单，预算金额不会因汇率变化
- 用户体验好：设置 ¥10000，始终显示 ¥10000

**缺点**:
- 历史花费会因汇率变化而"变化"
- 例如：昨天花了 $100（¥720），今天汇率变了，显示 ¥750

#### 选项 2: 多货币独立模式（精确）

```json
{
  "max_budget": 10000.0,
  "budget_currency": "CNY",
  "spend": 10000.0,  // 主货币累计（CNY）
  "spend_by_currency": {
    "USD": 100.0,    // USD 原始花费
    "CNY": 9280.0    // CNY 原始花费
  },
  "model_spend": {
    "gpt-4": {"amount": 100.0, "currency": "USD"},
    "qwen-max": {"amount": 800.0, "currency": "CNY"}
  }
}
```

**逻辑**:
- 分别记录每种货币的原始花费
- 预算检查时实时转换
- `spend_usd_eq = spend_by_currency.USD + (spend_by_currency.CNY / rate)`

**优点**:
- 历史数据准确，不受汇率变化影响
- 可以准确追踪原始花费

**缺点**:
- 复杂度高
- 需要修改很多代码

---

## 4. 推荐方案：混合模式

### 4.1 设计

```
存储层：
- 原生货币存储（不转换）
- 添加 currency 字段

计算层：
- 比较时实时转换
- 缓存汇率（1小时）

展示层：
- 默认显示原生货币
- 可选切换显示货币
```

### 4.2 核心改动

#### Schema 改动（最小化）

```prisma
model LiteLLM_VerificationToken {
  spend: Float @default(0.0)
  max_budget: Float?

  // 新增 2 个字段
  budget_currency: String @default("USD")
  spend_currency: String @default("USD")

  // 保持现有字段不变
  model_spend: Json @default("{}")
  model_max_budget: Json @default("{}")
}
```

#### Budget 检查逻辑改动

**位置**: `/litellm/proxy/auth/auth_checks.py`

```python
async def _virtual_key_max_budget_check(
    user_api_key_dict: UserAPIKeyAuth,
    # ... 其他参数
):
    """检查虚拟密钥预算"""

    # 1. 获取预算和花费
    max_budget = user_api_key_dict.max_budget
    current_spend = user_api_key_dict.spend
    budget_currency = user_api_key_dict.budget_currency or "USD"
    spend_currency = user_api_key_dict.spend_currency or "USD"

    if max_budget is None:
        return

    # 2. 如果货币不同，转换到相同货币比较
    if budget_currency != spend_currency:
        from litellm.utils.currency import convert_currency
        current_spend = convert_currency(
            amount=current_spend,
            from_currency=spend_currency,
            to_currency=budget_currency
        )

    # 3. 检查预算
    if current_spend >= max_budget:
        raise BudgetExceededError(
            f"Budget exceeded. "
            f"Spend: {current_spend:.2f} {budget_currency}, "
            f"Max: {max_budget:.2f} {budget_currency}"
        )
```

#### 费用累计逻辑改动

**位置**: `/litellm/proxy/hooks/proxy_track_cost_callback.py`

```python
async def _PROXY_track_cost_callback(
    kwargs, completion_response, start_time, end_time
):
    # 计算本次请求的成本
    response_cost = completion_cost(completion_response=completion_response)
    model = kwargs.get("model")

    # 获取模型的原始货币
    model_info = litellm.get_model_info(model)
    model_currency = model_info.get("currency", "USD")

    # 获取用户的预算货币
    user_api_key_dict = kwargs.get("litellm_params", {}).get("metadata", {}).get("user_api_key_dict", {})
    budget_currency = user_api_key_dict.get("budget_currency", "USD")

    # 如果货币不同，转换
    if model_currency != budget_currency:
        from litellm.utils.currency import convert_currency
        response_cost = convert_currency(
            amount=response_cost,
            from_currency=model_currency,
            to_currency=budget_currency
        )

    # 更新花费（用预算货币累计）
    new_spend = user_api_key_dict.get("spend", 0) + response_cost

    # 更新数据库
    await prisma_client.db.litellm_verificationtoken.update(
        where={"token": user_api_key_dict.token},
        data={
            "spend": new_spend,
            "spend_currency": budget_currency  # 确保记录货币
        }
    )
```

---

## 5. 实现方案对比

| 方案 | 优点 | 缺点 | 复杂度 | 推荐度 |
|------|------|------|--------|--------|
| **A. 强制转USD** | 简单，最小改动 | Budget 会因汇率变化 | ⭐ | ❌ |
| **B. 原生货币存储（单一）** | 预算稳定，用户体验好 | 历史数据受汇率影响 | ⭐⭐ | ⭐⭐⭐ |
| **C. 多货币独立** | 精确，无汇率影响 | 复杂度高 | ⭐⭐⭐⭐ | ⭐⭐ |
| **D. 混合模式** | 平衡精确性和复杂度 | 中等改动量 | ⭐⭐⭐ | ⭐⭐⭐⭐ |

---

## 6. 最终推荐：方案 D - 混合模式

### 6.1 核心设计

```
原则：
1. 预算用设置的货币存储（不变）
2. 费用用预算货币累计（统一）
3. 比较时如需转换，实时转换
```

### 6.2 数据流

```
┌─────────────────────────────────────┐
│ 用户设置预算                         │
│ max_budget: ¥10,000                 │
│ budget_currency: "CNY"              │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ API 请求                             │
│ Model: gpt-4 (USD pricing)          │
│ Cost: $10                           │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ 费用计算                             │
│ 1. 计算原始成本: $10                │
│ 2. 转换为预算货币: ¥72 (rate=7.2)  │
│ 3. 累计: spend += ¥72               │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ 预算检查                             │
│ spend (¥72) < max_budget (¥10,000)  │
│ ✅ 通过                             │
└─────────────────────────────────────┘
```

### 6.3 实现步骤

#### Phase 1: Schema 扩展
```sql
ALTER TABLE "LiteLLM_VerificationToken"
ADD COLUMN "budget_currency" TEXT DEFAULT 'USD',
ADD COLUMN "spend_currency" TEXT DEFAULT 'USD';

ALTER TABLE "LiteLLM_TeamTable"
ADD COLUMN "budget_currency" TEXT DEFAULT 'USD',
ADD COLUMN "spend_currency" TEXT DEFAULT 'USD';

ALTER TABLE "LiteLLM_BudgetTable"
ADD COLUMN "budget_currency" TEXT DEFAULT 'USD';
```

#### Phase 2: 费用追踪改动
- 修改 `proxy_track_cost_callback.py`
- 费用转换为预算货币后累计

#### Phase 3: 预算检查改动
- 修改所有 `*_budget_check` 函数
- 添加货币转换逻辑

#### Phase 4: UI 改动
- 预算设置时选择货币
- 显示预算和花费时标注货币

---

## 7. 汇率变化的影响

### 场景分析

```
T0: 用户设置
  max_budget: ¥10,000 (CNY)
  spend: ¥0 (CNY)
  rate: 1 USD = 7.2 CNY

T1: 调用 GPT-4
  cost: $100 (USD)
  convert: ¥720 (CNY)
  spend: ¥720 (CNY)

T2: 汇率变化
  rate: 1 USD = 7.5 CNY (汇率上涨)

T3: 再次调用 GPT-4
  cost: $100 (USD)
  convert: ¥750 (CNY)  ← 比 T1 贵了
  spend: ¥720 + ¥750 = ¥1470 (CNY)

结果：
- 预算仍然是 ¥10,000 ✅
- 总花费 ¥1470 ✅
- 剩余预算 ¥8530 ✅
- 用户体验：一致、可预测
```

### 与方案 A 对比

```
方案 A（强制 USD）:
T0: max_budget: $1388.89, spend: $0
T2: 汇率变化后
    显示预算: $1388.89 × 7.5 = ¥10,416 ❌
    用户困惑："我的预算怎么变多了？"

方案 D（原生货币）:
T0: max_budget: ¥10,000, spend: ¥0
T2: 汇率变化后
    显示预算: ¥10,000 ✅
    用户满意："预算稳定"
```

---

## 8. 总结

### 问题
✅ **精度**: Float 足够，无问题
⚠️ **Budget 兼容性**: 需要支持原生货币

### 方案
✅ **推荐**: 混合模式（原生货币 + 实时转换）

### 改动量
- Schema: +2 字段
- 后端: ~5-10 个函数
- 前端: ~3-5 个组件

### 优势
1. 预算稳定，不受汇率影响
2. 用户体验好，符合预期
3. 向后兼容（默认 USD）
4. 改动量适中

### 下一步
1. 确认方案
2. 实现 Schema migration
3. 修改费用追踪和预算检查
4. UI 适配
