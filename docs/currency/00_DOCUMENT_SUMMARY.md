# 多货币支持设计文档 - 内容总结

> **快速导航**: 每个文档的核心内容和代码示例

---

## 📚 文档内容总结

### 📋 概览文档

#### 01_IMPLEMENTATION_PLAN.md
**内容**: 5个阶段的实施计划和时间估算
- Phase 1: 基础设施（3-4天）
- Phase 2: 数据模型（3-4天）
- Phase 3: 计费逻辑（7-10天）
- Phase 4: API 端点（4天）
- Phase 5: UI 实现（8-11天）
- 总计: 32-43天（6-8周）

**适合阅读对象**: 项目经理、技术负责人

---

#### 05_TEST_PLAN.md
**内容**: 完整的测试策略和测试代码
- 测试金字塔：60% 单元测试 + 30% 集成测试 + 10% E2E
- 汇率管理器单元测试
- 多货币计费集成测试
- Playwright E2E 测试
- 性能测试（10000次转换 < 1秒）

**代码示例**:
```python
def test_round_trip_conversion(self):
    original = 100
    cny = self.manager.convert(original, "USD", "CNY")
    usd_back = self.manager.convert(cny, "CNY", "USD")
    assert abs(usd_back - original) < 0.001
```

**适合阅读对象**: QA 工程师、测试负责人

---

### 🔧 Phase 1: 基础设施

#### 02_CURRENCY_MODULE.md
**内容**: 汇率管理模块的完整实现
- `CurrencyExchangeRateManager` 单例类（300+ 行）
- 汇率加载、缓存（1小时TTL）、转换
- 配置文件格式 (`currency_exchange_rates.json`)
- 便捷函数封装
- 单元测试示例

**核心代码**:
```python
class CurrencyExchangeRateManager:
    _instance = None
    _rates: Dict[str, float] = {}
    _cache_ttl: int = 3600

    def convert(self, amount: float, from_currency: str, to_currency: str) -> float:
        rate = self.get_rate(from_currency, to_currency)
        return amount * rate
```

**文件位置**: `/litellm/utils/currency.py`

**适合阅读对象**: Python 后端开发者

---

### 💾 Phase 2: 数据模型

#### 03_SCHEMA_CHANGES.md
**内容**: Prisma Schema 改动概述
- 5个表的改动（VerificationToken、TeamTable、UserTable、BudgetTable、SpendLogs）
- 迁移 SQL 脚本
- 回滚脚本
- 性能影响评估（~30MB for 1M records）

**Schema 改动**:
```prisma
model LiteLLM_VerificationToken {
  // 新增字段
  budget_currency: String @default("USD")
  spend_currency: String @default("USD")
}
```

**迁移命令**:
```bash
cd litellm/proxy
npx prisma migrate dev --name add_currency_support
```

**适合阅读对象**: 数据库工程师、后端开发者

---

#### 06_PHASE2_DATA_MODEL_DESIGN.md
**内容**: 数据模型详细实现（最详细）
- TypedDict 定义（`UserAPIKeyAuth` 等）
- Pydantic 模型（`GenerateKeyRequest`、`UpdateExchangeRatesRequest` 等）
- 完整 Prisma Schema（包含所有表）
- 数据访问层函数（`get_key_with_currency_info`、`update_spend_with_currency` 等）
- 迁移验证脚本
- 测试数据生成脚本

**核心类型**:
```python
class UserAPIKeyAuth(TypedDict, total=False):
    # 现有字段...
    budget_currency: str
    spend_currency: str

class GenerateKeyRequest(BaseModel):
    budget_currency: SupportedCurrency = Field(default="USD")
    max_budget: Optional[float] = None
```

**适合阅读对象**: Python 后端开发者（详细实现）

---

### 💰 Phase 3: 计费逻辑

#### 07_PHASE3_BILLING_LOGIC_DESIGN.md
**内容**: 计费系统核心改动（最核心）
- `cost_calculator.py` 完整改造（支持多货币）
- `cost_per_token()` 函数扩展
- Budget 检查逻辑（虚拟密钥、团队、用户）
- 费用累计逻辑
- 模型配置扩展（添加 `currency` 字段）
- 日志记录增强

**核心改动**:
```python
def cost_per_token(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    return_currency: str = "USD",
    include_currency_info: bool = False
) -> Union[Tuple[float, float], Dict[str, Any]]:
    # 1. 获取模型货币
    model_currency = get_model_currency(model)

    # 2. 计算原始成本
    cost = tokens * rate

    # 3. 转换为返回货币
    if model_currency != return_currency:
        cost = convert_currency(cost, model_currency, return_currency)

    return cost
```

**Budget 检查**:
```python
async def _virtual_key_max_budget_check(user_api_key_dict):
    # 如果货币不同，转换后比较
    if spend_currency != budget_currency:
        current_spend = convert_currency(
            current_spend, spend_currency, budget_currency
        )

    if current_spend >= max_budget:
        raise BudgetExceededError()
```

**文件位置**:
- `/litellm/cost_calculator.py`
- `/litellm/proxy/auth/auth_checks.py`
- `/litellm/proxy/proxy_server.py`

**适合阅读对象**: Python 后端开发者（必读）

---

### 🌐 Phase 4: API 端点

#### 04_API_DESIGN.md
**内容**: API 端点规范和示例
- 3个新增端点（GET/PATCH/POST `/config/exchange_rates`）
- 4个扩展端点（`/key/generate`、`/key/info`、`/spend/logs` 等）
- 完整的请求/响应示例
- 错误处理示例
- 完整流程演示（curl 命令）

**API 示例**:
```bash
# 更新汇率
curl -X PATCH http://localhost:4001/config/exchange_rates \
  -H "Authorization: Bearer sk-1234" \
  -d '{"rates": {"CNY": 7.25}}'

# 创建 CNY 预算密钥
curl -X POST http://localhost:4001/key/generate \
  -d '{"max_budget": 10000.0, "budget_currency": "CNY"}'
```

**适合阅读对象**: API 使用者、前端开发者

---

#### 08_PHASE4_API_IMPLEMENTATION.md
**内容**: FastAPI 端点完整实现（最详细的后端代码）
- `/litellm/proxy/management_endpoints/currency_settings.py` 完整代码（300+ 行）
- 密钥管理端点扩展
- 费用日志端点扩展
- 货币中间件 (`CurrencyMiddleware`)
- 错误处理类（`UnsupportedCurrencyError`、`CurrencyConversionError` 等）
- 路由注册代码
- 集成测试示例

**完整端点实现**:
```python
@router.patch("/config/exchange_rates")
async def update_exchange_rates(
    request: UpdateExchangeRatesRequest,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)
):
    if user_api_key_dict.user_role != "proxy_admin":
        raise HTTPException(status_code=403)

    manager = CurrencyExchangeRateManager()
    for currency, rate in request.rates.items():
        manager.update_rate(currency, rate, save=False)

    manager.save_rates()
    return {"success": True, "message": "Updated successfully"}
```

**文件位置**: `/litellm/proxy/management_endpoints/currency_settings.py`

**适合阅读对象**: Python 后端开发者、FastAPI 开发者（详细实现）

---

### 🎨 Phase 5: UI 组件

#### 09_PHASE5_UI_COMPONENTS_DESIGN.md
**内容**: React UI 组件完整实现
- 汇率配置页面 (`/app/currency/page.tsx`，400+ 行）
- 密钥创建表单扩展（货币选择器）
- 费用展示组件（支持货币切换）
- 共享组件（`CurrencyDisplay`、`CurrencySelector`）
- 自定义 Hooks（`useCurrency`）
- E2E 测试（Playwright）
- CSS 样式文件

**主要组件**:
```typescript
// 汇率配置页面
export default function CurrencySettingsPage() {
  const { data } = useQuery({
    queryKey: ['exchangeRates'],
    queryFn: fetchExchangeRates
  });

  return (
    <Card title="Currency Settings">
      <Table columns={columns} dataSource={tableData} />
    </Card>
  );
}

// 货币显示组件
<CurrencyDisplay
  amount={100}
  currency="USD"
  convertTo="CNY"
  exchangeRate={7.2}
/>
```

**自定义 Hook**:
```typescript
export function useCurrency() {
  const { data: rates } = useQuery(['exchangeRates'], fetchRates);

  const convertCurrency = (amount, from, to) => {
    return (amount / rates[from]) * rates[to];
  };

  return { rates, convertCurrency };
}
```

**文件位置**:
- `/ui/litellm-dashboard/src/app/currency/`
- `/ui/litellm-dashboard/src/components/currency/`
- `/ui/litellm-dashboard/src/hooks/useCurrency.ts`

**适合阅读对象**: React 前端开发者、UI/UX 开发者

---

## 📊 文档统计

| Phase | 文档数量 | 总行数 | 代码示例 |
|-------|---------|--------|---------|
| Phase 1 | 1 | ~450 | Python 单例模式 |
| Phase 2 | 2 | ~850 | Prisma + Python |
| Phase 3 | 1 | ~650 | Python 计费逻辑 |
| Phase 4 | 2 | ~900 | FastAPI 端点 |
| Phase 5 | 1 | ~750 | React + TypeScript |
| 概览 | 2 | ~1000 | 测试代码 |
| **总计** | **9** | **~4600** | **全栈实现** |

---

## 🎯 阅读建议

### 如果你是...

**项目经理 / 技术负责人**:
1. 📋 01_IMPLEMENTATION_PLAN.md（时间估算）
2. 📋 05_TEST_PLAN.md（质量保证）
3. 📋 README.md（项目概览）

**Python 后端开发者**:
1. 🔧 02_CURRENCY_MODULE.md（基础模块）
2. 💾 06_PHASE2_DATA_MODEL_DESIGN.md（数据模型）
3. 💰 07_PHASE3_BILLING_LOGIC_DESIGN.md（计费核心，**必读**）
4. 🌐 08_PHASE4_API_IMPLEMENTATION.md（API 实现）

**数据库工程师**:
1. 💾 03_SCHEMA_CHANGES.md（Schema 改动）
2. 💾 06_PHASE2_DATA_MODEL_DESIGN.md（迁移脚本）

**前端开发者**:
1. 🌐 04_API_DESIGN.md（API 规范）
2. 🎨 09_PHASE5_UI_COMPONENTS_DESIGN.md（UI 实现）

**QA / 测试工程师**:
1. 📋 05_TEST_PLAN.md（测试策略）
2. 各 Phase 文档的测试部分

---

## 🔍 快速查找

### 需要查找特定主题？

| 主题 | 文档位置 |
|------|---------|
| 如何转换货币 | 02_CURRENCY_MODULE.md |
| 数据库迁移步骤 | 03_SCHEMA_CHANGES.md |
| Budget 检查逻辑 | 07_PHASE3_BILLING_LOGIC_DESIGN.md |
| API 调用示例 | 04_API_DESIGN.md |
| React 组件实现 | 09_PHASE5_UI_COMPONENTS_DESIGN.md |
| TypedDict 定义 | 06_PHASE2_DATA_MODEL_DESIGN.md |
| 错误处理 | 08_PHASE4_API_IMPLEMENTATION.md |
| E2E 测试 | 05_TEST_PLAN.md, 09_PHASE5_UI_COMPONENTS_DESIGN.md |

---

**最后更新**: 2026-01-04
**文档版本**: 1.0
