# 数据库迁移执行指南

## 日期：2026-01-04

## ⚠️ 重要提示

**在执行任何数据库迁移之前，请务必：**
1. ✅ **备份数据库** - 完整备份所有数据
2. ✅ **在测试环境验证** - 先在测试数据库上执行
3. ✅ **计划维护窗口** - 选择低流量时段
4. ✅ **准备回滚方案** - 确保可以快速回滚

---

## 迁移概述

本次迁移为 LiteLLM 添加多货币支持，修改 11 个数据库表，添加 23 个字段和 17 个索引。

**影响范围**:
- ✅ **向后兼容**: 所有新字段都有默认值 `"USD"`
- ✅ **无数据丢失**: 只添加字段，不删除或修改现有数据
- ✅ **自动降级**: 现有记录自动使用 USD
- ⚠️ **需要停机**: 建议在维护窗口执行（预计 5-10 分钟）

**修改的表**:
1. LiteLLM_BudgetTable (1 个字段, 1 个索引)
2. LiteLLM_TeamTable (2 个字段, 2 个索引)
3. LiteLLM_UserTable (2 个字段, 2 个索引)
4. LiteLLM_VerificationToken (2 个字段, 2 个索引)
5. LiteLLM_SpendLogs (4 个字段, 1 个索引)
6. LiteLLM_DailyUserSpend (1 个字段, 1 个索引)
7. LiteLLM_DailyOrganizationSpend (1 个字段, 1 个索引)
8. LiteLLM_DailyEndUserSpend (1 个字段, 1 个索引)
9. LiteLLM_DailyAgentSpend (1 个字段, 1 个索引)
10. LiteLLM_DailyTeamSpend (1 个字段, 1 个索引)
11. LiteLLM_DailyTagSpend (1 个字段, 1 个索引)

---

## 方法 1: 使用手动 SQL 脚本（推荐）

### 步骤 1: 备份数据库

```bash
# PostgreSQL 备份
pg_dump -h your-host -U your-user -d litellm -F c -f litellm_backup_$(date +%Y%m%d_%H%M%S).dump

# 或使用 SQL 格式
pg_dump -h your-host -U your-user -d litellm > litellm_backup_$(date +%Y%m%d_%H%M%S).sql
```

### 步骤 2: 在测试环境验证

```bash
# 恢复备份到测试数据库
pg_restore -h test-host -U test-user -d litellm_test litellm_backup.dump

# 执行迁移脚本
psql -h test-host -U test-user -d litellm_test -f migrations/add_currency_support.sql

# 验证迁移结果
psql -h test-host -U test-user -d litellm_test << 'EOF'
-- 检查新增字段
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'LiteLLM_BudgetTable'
  AND column_name = 'budget_currency';

-- 检查索引
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'LiteLLM_BudgetTable'
  AND indexname LIKE '%currency%';

-- 验证默认值
SELECT budget_currency, COUNT(*)
FROM "LiteLLM_BudgetTable"
GROUP BY budget_currency;
EOF
```

### 步骤 3: 执行迁移（生产环境）

```bash
# 进入维护模式（停止应用访问数据库）
# 方法取决于你的部署方式（Kubernetes、Docker 等）

# 执行迁移
psql -h production-host -U production-user -d litellm -f migrations/add_currency_support.sql

# 验证迁移成功
psql -h production-host -U production-user -d litellm << 'EOF'
-- 检查所有表是否都有 currency 字段
SELECT
    t.table_name,
    COUNT(c.column_name) as currency_columns
FROM information_schema.tables t
LEFT JOIN information_schema.columns c
    ON t.table_name = c.table_name
    AND c.column_name LIKE '%currency%'
WHERE t.table_schema = 'public'
  AND t.table_name LIKE 'LiteLLM_%'
GROUP BY t.table_name
ORDER BY t.table_name;
EOF

# 重启应用
# 恢复正常访问
```

### 步骤 4: 验证应用功能

```bash
# 检查应用日志
# 验证关键功能：
# - API Key 创建
# - 请求计费
# - 预算检查
# - Spend 记录
```

---

## 方法 2: 使用 Prisma Migrate（自动化）

### 前提条件

```bash
# 确保 DATABASE_URL 环境变量已设置
export DATABASE_URL="postgresql://user:password@host:5432/litellm"

# 确保 Prisma Client 已生成
poetry run prisma generate --schema=litellm/proxy/schema.prisma
```

### 步骤 1: 创建迁移

```bash
# 创建迁移（不执行）
poetry run prisma migrate dev --name add_currency_support --schema=litellm/proxy/schema.prisma --create-only

# 检查生成的迁移文件
ls -la litellm/proxy/prisma/migrations/
cat litellm/proxy/prisma/migrations/*/migration.sql
```

### 步骤 2: 在测试环境执行

```bash
# 设置测试数据库 URL
export DATABASE_URL="postgresql://test-user:test-password@test-host:5432/litellm_test"

# 执行迁移
poetry run prisma migrate deploy --schema=litellm/proxy/schema.prisma

# 验证
poetry run prisma db execute --schema=litellm/proxy/schema.prisma --stdin << 'EOF'
SELECT column_name FROM information_schema.columns
WHERE table_name = 'LiteLLM_BudgetTable' AND column_name LIKE '%currency%';
EOF
```

### 步骤 3: 生产环境执行

```bash
# ⚠️ 重要：进入维护模式

# 设置生产数据库 URL
export DATABASE_URL="postgresql://prod-user:prod-password@prod-host:5432/litellm"

# 执行迁移
poetry run prisma migrate deploy --schema=litellm/proxy/schema.prisma

# ✅ 退出维护模式
```

---

## 迁移脚本说明

### 正向迁移: `migrations/add_currency_support.sql`

**包含内容**:
- 添加所有货币字段（默认值 "USD"）
- 创建所有索引
- 添加字段注释

**执行时间**: 约 2-5 分钟（取决于数据量）

**影响**:
- 锁表时间短（DDL 操作）
- 不影响现有数据
- 所有现有记录自动使用 USD

### 回滚脚本: `migrations/rollback_currency_support.sql`

**包含内容**:
- 删除所有索引
- 删除所有货币字段

**⚠️ 警告**: 回滚会丢失所有货币配置信息！

**执行回滚**:
```bash
# 仅在必要时执行回滚
psql -h host -U user -d litellm -f migrations/rollback_currency_support.sql
```

---

## 迁移后验证清单

### 数据库层面

- [ ] 所有 11 个表都有相应的货币字段
- [ ] 所有 17 个索引都已创建
- [ ] 现有数据的货币字段都是 "USD"
- [ ] 表结构与 schema.prisma 一致

**验证脚本**:
```sql
-- 检查所有表的货币字段
SELECT
    table_name,
    column_name,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND column_name LIKE '%currency%'
ORDER BY table_name, column_name;

-- 检查所有索引
SELECT
    tablename,
    indexname
FROM pg_indexes
WHERE schemaname = 'public'
  AND indexname LIKE '%currency%'
ORDER BY tablename;

-- 验证数据完整性
SELECT
    'LiteLLM_BudgetTable' as table_name,
    COUNT(*) as total_rows,
    COUNT(CASE WHEN budget_currency = 'USD' THEN 1 END) as usd_rows
FROM "LiteLLM_BudgetTable"
UNION ALL
SELECT
    'LiteLLM_TeamTable',
    COUNT(*),
    COUNT(CASE WHEN budget_currency = 'USD' THEN 1 END)
FROM "LiteLLM_TeamTable"
UNION ALL
SELECT
    'LiteLLM_UserTable',
    COUNT(*),
    COUNT(CASE WHEN budget_currency = 'USD' THEN 1 END)
FROM "LiteLLM_UserTable";
```

### 应用层面

- [ ] Prisma Client 已重新生成
- [ ] 应用启动无错误
- [ ] 创建新 API Key 成功
- [ ] 完成一次 LLM 请求成功
- [ ] Spend 正确记录（包含 currency 字段）
- [ ] 预算检查正常工作

**测试脚本** (Python):
```python
import asyncio
from prisma import Prisma

async def test_migration():
    prisma = Prisma()
    await prisma.connect()

    # 测试 1: 读取现有数据
    budgets = await prisma.litellm_budgettable.find_many(take=5)
    print(f"✓ 读取预算表成功: {len(budgets)} 条记录")
    if budgets:
        print(f"  - budget_currency: {budgets[0].budget_currency}")

    # 测试 2: 创建新记录
    test_budget = await prisma.litellm_budgettable.create(
        data={
            "budget_id": "test-currency-migration",
            "max_budget": 100.0,
            "budget_currency": "CNY",  # 测试新字段
            "created_by": "migration-test",
            "updated_by": "migration-test",
        }
    )
    print(f"✓ 创建新记录成功: currency={test_budget.budget_currency}")

    # 测试 3: 查询带索引的字段
    cny_budgets = await prisma.litellm_budgettable.find_many(
        where={"budget_currency": "CNY"}
    )
    print(f"✓ 索引查询成功: 找到 {len(cny_budgets)} 条 CNY 记录")

    # 清理测试数据
    await prisma.litellm_budgettable.delete(
        where={"budget_id": "test-currency-migration"}
    )

    await prisma.disconnect()
    print("\n✅ 所有迁移测试通过！")

# 运行测试
asyncio.run(test_migration())
```

---

## 性能影响

### 迁移期间
- **锁表时间**: 2-5 分钟（添加列 + 创建索引）
- **停机时间**: 建议 5-10 分钟维护窗口
- **IO 影响**: 中等（创建索引需要扫描表）

### 迁移后
- **查询性能**: 无影响（新增索引可能略微提升）
- **写入性能**: 略微下降（~1-2%，因为多了 17 个索引）
- **存储空间**: 每条记录增加约 50-100 字节

---

## 常见问题

### Q1: 迁移失败如何回滚？

```bash
# 停止应用

# 执行回滚脚本
psql -h host -U user -d litellm -f migrations/rollback_currency_support.sql

# 恢复到迁移前的代码版本

# 重启应用
```

### Q2: 迁移后应用报错？

**检查项**:
1. Prisma Client 是否重新生成？
   ```bash
   poetry run prisma generate --schema=litellm/proxy/schema.prisma
   ```

2. 环境变量是否正确？
   ```bash
   echo $DATABASE_URL
   ```

3. 数据库连接是否正常？
   ```bash
   poetry run prisma db execute --schema=litellm/proxy/schema.prisma --stdin <<< "SELECT 1;"
   ```

### Q3: 如何验证迁移是否完全成功？

运行完整验证脚本：
```bash
# 1. 数据库层验证
psql -h host -U user -d litellm < scripts/verify_currency_migration.sql

# 2. 应用层验证
poetry run python scripts/test_currency_migration.py

# 3. 功能验证
# - 创建新 API Key
# - 完成一次 chat completion
# - 检查 spend logs 是否包含 currency 字段
```

### Q4: 可以分批执行迁移吗？

**不建议**。本次迁移是原子操作，必须一次性完成所有表的修改，否则可能导致：
- Prisma Client 与数据库不一致
- 应用代码报错
- 数据完整性问题

---

## 下一步

迁移成功后：

1. ✅ **验证功能** - 确保所有核心功能正常
2. ✅ **监控日志** - 观察是否有异常错误
3. ✅ **更新文档** - 更新运维文档
4. ➡️ **继续 Phase 3** - 执行代码集成
5. ➡️ **开发 Phase 4** - 实现 Management API

---

## 联系支持

如果迁移过程中遇到问题：
1. 保留错误日志
2. 记录执行的具体步骤
3. 准备数据库状态快照
4. 联系技术支持团队

---

## 文件清单

- ✅ `migrations/add_currency_support.sql` - 正向迁移
- ✅ `migrations/rollback_currency_support.sql` - 回滚脚本
- ✅ `litellm/proxy/schema.prisma` - 更新后的 Schema
- ✅ `litellm/proxy/schema.prisma.backup` - 备份文件
- ✅ `docs/multi_currency/MIGRATION_GUIDE.md` - 本文档
