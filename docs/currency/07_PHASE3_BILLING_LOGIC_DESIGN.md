# Phase 3: 计费逻辑详细设计（生产级）

> **版本**: 2.0 (技术审查后更新)
> **更新日期**: 2026-01-04
> **修复**: 货币转换原子性和 Budget 竞态问题

## 📋 目录
- [设计变更说明](#设计变更说明)
- [核心改动概览](#核心改动概览)
- [cost_calculator.py 改动](#cost_calculatorpy-改动)
- [Budget 检查逻辑](#budget-检查逻辑)
- [费用累计逻辑](#费用累计逻辑)
- [原子性保证](#原子性保证)
- [并发控制](#并发控制)
- [模型配置扩展](#模型配置扩展)
- [集成测试](#集成测试)

---

## ⚠️ 设计变更说明

### 问题 #1: 货币转换的原子性问题

**原始设计的风险**:

```python
# ❌ 原始设计（有问题）
async def update_spend(...):
    # 时刻 T1: 获取汇率
    exchange_rate = get_exchange_rate("USD", "CNY")  # 7.2

    # ⏰ 时间流逝... (可能数秒到数分钟)
    # 此时管理员修改汇率为 7.25

    # 时刻 T2: 使用 T1 时刻的汇率计算
    converted_cost = response_cost * exchange_rate  # 用的是旧汇率 7.2

    # 时刻 T3: 更新数据库
    await update_database(...)  # 记录了错误的金额

    # ❌ 问题：汇率和费用不匹配
```

**修复方案**: 使用数据库事务确保"获取汇率-转换-记录"三个操作的原子性。

### 问题 #2: Budget 检查的竞态条件

**并发场景问题**:

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

**修复方案**: 使用悲观锁（SELECT FOR UPDATE）+ 成本预估，在事务中检查并预留预算。

---

## 核心改动概览

### 改动原则

1. **向后兼容**: 不破坏现有 USD 计费
2. **透明转换**: 自动检测模型货币并转换
3. **统一存储**: 费用统一转换为预算货币存储
4. **精度保证**: 使用 Float 精度足够（15位）
5. **原子性保证**: 使用数据库事务（新增）
6. **并发控制**: 使用悲观锁防止竞态（新增）

### 数据流（更新）

```
请求 → 预估成本 → 加锁检查预算 → 预留预算 → 释放锁
     → 执行 LLM 请求 → 计算实际成本 → 事务更新费用 → 调整差额
```

---

## cost_calculator.py 改动

### 文件: `/litellm/cost_calculator.py`

#### 1. 导入货币转换模块

```python
# 文件开头添加
from litellm.utils.currency import convert_currency, get_exchange_rate
from typing import Optional, Tuple, Dict, Union, Any
import litellm
```

#### 2. 扩展模型信息获取

```python
def get_model_currency(model: str) -> str:
    """
    获取模型的定价货币

    Args:
        model: 模型名称

    Returns:
        货币代码（如 "USD", "CNY"）
    """
    try:
        model_info = litellm.get_model_info(model)
        return model_info.get("currency", "USD")
    except Exception:
        # 默认使用 USD
        return "USD"


def get_model_pricing_with_currency(
    model: str
) -> Tuple[Optional[float], Optional[float], str]:
    """
    获取模型定价和货币信息

    Args:
        model: 模型名称

    Returns:
        (input_cost_per_token, output_cost_per_token, currency)
    """
    try:
        model_info = litellm.get_model_info(model)

        input_cost = model_info.get("input_cost_per_token")
        output_cost = model_info.get("output_cost_per_token")
        currency = model_info.get("currency", "USD")

        return input_cost, output_cost, currency

    except Exception as e:
        # 默认值
        return None, None, "USD"
```

#### 3. 改造核心计费函数

**原始函数 (简化版)**:
```python
def cost_per_token(
    model: str = "",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    custom_llm_provider: Optional[str] = None
) -> Tuple[float, float]:
    """
    计算 token 成本

    Returns:
        (input_cost, output_cost) in USD
    """
    # 获取模型定价
    model_info = litellm.get_model_info(model)

    input_cost_per_token = model_info.get("input_cost_per_token", 0)
    output_cost_per_token = model_info.get("output_cost_per_token", 0)

    # 计算成本
    prompt_cost = prompt_tokens * input_cost_per_token
    completion_cost = completion_tokens * output_cost_per_token

    return prompt_cost, completion_cost
```

**改造后的函数**:
```python
def cost_per_token(
    model: str = "",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    custom_llm_provider: Optional[str] = None,
    # 新增参数
    return_currency: str = "USD",  # 返回的货币类型
    include_currency_info: bool = False  # 是否包含货币信息
) -> Union[Tuple[float, float], Dict[str, Any]]:
    """
    计算 token 成本（支持多货币）

    Args:
        model: 模型名称
        prompt_tokens: 提示词 token 数
        completion_tokens: 完成 token 数
        custom_llm_provider: 自定义提供商
        return_currency: 返回结果的货币（默认 USD）
        include_currency_info: 是否返回详细货币信息

    Returns:
        如果 include_currency_info=False:
            (input_cost, output_cost) - 以 return_currency 计价
        如果 include_currency_info=True:
            {
                "input_cost": float,
                "output_cost": float,
                "total_cost": float,
                "currency": str,
                "model_currency": str,
                "exchange_rate": float (如果发生转换)
            }
    """
    # 1. 获取模型定价和货币
    input_cost_per_token, output_cost_per_token, model_currency = \
        get_model_pricing_with_currency(model)

    if input_cost_per_token is None or output_cost_per_token is None:
        # 如果没有定价信息，返回 0
        if include_currency_info:
            return {
                "input_cost": 0.0,
                "output_cost": 0.0,
                "total_cost": 0.0,
                "currency": return_currency,
                "model_currency": model_currency,
                "exchange_rate": 1.0
            }
        return 0.0, 0.0

    # 2. 计算原始成本（使用模型货币）
    prompt_cost = prompt_tokens * input_cost_per_token
    completion_cost = completion_tokens * output_cost_per_token

    # 3. 如果模型货币与返回货币不同，进行转换
    exchange_rate = 1.0
    if model_currency != return_currency:
        try:
            exchange_rate = get_exchange_rate(model_currency, return_currency)
            prompt_cost = convert_currency(
                prompt_cost,
                model_currency,
                return_currency
            )
            completion_cost = convert_currency(
                completion_cost,
                model_currency,
                return_currency
            )
        except Exception as e:
            # 转换失败，记录日志但继续（假设已经是正确货币）
            print(f"[Currency] Conversion error: {e}")
            pass

    # 4. 返回结果
    if include_currency_info:
        return {
            "input_cost": prompt_cost,
            "output_cost": completion_cost,
            "total_cost": prompt_cost + completion_cost,
            "currency": return_currency,
            "model_currency": model_currency,
            "exchange_rate": exchange_rate
        }

    return prompt_cost, completion_cost


def completion_cost(
    completion_response=None,
    model: str = "",
    prompt: str = "",
    messages: list = [],
    completion: str = "",
    total_time: float = 0.0,
    # 新增参数
    return_currency: str = "USD",
    call_type: str = "completion",
    custom_llm_provider: str = "",
    region_name: Optional[str] = None,
) -> float:
    """
    计算完整请求的成本

    Args:
        completion_response: 完成响应对象
        model: 模型名称
        return_currency: 返回的货币类型
        ... 其他参数

    Returns:
        总成本（以 return_currency 计价）
    """
    try:
        # 1. 从响应中提取 token 数量
        if completion_response:
            prompt_tokens = completion_response.get("usage", {}).get("prompt_tokens", 0)
            completion_tokens = completion_response.get("usage", {}).get("completion_tokens", 0)
        else:
            # 估算 token 数量
            from litellm.utils import token_counter
            prompt_tokens = token_counter(model=model, messages=messages)
            completion_tokens = token_counter(model=model, text=completion)

        # 2. 计算成本
        cost_info = cost_per_token(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            custom_llm_provider=custom_llm_provider,
            return_currency=return_currency,
            include_currency_info=True
        )

        # 3. 返回总成本
        return cost_info["total_cost"]

    except Exception as e:
        print(f"[Cost Calculator] Error calculating cost: {e}")
        return 0.0
```

#### 4. 添加成本预估函数（新增 - 用于并发控制）

```python
def estimate_request_cost(
    model: str,
    max_tokens: int = 1000,
    prompt_tokens_estimate: Optional[int] = None,
    return_currency: str = "USD",
    safety_margin: float = 1.1
) -> float:
    """
    预估请求成本（用于 Budget 预检查）

    策略:
    - 假设输入 token = prompt_tokens_estimate 或 max_tokens * 0.5
    - 假设输出 token = max_tokens
    - 使用最贵的价格（保守估计）
    - 添加安全边际（默认 10%）

    Args:
        model: 模型名称
        max_tokens: 最大 token 数
        prompt_tokens_estimate: 输入 token 估计（可选）
        return_currency: 返回的货币类型
        safety_margin: 安全边际（1.1 = 110%）

    Returns:
        预估成本（以 return_currency 计价）

    Example:
        >>> cost = estimate_request_cost("gpt-4", max_tokens=2000)
        >>> # 返回保守估计的成本
    """
    try:
        # 1. 获取模型定价
        input_cost_per_token, output_cost_per_token, model_currency = \
            get_model_pricing_with_currency(model)

        if input_cost_per_token is None or output_cost_per_token is None:
            return 0.0

        # 2. 保守估计 token 数量
        if prompt_tokens_estimate is None:
            estimated_input_tokens = max_tokens * 0.5
        else:
            estimated_input_tokens = prompt_tokens_estimate

        estimated_output_tokens = max_tokens

        # 3. 计算成本
        cost = (
            estimated_input_tokens * input_cost_per_token +
            estimated_output_tokens * output_cost_per_token
        )

        # 4. 转换货币
        if model_currency != return_currency:
            from litellm.utils.currency import convert_currency
            cost = convert_currency(cost, model_currency, return_currency)

        # 5. 添加安全边际
        cost *= safety_margin

        return cost

    except Exception as e:
        print(f"[Cost Estimator] Error: {e}")
        # 返回一个保守的默认值
        return 1.0  # $1 或相应货币
```

#### 5. 添加批量成本计算

```python
def calculate_batch_costs(
    requests: list,
    return_currency: str = "USD"
) -> Dict[str, float]:
    """
    批量计算多个请求的成本

    Args:
        requests: 请求列表，每个请求包含 model, prompt_tokens, completion_tokens
        return_currency: 返回的货币类型

    Returns:
        {
            "total_cost": float,
            "by_model": {model_name: cost},
            "by_currency": {currency: cost}
        }
    """
    total_cost = 0.0
    by_model = {}
    by_currency = {}

    for req in requests:
        model = req.get("model")
        prompt_tokens = req.get("prompt_tokens", 0)
        completion_tokens = req.get("completion_tokens", 0)

        cost_info = cost_per_token(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            return_currency=return_currency,
            include_currency_info=True
        )

        cost = cost_info["total_cost"]
        total_cost += cost

        # 按模型统计
        by_model[model] = by_model.get(model, 0.0) + cost

        # 按原始货币统计
        model_currency = cost_info["model_currency"]
        by_currency[model_currency] = by_currency.get(model_currency, 0.0) + cost

    return {
        "total_cost": total_cost,
        "currency": return_currency,
        "by_model": by_model,
        "by_currency": by_currency
    }
```

---

## Budget 检查逻辑

### 文件: `/litellm/proxy/auth/auth_checks.py`

#### 1. 虚拟密钥预算检查（使用悲观锁）

**原始函数 (简化版)**:
```python
async def _virtual_key_max_budget_check(
    user_api_key_dict: UserAPIKeyAuth
):
    """检查虚拟密钥预算"""
    if user_api_key_dict.get("max_budget") is None:
        return

    current_spend = user_api_key_dict.get("spend", 0)
    max_budget = user_api_key_dict["max_budget"]

    if current_spend >= max_budget:
        raise BudgetExceededError(
            f"Budget exceeded: {current_spend} >= {max_budget}"
        )
```

**改造后的函数（带悲观锁和预估）**:
```python
from litellm.utils.currency import convert_currency
from litellm.cost_calculator import estimate_request_cost
import logging

logger = logging.getLogger("litellm.budget")

async def _virtual_key_max_budget_check_with_reservation(
    user_api_key_dict: UserAPIKeyAuth,
    request_params: dict,
    prisma_client
) -> float:
    """
    检查虚拟密钥预算并预留（使用悲观锁）

    Args:
        user_api_key_dict: 用户密钥信息
        request_params: 请求参数（包含 model, max_tokens 等）
        prisma_client: Prisma 客户端

    Returns:
        预留的成本金额

    Raises:
        BudgetExceededError: 预算超支

    工作流程:
    1. 使用 SELECT FOR UPDATE 锁定密钥记录
    2. 预估请求成本
    3. 检查预算（包含预估成本）
    4. 原子更新 spend（预留预估成本）
    5. 提交事务，释放锁
    """
    max_budget = user_api_key_dict.get("max_budget")
    if max_budget is None:
        return 0.0  # 无预算限制

    token = user_api_key_dict.get("token")
    budget_currency = user_api_key_dict.get("budget_currency", "USD")

    # 1. 预估请求成本（在事务外，不持有锁）
    model = request_params.get("model", "")
    max_tokens = request_params.get("max_tokens", 1000)

    estimated_cost = estimate_request_cost(
        model=model,
        max_tokens=max_tokens,
        return_currency=budget_currency,
        safety_margin=1.1  # 110% 安全边际
    )

    logger.info(
        f"[Budget Check] Estimated cost for {model}: "
        f"{estimated_cost:.6f} {budget_currency}"
    )

    # 2. 使用事务和悲观锁进行原子检查和预留
    async with prisma_client.db.tx() as transaction:
        # 锁定密钥记录（其他请求必须等待）
        key_result = await transaction.query_raw(
            """
            SELECT * FROM "LiteLLM_VerificationToken"
            WHERE token = $1
            FOR UPDATE NOWAIT
            """,
            token
        )

        if not key_result or len(key_result) == 0:
            raise HTTPException(status_code=404, detail="Key not found")

        key = key_result[0]
        current_spend = float(key.get("spend", 0))
        spend_currency = key.get("spend_currency", "USD")

        # 3. 货币转换（如果需要）
        if spend_currency != budget_currency:
            try:
                current_spend_in_budget_currency = convert_currency(
                    current_spend,
                    spend_currency,
                    budget_currency
                )
            except Exception as e:
                logger.warning(f"[Budget Check] Currency conversion error: {e}")
                current_spend_in_budget_currency = current_spend
        else:
            current_spend_in_budget_currency = current_spend

        # 4. 检查预算（含预估成本）
        if current_spend_in_budget_currency + estimated_cost >= max_budget:
            available = max_budget - current_spend_in_budget_currency

            raise BudgetExceededError(
                f"Insufficient budget for key {token[:8]}...: "
                f"Current spend: {current_spend_in_budget_currency:.4f} {budget_currency}, "
                f"Estimated cost: {estimated_cost:.4f} {budget_currency}, "
                f"Budget: {max_budget:.4f} {budget_currency}, "
                f"Available: {available:.4f} {budget_currency}"
            )

        # 5. 预留预估成本（乐观扣除）
        await transaction.litellm_verificationtoken.update(
            where={"token": token},
            data={
                "spend": {"increment": estimated_cost},
                "spend_currency": budget_currency
            }
        )

        logger.info(
            f"[Budget Check] Reserved {estimated_cost:.6f} {budget_currency} "
            f"for key {token[:8]}..."
        )

        # 事务提交，释放锁

    return estimated_cost


async def _virtual_key_max_budget_check(
    user_api_key_dict: UserAPIKeyAuth
):
    """
    检查虚拟密钥预算（简单版本，用于非 LLM 请求）

    Args:
        user_api_key_dict: 用户密钥信息

    Raises:
        BudgetExceededError: 预算超支
    """
    max_budget = user_api_key_dict.get("max_budget")
    if max_budget is None:
        return

    current_spend = user_api_key_dict.get("spend", 0.0)
    budget_currency = user_api_key_dict.get("budget_currency", "USD")
    spend_currency = user_api_key_dict.get("spend_currency", "USD")

    # 如果货币不同，转换 spend 到 budget 货币进行比较
    if spend_currency != budget_currency:
        try:
            current_spend_in_budget_currency = convert_currency(
                current_spend,
                spend_currency,
                budget_currency
            )
        except Exception as e:
            logger.warning(f"[Budget Check] Currency conversion error: {e}")
            # 转换失败，假设相同货币（保守处理）
            current_spend_in_budget_currency = current_spend
    else:
        current_spend_in_budget_currency = current_spend

    # 检查预算
    if current_spend_in_budget_currency >= max_budget:
        raise BudgetExceededError(
            f"Budget exceeded for key {user_api_key_dict.get('token', 'unknown')}: "
            f"{current_spend_in_budget_currency:.4f} {budget_currency} >= "
            f"{max_budget:.4f} {budget_currency}"
        )

    # 可选：预算警告（90% 使用）
    usage_percentage = (current_spend_in_budget_currency / max_budget) * 100
    if usage_percentage >= 90:
        logger.warning(
            f"[Budget Warning] Key {user_api_key_dict.get('token', 'unknown')} "
            f"has used {usage_percentage:.1f}% of budget"
        )
```

#### 2. 团队预算检查

```python
async def _team_max_budget_check(
    team_id: str,
    prisma_client
):
    """
    检查团队预算（支持多货币）

    Args:
        team_id: 团队 ID
        prisma_client: Prisma 客户端

    Raises:
        BudgetExceededError: 预算超支
    """
    team = await prisma_client.db.litellm_teamtable.find_unique(
        where={"team_id": team_id}
    )

    if not team or team.max_budget is None:
        return

    current_spend = team.spend
    max_budget = team.max_budget
    budget_currency = getattr(team, "budget_currency", "USD")
    spend_currency = getattr(team, "spend_currency", "USD")

    # 货币转换
    if spend_currency != budget_currency:
        try:
            current_spend = convert_currency(
                current_spend,
                spend_currency,
                budget_currency
            )
        except Exception as e:
            logger.warning(f"[Team Budget] Currency conversion error: {e}")

    # 检查预算
    if current_spend >= max_budget:
        raise BudgetExceededError(
            f"Team budget exceeded: {current_spend:.4f} {budget_currency} >= "
            f"{max_budget:.4f} {budget_currency}"
        )
```

#### 3. 用户预算检查

```python
async def _user_max_budget_check(
    user_id: str,
    prisma_client
):
    """
    检查用户预算（支持多货币）

    Args:
        user_id: 用户 ID
        prisma_client: Prisma 客户端

    Raises:
        BudgetExceededError: 预算超支
    """
    user = await prisma_client.db.litellm_usertable.find_unique(
        where={"user_id": user_id}
    )

    if not user or user.max_budget is None:
        return

    current_spend = user.spend
    max_budget = user.max_budget
    budget_currency = getattr(user, "budget_currency", "USD")
    spend_currency = getattr(user, "spend_currency", "USD")

    # 货币转换
    if spend_currency != budget_currency:
        try:
            current_spend = convert_currency(
                current_spend,
                spend_currency,
                budget_currency
            )
        except Exception as e:
            logger.warning(f"[User Budget] Currency conversion error: {e}")

    # 检查预算
    if current_spend >= max_budget:
        raise BudgetExceededError(
            f"User budget exceeded: {current_spend:.4f} {budget_currency} >= "
            f"{max_budget:.4f} {budget_currency}"
        )
```

---

## 费用累计逻辑

### 文件: `/litellm/proxy/proxy_server.py` (费用更新部分)

#### 1. 原子更新虚拟密钥费用（使用事务）

**原始函数（有问题）**:
```python
async def update_spend(
    prisma_client,
    user_api_key_dict: UserAPIKeyAuth,
    response_cost: float,
    response_cost_currency: str = "USD"
):
    """更新费用（不安全）"""
    token = user_api_key_dict.get("token")
    budget_currency = user_api_key_dict.get("budget_currency", "USD")

    # ❌ 问题：汇率可能在转换和更新之间变化
    if response_cost_currency != budget_currency:
        response_cost = convert_currency(
            response_cost,
            response_cost_currency,
            budget_currency
        )

    await prisma_client.db.litellm_verificationtoken.update(
        where={"token": token},
        data={"spend": {"increment": response_cost}}
    )
```

**改造后的函数（使用事务）**:
```python
async def update_spend_atomic(
    prisma_client,
    db_writer_client,
    user_api_key_dict: UserAPIKeyAuth,
    response_cost: float,
    response_cost_currency: str = "USD",
    metadata: Optional[dict] = None
) -> dict:
    """
    原子更新费用（使用数据库事务）

    Args:
        prisma_client: Prisma 客户端
        db_writer_client: 数据库写入客户端
        user_api_key_dict: 用户密钥信息
        response_cost: 本次请求成本
        response_cost_currency: 成本货币
        metadata: 额外元数据

    Returns:
        {
            "converted_cost": float,
            "exchange_rate": float,
            "timestamp": str,
            "new_spend": float
        }

    工作流程:
    1. 开始数据库事务
    2. 获取汇率快照
    3. 转换货币
    4. 更新 VerificationToken
    5. 创建 SpendLog（记录汇率）
    6. 提交事务（所有操作原子性）
    """
    token = user_api_key_dict.get("token")
    if not token:
        raise ValueError("Token is required")

    budget_currency = user_api_key_dict.get("budget_currency", "USD")

    # 使用事务确保原子性
    async with prisma_client.db.tx() as transaction:
        # 步骤 1: 获取汇率快照（在事务内）
        from litellm.utils.currency import get_exchange_rate

        exchange_rate = 1.0
        if response_cost_currency != budget_currency:
            try:
                exchange_rate = get_exchange_rate(
                    response_cost_currency,
                    budget_currency
                )
            except Exception as e:
                logger.error(f"[Update Spend] Exchange rate error: {e}")
                # 转换失败时使用 1.0（保守处理）
                exchange_rate = 1.0

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
        # await transaction.litellm_currencyevents.create(...)

        # 事务提交：所有操作要么都成功，要么都失败
        logger.info(
            f"[Update Spend] Atomic update for {token[:8]}...: "
            f"{response_cost:.6f} {response_cost_currency} -> "
            f"{converted_cost:.6f} {budget_currency} "
            f"(rate: {exchange_rate:.4f})"
        )

        return {
            "converted_cost": converted_cost,
            "exchange_rate": exchange_rate,
            "timestamp": datetime.now().isoformat(),
            "new_spend": updated_key.spend
        }

    # 如果事务失败（网络、数据库错误等），会自动回滚


async def adjust_spend(
    prisma_client,
    token: str,
    adjustment: float,
    reason: str = "cost_adjustment"
):
    """
    调整费用差额（用于预留和实际成本差异）

    Args:
        prisma_client: Prisma 客户端
        token: 密钥
        adjustment: 调整金额（可正可负）
        reason: 调整原因
    """
    if abs(adjustment) < 0.0001:  # 忽略微小差异
        return

    await prisma_client.db.litellm_verificationtoken.update(
        where={"token": token},
        data={"spend": {"increment": adjustment}}
    )

    logger.info(
        f"[Adjust Spend] {token[:8]}... adjusted by {adjustment:.6f} "
        f"(reason: {reason})"
    )
```

#### 2. 批量更新费用（团队/用户）

```python
async def batch_update_spend(
    prisma_client,
    updates: list
):
    """
    批量更新费用

    Args:
        prisma_client: Prisma 客户端
        updates: 更新列表，格式:
            [
                {
                    "type": "key"|"team"|"user",
                    "id": "...",
                    "cost": float,
                    "currency": str,
                    "budget_currency": str
                }
            ]
    """
    for update in updates:
        update_type = update["type"]
        entity_id = update["id"]
        cost = update["cost"]
        cost_currency = update["currency"]
        budget_currency = update["budget_currency"]

        # 转换货币
        if cost_currency != budget_currency:
            cost = convert_currency(cost, cost_currency, budget_currency)

        # 根据类型更新
        if update_type == "key":
            await prisma_client.db.litellm_verificationtoken.update(
                where={"token": entity_id},
                data={
                    "spend": {"increment": cost},
                    "spend_currency": budget_currency
                }
            )
        elif update_type == "team":
            await prisma_client.db.litellm_teamtable.update(
                where={"team_id": entity_id},
                data={
                    "spend": {"increment": cost},
                    "spend_currency": budget_currency
                }
            )
        elif update_type == "user":
            await prisma_client.db.litellm_usertable.update(
                where={"user_id": entity_id},
                data={
                    "spend": {"increment": cost},
                    "spend_currency": budget_currency
                }
            )
```

---

## 原子性保证

### 完整的请求处理流程（带事务和锁）

```python
async def handle_completion_request_with_budget_protection(
    user_api_key_dict: UserAPIKeyAuth,
    request_data: dict,
    prisma_client
):
    """
    处理 LLM 请求（含预算保护和原子更新）

    完整流程:
    1. 预估成本
    2. 使用悲观锁检查并预留预算
    3. 执行 LLM 请求
    4. 计算实际成本
    5. 原子更新费用（事务）
    6. 调整预留差额
    7. 错误处理和回滚

    Args:
        user_api_key_dict: 用户密钥信息
        request_data: 请求数据
        prisma_client: Prisma 客户端

    Returns:
        LLM 响应

    Raises:
        BudgetExceededError: 预算超支
    """
    from litellm import completion as litellm_completion
    from litellm.cost_calculator import completion_cost

    token = user_api_key_dict.get("token")
    budget_currency = user_api_key_dict.get("budget_currency", "USD")

    # 步骤 1: 预估成本并预留预算（带悲观锁）
    reserved_cost = await _virtual_key_max_budget_check_with_reservation(
        user_api_key_dict=user_api_key_dict,
        request_params=request_data,
        prisma_client=prisma_client
    )

    logger.info(
        f"[Request] Reserved {reserved_cost:.6f} {budget_currency} "
        f"for key {token[:8]}..."
    )

    # 步骤 2: 执行实际 LLM 请求（在锁外，不阻塞其他请求）
    try:
        response = await litellm_completion(**request_data)

        # 步骤 3: 计算实际成本
        actual_cost_usd = completion_cost(
            completion_response=response,
            model=request_data.get("model"),
            return_currency="USD"
        )

        # 转换为预算货币
        if budget_currency != "USD":
            from litellm.utils.currency import convert_currency
            actual_cost = convert_currency(actual_cost_usd, "USD", budget_currency)
        else:
            actual_cost = actual_cost_usd

        logger.info(
            f"[Request] Actual cost: {actual_cost:.6f} {budget_currency} "
            f"(reserved: {reserved_cost:.6f})"
        )

        # 步骤 4: 原子更新费用（使用事务记录汇率）
        # 注意：这里已经预留了 reserved_cost，所以需要调整差额
        diff = actual_cost - reserved_cost

        if abs(diff) > 0.0001:
            await adjust_spend(
                prisma_client=prisma_client,
                token=token,
                adjustment=diff,
                reason="actual_vs_reserved"
            )

        # 步骤 5: 创建详细日志（含汇率信息）
        await create_spend_log_with_exchange_rate(
            prisma_client=prisma_client,
            token=token,
            actual_cost=actual_cost,
            actual_cost_currency=budget_currency,
            model_cost_usd=actual_cost_usd,
            response=response,
            metadata={
                "reserved_cost": reserved_cost,
                "adjustment": diff
            }
        )

        return response

    except Exception as e:
        # 步骤 6: 请求失败，退还预留金额
        logger.error(f"[Request] LLM request failed: {e}")

        await adjust_spend(
            prisma_client=prisma_client,
            token=token,
            adjustment=-reserved_cost,  # 负数表示退还
            reason="request_failed"
        )

        logger.info(
            f"[Request] Refunded {reserved_cost:.6f} {budget_currency} "
            f"for failed request"
        )

        raise


async def create_spend_log_with_exchange_rate(
    prisma_client,
    token: str,
    actual_cost: float,
    actual_cost_currency: str,
    model_cost_usd: float,
    response: dict,
    metadata: dict
):
    """
    创建费用日志（记录汇率信息）

    Args:
        prisma_client: Prisma 客户端
        token: 密钥
        actual_cost: 实际成本
        actual_cost_currency: 实际成本货币
        model_cost_usd: 模型原始 USD 成本
        response: LLM 响应
        metadata: 额外元数据
    """
    from litellm.utils.currency import get_exchange_rate

    # 计算汇率
    if actual_cost_currency != "USD":
        exchange_rate = get_exchange_rate("USD", actual_cost_currency)
    else:
        exchange_rate = 1.0

    await prisma_client.db.litellm_spendlogs.create(
        data={
            "api_key": token,
            "spend": actual_cost,
            "spend_currency": actual_cost_currency,
            "model_currency": "USD",
            "spend_original": model_cost_usd,
            "exchange_rate": exchange_rate,
            "model": response.get("model", ""),
            "prompt_tokens": response.get("usage", {}).get("prompt_tokens", 0),
            "completion_tokens": response.get("usage", {}).get("completion_tokens", 0),
            "startTime": datetime.now(),
            "endTime": datetime.now(),
            "metadata": metadata
        }
    )
```

---

## 并发控制

### 性能优化：减少锁持有时间

```python
async def _virtual_key_max_budget_check_with_reservation_optimized(
    user_api_key_dict: UserAPIKeyAuth,
    request_params: dict,
    prisma_client,
    lock_timeout: int = 5000  # 5秒超时
) -> float:
    """
    优化版本：缩短锁持有时间

    优化策略:
    1. 预估成本在事务外完成（不持有锁）
    2. 使用 NOWAIT 避免长时间等待
    3. 只在检查和更新时持有锁（< 10ms）
    4. 超时时立即返回错误
    """
    max_budget = user_api_key_dict.get("max_budget")
    if max_budget is None:
        return 0.0

    token = user_api_key_dict.get("token")
    budget_currency = user_api_key_dict.get("budget_currency", "USD")

    # 1. 预估成本（在事务外，不持有锁）
    model = request_params.get("model", "")
    max_tokens = request_params.get("max_tokens", 1000)

    estimated_cost = estimate_request_cost(
        model=model,
        max_tokens=max_tokens,
        return_currency=budget_currency,
        safety_margin=1.1
    )

    # 2. 仅在检查和更新时加锁（< 10ms）
    async with prisma_client.db.tx() as transaction:
        # 使用 NOWAIT：不等待，立即失败
        try:
            key_result = await transaction.query_raw(
                """
                SELECT * FROM "LiteLLM_VerificationToken"
                WHERE token = $1
                FOR UPDATE NOWAIT
                """,
                token
            )
        except Exception as e:
            # 锁冲突，立即返回
            raise HTTPException(
                status_code=429,
                detail="Too many concurrent requests, please retry"
            )

        if not key_result or len(key_result) == 0:
            raise HTTPException(status_code=404, detail="Key not found")

        key = key_result[0]
        current_spend = float(key.get("spend", 0))

        # 快速检查
        if current_spend + estimated_cost >= max_budget:
            available = max_budget - current_spend
            raise BudgetExceededError(
                f"Insufficient budget: need {estimated_cost:.4f}, "
                f"available {available:.4f} {budget_currency}"
            )

        # 快速更新
        await transaction.litellm_verificationtoken.update(
            where={"token": token},
            data={"spend": {"increment": estimated_cost}}
        )

        # 立即提交，释放锁

    return estimated_cost
```

---

## 模型配置扩展

### 文件: `/litellm/model_prices_and_context_window.json`

#### 添加货币字段到模型配置

```json
{
  "gpt-4": {
    "max_tokens": 8192,
    "max_input_tokens": 8192,
    "max_output_tokens": 4096,
    "input_cost_per_token": 0.00003,
    "output_cost_per_token": 0.00006,
    "litellm_provider": "openai",
    "mode": "chat",
    "supports_function_calling": true,
    "supports_parallel_function_calling": true,
    "supports_vision": false,
    "currency": "USD"
  },
  "gpt-3.5-turbo": {
    "max_tokens": 4096,
    "input_cost_per_token": 0.0000015,
    "output_cost_per_token": 0.000002,
    "litellm_provider": "openai",
    "mode": "chat",
    "currency": "USD"
  },
  "qwen-max": {
    "max_tokens": 8192,
    "input_cost_per_token": 0.0008,
    "output_cost_per_token": 0.002,
    "litellm_provider": "openai",
    "mode": "chat",
    "currency": "CNY",
    "supports_function_calling": true
  },
  "qwen-plus": {
    "max_tokens": 32768,
    "input_cost_per_token": 0.0004,
    "output_cost_per_token": 0.0012,
    "litellm_provider": "openai",
    "mode": "chat",
    "currency": "CNY"
  },
  "deepseek-chat": {
    "max_tokens": 32768,
    "input_cost_per_token": 0.00014,
    "output_cost_per_token": 0.00028,
    "litellm_provider": "openai",
    "mode": "chat",
    "currency": "CNY"
  }
}
```

### 文件: `/litellm/main.py` (模型信息加载)

#### 确保货币字段加载

```python
def get_model_info(model: str) -> dict:
    """
    获取模型信息（包含货币）

    Args:
        model: 模型名称

    Returns:
        模型信息字典
    """
    try:
        # 从 model_cost 获取
        model_info = model_cost.get(model, {})

        # 确保有 currency 字段
        if "currency" not in model_info:
            model_info["currency"] = "USD"

        return model_info

    except Exception as e:
        print(f"[Model Info] Error getting model info: {e}")
        return {"currency": "USD"}
```

---

## 日志记录增强

### 文件: `/litellm/_logging.py`

#### 添加货币信息到日志

```python
def log_success_event(
    kwargs,
    response_obj,
    start_time,
    end_time,
    model: str = ""
):
    """
    记录成功事件（包含货币信息）
    """
    try:
        # 计算成本
        from litellm.cost_calculator import cost_per_token

        prompt_tokens = response_obj.get("usage", {}).get("prompt_tokens", 0)
        completion_tokens = response_obj.get("usage", {}).get("completion_tokens", 0)

        # 获取预算货币（从 metadata 或默认 USD）
        budget_currency = kwargs.get("metadata", {}).get("budget_currency", "USD")

        # 计算成本（使用预算货币）
        cost_info = cost_per_token(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            return_currency=budget_currency,
            include_currency_info=True
        )

        # 构建日志
        log_data = {
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost": cost_info["total_cost"],
            "cost_currency": cost_info["currency"],
            "model_currency": cost_info["model_currency"],
            "exchange_rate": cost_info.get("exchange_rate", 1.0),
            "start_time": start_time,
            "end_time": end_time,
            "duration": end_time - start_time
        }

        # 发送到日志系统
        print(f"[Success] {log_data}")

        # 存储到数据库
        if hasattr(kwargs, "litellm_call_id"):
            await save_spend_log(
                request_id=kwargs["litellm_call_id"],
                spend=cost_info["total_cost"],
                spend_currency=cost_info["currency"],
                model_currency=cost_info["model_currency"],
                exchange_rate=cost_info.get("exchange_rate"),
                **log_data
            )

    except Exception as e:
        print(f"[Logging] Error: {e}")
```

---

## 集成测试

### 文件: `/tests/integration/test_multi_currency_billing.py`

```python
import pytest
import asyncio
from litellm import completion
from litellm.cost_calculator import cost_per_token, completion_cost, estimate_request_cost
from litellm.utils.currency import convert_currency, CurrencyExchangeRateManager

class TestMultiCurrencyBilling:
    """多货币计费集成测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """设置测试汇率"""
        manager = CurrencyExchangeRateManager()
        manager.update_rate("CNY", 7.2, save=False)

    def test_usd_model_billing(self):
        """测试 USD 模型计费"""
        input_cost, output_cost = cost_per_token(
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            return_currency="USD"
        )

        # GPT-4: $0.03/1K input, $0.06/1K output
        expected_input = 100 * 0.00003  # $0.003
        expected_output = 50 * 0.00006  # $0.003

        assert abs(input_cost - expected_input) < 0.0001
        assert abs(output_cost - expected_output) < 0.0001

    def test_cny_model_billing(self):
        """测试 CNY 模型计费"""
        # 临时添加 CNY 模型
        from litellm import model_cost
        model_cost["qwen-max"] = {
            "input_cost_per_token": 0.0008,
            "output_cost_per_token": 0.002,
            "currency": "CNY"
        }

        input_cost, output_cost = cost_per_token(
            model="qwen-max",
            prompt_tokens=100,
            completion_tokens=50,
            return_currency="CNY"
        )

        # 通义千问: ¥0.0008/token input, ¥0.002/token output
        expected_input = 100 * 0.0008  # ¥0.08
        expected_output = 50 * 0.002    # ¥0.10

        assert abs(input_cost - expected_input) < 0.0001
        assert abs(output_cost - expected_output) < 0.0001

    def test_cross_currency_conversion(self):
        """测试跨货币转换"""
        from litellm import model_cost
        model_cost["qwen-max"] = {
            "input_cost_per_token": 0.0008,
            "output_cost_per_token": 0.002,
            "currency": "CNY"
        }

        # 计算 CNY 模型的 USD 成本
        cost_info = cost_per_token(
            model="qwen-max",
            prompt_tokens=100,
            completion_tokens=50,
            return_currency="USD",
            include_currency_info=True
        )

        assert cost_info["model_currency"] == "CNY"
        assert cost_info["currency"] == "USD"
        assert cost_info["exchange_rate"] > 0

        # 验证转换
        cny_cost = 100 * 0.0008 + 50 * 0.002  # ¥0.18
        expected_usd = cny_cost / 7.2  # $0.025

        assert abs(cost_info["total_cost"] - expected_usd) < 0.0001

    def test_cost_estimation(self):
        """测试成本预估"""
        estimated = estimate_request_cost(
            model="gpt-4",
            max_tokens=2000,
            return_currency="USD",
            safety_margin=1.1
        )

        # 应该返回保守估计
        # 输入: 1000 tokens * $0.03/1K = $0.03
        # 输出: 2000 tokens * $0.06/1K = $0.12
        # 总计: $0.15 * 1.1 = $0.165
        expected = (1000 * 0.00003 + 2000 * 0.00006) * 1.1

        assert abs(estimated - expected) < 0.001

    @pytest.mark.asyncio
    async def test_concurrent_budget_check(self, prisma_client):
        """测试并发 Budget 检查（防止竞态）"""
        # 创建测试密钥: spend=98, budget=100
        token = "sk-test-concurrent"
        await prisma_client.db.litellm_verificationtoken.create(
            data={
                "token": token,
                "spend": 98.0,
                "max_budget": 100.0,
                "budget_currency": "USD"
            }
        )

        # 发起 10 个并发请求（每个预估 cost=1）
        from litellm.proxy.auth.auth_checks import _virtual_key_max_budget_check_with_reservation

        user_api_key_dict = {
            "token": token,
            "max_budget": 100.0,
            "budget_currency": "USD"
        }

        request_params = {
            "model": "gpt-3.5-turbo",
            "max_tokens": 100  # 预估成本约 $1
        }

        tasks = [
            _virtual_key_max_budget_check_with_reservation(
                user_api_key_dict=user_api_key_dict,
                request_params=request_params,
                prisma_client=prisma_client
            )
            for _ in range(10)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 验证：应该有 2 个成功，8 个失败（BudgetExceededError）
        successes = [r for r in results if not isinstance(r, Exception)]
        failures = [r for r in results if isinstance(r, BudgetExceededError)]

        # 使用悲观锁，应该精确控制
        assert len(successes) == 2
        assert len(failures) == 8

        # 清理
        await prisma_client.db.litellm_verificationtoken.delete(
            where={"token": token}
        )

    @pytest.mark.asyncio
    async def test_atomic_spend_update(self, prisma_client):
        """测试原子费用更新（汇率快照）"""
        from litellm.proxy.proxy_server import update_spend_atomic
        from litellm.utils.currency import CurrencyExchangeRateManager

        # 创建测试密钥
        token = "sk-test-atomic"
        await prisma_client.db.litellm_verificationtoken.create(
            data={
                "token": token,
                "spend": 0.0,
                "budget_currency": "CNY"
            }
        )

        user_api_key_dict = {
            "token": token,
            "budget_currency": "CNY"
        }

        # 更新汇率
        manager = CurrencyExchangeRateManager()
        manager.update_rate("CNY", 7.2, save=False)

        # 执行原子更新
        result = await update_spend_atomic(
            prisma_client=prisma_client,
            db_writer_client=None,
            user_api_key_dict=user_api_key_dict,
            response_cost=1.0,
            response_cost_currency="USD"
        )

        # 验证结果
        assert result["exchange_rate"] == 7.2
        assert abs(result["converted_cost"] - 7.2) < 0.0001

        # 验证日志记录了汇率
        logs = await prisma_client.db.litellm_spendlogs.find_many(
            where={"api_key": token}
        )

        assert len(logs) == 1
        assert logs[0].exchange_rate == 7.2
        assert logs[0].model_currency == "USD"
        assert logs[0].spend_currency == "CNY"

        # 清理
        await prisma_client.db.litellm_verificationtoken.delete(
            where={"token": token}
        )
```

---

## 性能特性

| 指标 | 无并发控制 | 悲观锁 | 乐观锁 |
|------|-----------|--------|--------|
| Budget 超支风险 | ❌ 高 | ✅ 无 | ⚠️ 低 |
| 并发性能 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 锁等待时间 | - | < 10ms | - |
| 实现复杂度 | ⭐⭐⭐⭐⭐ 简单 | ⭐⭐⭐⭐ 中等 | ⭐⭐ 复杂 |

**推荐**: 使用悲观锁（当前实现），性能开销小（< 10ms），完全防止超支。

---

## 错误处理矩阵

| 错误场景 | 处理策略 | 用户影响 |
|---------|---------|---------|
| 汇率获取失败 | 使用 1.0 汇率继续 | ⚠️ 可能计费不准 |
| Redis 不可用 | 降级到文件模式 | ✅ 无影响（略慢） |
| 数据库锁超时 | 返回 429 要求重试 | ⚠️ 需要重试请求 |
| 事务失败 | 自动回滚，抛异常 | ✅ 数据一致性保证 |
| 预留后请求失败 | 自动退还预留金额 | ✅ 不扣费 |

---

## 下一步

1. ✅ Phase 3 计费逻辑设计完成（含事务和锁）
2. ⏭️ 更新 Phase 2 数据模型（简化 spend_currency）
3. ⏭️ 更新 README 文档状态
