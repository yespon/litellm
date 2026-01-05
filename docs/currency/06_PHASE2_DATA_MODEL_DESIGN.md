# Phase 2: 数据模型详细设计（生产级）

> **版本**: 2.0 (技术审查后更新)
> **更新日期**: 2026-01-04
> **修复**: 简化 spend_currency 语义

## 📋 目录
- [设计变更说明](#设计变更说明)
- [TypedDict 定义](#typeddict-定义)
- [Pydantic 模型](#pydantic-模型)
- [数据库模型扩展](#数据库模型扩展)
- [数据访问层](#数据访问层)
- [迁移脚本](#迁移脚本)
- [测试数据生成](#测试数据生成)

---

## ⚠️ 设计变更说明

### 问题: spend_currency 语义不清晰

**原始设计的混淆**:

在初始设计中，`spend_currency` 和 `budget_currency` 是两个独立字段，可能导致混淆：

```python
# ❌ 原始设计（语义不明确）
class UserAPIKeyAuth(TypedDict):
    budget_currency: str  # 预算货币
    spend_currency: str   # 费用货币 - 这是什么？可以不同吗？

# 用户可能疑惑：
# - spend_currency 可以与 budget_currency 不同吗？
# - 如果不同，如何处理？
# - 什么时候需要转换？
```

**修复方案: 简化设计**:

**核心原则**:
1. **单一货币源**: 每个实体（Key/Team/User）只有一个货币 - `budget_currency`
2. **自动同步**: `spend_currency` 始终自动设置为 `budget_currency`
3. **应用层保证**: 更新费用时，系统自动转换为 `budget_currency` 并存储

**实现策略**:
```python
# ✅ 简化后的设计
class UserAPIKeyAuth(TypedDict):
    budget_currency: str  # 唯一的货币字段
    # spend_currency 不暴露给应用层，由系统自动管理

# 数据库层（向后兼容）:
# - 保留 spend_currency 字段
# - 但始终设置为 budget_currency
# - 用于历史兼容和数据完整性检查
```

**迁移路径**:
1. Phase 2: 添加 `budget_currency` 字段
2. Phase 3: 更新所有费用累计逻辑，确保 `spend_currency = budget_currency`
3. 未来: 可选地删除 `spend_currency` 字段（数据库 schema 清理）

---

## TypedDict 定义

### 文件: `/litellm/types/router.py`

```python
from typing import TypedDict, Optional, Literal

# 支持的货币类型
SupportedCurrency = Literal["USD", "CNY", "EUR", "GBP", "JPY"]

class UserAPIKeyAuth(TypedDict, total=False):
    """用户 API 密钥认证信息"""
    # 现有字段
    token: str
    key_name: Optional[str]
    key_alias: Optional[str]
    spend: float
    max_budget: Optional[float]
    expires: Optional[str]
    models: list
    aliases: dict
    config: dict
    user_id: Optional[str]
    team_id: Optional[str]
    max_parallel_requests: Optional[int]
    metadata: dict
    tpm_limit: Optional[int]
    rpm_limit: Optional[int]

    # 新增字段 - 多货币支持（简化版）
    budget_currency: str  # 预算和费用使用的货币，默认 "USD"
    # 注意：spend_currency 由系统自动管理，应用层不直接访问

    # 其他现有字段
    user_role: Optional[str]
    allowed_cache_controls: Optional[list]
    permissions: Optional[dict]
    model_spend: Optional[dict]
    model_max_budget: Optional[dict]


class TeamMemberAuth(TypedDict, total=False):
    """团队成员认证信息"""
    # 现有字段
    team_id: str
    team_alias: Optional[str]
    spend: float
    max_budget: Optional[float]
    models: list

    # 新增字段（简化版）
    budget_currency: str  # 团队预算货币

    # 其他现有字段
    tpm_limit: Optional[int]
    rpm_limit: Optional[int]
    metadata: dict


class EndUserAuth(TypedDict, total=False):
    """终端用户认证信息"""
    # 现有字段
    user_id: str
    spend: float
    max_budget: Optional[float]

    # 新增字段（简化版）
    budget_currency: str  # 用户预算货币

    # 其他现有字段
    allowed_model_region: Optional[str]
    metadata: dict
```

---

## Pydantic 模型

### 文件: `/litellm/proxy/proxy_server.py` (扩展部分)

#### 1. 密钥生成请求模型

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
from litellm.types.router import SupportedCurrency

class GenerateKeyRequest(BaseModel):
    """生成密钥请求"""
    # 现有字段
    duration: Optional[str] = None
    models: Optional[List[str]] = []
    aliases: Optional[Dict] = {}
    config: Optional[Dict] = {}
    spend: Optional[float] = 0.0
    max_budget: Optional[float] = None
    user_id: Optional[str] = None
    team_id: Optional[str] = None
    max_parallel_requests: Optional[int] = None
    metadata: Optional[Dict] = {}
    tpm_limit: Optional[int] = None
    rpm_limit: Optional[int] = None
    key_alias: Optional[str] = None

    # 新增字段 - 多货币支持（简化版）
    budget_currency: SupportedCurrency = Field(
        default="USD",
        description="预算货币类型（费用将自动转换为此货币）"
    )

    @validator('budget_currency')
    def validate_budget_currency(cls, v):
        """验证货币类型"""
        supported = ["USD", "CNY", "EUR", "GBP", "JPY"]
        if v not in supported:
            raise ValueError(f"Unsupported currency: {v}. Must be one of {supported}")
        return v

    @validator('max_budget')
    def validate_max_budget(cls, v, values):
        """验证预算值"""
        if v is not None and v <= 0:
            raise ValueError("max_budget must be greater than 0")
        return v

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


class UpdateKeyRequest(BaseModel):
    """更新密钥请求"""
    # 现有字段
    key: str
    spend: Optional[float] = None
    max_budget: Optional[float] = None
    models: Optional[List[str]] = None

    # 新增字段
    budget_currency: Optional[SupportedCurrency] = None

    @validator('budget_currency')
    def validate_currency_change(cls, v, values):
        """验证货币更改"""
        # 警告：更改货币需要谨慎，因为会影响现有 spend 的解释
        if v is not None:
            import warnings
            warnings.warn(
                "Changing budget_currency will affect spend interpretation. "
                "Current spend will be reinterpreted in the new currency.",
                UserWarning
            )
        return v


class NewTeamRequest(BaseModel):
    """创建团队请求"""
    # 现有字段
    team_alias: Optional[str] = None
    organization_id: Optional[str] = None
    admins: Optional[List[str]] = []
    members: Optional[List[str]] = []
    members_with_roles: Optional[List[Dict]] = []
    metadata: Optional[Dict] = {}
    tpm_limit: Optional[int] = None
    rpm_limit: Optional[int] = None
    max_budget: Optional[float] = None
    models: Optional[List[str]] = []

    # 新增字段
    budget_currency: SupportedCurrency = Field(
        default="USD",
        description="团队预算货币类型"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "team_alias": "engineering-team",
                "max_budget": 50000.0,
                "budget_currency": "CNY",
                "members": ["user1@example.com", "user2@example.com"]
            }
        }


class NewUserRequest(BaseModel):
    """创建用户请求"""
    # 现有字段
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    user_role: Optional[str] = None
    max_budget: Optional[float] = None
    models: Optional[List[str]] = []
    tpm_limit: Optional[int] = None
    rpm_limit: Optional[int] = None

    # 新增字段
    budget_currency: SupportedCurrency = Field(
        default="USD",
        description="用户预算货币类型"
    )
```

#### 2. 响应模型

```python
class KeyInfoResponse(BaseModel):
    """密钥信息响应"""
    key: str
    key_alias: Optional[str] = None
    spend: float
    max_budget: Optional[float] = None
    budget_currency: str

    # 注意：不暴露 spend_currency，因为它始终等于 budget_currency

    # 现有字段
    expires: Optional[str] = None
    models: List[str]
    user_id: Optional[str] = None
    team_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "key": "sk-proj-abc123...",
                "key_alias": "my-cny-key",
                "spend": 5000.0,
                "max_budget": 10000.0,
                "budget_currency": "CNY"
            }
        }


class ExchangeRateInfo(BaseModel):
    """汇率信息"""
    base_currency: str = "USD"
    rates: Dict[str, float]
    last_updated: Optional[str] = None
    source: str = "manual"
    supported_currencies: List[str]

    class Config:
        json_schema_extra = {
            "example": {
                "base_currency": "USD",
                "rates": {
                    "USD": 1.0,
                    "CNY": 7.2,
                    "EUR": 0.92
                },
                "last_updated": "2026-01-03T10:00:00Z",
                "source": "manual",
                "supported_currencies": ["USD", "CNY", "EUR", "GBP", "JPY"]
            }
        }


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
            # 验证货币代码
            if currency not in ["CNY", "EUR", "GBP", "JPY"]:
                raise ValueError(f"Unsupported currency: {currency}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "rates": {
                    "CNY": 7.25,
                    "EUR": 0.93
                }
            }
        }
```

---

## 数据库模型扩展

### 文件: `/litellm/proxy/schema.prisma` (完整改动)

```prisma
// 1. LiteLLM_VerificationToken - 虚拟密钥
model LiteLLM_VerificationToken {
  token                String    @id @default(uuid())
  key_name             String?
  key_alias            String?
  spend                Float     @default(0.0)
  max_budget           Float?
  expires              DateTime?
  models               Json      @default("[]")
  aliases              Json      @default("{}")
  config               Json      @default("{}")
  user_id              String?
  team_id              String?
  max_parallel_requests Int?
  metadata             Json      @default("{}")
  tpm_limit            Int?
  rpm_limit            Int?
  max_budget_in_team   Float?
  budget_duration      String?
  budget_reset_at      DateTime?
  allowed_cache_controls Json?
  permissions          Json      @default("{}")
  model_spend          Json      @default("{}")
  model_max_budget     Json      @default("{}")

  // 新增字段 - 多货币支持（简化版）
  budget_currency      String    @default("USD")  // 主货币字段
  spend_currency       String    @default("USD")  // 自动维护，始终等于 budget_currency

  // 注释：spend_currency 由应用层自动维护，确保与 budget_currency 一致
  // 保留此字段是为了向后兼容和数据完整性检查

  token_id             String?
  created_at           DateTime  @default(now())
  updated_at           DateTime  @default(now()) @updatedAt

  @@index([budget_currency], name: "idx_verification_token_currency")
  @@index([user_id])
  @@index([team_id])
}

// 2. LiteLLM_TeamTable - 团队
model LiteLLM_TeamTable {
  team_id              String    @id @default(uuid())
  team_alias           String?
  organization_id      String?
  admins               Json      @default("[]")
  members              Json      @default("[]")
  members_with_roles   Json      @default("[]")
  metadata             Json      @default("{}")
  tpm_limit            Int?
  rpm_limit            Int?
  max_budget           Float?
  spend                Float     @default(0.0)
  models               Json      @default("[]")
  blocked              Boolean   @default(false)

  // 新增字段（简化版）
  budget_currency      String    @default("USD")  // 主货币字段
  spend_currency       String    @default("USD")  // 自动维护

  model_spend          Json      @default("{}")
  model_max_budget     Json      @default("{}")
  created_at           DateTime  @default(now())
  updated_at           DateTime  @default(now()) @updatedAt

  @@index([budget_currency], name: "idx_team_currency")
  @@index([organization_id])
}

// 3. LiteLLM_UserTable - 用户
model LiteLLM_UserTable {
  user_id              String    @id @default(uuid())
  user_email           String?   @unique
  user_role            String?
  spend                Float     @default(0.0)
  max_budget           Float?
  models               Json      @default("[]")
  tpm_limit            Int?
  rpm_limit            Int?
  max_parallel_requests Int?
  metadata             Json      @default("{}")

  // 新增字段（简化版）
  budget_currency      String    @default("USD")  // 主货币字段
  spend_currency       String    @default("USD")  // 自动维护

  model_spend          Json      @default("{}")
  model_max_budget     Json      @default("{}")
  created_at           DateTime  @default(now())
  updated_at           DateTime  @default(now()) @updatedAt

  @@index([budget_currency], name: "idx_user_currency")
  @@index([user_email])
}

// 4. LiteLLM_BudgetTable - 预算
model LiteLLM_BudgetTable {
  budget_id            String    @id @default(uuid())
  max_budget           Float?
  soft_budget          Float?
  max_parallel_requests Int?
  tpm_limit            Int?
  rpm_limit            Int?
  model_max_budget     Json?

  // 新增字段
  budget_currency      String    @default("USD")

  budget_duration      String?
  budget_reset_at      DateTime?
  created_at           DateTime  @default(now())
  updated_at           DateTime  @default(now()) @updatedAt
  created_by           String
  updated_by           String

  @@index([created_by])
}

// 5. LiteLLM_SpendLogs - 费用日志
model LiteLLM_SpendLogs {
  request_id           String    @id @default(uuid())
  call_type            String
  api_key              String    @default("")
  spend                Float     @default(0.0)
  total_tokens         Int       @default(0)
  prompt_tokens        Int       @default(0)
  completion_tokens    Int       @default(0)
  startTime            DateTime
  endTime              DateTime
  model                String    @default("")
  user                 String    @default("")
  metadata             Json      @default("{}")
  cache_hit            String    @default("")
  cache_key            String    @default("")
  request_tags         Json      @default("[]")
  team_id              String?
  user_id              String?

  // 新增字段 - 货币追踪（用于审计）
  spend_currency       String    @default("USD")  // 记录的货币（等于相应实体的 budget_currency）

  // 详细货币信息（用于汇率审计）
  model_currency       String?   // 模型原始货币（如 "CNY"）
  spend_original       Float?    // 原始货币金额
  exchange_rate        Float?    // 使用的汇率快照

  @@index([api_key, startTime])
  @@index([team_id, startTime])
  @@index([user_id, startTime])
  @@index([spend_currency])
}
```

---

## 数据访问层

### 文件: `/litellm/proxy/utils/db_utils.py` (新增函数)

```python
from typing import Optional, Dict, Any
from litellm.proxy._types import LiteLLM_VerificationToken
from litellm.utils.currency import convert_currency
import logging

logger = logging.getLogger("litellm.db_utils")

async def get_key_with_currency_info(
    prisma_client,
    token: str
) -> Optional[Dict[str, Any]]:
    """
    获取密钥信息（包含货币信息）

    Args:
        prisma_client: Prisma 客户端
        token: API 密钥

    Returns:
        包含货币信息的密钥数据
    """
    key = await prisma_client.db.litellm_verificationtoken.find_unique(
        where={"token": token}
    )

    if not key:
        return None

    # 转换为字典
    key_dict = key.dict()

    # 验证 spend_currency == budget_currency（数据完整性检查）
    if key.spend_currency != key.budget_currency:
        logger.warning(
            f"Data inconsistency for key {token[:8]}...: "
            f"spend_currency={key.spend_currency} != budget_currency={key.budget_currency}. "
            f"Auto-correcting to budget_currency."
        )
        # 自动修正
        await prisma_client.db.litellm_verificationtoken.update(
            where={"token": token},
            data={"spend_currency": key.budget_currency}
        )
        key_dict["spend_currency"] = key.budget_currency

    return key_dict


async def update_spend_with_currency(
    prisma_client,
    token: str,
    additional_spend: float,
    spend_currency: str = "USD"
) -> None:
    """
    更新费用（自动转换为 budget_currency）

    工作流程:
    1. 转换 additional_spend 到 budget_currency
    2. 累计到 spend
    3. 确保 spend_currency = budget_currency

    Args:
        prisma_client: Prisma 客户端
        token: API 密钥
        additional_spend: 增加的费用
        spend_currency: 费用的原始货币
    """
    # 获取当前密钥
    key = await prisma_client.db.litellm_verificationtoken.find_unique(
        where={"token": token}
    )

    if not key:
        raise ValueError(f"Key not found: {token}")

    # 转换为预算货币
    if spend_currency != key.budget_currency:
        additional_spend_converted = convert_currency(
            additional_spend,
            spend_currency,
            key.budget_currency
        )
        logger.debug(
            f"[Update Spend] Converted {additional_spend:.6f} {spend_currency} -> "
            f"{additional_spend_converted:.6f} {key.budget_currency}"
        )
    else:
        additional_spend_converted = additional_spend

    # 更新费用（确保 spend_currency = budget_currency）
    await prisma_client.db.litellm_verificationtoken.update(
        where={"token": token},
        data={
            "spend": key.spend + additional_spend_converted,
            "spend_currency": key.budget_currency  # 始终设置为 budget_currency
        }
    )


async def create_spend_log_with_currency(
    prisma_client,
    request_id: str,
    api_key: str,
    model: str,
    spend: float,
    spend_currency: str,
    model_currency: Optional[str] = None,
    exchange_rate: Optional[float] = None,
    **kwargs
) -> None:
    """
    创建费用日志（包含货币信息）

    Args:
        prisma_client: Prisma 客户端
        request_id: 请求 ID
        api_key: API 密钥
        model: 模型名称
        spend: 费用金额（已转换为 spend_currency）
        spend_currency: 记录的货币（应该是实体的 budget_currency）
        model_currency: 模型原始货币（用于审计）
        exchange_rate: 使用的汇率快照（用于审计）
        **kwargs: 其他字段
    """
    await prisma_client.db.litellm_spendlogs.create(
        data={
            "request_id": request_id,
            "api_key": api_key,
            "model": model,
            "spend": spend,
            "spend_currency": spend_currency,
            "model_currency": model_currency,
            "exchange_rate": exchange_rate,
            **kwargs
        }
    )


async def get_team_spend_in_currency(
    prisma_client,
    team_id: str,
    target_currency: Optional[str] = None
) -> float:
    """
    获取团队费用（可选转换为指定货币）

    Args:
        prisma_client: Prisma 客户端
        team_id: 团队 ID
        target_currency: 目标货币（None 则返回原始货币）

    Returns:
        费用金额
    """
    team = await prisma_client.db.litellm_teamtable.find_unique(
        where={"team_id": team_id}
    )

    if not team:
        raise ValueError(f"Team not found: {team_id}")

    # 如果不指定目标货币，或货币相同，直接返回
    if target_currency is None or team.budget_currency == target_currency:
        return team.spend

    # 转换货币
    return convert_currency(
        team.spend,
        team.budget_currency,  # 使用 budget_currency 作为源货币
        target_currency
    )


async def ensure_currency_consistency(
    prisma_client,
    table_name: str,
    id_field: str,
    id_value: str
) -> bool:
    """
    确保 spend_currency == budget_currency（数据完整性检查）

    Args:
        prisma_client: Prisma 客户端
        table_name: 表名
        id_field: ID 字段名
        id_value: ID 值

    Returns:
        True if consistent or fixed, False if failed
    """
    try:
        # 查询记录
        if table_name == "LiteLLM_VerificationToken":
            record = await prisma_client.db.litellm_verificationtoken.find_unique(
                where={id_field: id_value}
            )
        elif table_name == "LiteLLM_TeamTable":
            record = await prisma_client.db.litellm_teamtable.find_unique(
                where={id_field: id_value}
            )
        elif table_name == "LiteLLM_UserTable":
            record = await prisma_client.db.litellm_usertable.find_unique(
                where={id_field: id_value}
            )
        else:
            logger.error(f"Unknown table: {table_name}")
            return False

        if not record:
            return False

        # 检查一致性
        if record.spend_currency != record.budget_currency:
            logger.warning(
                f"[Data Consistency] Fixing {table_name}.{id_field}={id_value}: "
                f"spend_currency={record.spend_currency} -> budget_currency={record.budget_currency}"
            )

            # 自动修正
            if table_name == "LiteLLM_VerificationToken":
                await prisma_client.db.litellm_verificationtoken.update(
                    where={id_field: id_value},
                    data={"spend_currency": record.budget_currency}
                )
            elif table_name == "LiteLLM_TeamTable":
                await prisma_client.db.litellm_teamtable.update(
                    where={id_field: id_value},
                    data={"spend_currency": record.budget_currency}
                )
            elif table_name == "LiteLLM_UserTable":
                await prisma_client.db.litellm_usertable.update(
                    where={id_field: id_value},
                    data={"spend_currency": record.budget_currency}
                )

        return True

    except Exception as e:
        logger.error(f"[Data Consistency] Error: {e}")
        return False
```

---

## 迁移脚本

### 文件: `/litellm/proxy/migrations/20260104000000_add_currency_support/migration.sql`

```sql
-- Add currency columns to LiteLLM_VerificationToken
ALTER TABLE "LiteLLM_VerificationToken"
ADD COLUMN IF NOT EXISTS "budget_currency" TEXT NOT NULL DEFAULT 'USD',
ADD COLUMN IF NOT EXISTS "spend_currency" TEXT NOT NULL DEFAULT 'USD';

-- Add currency columns to LiteLLM_TeamTable
ALTER TABLE "LiteLLM_TeamTable"
ADD COLUMN IF NOT EXISTS "budget_currency" TEXT NOT NULL DEFAULT 'USD',
ADD COLUMN IF NOT EXISTS "spend_currency" TEXT NOT NULL DEFAULT 'USD';

-- Add currency columns to LiteLLM_UserTable
ALTER TABLE "LiteLLM_UserTable"
ADD COLUMN IF NOT EXISTS "budget_currency" TEXT NOT NULL DEFAULT 'USD',
ADD COLUMN IF NOT EXISTS "spend_currency" TEXT NOT NULL DEFAULT 'USD';

-- Add currency column to LiteLLM_BudgetTable
ALTER TABLE "LiteLLM_BudgetTable"
ADD COLUMN IF NOT EXISTS "budget_currency" TEXT NOT NULL DEFAULT 'USD';

-- Add currency columns to LiteLLM_SpendLogs
ALTER TABLE "LiteLLM_SpendLogs"
ADD COLUMN IF NOT EXISTS "spend_currency" TEXT NOT NULL DEFAULT 'USD',
ADD COLUMN IF NOT EXISTS "model_currency" TEXT,
ADD COLUMN IF NOT EXISTS "spend_original" DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS "exchange_rate" DOUBLE PRECISION;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS "idx_verification_token_currency"
ON "LiteLLM_VerificationToken"("budget_currency");

CREATE INDEX IF NOT EXISTS "idx_team_currency"
ON "LiteLLM_TeamTable"("budget_currency");

CREATE INDEX IF NOT EXISTS "idx_user_currency"
ON "LiteLLM_UserTable"("budget_currency");

CREATE INDEX IF NOT EXISTS "idx_spend_logs_currency"
ON "LiteLLM_SpendLogs"("spend_currency");

-- Add comments for documentation
COMMENT ON COLUMN "LiteLLM_VerificationToken"."budget_currency" IS 'Primary currency for budget and spend (e.g., USD, CNY)';
COMMENT ON COLUMN "LiteLLM_VerificationToken"."spend_currency" IS 'Auto-maintained: always equals budget_currency. Kept for backward compatibility.';
COMMENT ON COLUMN "LiteLLM_SpendLogs"."model_currency" IS 'Original currency of the model pricing (for audit)';
COMMENT ON COLUMN "LiteLLM_SpendLogs"."exchange_rate" IS 'Exchange rate snapshot used for conversion (for audit)';

-- Data consistency check: Ensure spend_currency = budget_currency for all existing records
UPDATE "LiteLLM_VerificationToken"
SET "spend_currency" = "budget_currency"
WHERE "spend_currency" != "budget_currency";

UPDATE "LiteLLM_TeamTable"
SET "spend_currency" = "budget_currency"
WHERE "spend_currency" != "budget_currency";

UPDATE "LiteLLM_UserTable"
SET "spend_currency" = "budget_currency"
WHERE "spend_currency" != "budget_currency";

-- Add constraint (optional, for strict enforcement)
-- Note: This is commented out for flexibility, but can be enabled if desired
-- ALTER TABLE "LiteLLM_VerificationToken"
-- ADD CONSTRAINT "chk_spend_currency_equals_budget"
-- CHECK ("spend_currency" = "budget_currency");
```

---

## 数据验证脚本

### 文件: `/scripts/validate_currency_migration.py`

```python
"""验证货币字段迁移和数据一致性"""
import asyncio
from litellm.proxy.proxy_server import prisma_client
import logging

logger = logging.getLogger(__name__)

async def validate_migration():
    """验证迁移是否成功"""
    print("🔍 Validating currency migration...")

    # 1. 检查所有表是否有 currency 字段
    tables = [
        ("LiteLLM_VerificationToken", ["budget_currency", "spend_currency"]),
        ("LiteLLM_TeamTable", ["budget_currency", "spend_currency"]),
        ("LiteLLM_UserTable", ["budget_currency", "spend_currency"]),
        ("LiteLLM_BudgetTable", ["budget_currency"]),
        ("LiteLLM_SpendLogs", ["spend_currency"])
    ]

    for table_name, columns in tables:
        print(f"\n✓ Checking {table_name}...")
        for col in columns:
            # 检查字段是否存在
            result = await prisma_client.db.query_raw(f"""
                SELECT COUNT(*) as count
                FROM information_schema.columns
                WHERE table_name = '{table_name}'
                AND column_name = '{col}'
            """)
            if result[0]['count'] > 0:
                print(f"  ✓ {col} exists")
            else:
                print(f"  ✗ {col} missing!")
                return False

    # 2. 检查默认值
    print("\n🔍 Checking default values...")

    # 检查 VerificationToken
    tokens = await prisma_client.db.litellm_verificationtoken.find_many(
        take=10
    )
    for token in tokens:
        assert token.budget_currency == "USD", "Default budget_currency should be USD"
        assert token.spend_currency == "USD", "Default spend_currency should be USD"

    print("✓ All default values are correct")

    # 3. 检查数据一致性：spend_currency == budget_currency
    print("\n🔍 Checking data consistency (spend_currency = budget_currency)...")

    # 检查 VerificationToken
    inconsistent_tokens = await prisma_client.db.query_raw("""
        SELECT COUNT(*) as count
        FROM "LiteLLM_VerificationToken"
        WHERE "spend_currency" != "budget_currency"
    """)

    if inconsistent_tokens[0]['count'] > 0:
        print(f"  ⚠️  Found {inconsistent_tokens[0]['count']} inconsistent tokens")
        print("  Auto-fixing...")
        await prisma_client.db.execute_raw("""
            UPDATE "LiteLLM_VerificationToken"
            SET "spend_currency" = "budget_currency"
            WHERE "spend_currency" != "budget_currency"
        """)
        print("  ✓ Fixed")
    else:
        print("  ✓ All VerificationTokens consistent")

    # 检查 TeamTable
    inconsistent_teams = await prisma_client.db.query_raw("""
        SELECT COUNT(*) as count
        FROM "LiteLLM_TeamTable"
        WHERE "spend_currency" != "budget_currency"
    """)

    if inconsistent_teams[0]['count'] > 0:
        print(f"  ⚠️  Found {inconsistent_teams[0]['count']} inconsistent teams")
        print("  Auto-fixing...")
        await prisma_client.db.execute_raw("""
            UPDATE "LiteLLM_TeamTable"
            SET "spend_currency" = "budget_currency"
            WHERE "spend_currency" != "budget_currency"
        """)
        print("  ✓ Fixed")
    else:
        print("  ✓ All Teams consistent")

    # 检查 UserTable
    inconsistent_users = await prisma_client.db.query_raw("""
        SELECT COUNT(*) as count
        FROM "LiteLLM_UserTable"
        WHERE "spend_currency" != "budget_currency"
    """)

    if inconsistent_users[0]['count'] > 0:
        print(f"  ⚠️  Found {inconsistent_users[0]['count']} inconsistent users")
        print("  Auto-fixing...")
        await prisma_client.db.execute_raw("""
            UPDATE "LiteLLM_UserTable"
            SET "spend_currency" = "budget_currency"
            WHERE "spend_currency" != "budget_currency"
        """)
        print("  ✓ Fixed")
    else:
        print("  ✓ All Users consistent")

    # 4. 检查索引
    print("\n🔍 Checking indexes...")
    indexes = await prisma_client.db.query_raw("""
        SELECT indexname
        FROM pg_indexes
        WHERE tablename IN (
            'LiteLLM_VerificationToken',
            'LiteLLM_TeamTable',
            'LiteLLM_UserTable',
            'LiteLLM_SpendLogs'
        )
        AND indexname LIKE '%currency%'
    """)

    expected_indexes = [
        'idx_verification_token_currency',
        'idx_team_currency',
        'idx_user_currency',
        'idx_spend_logs_currency'
    ]

    found_indexes = [idx['indexname'] for idx in indexes]
    for expected in expected_indexes:
        if expected in found_indexes:
            print(f"  ✓ {expected} exists")
        else:
            print(f"  ✗ {expected} missing!")

    print("\n✅ Migration validation complete!")
    print("\n📊 Summary:")
    print(f"  - All currency fields present")
    print(f"  - Data consistency enforced: spend_currency = budget_currency")
    print(f"  - Indexes created for performance")

    return True

if __name__ == "__main__":
    asyncio.run(validate_migration())
```

---

## 测试数据生成

### 文件: `/scripts/generate_test_data_with_currency.py`

```python
"""生成测试数据（包含多货币）"""
import asyncio
from litellm.proxy.proxy_server import prisma_client

async def generate_test_data():
    """生成测试数据"""
    print("🔧 Generating test data with currency support...")

    # 1. 创建 USD 密钥
    usd_key = await prisma_client.db.litellm_verificationtoken.create(
        data={
            "token": "sk-test-usd-key",
            "key_alias": "Test USD Key",
            "max_budget": 1000.0,
            "budget_currency": "USD",
            "spend_currency": "USD",  # 自动设置为 budget_currency
            "spend": 0.0
        }
    )
    print(f"✓ Created USD key: {usd_key.token}")

    # 2. 创建 CNY 密钥
    cny_key = await prisma_client.db.litellm_verificationtoken.create(
        data={
            "token": "sk-test-cny-key",
            "key_alias": "Test CNY Key",
            "max_budget": 10000.0,
            "budget_currency": "CNY",
            "spend_currency": "CNY",  # 自动设置为 budget_currency
            "spend": 0.0
        }
    )
    print(f"✓ Created CNY key: {cny_key.token}")

    # 3. 创建 CNY 团队
    cny_team = await prisma_client.db.litellm_teamtable.create(
        data={
            "team_id": "team-cny-test",
            "team_alias": "CNY Test Team",
            "max_budget": 50000.0,
            "budget_currency": "CNY",
            "spend_currency": "CNY",  # 自动设置
            "spend": 0.0
        }
    )
    print(f"✓ Created CNY team: {cny_team.team_id}")

    # 4. 创建测试用户
    test_user = await prisma_client.db.litellm_usertable.create(
        data={
            "user_id": "user-cny-test",
            "user_email": "cny-test@example.com",
            "max_budget": 5000.0,
            "budget_currency": "CNY",
            "spend_currency": "CNY",  # 自动设置
            "spend": 0.0
        }
    )
    print(f"✓ Created CNY user: {test_user.user_id}")

    # 5. 验证数据一致性
    print("\n🔍 Verifying data consistency...")
    all_keys = await prisma_client.db.litellm_verificationtoken.find_many()
    for key in all_keys:
        if key.spend_currency != key.budget_currency:
            print(f"  ⚠️  Inconsistency found in {key.token[:8]}...")
        else:
            print(f"  ✓ {key.token[:8]}... consistent")

    print("\n✅ Test data generation complete!")
    print("\nTest keys:")
    print(f"  USD: {usd_key.token}")
    print(f"  CNY: {cny_key.token}")

if __name__ == "__main__":
    asyncio.run(generate_test_data())
```

---

## 设计原则总结

### 核心原则

1. **单一货币源**: 每个实体只有一个货币 - `budget_currency`
2. **自动同步**: `spend_currency` 由系统自动维护，始终等于 `budget_currency`
3. **应用层保证**: 更新费用时，系统自动转换并确保一致性
4. **向后兼容**: 保留 `spend_currency` 字段用于迁移和数据完整性检查

### 最佳实践

```python
# ✅ 正确：使用 budget_currency
user_api_key_dict = {
    "token": "sk-xxx",
    "budget_currency": "CNY",
    "spend": 1000.0
}

# ❌ 错误：手动设置 spend_currency
user_api_key_dict = {
    "token": "sk-xxx",
    "budget_currency": "CNY",
    "spend_currency": "USD"  # 不要这样做！
}

# ✅ 正确：更新费用时自动设置 spend_currency
await update_spend_atomic(
    ...,
    response_cost=10.0,
    response_cost_currency="USD"
)
# 系统会自动：
# 1. 转换为 budget_currency
# 2. 设置 spend_currency = budget_currency
```

---

## 下一步

1. ✅ Phase 2 数据模型设计完成（简化版）
2. ✅ Phase 3 计费逻辑设计完成（含事务和锁）
3. ⏭️ 更新 README 文档状态
