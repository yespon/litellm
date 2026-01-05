# 测试计划 - 多货币支持

## 📋 目录
- [测试策略](#测试策略)
- [单元测试](#单元测试)
- [集成测试](#集成测试)
- [E2E测试](#e2e测试)
- [性能测试](#性能测试)

---

## 测试策略

### 测试金字塔

```
        /\
       /  \       E2E测试 (10%)
      /____\      - 用户流程测试
     /      \
    /        \    集成测试 (30%)
   /__________\   - API端点测试
  /            \  - 数据库测试
 /              \
/________________\ 单元测试 (60%)
                  - 函数测试
                  - 货币转换测试
```

### 测试覆盖目标
- **单元测试**: > 90%
- **集成测试**: > 80%
- **E2E测试**: 核心流程 100%

---

## 单元测试

### 文件: `/tests/test_currency.py`

#### 1. 汇率管理器测试

```python
import pytest
from datetime import datetime
from litellm.utils.currency import (
    CurrencyExchangeRateManager,
    convert_currency,
    get_exchange_rate,
    reload_exchange_rates
)

class TestCurrencyExchangeRateManager:
    """汇率管理器单元测试"""

    def setup_method(self):
        """每个测试前的设置"""
        self.manager = CurrencyExchangeRateManager()
        self.manager.load_rates(force=True)

    def test_singleton_pattern(self):
        """测试单例模式"""
        manager1 = CurrencyExchangeRateManager()
        manager2 = CurrencyExchangeRateManager()
        assert manager1 is manager2

    def test_load_rates(self):
        """测试加载汇率"""
        self.manager.load_rates(force=True)
        rates = self.manager.get_all_rates()

        assert "USD" in rates
        assert "CNY" in rates
        assert rates["USD"] == 1.0
        assert rates["CNY"] > 0

    def test_get_rate_same_currency(self):
        """测试相同货币的汇率"""
        rate = self.manager.get_rate("USD", "USD")
        assert rate == 1.0

    def test_get_rate_usd_to_cny(self):
        """测试 USD 到 CNY 的汇率"""
        rate = self.manager.get_rate("USD", "CNY")
        assert rate > 1.0  # CNY 应该比 USD 大

    def test_get_rate_cny_to_usd(self):
        """测试 CNY 到 USD 的汇率"""
        rate = self.manager.get_rate("CNY", "USD")
        assert 0 < rate < 1.0  # USD 应该比 CNY 小

    def test_get_rate_unsupported_currency(self):
        """测试不支持的货币"""
        with pytest.raises(ValueError, match="Unsupported currency"):
            self.manager.get_rate("USD", "XXX")

    def test_convert_same_currency(self):
        """测试相同货币转换"""
        result = self.manager.convert(100, "USD", "USD")
        assert result == 100

    def test_convert_usd_to_cny(self):
        """测试 USD 转 CNY"""
        result = self.manager.convert(100, "USD", "CNY")
        expected = 100 * self.manager.get_rate("USD", "CNY")
        assert abs(result - expected) < 0.01

    def test_convert_cny_to_usd(self):
        """测试 CNY 转 USD"""
        result = self.manager.convert(720, "CNY", "USD")
        # 假设汇率 7.2
        assert abs(result - 100) < 0.01

    def test_round_trip_conversion(self):
        """测试往返转换"""
        original = 100
        cny = self.manager.convert(original, "USD", "CNY")
        usd_back = self.manager.convert(cny, "CNY", "USD")
        assert abs(usd_back - original) < 0.001  # 允许浮点误差

    def test_update_rate(self):
        """测试更新汇率"""
        old_rate = self.manager.get_rate("USD", "CNY")
        self.manager.update_rate("CNY", 7.5, save=False)
        new_rate = self.manager.get_rate("USD", "CNY")

        assert new_rate != old_rate
        assert new_rate == 7.5

    def test_update_rate_invalid(self):
        """测试无效汇率"""
        with pytest.raises(ValueError, match="Invalid rate"):
            self.manager.update_rate("CNY", 0, save=False)

        with pytest.raises(ValueError, match="Invalid rate"):
            self.manager.update_rate("CNY", -1, save=False)

    def test_cache_validity(self):
        """测试缓存有效性"""
        self.manager._cache_ttl = 10  # 10秒缓存
        self.manager.load_rates(force=True)
        first_update = self.manager._last_update

        # 立即再次加载（应该使用缓存）
        self.manager.load_rates()
        second_update = self.manager._last_update

        assert first_update == second_update

    def test_get_supported_currencies(self):
        """测试获取支持的货币列表"""
        currencies = self.manager.get_supported_currencies()
        assert "USD" in currencies
        assert "CNY" in currencies
        assert isinstance(currencies, list)
```

#### 2. 便捷函数测试

```python
class TestConvenienceFunctions:
    """便捷函数测试"""

    def test_convert_currency_function(self):
        """测试 convert_currency 函数"""
        result = convert_currency(100, "USD", "CNY")
        assert result > 100  # CNY 应该更大

    def test_get_exchange_rate_function(self):
        """测试 get_exchange_rate 函数"""
        rate = get_exchange_rate("USD", "CNY")
        assert rate > 0
        assert isinstance(rate, float)

    def test_reload_exchange_rates_function(self):
        """测试 reload_exchange_rates 函数"""
        reload_exchange_rates()
        # 验证加载成功
        rate = get_exchange_rate("USD", "CNY")
        assert rate > 0
```

---

## 集成测试

### 文件: `/tests/integration/test_multi_currency_billing.py`

#### 1. 计费逻辑测试

```python
import pytest
import litellm
from litellm.utils.currency import convert_currency

class TestMultiCurrencyBilling:
    """多货币计费集成测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """测试前设置"""
        # 设置测试汇率
        from litellm.utils.currency import CurrencyExchangeRateManager
        manager = CurrencyExchangeRateManager()
        manager.update_rate("CNY", 7.2, save=False)

    def test_usd_model_cost_calculation(self):
        """测试 USD 模型成本计算"""
        # 模拟 GPT-4 调用
        model = "gpt-4"
        prompt_tokens = 100
        completion_tokens = 50

        from litellm.cost_calculator import cost_per_token
        input_cost, output_cost = cost_per_token(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens
        )

        assert input_cost > 0
        assert output_cost > 0
        assert isinstance(input_cost, float)
        assert isinstance(output_cost, float)

    def test_cny_model_cost_calculation(self):
        """测试 CNY 模型成本计算"""
        # 模拟通义千问调用
        model = "qwen-max"
        prompt_tokens = 100
        completion_tokens = 50

        # 假设 qwen-max 使用 CNY 定价
        from litellm.cost_calculator import cost_per_token
        from litellm import model_cost

        # 临时设置 CNY 定价
        original_info = model_cost.get(model, {})
        model_cost[model] = {
            "input_cost_per_token": 0.0008,
            "output_cost_per_token": 0.002,
            "currency": "CNY"
        }

        try:
            input_cost, output_cost = cost_per_token(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens
            )

            # 成本应该已转换为 USD
            assert input_cost > 0
            assert output_cost > 0

        finally:
            # 恢复原始配置
            if original_info:
                model_cost[model] = original_info

    def test_mixed_currency_tracking(self):
        """测试混合货币追踪"""
        # 这个测试需要完整的数据库和代理服务器
        # 标记为集成测试
        pytest.skip("Requires full proxy server")
```

#### 2. 预算检查测试

```python
class TestBudgetChecks:
    """预算检查集成测试"""

    @pytest.fixture
    async def test_key(self, prisma_client):
        """创建测试密钥"""
        key = await prisma_client.db.litellm_verificationtoken.create(
            data={
                "token": "sk-test-currency-budget",
                "max_budget": 10000.0,
                "budget_currency": "CNY",
                "spend": 0.0,
                "spend_currency": "CNY"
            }
        )
        yield key
        # 清理
        await prisma_client.db.litellm_verificationtoken.delete(
            where={"token": key.token}
        )

    async def test_cny_budget_check_pass(self, test_key):
        """测试 CNY 预算检查（通过）"""
        from litellm.proxy.auth.auth_checks import _virtual_key_max_budget_check

        # 模拟费用增加
        test_key.spend = 5000.0  # ¥5000

        # 应该不抛出异常
        await _virtual_key_max_budget_check(test_key)

    async def test_cny_budget_check_fail(self, test_key):
        """测试 CNY 预算检查（失败）"""
        from litellm.proxy.auth.auth_checks import _virtual_key_max_budget_check
        from litellm.proxy.auth.auth_utils import BudgetExceededError

        # 模拟预算超支
        test_key.spend = 10001.0  # ¥10001 > ¥10000

        # 应该抛出预算超支异常
        with pytest.raises(BudgetExceededError):
            await _virtual_key_max_budget_check(test_key)

    async def test_cross_currency_budget_check(self, test_key):
        """测试跨货币预算检查"""
        from litellm.proxy.auth.auth_checks import _virtual_key_max_budget_check

        # 预算是 CNY，但费用用 USD 累计
        test_key.spend = 1000.0  # $1000
        test_key.spend_currency = "USD"
        test_key.budget_currency = "CNY"
        test_key.max_budget = 10000.0  # ¥10000

        # $1000 × 7.2 = ¥7200 < ¥10000
        # 应该不抛出异常
        await _virtual_key_max_budget_check(test_key)
```

---

## E2E测试

### 文件: `/ui/litellm-dashboard/e2e_tests/currency.spec.ts`

#### 1. 汇率配置流程

```typescript
import { test, expect } from '@playwright/test';

test.describe('Currency Configuration', () => {

  test.beforeEach(async ({ page }) => {
    // 登录
    await page.goto('/login');
    await page.fill('[name=username]', 'admin');
    await page.fill('[name=password]', 'sk-1234');
    await page.click('button[type=submit]');
    await page.waitForURL(/.*page=/);
  });

  test('管理员可以查看汇率配置', async ({ page }) => {
    // 导航到货币设置
    await page.goto('/?page=currency-settings');

    // 验证页面元素
    await expect(page.locator('h1')).toContainText('Currency Settings');
    await expect(page.locator('[data-testid=exchange-rate-table]')).toBeVisible();

    // 验证 USD 汇率
    const usdRate = await page.locator('[data-currency=USD]').textContent();
    expect(usdRate).toBe('1.0');
  });

  test('管理员可以更新 CNY 汇率', async ({ page }) => {
    await page.goto('/?page=currency-settings');

    // 输入新汇率
    await page.fill('[name=cny-rate]', '7.25');
    await page.click('button:has-text("Update Rate")');

    // 验证成功提示
    await expect(page.locator('.success-message')).toBeVisible();
    await expect(page.locator('.success-message')).toContainText('updated successfully');

    // 刷新页面验证保存
    await page.reload();
    const newRate = await page.locator('[name=cny-rate]').inputValue();
    expect(newRate).toBe('7.25');
  });

  test('管理员可以重新加载汇率', async ({ page }) => {
    await page.goto('/?page=currency-settings');

    // 点击重新加载按钮
    await page.click('button:has-text("Reload Rates")');

    // 验证成功提示
    await expect(page.locator('.success-message')).toBeVisible();
  });
});
```

#### 2. 密钥创建流程

```typescript
test.describe('Key Creation with Currency', () => {

  test('可以创建 CNY 预算的密钥', async ({ page }) => {
    await page.goto('/?page=api-keys');

    // 点击创建密钥按钮
    await page.click('button:has-text("Create Key")');

    // 填写表单
    await page.fill('[name=key_alias]', 'test-cny-key');
    await page.fill('[name=max_budget]', '10000');
    await page.selectOption('[name=budget_currency]', 'CNY');

    // 提交
    await page.click('button[type=submit]');

    // 验证成功
    await expect(page.locator('.success-message')).toBeVisible();

    // 验证密钥显示
    await expect(page.locator('text=test-cny-key')).toBeVisible();
    await expect(page.locator('text=¥10,000')).toBeVisible();
  });
});
```

#### 3. 费用显示流程

```typescript
test.describe('Spend Display with Currency', () => {

  test('可以切换费用显示货币', async ({ page }) => {
    await page.goto('/?page=usage');

    // 默认显示 USD
    await expect(page.locator('.total-spend')).toContainText('$');

    // 切换到 CNY
    await page.selectOption('[name=display-currency]', 'CNY');

    // 等待更新
    await page.waitForTimeout(500);

    // 验证显示变为 CNY
    await expect(page.locator('.total-spend')).toContainText('¥');
  });

  test('费用统计正确转换货币', async ({ page }) => {
    await page.goto('/?page=usage');

    // 获取 USD 金额
    const usdText = await page.locator('.total-spend').textContent();
    const usdAmount = parseFloat(usdText.replace(/[^\d.]/g, ''));

    // 切换到 CNY
    await page.selectOption('[name=display-currency]', 'CNY');
    await page.waitForTimeout(500);

    // 获取 CNY 金额
    const cnyText = await page.locator('.total-spend').textContent();
    const cnyAmount = parseFloat(cnyText.replace(/[^\d.]/g, ''));

    // 验证转换比例合理（假设汇率 ~7.2）
    const ratio = cnyAmount / usdAmount;
    expect(ratio).toBeGreaterThan(6);
    expect(ratio).toBeLessThan(8);
  });
});
```

---

## 性能测试

### 文件: `/tests/performance/test_currency_performance.py`

#### 1. 汇率转换性能

```python
import pytest
import time
from litellm.utils.currency import convert_currency

class TestCurrencyPerformance:
    """货币转换性能测试"""

    def test_single_conversion_performance(self):
        """测试单次转换性能"""
        start = time.time()

        for _ in range(10000):
            convert_currency(100, "USD", "CNY")

        elapsed = time.time() - start

        # 10000次转换应该在 1 秒内完成
        assert elapsed < 1.0
        print(f"\n10000 conversions: {elapsed:.4f}s ({10000/elapsed:.0f} ops/s)")

    def test_cache_effectiveness(self):
        """测试缓存效果"""
        from litellm.utils.currency import CurrencyExchangeRateManager
        manager = CurrencyExchangeRateManager()

        # 第一次加载（冷缓存）
        manager._rates = {}
        start = time.time()
        manager.load_rates(force=True)
        cold_time = time.time() - start

        # 第二次加载（热缓存）
        start = time.time()
        manager.load_rates()
        hot_time = time.time() - start

        # 缓存应该显著加快
        assert hot_time < cold_time / 10
        print(f"\nCold load: {cold_time:.4f}s, Hot load: {hot_time:.6f}s")
```

#### 2. 预算检查性能

```python
class TestBudgetCheckPerformance:
    """预算检查性能测试"""

    async def test_budget_check_with_currency_conversion(self):
        """测试带货币转换的预算检查性能"""
        from litellm.proxy.auth.auth_checks import _virtual_key_max_budget_check

        # 模拟用户密钥
        test_key = {
            "token": "test",
            "spend": 5000.0,
            "spend_currency": "USD",
            "max_budget": 40000.0,
            "budget_currency": "CNY"
        }

        # 测试 1000 次预算检查
        start = time.time()

        for _ in range(1000):
            await _virtual_key_max_budget_check(test_key)

        elapsed = time.time() - start

        # 1000次检查应该在 0.5 秒内完成
        assert elapsed < 0.5
        print(f"\n1000 budget checks: {elapsed:.4f}s ({1000/elapsed:.0f} ops/s)")
```

---

## 测试运行

### 运行所有测试

```bash
# 单元测试
pytest tests/test_currency.py -v

# 集成测试
pytest tests/integration/test_multi_currency_billing.py -v

# E2E 测试
cd ui/litellm-dashboard
npm run e2e currency.spec.ts

# 性能测试
pytest tests/performance/test_currency_performance.py -v -s

# 覆盖率报告
pytest tests/ --cov=litellm.utils.currency --cov-report=html
```

### CI/CD 配置

```yaml
# .github/workflows/currency_tests.yml
name: Currency Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v2

      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest pytest-cov

      - name: Run unit tests
        run: pytest tests/test_currency.py -v --cov

      - name: Run integration tests
        run: pytest tests/integration/test_multi_currency_billing.py -v

      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

---

## 测试检查清单

### Phase 1 - 基础设施
- [ ] 汇率管理器单元测试
- [ ] 货币转换函数测试
- [ ] 配置加载测试
- [ ] 缓存机制测试

### Phase 2 - 数据模型
- [ ] Schema 迁移测试
- [ ] 默认值测试
- [ ] 向后兼容性测试

### Phase 3 - 计费逻辑
- [ ] USD 模型计费测试
- [ ] CNY 模型计费测试
- [ ] 混合货币计费测试
- [ ] 预算检查测试

### Phase 4 - API
- [ ] 汇率 API 测试
- [ ] 密钥创建 API 测试
- [ ] 费用查询 API 测试

### Phase 5 - UI
- [ ] 汇率配置 UI 测试
- [ ] 密钥创建 UI 测试
- [ ] 费用显示 UI 测试

---

## 下一步

1. ✅ 测试计划创建完成
2. ⏭️ 创建用户文档
3. ⏭️ 创建总结文档
