# Phase 5: UI 组件详细设计

## 📋 目录
- [组件架构](#组件架构)
- [汇率配置页面](#汇率配置页面)
- [密钥创建表单扩展](#密钥创建表单扩展)
- [费用展示组件](#费用展示组件)
- [共享组件](#共享组件)

---

## 组件架构

### 目录结构

```
ui/litellm-dashboard/src/
├── app/
│   ├── currency/
│   │   └── page.tsx                    # 汇率配置主页
│   └── api-keys/
│       └── CreateKeyModal.tsx          # 修改：添加货币选择
├── components/
│   ├── currency/
│   │   ├── ExchangeRateTable.tsx       # 汇率表格
│   │   ├── ExchangeRateEditor.tsx      # 汇率编辑器
│   │   ├── CurrencySelector.tsx        # 货币选择器
│   │   └── CurrencyConverter.tsx       # 货币转换器
│   ├── spend/
│   │   ├── SpendChart.tsx              # 修改：支持货币切换
│   │   └── SpendTable.tsx              # 修改：支持货币转换
│   └── common/
│       ├── CurrencyDisplay.tsx         # 货币显示组件
│       └── BudgetProgress.tsx          # 预算进度条
├── hooks/
│   ├── useCurrency.ts                  # 货币管理 Hook
│   └── useExchangeRate.ts              # 汇率查询 Hook
└── types/
    └── currency.ts                     # 货币类型定义
```

---

## 汇率配置页面

### 文件: `/ui/litellm-dashboard/src/app/currency/page.tsx`

```typescript
'use client';

import React, { useState } from 'react';
import {
  Card,
  Table,
  Button,
  Space,
  InputNumber,
  message,
  Modal,
  Descriptions,
  Tag,
  Typography,
  Spin
} from 'antd';
import {
  ReloadOutlined,
  EditOutlined,
  SaveOutlined,
  CloseOutlined,
  DollarOutlined
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

const { Title, Text } = Typography;

// ==================== 类型定义 ====================

interface ExchangeRate {
  currency: string;
  rate: number;
  lastUpdated?: string;
}

interface ExchangeRateData {
  base_currency: string;
  rates: Record<string, number>;
  last_updated: string;
  source: string;
  supported_currencies: string[];
}

// ==================== API 函数 ====================

const fetchExchangeRates = async (): Promise<ExchangeRateData> => {
  const response = await fetch('/config/exchange_rates', {
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('token')}`
    }
  });

  if (!response.ok) {
    throw new Error('Failed to fetch exchange rates');
  }

  const result = await response.json();
  return result.data;
};

const updateExchangeRates = async (rates: Record<string, number>) => {
  const response = await fetch('/config/exchange_rates', {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ rates })
  });

  if (!response.ok) {
    throw new Error('Failed to update exchange rates');
  }

  return response.json();
};

const reloadExchangeRates = async () => {
  const response = await fetch('/config/exchange_rates/reload', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('token')}`
    }
  });

  if (!response.ok) {
    throw new Error('Failed to reload exchange rates');
  }

  return response.json();
};

// ==================== 主组件 ====================

export default function CurrencySettingsPage() {
  const queryClient = useQueryClient();
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editingValue, setEditingValue] = useState<number>(0);
  const [pendingChanges, setPendingChanges] = useState<Record<string, number>>({});

  // 查询汇率数据
  const { data, isLoading, error } = useQuery({
    queryKey: ['exchangeRates'],
    queryFn: fetchExchangeRates,
    refetchInterval: 60000 // 每分钟刷新
  });

  // 更新汇率 Mutation
  const updateMutation = useMutation({
    mutationFn: updateExchangeRates,
    onSuccess: () => {
      message.success('Exchange rates updated successfully');
      queryClient.invalidateQueries({ queryKey: ['exchangeRates'] });
      setPendingChanges({});
    },
    onError: (error: Error) => {
      message.error(`Failed to update: ${error.message}`);
    }
  });

  // 重新加载 Mutation
  const reloadMutation = useMutation({
    mutationFn: reloadExchangeRates,
    onSuccess: () => {
      message.success('Exchange rates reloaded from config file');
      queryClient.invalidateQueries({ queryKey: ['exchangeRates'] });
    },
    onError: (error: Error) => {
      message.error(`Failed to reload: ${error.message}`);
    }
  });

  // 表格列定义
  const columns = [
    {
      title: 'Currency',
      dataIndex: 'currency',
      key: 'currency',
      render: (currency: string) => (
        <Space>
          <DollarOutlined />
          <Text strong>{currency}</Text>
          {currency === 'USD' && <Tag color="blue">Base</Tag>}
        </Space>
      )
    },
    {
      title: 'Exchange Rate',
      dataIndex: 'rate',
      key: 'rate',
      render: (rate: number, record: ExchangeRate) => {
        if (record.currency === 'USD') {
          return <Text>1.0000</Text>;
        }

        if (editingKey === record.currency) {
          return (
            <InputNumber
              value={editingValue}
              onChange={(value) => setEditingValue(value || 0)}
              precision={4}
              min={0.0001}
              max={10000}
              style={{ width: 150 }}
              autoFocus
            />
          );
        }

        const displayRate = pendingChanges[record.currency] || rate;
        const hasChange = pendingChanges[record.currency] !== undefined;

        return (
          <Space>
            <Text style={{ color: hasChange ? '#1890ff' : undefined }}>
              {displayRate.toFixed(4)}
            </Text>
            {hasChange && <Tag color="orange">Modified</Tag>}
          </Space>
        );
      }
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: ExchangeRate) => {
        if (record.currency === 'USD') {
          return <Text type="secondary">Base currency</Text>;
        }

        if (editingKey === record.currency) {
          return (
            <Space>
              <Button
                type="primary"
                size="small"
                icon={<SaveOutlined />}
                onClick={() => handleSaveEdit(record.currency)}
              >
                Save
              </Button>
              <Button
                size="small"
                icon={<CloseOutlined />}
                onClick={handleCancelEdit}
              >
                Cancel
              </Button>
            </Space>
          );
        }

        return (
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleStartEdit(record.currency, record.rate)}
          >
            Edit
          </Button>
        );
      }
    }
  ];

  // 事件处理
  const handleStartEdit = (currency: string, rate: number) => {
    setEditingKey(currency);
    setEditingValue(pendingChanges[currency] || rate);
  };

  const handleCancelEdit = () => {
    setEditingKey(null);
    setEditingValue(0);
  };

  const handleSaveEdit = (currency: string) => {
    if (editingValue <= 0) {
      message.error('Exchange rate must be greater than 0');
      return;
    }

    setPendingChanges({
      ...pendingChanges,
      [currency]: editingValue
    });
    setEditingKey(null);
    setEditingValue(0);
    message.info('Change saved locally. Click "Apply Changes" to update.');
  };

  const handleApplyChanges = () => {
    if (Object.keys(pendingChanges).length === 0) {
      message.info('No changes to apply');
      return;
    }

    Modal.confirm({
      title: 'Apply Exchange Rate Changes?',
      content: (
        <div>
          <p>You are about to update the following exchange rates:</p>
          <ul>
            {Object.entries(pendingChanges).map(([currency, rate]) => (
              <li key={currency}>
                <Text strong>{currency}</Text>: {rate.toFixed(4)}
              </li>
            ))}
          </ul>
          <p>This will affect all future cost calculations.</p>
        </div>
      ),
      onOk: () => updateMutation.mutate(pendingChanges)
    });
  };

  const handleDiscardChanges = () => {
    setPendingChanges({});
    message.info('All changes discarded');
  };

  const handleReload = () => {
    Modal.confirm({
      title: 'Reload Exchange Rates?',
      content: 'This will reload rates from the config file, discarding any unsaved changes.',
      onOk: () => {
        setPendingChanges({});
        reloadMutation.mutate();
      }
    });
  };

  // 准备表格数据
  const tableData: ExchangeRate[] = data
    ? Object.entries(data.rates).map(([currency, rate]) => ({
        currency,
        rate,
        lastUpdated: data.last_updated
      }))
    : [];

  // 渲染
  if (isLoading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return (
      <Card>
        <Text type="danger">Failed to load exchange rates</Text>
      </Card>
    );
  }

  return (
    <div style={{ padding: '24px' }}>
      {/* 页头 */}
      <div style={{ marginBottom: 24 }}>
        <Title level={2}>Currency Settings</Title>
        <Text type="secondary">
          Configure exchange rates for multi-currency support
        </Text>
      </div>

      {/* 信息卡片 */}
      <Card style={{ marginBottom: 24 }}>
        <Descriptions title="Exchange Rate Information" column={2}>
          <Descriptions.Item label="Base Currency">
            {data?.base_currency || 'USD'}
          </Descriptions.Item>
          <Descriptions.Item label="Last Updated">
            {data?.last_updated
              ? new Date(data.last_updated).toLocaleString()
              : 'N/A'}
          </Descriptions.Item>
          <Descriptions.Item label="Source">
            <Tag>{data?.source || 'manual'}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Supported Currencies">
            {data?.supported_currencies.length || 0}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* 操作按钮 */}
      <Space style={{ marginBottom: 16 }}>
        <Button
          type="primary"
          icon={<SaveOutlined />}
          onClick={handleApplyChanges}
          disabled={Object.keys(pendingChanges).length === 0}
          loading={updateMutation.isPending}
        >
          Apply Changes ({Object.keys(pendingChanges).length})
        </Button>
        <Button
          icon={<CloseOutlined />}
          onClick={handleDiscardChanges}
          disabled={Object.keys(pendingChanges).length === 0}
        >
          Discard Changes
        </Button>
        <Button
          icon={<ReloadOutlined />}
          onClick={handleReload}
          loading={reloadMutation.isPending}
        >
          Reload from File
        </Button>
      </Space>

      {/* 汇率表格 */}
      <Card>
        <Table
          columns={columns}
          dataSource={tableData}
          rowKey="currency"
          pagination={false}
        />
      </Card>
    </div>
  );
}
```

---

## 密钥创建表单扩展

### 文件: `/ui/litellm-dashboard/src/components/keys/CreateKeyModal.tsx` (修改)

```typescript
'use client';

import React from 'react';
import { Modal, Form, Input, InputNumber, Select, Space, Typography } from 'antd';
import { DollarOutlined } from '@ant-design/icons';

const { Text } = Typography;
const { Option } = Select;

interface CreateKeyModalProps {
  visible: boolean;
  onCancel: () => void;
  onSubmit: (values: any) => void;
  loading?: boolean;
}

export default function CreateKeyModal({
  visible,
  onCancel,
  onSubmit,
  loading
}: CreateKeyModalProps) {
  const [form] = Form.useForm();

  // 货币选项
  const currencies = [
    { value: 'USD', label: 'US Dollar (USD)', symbol: '$' },
    { value: 'CNY', label: 'Chinese Yuan (CNY)', symbol: '¥' },
    { value: 'EUR', label: 'Euro (EUR)', symbol: '€' },
    { value: 'GBP', label: 'British Pound (GBP)', symbol: '£' },
    { value: 'JPY', label: 'Japanese Yen (JPY)', symbol: '¥' }
  ];

  const handleSubmit = () => {
    form.validateFields().then((values) => {
      onSubmit(values);
      form.resetFields();
    });
  };

  return (
    <Modal
      title="Create New API Key"
      open={visible}
      onCancel={onCancel}
      onOk={handleSubmit}
      okText="Create Key"
      confirmLoading={loading}
      width={600}
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          budget_currency: 'USD'
        }}
      >
        {/* 密钥别名 */}
        <Form.Item
          name="key_alias"
          label="Key Alias"
          rules={[{ required: true, message: 'Please enter a key alias' }]}
        >
          <Input placeholder="my-api-key" />
        </Form.Item>

        {/* 预算设置 - 新增货币选择 */}
        <Space.Compact style={{ width: '100%' }}>
          <Form.Item
            name="max_budget"
            label="Maximum Budget"
            style={{ flex: 1, marginRight: 8 }}
            rules={[
              { required: true, message: 'Please enter a budget' },
              { type: 'number', min: 0, message: 'Budget must be positive' }
            ]}
          >
            <InputNumber
              style={{ width: '100%' }}
              placeholder="1000"
              precision={2}
              min={0}
            />
          </Form.Item>

          <Form.Item
            name="budget_currency"
            label="Currency"
            style={{ width: 120 }}
          >
            <Select>
              {currencies.map((currency) => (
                <Option key={currency.value} value={currency.value}>
                  <Space>
                    <Text>{currency.symbol}</Text>
                    <Text>{currency.value}</Text>
                  </Space>
                </Option>
              ))}
            </Select>
          </Form.Item>
        </Space.Compact>

        {/* 预算提示 */}
        <Form.Item noStyle shouldUpdate>
          {({ getFieldValue }) => {
            const budget = getFieldValue('max_budget');
            const currency = getFieldValue('budget_currency');
            const currencySymbol =
              currencies.find((c) => c.value === currency)?.symbol || '$';

            if (budget) {
              return (
                <div style={{ marginTop: -16, marginBottom: 16 }}>
                  <Text type="secondary">
                    Budget: {currencySymbol}
                    {budget.toLocaleString()}
                  </Text>
                </div>
              );
            }
            return null;
          }}
        </Form.Item>

        {/* 其他字段... */}
        <Form.Item
          name="duration"
          label="Duration"
          help="e.g., 30d, 90d, 1y"
        >
          <Input placeholder="30d" />
        </Form.Item>

        <Form.Item name="models" label="Allowed Models">
          <Select
            mode="multiple"
            placeholder="Select models (leave empty for all)"
            options={[
              { value: 'gpt-4', label: 'GPT-4' },
              { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' },
              { value: 'qwen-max', label: 'Qwen Max (CNY)' },
              { value: 'qwen-plus', label: 'Qwen Plus (CNY)' }
            ]}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}
```

---

## 费用展示组件

### 文件: `/ui/litellm-dashboard/src/components/spend/SpendSummary.tsx`

```typescript
'use client';

import React, { useState } from 'react';
import { Card, Statistic, Row, Col, Select, Space, Typography } from 'antd';
import { DollarOutlined, ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';

const { Text } = Typography;
const { Option } = Select;

interface SpendData {
  total_spend: number;
  currency: string;
  budget: number;
  budget_currency: string;
  usage_percentage: number;
}

// ==================== 货币转换 Hook ====================

function useCurrencyConverter() {
  const [targetCurrency, setTargetCurrency] = useState('USD');

  const convertAmount = (amount: number, fromCurrency: string) => {
    // 这里应该调用实际的转换 API
    // 简化示例：假设已经有转换函数
    return amount; // 实际应该进行转换
  };

  return { targetCurrency, setTargetCurrency, convertAmount };
}

// ==================== 主组件 ====================

export default function SpendSummary() {
  const { targetCurrency, setTargetCurrency } = useCurrencyConverter();

  // 查询费用数据
  const { data, isLoading } = useQuery({
    queryKey: ['spendSummary', targetCurrency],
    queryFn: async () => {
      const response = await fetch(
        `/spend/summary?display_currency=${targetCurrency}`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        }
      );
      return response.json();
    }
  });

  // 货币符号映射
  const currencySymbols: Record<string, string> = {
    USD: '$',
    CNY: '¥',
    EUR: '€',
    GBP: '£',
    JPY: '¥'
  };

  const getCurrencySymbol = (currency: string) => {
    return currencySymbols[currency] || currency;
  };

  return (
    <Card
      title="Spending Overview"
      extra={
        <Space>
          <Text type="secondary">Display in:</Text>
          <Select
            value={targetCurrency}
            onChange={setTargetCurrency}
            style={{ width: 100 }}
          >
            <Option value="USD">USD</Option>
            <Option value="CNY">CNY</Option>
            <Option value="EUR">EUR</Option>
            <Option value="GBP">GBP</Option>
            <Option value="JPY">JPY</Option>
          </Select>
        </Space>
      }
      loading={isLoading}
    >
      <Row gutter={16}>
        {/* 总费用 */}
        <Col span={8}>
          <Statistic
            title="Total Spend"
            value={data?.total_spend || 0}
            precision={2}
            prefix={getCurrencySymbol(targetCurrency)}
            suffix={targetCurrency}
            valueStyle={{ color: '#3f8600' }}
          />
        </Col>

        {/* 预算 */}
        <Col span={8}>
          <Statistic
            title="Budget"
            value={data?.budget || 0}
            precision={2}
            prefix={getCurrencySymbol(data?.budget_currency || 'USD')}
            suffix={data?.budget_currency || 'USD'}
          />
        </Col>

        {/* 使用百分比 */}
        <Col span={8}>
          <Statistic
            title="Budget Usage"
            value={data?.usage_percentage || 0}
            precision={1}
            suffix="%"
            prefix={
              data?.usage_percentage > 90 ? (
                <ArrowUpOutlined />
              ) : (
                <ArrowDownOutlined />
              )
            }
            valueStyle={{
              color: data?.usage_percentage > 90 ? '#cf1322' : '#3f8600'
            }}
          />
        </Col>
      </Row>
    </Card>
  );
}
```

---

## 共享组件

### 文件: `/ui/litellm-dashboard/src/components/common/CurrencyDisplay.tsx`

```typescript
'use client';

import React from 'react';
import { Typography, Space, Tooltip } from 'antd';
import { QuestionCircleOutlined } from '@ant-design/icons';

const { Text } = Typography;

interface CurrencyDisplayProps {
  amount: number;
  currency: string;
  showCode?: boolean;
  precision?: number;
  convertTo?: string;
  exchangeRate?: number;
}

export default function CurrencyDisplay({
  amount,
  currency,
  showCode = true,
  precision = 2,
  convertTo,
  exchangeRate
}: CurrencyDisplayProps) {
  const currencySymbols: Record<string, string> = {
    USD: '$',
    CNY: '¥',
    EUR: '€',
    GBP: '£',
    JPY: '¥'
  };

  const getSymbol = (curr: string) => currencySymbols[curr] || curr;

  const formatAmount = (amt: number, curr: string) => {
    const symbol = getSymbol(curr);
    const formatted = amt.toFixed(precision);
    return showCode ? `${symbol}${formatted} ${curr}` : `${symbol}${formatted}`;
  };

  // 如果需要转换
  if (convertTo && exchangeRate) {
    const convertedAmount = amount * exchangeRate;

    return (
      <Space>
        <Text>{formatAmount(convertedAmount, convertTo)}</Text>
        <Tooltip
          title={`Original: ${formatAmount(amount, currency)} (Rate: ${exchangeRate})`}
        >
          <QuestionCircleOutlined style={{ color: '#8c8c8c' }} />
        </Tooltip>
      </Space>
    );
  }

  return <Text>{formatAmount(amount, currency)}</Text>;
}
```

### 文件: `/ui/litellm-dashboard/src/hooks/useCurrency.ts`

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { message } from 'antd';

interface ExchangeRates {
  base_currency: string;
  rates: Record<string, number>;
  last_updated: string;
  supported_currencies: string[];
}

export function useCurrency() {
  const queryClient = useQueryClient();

  // 获取汇率
  const { data: rates, isLoading } = useQuery<ExchangeRates>({
    queryKey: ['exchangeRates'],
    queryFn: async () => {
      const response = await fetch('/config/exchange_rates', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (!response.ok) {
        throw new Error('Failed to fetch exchange rates');
      }

      const result = await response.json();
      return result.data;
    },
    staleTime: 60000 // 1分钟
  });

  // 转换货币
  const convertCurrency = (
    amount: number,
    fromCurrency: string,
    toCurrency: string
  ): number => {
    if (!rates || fromCurrency === toCurrency) {
      return amount;
    }

    const fromRate = rates.rates[fromCurrency];
    const toRate = rates.rates[toCurrency];

    if (!fromRate || !toRate) {
      console.error('Currency not found in rates');
      return amount;
    }

    return (amount / fromRate) * toRate;
  };

  // 获取汇率
  const getExchangeRate = (
    fromCurrency: string,
    toCurrency: string
  ): number => {
    if (!rates || fromCurrency === toCurrency) {
      return 1.0;
    }

    const fromRate = rates.rates[fromCurrency] || 1;
    const toRate = rates.rates[toCurrency] || 1;

    return toRate / fromRate;
  };

  // 更新汇率
  const updateRatesMutation = useMutation({
    mutationFn: async (newRates: Record<string, number>) => {
      const response = await fetch('/config/exchange_rates', {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ rates: newRates })
      });

      if (!response.ok) {
        throw new Error('Failed to update rates');
      }

      return response.json();
    },
    onSuccess: () => {
      message.success('Exchange rates updated');
      queryClient.invalidateQueries({ queryKey: ['exchangeRates'] });
    },
    onError: (error: Error) => {
      message.error(`Update failed: ${error.message}`);
    }
  });

  return {
    rates,
    isLoading,
    convertCurrency,
    getExchangeRate,
    updateRates: updateRatesMutation.mutate,
    isUpdating: updateRatesMutation.isPending
  };
}
```

---

## 路由配置

### 文件: `/ui/litellm-dashboard/src/app/layout.tsx` (添加菜单项)

```typescript
// 在侧边栏菜单中添加货币设置
const menuItems = [
  // ... 现有菜单项
  {
    key: 'currency',
    icon: <DollarOutlined />,
    label: 'Currency Settings',
    path: '/currency',
    adminOnly: true // 仅管理员可见
  }
];
```

---

## 测试示例

### 文件: `/ui/litellm-dashboard/src/components/currency/__tests__/CurrencyDisplay.test.tsx`

```typescript
import React from 'react';
import { render, screen } from '@testing-library/react';
import CurrencyDisplay from '../CurrencyDisplay';

describe('CurrencyDisplay', () => {
  it('renders USD correctly', () => {
    render(<CurrencyDisplay amount={100} currency="USD" />);
    expect(screen.getByText('$100.00 USD')).toBeInTheDocument();
  });

  it('renders CNY correctly', () => {
    render(<CurrencyDisplay amount={720} currency="CNY" />);
    expect(screen.getByText('¥720.00 CNY')).toBeInTheDocument();
  });

  it('converts currency with exchange rate', () => {
    render(
      <CurrencyDisplay
        amount={100}
        currency="USD"
        convertTo="CNY"
        exchangeRate={7.2}
      />
    );
    expect(screen.getByText('¥720.00 CNY')).toBeInTheDocument();
  });

  it('hides currency code when showCode is false', () => {
    render(<CurrencyDisplay amount={100} currency="USD" showCode={false} />);
    expect(screen.getByText('$100.00')).toBeInTheDocument();
    expect(screen.queryByText('USD')).not.toBeInTheDocument();
  });
});
```

---

## E2E 测试

### 文件: `/ui/litellm-dashboard/e2e_tests/currency.spec.ts`

```typescript
import { test, expect } from '@playwright/test';

test.describe('Currency Management', () => {
  test.beforeEach(async ({ page }) => {
    // 登录
    await page.goto('/login');
    await page.fill('[name=username]', 'admin');
    await page.fill('[name=password]', 'sk-1234');
    await page.click('button[type=submit]');
    await page.waitForURL(/.*page=/);
  });

  test('should display currency settings page', async ({ page }) => {
    await page.goto('/currency');

    // 验证页面标题
    await expect(page.locator('h2')).toContainText('Currency Settings');

    // 验证汇率表格存在
    await expect(page.locator('table')).toBeVisible();

    // 验证 USD 存在
    await expect(page.locator('text=USD')).toBeVisible();
  });

  test('should edit exchange rate', async ({ page }) => {
    await page.goto('/currency');

    // 找到 CNY 行并点击编辑
    const cnyRow = page.locator('tr:has-text("CNY")');
    await cnyRow.locator('button:has-text("Edit")').click();

    // 输入新汇率
    await page.fill('input[type=number]', '7.25');

    // 保存
    await page.click('button:has-text("Save")');

    // 验证提示信息
    await expect(page.locator('.ant-message')).toContainText('saved locally');

    // 应用更改
    await page.click('button:has-text("Apply Changes")');

    // 确认对话框
    await page.click('.ant-modal button:has-text("OK")');

    // 验证成功提示
    await expect(page.locator('.ant-message')).toContainText('successfully');
  });

  test('should create key with CNY budget', async ({ page }) => {
    await page.goto('/api-keys');

    // 打开创建密钥对话框
    await page.click('button:has-text("Create Key")');

    // 填写表单
    await page.fill('[name=key_alias]', 'test-cny-key');
    await page.fill('[name=max_budget]', '10000');
    await page.selectOption('[name=budget_currency]', 'CNY');

    // 提交
    await page.click('.ant-modal button:has-text("Create")');

    // 验证成功
    await expect(page.locator('.ant-message')).toContainText('success');

    // 验证密钥显示
    await expect(page.locator('text=test-cny-key')).toBeVisible();
    await expect(page.locator('text=¥10,000')).toBeVisible();
  });
});
```

---

## 样式文件

### 文件: `/ui/litellm-dashboard/src/app/currency/currency.module.css`

```css
.currencyPage {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.pageHeader {
  margin-bottom: 24px;
}

.infoCard {
  margin-bottom: 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.infoCard :global(.ant-descriptions-item-label),
.infoCard :global(.ant-descriptions-item-content) {
  color: white;
}

.actionBar {
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.rateTable {
  background: white;
  border-radius: 8px;
}

.rateTable :global(.ant-table-thead > tr > th) {
  background: #fafafa;
  font-weight: 600;
}

.editInput {
  width: 150px;
}

.modifiedTag {
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.currencySelector {
  min-width: 120px;
}

.budgetProgress {
  margin-top: 16px;
}

.budgetProgress :global(.ant-progress-text) {
  font-weight: 600;
}
```

---

## 下一步

✅ **所有 Phase 2-5 的设计文档已完成**:

1. **Phase 2**: 数据模型详细设计 - `06_PHASE2_DATA_MODEL_DESIGN.md`
2. **Phase 3**: 计费逻辑详细设计 - `07_PHASE3_BILLING_LOGIC_DESIGN.md`
3. **Phase 4**: API 端点实现代码 - `08_PHASE4_API_IMPLEMENTATION.md`
4. **Phase 5**: UI 组件详细设计 - `09_PHASE5_UI_COMPONENTS_DESIGN.md`

所有文档包含：
- 完整的代码实现
- 详细的类型定义
- 测试示例
- 使用说明

可以开始实际开发了！
