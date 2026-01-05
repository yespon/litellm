# Prisma Schema 改动 - 多货币支持

## 📋 目录
- [Schema 改动概览](#schema-改动概览)
- [详细改动](#详细改动)
- [迁移脚本](#迁移脚本)
- [向后兼容性](#向后兼容性)

---

## Schema 改动概览

### 改动策略
- **最小化改动**: 仅添加必要字段
- **默认值**: 所有新字段默认为 "USD"
- **向后兼容**: 不破坏现有数据

### 受影响的表
1. `LiteLLM_VerificationToken` - 虚拟密钥表
2. `LiteLLM_TeamTable` - 团队表
3. `LiteLLM_UserTable` - 用户表
4. `LiteLLM_BudgetTable` - 预算表
5. `LiteLLM_SpendLogs` - 费用日志表（可选）

---

## 详细改动

### 文件: `/litellm/proxy/schema.prisma`

### 1. LiteLLM_VerificationToken (虚拟密钥)

**改动前**:
```prisma
model LiteLLM_VerificationToken {
  token      String   @id
  spend      Float    @default(0.0)
  max_budget Float?
  model_spend      Json @default("{}")
  model_max_budget Json @default("{}")
  // ... 其他字段
}
```

**改动后**:
```prisma
model LiteLLM_VerificationToken {
  token      String   @id
  spend      Float    @default(0.0)
  max_budget Float?

  // 新增字段 - 货币支持
  budget_currency String @default("USD")  // 预算货币
  spend_currency  String @default("USD")  // 费用累计货币

  model_spend      Json @default("{}")
  model_max_budget Json @default("{}")
  // ... 其他字段
}
```

**字段说明**:
- `budget_currency`: 预算设置时使用的货币（如 "USD", "CNY"）
- `spend_currency`: 费用累计使用的货币（通常与 budget_currency 相同）

---

### 2. LiteLLM_TeamTable (团队)

**改动前**:
```prisma
model LiteLLM_TeamTable {
  team_id    String   @id @default(uuid())
  spend      Float    @default(0.0)
  max_budget Float?
  model_spend      Json @default("{}")
  model_max_budget Json @default("{}")
  // ... 其他字段
}
```

**改动后**:
```prisma
model LiteLLM_TeamTable {
  team_id    String   @id @default(uuid())
  spend      Float    @default(0.0)
  max_budget Float?

  // 新增字段
  budget_currency String @default("USD")
  spend_currency  String @default("USD")

  model_spend      Json @default("{}")
  model_max_budget Json @default("{}")
  // ... 其他字段
}
```

---

### 3. LiteLLM_UserTable (用户)

**改动前**:
```prisma
model LiteLLM_UserTable {
  user_id    String   @id @default(uuid())
  spend      Float    @default(0.0)
  max_budget Float?
  model_spend      Json @default("{}")
  model_max_budget Json @default("{}")
  // ... 其他字段
}
```

**改动后**:
```prisma
model LiteLLM_UserTable {
  user_id    String   @id @default(uuid())
  spend      Float    @default(0.0)
  max_budget Float?

  // 新增字段
  budget_currency String @default("USD")
  spend_currency  String @default("USD")

  model_spend      Json @default("{}")
  model_max_budget Json @default("{}")
  // ... 其他字段
}
```

---

### 4. LiteLLM_BudgetTable (预算)

**改动前**:
```prisma
model LiteLLM_BudgetTable {
  budget_id   String @id @default(uuid())
  max_budget  Float?
  soft_budget Float?
  model_max_budget Json?
  // ... 其他字段
}
```

**改动后**:
```prisma
model LiteLLM_BudgetTable {
  budget_id   String @id @default(uuid())
  max_budget  Float?
  soft_budget Float?

  // 新增字段
  budget_currency String @default("USD")

  model_max_budget Json?
  // ... 其他字段
}
```

**注意**: BudgetTable 只需要 `budget_currency`，因为它不累计费用。

---

### 5. LiteLLM_SpendLogs (费用日志) - 可选

**改动前**:
```prisma
model LiteLLM_SpendLogs {
  request_id String @id
  spend      Float  @default(0.0)
  model      String
  // ... 其他字段
}
```

**改动后 - 选项 A (简单)**:
```prisma
model LiteLLM_SpendLogs {
  request_id String @id
  spend      Float  @default(0.0)
  model      String

  // 新增字段 - 记录使用的货币
  spend_currency String @default("USD")

  // ... 其他字段
}
```

**改动后 - 选项 B (详细)**:
```prisma
model LiteLLM_SpendLogs {
  request_id String @id
  spend      Float  @default(0.0)
  model      String

  // 新增字段 - 多币种支持
  spend_currency      String @default("USD")  // 记录的货币
  model_currency      String?                 // 模型的原始货币
  spend_original      Float?                  // 原始货币金额
  exchange_rate       Float?                  // 使用的汇率

  // ... 其他字段
}
```

**推荐**: 使用选项 A（简单），Phase 2+ 可升级到选项 B

---

## 迁移脚本

### 步骤 1: 生成迁移

```bash
cd litellm/proxy
npx prisma migrate dev --name add_currency_support
```

### 步骤 2: 查看生成的迁移文件

**文件**: `/litellm/proxy/migrations/20260103XXXXXX_add_currency_support/migration.sql`

```sql
-- AddCurrencySupport
-- 为多货币支持添加 currency 字段

-- 1. LiteLLM_VerificationToken
ALTER TABLE "LiteLLM_VerificationToken"
ADD COLUMN "budget_currency" TEXT NOT NULL DEFAULT 'USD',
ADD COLUMN "spend_currency" TEXT NOT NULL DEFAULT 'USD';

-- 2. LiteLLM_TeamTable
ALTER TABLE "LiteLLM_TeamTable"
ADD COLUMN "budget_currency" TEXT NOT NULL DEFAULT 'USD',
ADD COLUMN "spend_currency" TEXT NOT NULL DEFAULT 'USD';

-- 3. LiteLLM_UserTable
ALTER TABLE "LiteLLM_UserTable"
ADD COLUMN "budget_currency" TEXT NOT NULL DEFAULT 'USD',
ADD COLUMN "spend_currency" TEXT NOT NULL DEFAULT 'USD';

-- 4. LiteLLM_BudgetTable
ALTER TABLE "LiteLLM_BudgetTable"
ADD COLUMN "budget_currency" TEXT NOT NULL DEFAULT 'USD';

-- 5. LiteLLM_SpendLogs (可选)
ALTER TABLE "LiteLLM_SpendLogs"
ADD COLUMN "spend_currency" TEXT NOT NULL DEFAULT 'USD';

-- 创建索引以优化货币相关查询
CREATE INDEX "idx_verification_token_currency" ON "LiteLLM_VerificationToken"("budget_currency");
CREATE INDEX "idx_team_currency" ON "LiteLLM_TeamTable"("budget_currency");
CREATE INDEX "idx_user_currency" ON "LiteLLM_UserTable"("budget_currency");
```

### 步骤 3: 验证迁移

```bash
# 测试环境验证
npx prisma migrate dev

# 查看当前 schema
npx prisma db pull

# 验证数据
npx prisma studio
```

### 步骤 4: 生产环境迁移

```bash
# 1. 备份数据库
pg_dump -h localhost -U postgres litellm > backup_before_currency.sql

# 2. 应用迁移
npx prisma migrate deploy

# 3. 验证
psql -h localhost -U postgres litellm -c "SELECT table_name, column_name FROM information_schema.columns WHERE column_name LIKE '%currency%';"
```

---

## 向后兼容性

### 1. 默认值策略

所有新字段默认为 "USD"，确保：
- ✅ 现有数据不受影响
- ✅ 现有代码继续工作
- ✅ 新功能逐步启用

### 2. 数据迁移检查

```sql
-- 检查是否有非默认货币的数据
SELECT
  COUNT(*) as total_keys,
  SUM(CASE WHEN budget_currency != 'USD' THEN 1 ELSE 0 END) as non_usd_keys
FROM "LiteLLM_VerificationToken";

-- 结果应该是：
-- total_keys | non_usd_keys
-- -----------|-------------
--    1000    |      0
```

### 3. 回滚脚本

**文件**: `/litellm/proxy/migrations/rollback_currency_support.sql`

```sql
-- 回滚货币支持改动

-- 1. 删除索引
DROP INDEX IF EXISTS "idx_verification_token_currency";
DROP INDEX IF EXISTS "idx_team_currency";
DROP INDEX IF EXISTS "idx_user_currency";

-- 2. 删除列
ALTER TABLE "LiteLLM_VerificationToken"
DROP COLUMN IF EXISTS "budget_currency",
DROP COLUMN IF EXISTS "spend_currency";

ALTER TABLE "LiteLLM_TeamTable"
DROP COLUMN IF EXISTS "budget_currency",
DROP COLUMN IF EXISTS "spend_currency";

ALTER TABLE "LiteLLM_UserTable"
DROP COLUMN IF EXISTS "budget_currency",
DROP COLUMN IF EXISTS "spend_currency";

ALTER TABLE "LiteLLM_BudgetTable"
DROP COLUMN IF EXISTS "budget_currency";

ALTER TABLE "LiteLLM_SpendLogs"
DROP COLUMN IF EXISTS "spend_currency";
```

---

## TypedDict 更新

### 文件: `/litellm/types/router.py`

**添加货币字段到 UserAPIKeyAuth**:

```python
from typing import TypedDict, Optional

class UserAPIKeyAuth(TypedDict, total=False):
    """用户 API 密钥认证信息"""
    token: str
    spend: float
    max_budget: Optional[float]

    # 新增字段
    budget_currency: str  # 预算货币
    spend_currency: str   # 费用货币

    # ... 其他字段
```

---

## 测试数据

### 创建测试数据

```sql
-- 创建 CNY 预算的测试密钥
INSERT INTO "LiteLLM_VerificationToken" (
  token,
  max_budget,
  budget_currency,
  spend_currency,
  spend
) VALUES (
  'sk-test-cny-budget',
  10000.0,
  'CNY',
  'CNY',
  0.0
);

-- 创建混合货币的团队
INSERT INTO "LiteLLM_TeamTable" (
  team_id,
  team_alias,
  max_budget,
  budget_currency,
  spend_currency,
  spend
) VALUES (
  'team-multi-currency',
  'Multi-Currency Team',
  5000.0,
  'CNY',
  'CNY',
  0.0
);
```

### 验证测试数据

```sql
-- 查询测试密钥
SELECT
  token,
  max_budget,
  budget_currency,
  spend,
  spend_currency
FROM "LiteLLM_VerificationToken"
WHERE token LIKE 'sk-test%';

-- 预期结果：
-- token              | max_budget | budget_currency | spend | spend_currency
-- -------------------|------------|-----------------|-------|---------------
-- sk-test-cny-budget |  10000.0   | CNY             | 0.0   | CNY
```

---

## 性能影响评估

### 1. 额外存储

```
每行新增:
- 2个 TEXT 字段 (约 8-16 bytes)
- 总影响: < 32 bytes/row

对于 100万条记录:
- 额外空间: ~30 MB
- 影响: 可忽略
```

### 2. 查询性能

```sql
-- 添加索引后的查询性能
EXPLAIN ANALYZE
SELECT * FROM "LiteLLM_VerificationToken"
WHERE budget_currency = 'CNY';

-- 预期: Index Scan，<10ms
```

### 3. 迁移时间

```
估算（基于 PostgreSQL）:
- 10万条记录: ~2-5 秒
- 100万条记录: ~20-30 秒
- 1000万条记录: ~3-5 分钟

建议: 在低峰期执行
```

---

## 下一步

1. ✅ Schema 改动设计完成
2. ⏭️ 创建计费逻辑改造示例
3. ⏭️ 创建 API 端点设计
4. ⏭️ 创建测试计划
