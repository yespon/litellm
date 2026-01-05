# 多货币支持 - 实现计划

## 📋 目录
- [Phase 1: 基础设施](#phase-1-基础设施)
- [Phase 2: 数据模型](#phase-2-数据模型)
- [Phase 3: 计费逻辑](#phase-3-计费逻辑)
- [Phase 4: API 端点](#phase-4-api-端点)
- [Phase 5: UI 实现](#phase-5-ui-实现)

---

## Phase 1: 基础设施

### 1.1 汇率管理模块

**文件**: `/litellm/utils/currency.py`

**功能**:
- 汇率加载和缓存
- 货币转换
- 汇率更新

**优先级**: P0 (必须)
**预计工时**: 2-3 天

---

### 1.2 汇率配置文件

**文件**: `/currency_exchange_rates.json`

**格式**:
```json
{
  "version": "1.0",
  "base_currency": "USD",
  "last_updated": "2026-01-03T10:00:00Z",
  "rates": {
    "USD": 1.0,
    "CNY": 7.2
  }
}
```

**优先级**: P0 (必须)
**预计工时**: 0.5 天

---

### 1.3 环境变量配置

**新增环境变量**:
```bash
# 汇率配置
CURRENCY_EXCHANGE_RATE_FILE=/path/to/currency_exchange_rates.json
CURRENCY_AUTO_UPDATE=false
CURRENCY_UPDATE_INTERVAL_HOURS=24

# 默认货币
DEFAULT_BUDGET_CURRENCY=USD
DEFAULT_DISPLAY_CURRENCY=USD
```

**优先级**: P1 (重要)
**预计工时**: 0.5 天

---

## Phase 2: 数据模型

### 2.1 Prisma Schema 扩展

**文件**: `/litellm/proxy/schema.prisma`

**改动内容**:
- 添加 `budget_currency` 字段
- 添加 `spend_currency` 字段
- 扩展相关表

**优先级**: P0 (必须)
**预计工时**: 1 天

---

### 2.2 TypedDict 扩展

**文件**: `/litellm/types/utils.py`

**改动内容**:
- 添加 `currency` 字段到 `ModelInfoBase`
- 创建 `CurrencyConfig` TypedDict
- 创建 `ExchangeRate` TypedDict

**优先级**: P0 (必须)
**预计工时**: 1 天

---

### 2.3 数据库迁移

**步骤**:
1. 生成迁移文件
2. 测试迁移（开发环境）
3. 准备回滚脚本
4. 生产环境迁移

**优先级**: P0 (必须)
**预计工时**: 1-2 天

---

## Phase 3: 计费逻辑

### 3.1 核心计费函数改造

**文件**: `/litellm/cost_calculator.py`

**改动函数**:
- `cost_per_token()`
- `completion_cost()`
- `generic_cost_per_token()`

**优先级**: P0 (必须)
**预计工时**: 3-4 天

---

### 3.2 费用追踪改造

**文件**: `/litellm/proxy/hooks/proxy_track_cost_callback.py`

**改动内容**:
- 货币转换逻辑
- 费用累计逻辑
- 数据库更新

**优先级**: P0 (必须)
**预计工时**: 2-3 天

---

### 3.3 预算检查改造

**文件**: `/litellm/proxy/auth/auth_checks.py`

**改动函数**:
- `_virtual_key_max_budget_check()`
- `_team_max_budget_check()`
- `_organization_max_budget_check()`

**优先级**: P0 (必须)
**预计工时**: 2-3 天

---

## Phase 4: API 端点

### 4.1 汇率管理 API

**新增端点**:
- `GET /config/exchange_rates`
- `PATCH /config/exchange_rates`
- `POST /config/exchange_rates/reload`

**优先级**: P0 (必须)
**预计工时**: 2 天

---

### 4.2 扩展现有 API

**改动端点**:
- `GET /public/litellm_model_cost_map`
- `GET /spend/logs`
- `GET /user/info`

**优先级**: P1 (重要)
**预计工时**: 2 天

---

## Phase 5: UI 实现

### 5.1 汇率配置页面

**组件**:
- `CurrencySettings/index.tsx`
- `ExchangeRateTable.tsx`
- `ExchangeRateForm.tsx`

**优先级**: P0 (必须)
**预计工时**: 3-4 天

---

### 5.2 预算设置改进

**改动组件**:
- 添加货币选择器
- 显示货币标识
- 实时汇率提示

**优先级**: P1 (重要)
**预计工时**: 2-3 天

---

### 5.3 费用展示改进

**改动组件**:
- 货币切换器
- 多币种图表
- 汇率信息展示

**优先级**: P1 (重要)
**预计工时**: 3-4 天

---

## 总体时间估算

| Phase | 工作内容 | 预计工时 |
|-------|---------|---------|
| Phase 1 | 基础设施 | 3-4 天 |
| Phase 2 | 数据模型 | 3-4 天 |
| Phase 3 | 计费逻辑 | 7-10 天 |
| Phase 4 | API 端点 | 4 天 |
| Phase 5 | UI 实现 | 8-11 天 |
| **测试** | 单元/集成/E2E | 5-7 天 |
| **文档** | API/用户文档 | 2-3 天 |

**总计**: **32-43 天** (约 6-8 周)

---

## 风险评估

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 数据库迁移失败 | 高 | 低 | 充分测试，准备回滚 |
| 性能下降 | 中 | 中 | 汇率缓存，性能测试 |
| 向后兼容问题 | 高 | 低 | 默认 USD，渐进迁移 |
| 汇率数据不准确 | 中 | 中 | 手动审核，多源验证 |

---

## 下一步行动

1. ✅ 创建实现计划文档
2. ⏭️ 创建详细的代码实现示例
3. ⏭️ 创建 API 设计文档
4. ⏭️ 创建测试计划
