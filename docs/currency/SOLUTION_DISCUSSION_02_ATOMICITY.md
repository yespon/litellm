# 多货币支持 - 修复方案讨论 (问题 #2 & #3)

> **讨论主题**: 原子性和并发控制
> **日期**: 2026-01-04

---

## 🔴 问题 #2: 货币转换的原子性问题

### 问题描述

**当前设计的风险**:

```python
# 当前代码（有问题）
async def update_spend(...):
    # 时刻 T1: 获取汇率
    exchange_rate = get_exchange_rate("USD", "CNY")  # 7.2

    # ⏰ 时间流逝... (可能数秒到数分钟)
    # 此时管理员修改汇率为 7.25

    # 时刻 T2: 使用 T1 时刻的汇率计算
    converted_cost = response_cost * exchange_rate  # 用的是旧汇率 7.2

    # 时刻 T3: 更新数据库
    await prisma_client.db.litellm_verificationtoken.update(
        data={"spend": {"increment": converted_cost}}  # 记录了错误的金额
    )

    # ❌ 问题：汇率和费用不匹配
    # 实际使用汇率：7.25（新）
    # 记录的汇率：7.2（旧）
    # 差异：0.05 * cost
```

**影响**:
- 费用记录不准确
- 审计追溯困难
- 累计误差可能显著

---

## 方案对比

### 方案 A: 数据库事务 + 汇率快照 ⭐ 推荐

#### 核心思想

在同一个数据库事务中：
1. 获取并锁定汇率
2. 计算转换后的费用
3. 更新费用记录
4. 创建日志（包含使用的汇率）

确保"汇率-转换-记录"三个操作的原子性。

#### 实现代码

```python
async def update_spend_atomic(
    prisma_client,
    token: str,
    response_cost: float,
    response_cost_currency: str,
    budget_currency: str,
    metadata: dict = None
) -> dict:
    """
    原子性费用更新

    Returns:
        {
            "converted_cost": float,
            "exchange_rate": float,
            "timestamp": str
        }
    """
    async with prisma_client.db.tx() as transaction:
        # 步骤 1: 获取汇率（快照）
        # 在事务开始时获取，确保整个事务使用同一汇率
        from litellm.utils.currency import get_exchange_rate

        exchange_rate = get_exchange_rate(
            response_cost_currency,
            budget_currency
        )
        converted_cost = response_cost * exchange_rate

        # 步骤 2: 更新 VerificationToken 费用
        updated_key = await transaction.litellm_verificationtoken.update(
            where={"token": token},
            data={
                "spend": {"increment": converted_cost},
                "spend_currency": budget_currency  # 确保货币一致
            }
        )

        # 步骤 3: 创建 SpendLog（记录使用的汇率）
        log = await transaction.litellm_spendlogs.create(
            data={
                "api_key": token,
                "spend": converted_cost,
                "spend_currency": budget_currency,

                # 关键：记录原始信息和汇率
                "model_currency": response_cost_currency,
                "spend_original": response_cost,
                "exchange_rate": exchange_rate,  # 快照汇率

                "startTime": datetime.now(),
                "endTime": datetime.now(),
                **(metadata or {})
            }
        )

        # 步骤 4: （可选）记录汇率使用事件
        await transaction.litellm_currencyevents.create(
            data={
                "event_type": "conversion",
                "from_currency": response_cost_currency,
                "to_currency": budget_currency,
                "exchange_rate": exchange_rate,
                "amount": response_cost,
                "converted_amount": converted_cost,
                "timestamp": datetime.now()
            }
        )

        # 事务提交：所有操作要么都成功，要么都失败
        return {
            "converted_cost": converted_cost,
            "exchange_rate": exchange_rate,
            "timestamp": datetime.now().isoformat(),
            "new_spend": updated_key.spend
        }

    # 如果事务失败（网络、数据库错误等），会自动回滚
```

#### 新增数据表

为了更好地追踪汇率使用，建议添加新表：

```prisma
// 汇率转换事件表（可选，用于详细审计）
model LiteLLM_CurrencyEvents {
  id                String   @id @default(uuid())
  event_type        String   // "conversion", "rate_update"
  from_currency     String
  to_currency       String
  exchange_rate     Float
  amount            Float?   // 原始金额
  converted_amount  Float?   // 转换后金额
  timestamp         DateTime @default(now())
  metadata          Json?

  @@index([timestamp])
  @@index([from_currency, to_currency])
}
```

#### 优点

✅ **完全原子性**: 数据库事务保证
✅ **可追溯**: 每笔费用都记录了使用的汇率
✅ **审计友好**: 可以重新验证历史费用
✅ **一致性强**: 汇率和费用匹配

#### 缺点

❌ **事务开销**: 每次更新需要事务
❌ **表增多**: 需要额外的事件表（可选）
❌ **锁竞争**: 高并发下可能有锁等待

---

### 方案 B: 两阶段提交 + 补偿机制

#### 核心思想

1. 先记录费用（使用当前汇率）
2. 异步校验汇率是否变化
3. 如有变化，创建补偿记录

#### 实现代码

```python
async def update_spend_two_phase(
    prisma_client,
    token: str,
    response_cost: float,
    response_cost_currency: str,
    budget_currency: str
):
    """两阶段提交方案"""

    # 阶段 1: 快速提交（使用当前汇率）
    exchange_rate_snapshot = get_exchange_rate(
        response_cost_currency,
        budget_currency
    )
    converted_cost = response_cost * exchange_rate_snapshot
    timestamp = datetime.now()

    # 更新费用
    await prisma_client.db.litellm_verificationtoken.update(
        where={"token": token},
        data={"spend": {"increment": converted_cost}}
    )

    # 创建日志
    log_id = await prisma_client.db.litellm_spendlogs.create(
        data={
            "spend": converted_cost,
            "exchange_rate": exchange_rate_snapshot,
            "verified": False,  # 标记未校验
            "timestamp": timestamp
        }
    )

    # 阶段 2: 异步校验（后台任务）
    asyncio.create_task(
        verify_and_compensate(
            log_id,
            response_cost,
            response_cost_currency,
            budget_currency,
            exchange_rate_snapshot,
            timestamp
        )
    )

async def verify_and_compensate(
    log_id,
    original_cost,
    from_currency,
    to_currency,
    used_rate,
    timestamp
):
    """校验并补偿"""
    await asyncio.sleep(5)  # 延迟 5 秒再校验

    # 获取校验时刻的汇率
    current_rate = get_exchange_rate(from_currency, to_currency)

    # 计算差异
    diff = abs(current_rate - used_rate) / used_rate

    if diff > 0.001:  # 差异超过 0.1%
        # 记录差异
        await prisma_client.db.litellm_currencydiscrepancies.create(
            data={
                "log_id": log_id,
                "used_rate": used_rate,
                "actual_rate": current_rate,
                "difference_pct": diff * 100,
                "timestamp": datetime.now()
            }
        )

        # 可选：自动补偿
        if diff > 0.01:  # 差异超过 1%，进行补偿
            adjustment = original_cost * (current_rate - used_rate)
            await adjust_spend(token, adjustment)

    # 标记为已校验
    await prisma_client.db.litellm_spendlogs.update(
        where={"id": log_id},
        data={"verified": True}
    )
```

#### 优点

✅ **快速响应**: 不阻塞主流程
✅ **灵活**: 可以异步修正错误

#### 缺点

❌ **最终一致性**: 不是强一致性
❌ **复杂**: 需要补偿逻辑
❌ **可能不准确**: 仍然有时间窗口

---

### 方案 C: 汇率版本控制

#### 核心思想

为汇率添加版本号，记录时引用版本。

#### 实现代码

```python
# 汇率配置带版本
{
  "version": 123,  # 每次更新递增
  "timestamp": "2026-01-04T10:00:00Z",
  "rates": {
    "USD": 1.0,
    "CNY": 7.2
  }
}

# 使用时记录版本
async def update_spend_versioned(
    token: str,
    cost: float,
    from_currency: str,
    to_currency: str
):
    # 获取汇率和版本
    rate_info = get_exchange_rate_with_version(from_currency, to_currency)
    # {
    #   "rate": 7.2,
    #   "version": 123,
    #   "timestamp": "2026-01-04T10:00:00Z"
    # }

    converted = cost * rate_info["rate"]

    # 记录时包含版本
    await prisma_client.db.litellm_spendlogs.create(
        data={
            "spend": converted,
            "exchange_rate": rate_info["rate"],
            "rate_version": rate_info["version"],  # 版本号
            "rate_timestamp": rate_info["timestamp"]
        }
    )
```

#### 优点

✅ **可追溯**: 知道使用的是哪个版本的汇率
✅ **验证**: 可以用版本号重新计算

#### 缺点

❌ **仍有时间窗口**: 不解决原子性问题
❌ **复杂**: 需要版本管理

---

## 方案对比

| 维度 | 事务方案 (A) | 两阶段提交 (B) | 版本控制 (C) |
|------|-------------|---------------|-------------|
| **原子性** | ⭐⭐⭐⭐⭐ 强一致 | ⭐⭐⭐ 最终一致 | ⭐⭐ 不保证 |
| **性能** | ⭐⭐⭐⭐ 略慢 | ⭐⭐⭐⭐⭐ 最快 | ⭐⭐⭐⭐ 较快 |
| **准确性** | ⭐⭐⭐⭐⭐ 100% | ⭐⭐⭐⭐ 可补偿 | ⭐⭐⭐ 依赖版本 |
| **复杂度** | ⭐⭐⭐⭐ 简单 | ⭐⭐ 复杂 | ⭐⭐⭐ 中等 |
| **可维护性** | ⭐⭐⭐⭐⭐ 最好 | ⭐⭐ 较差 | ⭐⭐⭐ 中等 |

### 推荐：**方案 A（数据库事务）**

理由：
- 计费系统对准确性要求高
- 事务性能开销可接受
- 实现简单，易维护

---

## 🔴 问题 #3: Budget 检查的竞态条件

### 问题描述

**并发场景**:

```
时刻 T0: Key 状态 spend=98, budget=100 (剩余2)

并发请求 A (预计花费 1.5):
  T1: 检查 98 < 100 ✓ 通过
  T2: 调用 LLM API...
  T3: 实际花费 1.5
  T4: 更新 spend=99.5

并发请求 B (预计花费 1.5):
  T1: 检查 98 < 100 ✓ 通过（还是旧值！）
  T2: 调用 LLM API...
  T3: 实际花费 1.5
  T4: 更新 spend=101  ❌ 超支了！

最终结果: spend=101, budget=100 (超支 1)
```

---

## 方案对比

### 方案 A: 悲观锁（SELECT FOR UPDATE）⭐ 推荐

#### 核心思想

使用数据库行锁，确保同一时刻只有一个请求可以检查和更新。

#### 实现代码

```python
async def handle_request_with_pessimistic_lock(
    user_api_key_dict: UserAPIKeyAuth,
    request_params: dict
):
    """使用悲观锁的请求处理"""

    async with prisma_client.db.tx() as transaction:
        # 步骤 1: 锁定密钥记录（其他请求必须等待）
        key = await transaction.query_raw("""
            SELECT *
            FROM "LiteLLM_VerificationToken"
            WHERE token = $1
            FOR UPDATE  -- 排他锁
        """, [user_api_key_dict.token])

        if not key:
            raise HTTPException(status_code=404, detail="Key not found")

        # 步骤 2: 预估请求成本
        estimated_cost = estimate_request_cost(
            model=request_params["model"],
            max_tokens=request_params.get("max_tokens", 1000),
            budget_currency=key[0]["budget_currency"]
        )

        # 步骤 3: 检查预算（含预估成本）
        current_spend = key[0]["spend"]
        max_budget = key[0]["max_budget"]

        if current_spend + estimated_cost >= max_budget:
            raise BudgetExceededError(
                f"Insufficient budget. "
                f"Current: {current_spend}, "
                f"Estimated cost: {estimated_cost}, "
                f"Budget: {max_budget}, "
                f"Available: {max_budget - current_spend}"
            )

        # 步骤 4: 预先扣除预估成本（乐观扣除）
        await transaction.litellm_verificationtoken.update(
            where={"token": user_api_key_dict.token},
            data={
                "spend": {"increment": estimated_cost}
            }
        )

        # 提交事务，释放锁

    # 步骤 5: 执行实际 LLM 请求（在事务外）
    try:
        response = await litellm.completion(**request_params)

        # 步骤 6: 计算实际成本
        actual_cost = calculate_actual_cost(
            response,
            budget_currency=key[0]["budget_currency"]
        )

        # 步骤 7: 调整差额
        diff = actual_cost - estimated_cost

        if abs(diff) > 0.0001:
            await prisma_client.db.litellm_verificationtoken.update(
                where={"token": user_api_key_dict.token},
                data={"spend": {"increment": diff}}
            )

        return response

    except Exception as e:
        # 请求失败，退还预留金额
        await prisma_client.db.litellm_verificationtoken.update(
            where={"token": user_api_key_dict.token},
            data={"spend": {"increment": -estimated_cost}}
        )
        raise
```

#### 成本预估函数

```python
def estimate_request_cost(
    model: str,
    max_tokens: int,
    budget_currency: str = "USD"
) -> float:
    """
    预估请求成本

    策略：
    - 假设输入 token = max_tokens * 0.5
    - 假设输出 token = max_tokens
    - 使用最贵的价格（保守估计）
    """
    from litellm.utils.currency import convert_currency
    from litellm import model_cost

    model_info = model_cost.get(model, {})

    # 获取价格和货币
    input_price = model_info.get("input_cost_per_token", 0)
    output_price = model_info.get("output_cost_per_token", 0)
    model_currency = model_info.get("currency", "USD")

    # 保守估计
    estimated_input_tokens = max_tokens * 0.5
    estimated_output_tokens = max_tokens

    # 计算成本
    cost = (
        estimated_input_tokens * input_price +
        estimated_output_tokens * output_price
    )

    # 转换为预算货币
    if model_currency != budget_currency:
        cost = convert_currency(cost, model_currency, budget_currency)

    # 添加 10% 安全边际
    cost *= 1.1

    return cost
```

#### 优点

✅ **完全防止超支**: 数据库锁保证
✅ **强一致性**: 不会有竞态条件
✅ **实现简单**: 标准的数据库特性

#### 缺点

❌ **性能**: 高并发下锁等待
❌ **预估可能不准**: 需要合理的预估算法

#### 性能优化

```python
# 优化：减少锁持有时间
async def handle_request_optimized(
    user_api_key_dict: UserAPIKeyAuth,
    request_params: dict
):
    """优化版本：缩短锁时间"""

    # 在事务外预估（不持有锁）
    estimated_cost = estimate_request_cost(...)

    # 只在检查和扣除时加锁（< 10ms）
    async with prisma_client.db.tx() as transaction:
        key = await transaction.query_raw(
            "SELECT * FROM ... FOR UPDATE NOWAIT"  # 不等待，立即失败
        )

        if current_spend + estimated_cost >= max_budget:
            raise BudgetExceededError()

        await transaction.litellm_verificationtoken.update(...)
        # 立即提交，释放锁

    # 长时间操作（LLM 调用）在锁外执行
    response = await litellm.completion(**request_params)

    # 调整差额
    ...
```

---

### 方案 B: 乐观锁（版本号）

#### 核心思想

使用版本号检测并发修改，失败时重试。

#### 实现代码

```python
async def handle_request_with_optimistic_lock(
    user_api_key_dict: UserAPIKeyAuth,
    request_params: dict,
    max_retries: int = 3
):
    """使用乐观锁的请求处理"""

    for attempt in range(max_retries):
        # 步骤 1: 读取当前状态（包含版本号）
        key = await prisma_client.db.litellm_verificationtoken.find_unique(
            where={"token": user_api_key_dict.token}
        )

        current_version = key.version  # 假设有版本字段
        current_spend = key.spend
        max_budget = key.max_budget

        # 步骤 2: 预估成本
        estimated_cost = estimate_request_cost(...)

        # 步骤 3: 检查预算
        if current_spend + estimated_cost >= max_budget:
            raise BudgetExceededError()

        # 步骤 4: 尝试更新（检查版本号）
        try:
            updated = await prisma_client.db.litellm_verificationtoken.update(
                where={
                    "token": user_api_key_dict.token,
                    "version": current_version  # 乐观锁条件
                },
                data={
                    "spend": current_spend + estimated_cost,
                    "version": {"increment": 1}  # 递增版本号
                }
            )

            # 更新成功，跳出重试循环
            break

        except PrismaClientKnownRequestError as e:
            # 版本不匹配（有其他请求更新了），重试
            if attempt < max_retries - 1:
                await asyncio.sleep(0.01 * (2 ** attempt))  # 指数退避
                continue
            else:
                raise HTTPException(
                    status_code=429,
                    detail="Too many concurrent requests, please retry"
                )

    # 执行 LLM 请求
    response = await litellm.completion(**request_params)

    # 调整实际成本...
    ...
```

#### Schema 改动

```prisma
model LiteLLM_VerificationToken {
  // 现有字段...

  // 新增：版本号（乐观锁）
  version: Int @default(0)

  // 复合唯一索引
  @@unique([token, version])
}
```

#### 优点

✅ **无锁**: 不阻塞其他请求
✅ **高并发**: 适合大量并发

#### 缺点

❌ **可能重试**: 高冲突时重试多次
❌ **复杂**: 需要重试逻辑
❌ **不保证**: 重试次数用完仍可能失败

---

### 方案 C: 分布式锁（Redis）

#### 实现代码

```python
import redis
from contextlib import asynccontextmanager

@asynccontextmanager
async def redis_lock(key: str, timeout: int = 10):
    """Redis 分布式锁"""
    lock_key = f"lock:{key}"
    lock_value = str(uuid.uuid4())

    # 尝试获取锁
    acquired = redis_client.set(
        lock_key,
        lock_value,
        nx=True,  # 仅在不存在时设置
        ex=timeout  # 过期时间
    )

    if not acquired:
        raise HTTPException(
            status_code=429,
            detail="Too many concurrent requests"
        )

    try:
        yield
    finally:
        # 释放锁（检查所有权）
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        redis_client.eval(lua_script, 1, lock_key, lock_value)

async def handle_request_with_redis_lock(
    user_api_key_dict: UserAPIKeyAuth,
    request_params: dict
):
    """使用 Redis 分布式锁"""

    async with redis_lock(f"budget:{user_api_key_dict.token}"):
        # 在锁保护下执行检查和扣除
        key = await prisma_client.db.litellm_verificationtoken.find_unique(...)

        if key.spend + estimated_cost >= key.max_budget:
            raise BudgetExceededError()

        await prisma_client.db.litellm_verificationtoken.update(...)

    # 释放锁后执行 LLM 调用
    response = await litellm.completion(**request_params)
    ...
```

#### 优点

✅ **分布式**: 跨多个 Proxy 实例工作
✅ **灵活**: 可以控制锁粒度

#### 缺点

❌ **依赖 Redis**: 额外的基础设施
❌ **复杂**: 锁管理复杂
❌ **风险**: 锁未释放会死锁

---

## 方案对比

| 维度 | 悲观锁 (A) | 乐观锁 (B) | 分布式锁 (C) |
|------|-----------|-----------|-------------|
| **防超支** | ⭐⭐⭐⭐⭐ 100% | ⭐⭐⭐⭐ 高概率 | ⭐⭐⭐⭐⭐ 100% |
| **性能** | ⭐⭐⭐ 有锁等待 | ⭐⭐⭐⭐⭐ 最高 | ⭐⭐⭐ 网络开销 |
| **复杂度** | ⭐⭐⭐⭐ 简单 | ⭐⭐⭐ 需重试 | ⭐⭐ 最复杂 |
| **可靠性** | ⭐⭐⭐⭐⭐ 最高 | ⭐⭐⭐⭐ 较高 | ⭐⭐⭐ 依赖Redis |

### 推荐：**方案 A（悲观锁）+ 性能优化**

理由：
- Budget 超支后果严重，必须100%防止
- 数据库锁性能可接受（优化后锁时间 < 10ms）
- 实现简单，可靠性高

---

## 🎯 最终推荐组合

### 问题 #1 (汇率缓存): Redis + 文件监控混合
### 问题 #2 (货币转换): 数据库事务
### 问题 #3 (Budget 检查): 悲观锁 + 预估扣除

### 实现优先级

1. **Phase 1 实现时**: 先用文件监控（简单）
2. **Phase 3 测试时**: 添加事务保护
3. **上线前**: 评估是否需要 Redis（根据规模）

您同意这些方案吗？或者有其他考虑？
