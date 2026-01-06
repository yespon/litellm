"use client";
import React, { useEffect, useState } from "react";
import {
  Card,
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  TableCell,
  TableBody,
  Text,
  Title,
  Button as TremorButton,
  Badge,
} from "@tremor/react";
import { Button, Form, InputNumber, message, Tooltip } from "antd";
import { InfoCircleOutlined, ReloadOutlined } from "@ant-design/icons";
import { getExchangeRates, getSupportedCurrencies, updateExchangeRates } from "../networking";
import NotificationsManager from "../molecules/notifications_manager";

interface Currency {
  code: string;
  name: string;
}

interface ExchangeRate {
  currency: string;
  name: string;
  rate: number;
}

interface CurrencyManagementPageProps {
  accessToken: string | null;
  userRole: string | null;
}

/**
 * Currency Management UI Component
 *
 * Admin-only page for managing exchange rates.
 * Features:
 * - View all supported currencies and their exchange rates
 * - Update exchange rates (relative to USD)
 * - Refresh rates from the server
 * - Last updated timestamp
 */
const CurrencyManagementPage: React.FC<CurrencyManagementPageProps> = ({ accessToken, userRole }) => {
  const [currencies, setCurrencies] = useState<Currency[]>([]);
  const [exchangeRates, setExchangeRates] = useState<Record<string, number>>({});
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [editMode, setEditMode] = useState<boolean>(false);
  const [form] = Form.useForm();

  // Check if user is admin
  const isAdmin = userRole === "proxy_admin" || userRole === "admin";

  useEffect(() => {
    if (accessToken) {
      fetchData();
    }
  }, [accessToken]);

  const fetchData = async () => {
    setLoading(true);
    try {
      // Fetch supported currencies
      const currenciesData = await getSupportedCurrencies(accessToken!);
      setCurrencies(currenciesData.currencies || []);

      // Fetch exchange rates
      const ratesData = await getExchangeRates(accessToken!);
      setExchangeRates(ratesData.rates || {});
      setLastUpdated(ratesData.last_updated || null);

      // Set form values
      const formValues: Record<string, number> = {};
      Object.entries(ratesData.rates || {}).forEach(([currency, rate]) => {
        formValues[currency] = rate as number;
      });
      form.setFieldsValue(formValues);
    } catch (error) {
      console.error("Error fetching currency data:", error);
      NotificationsManager.error("Failed to fetch currency data");
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = async (values: Record<string, any>) => {
    if (!accessToken || !isAdmin) {
      NotificationsManager.error("Only administrators can update exchange rates");
      return;
    }

    try {
      setLoading(true);
      NotificationsManager.info("Updating exchange rates...");

      // Filter out USD (cannot be modified) and unchanged values
      const updates: Record<string, number> = {};
      Object.entries(values).forEach(([currency, rate]) => {
        if (currency !== "USD" && rate !== undefined && rate !== null) {
          updates[currency] = rate as number;
        }
      });

      if (Object.keys(updates).length === 0) {
        NotificationsManager.warning("No changes to update");
        return;
      }

      const response = await updateExchangeRates(accessToken, updates);
      NotificationsManager.success(
        `Successfully updated ${response.updated_currencies?.length || 0} currencies`
      );

      // Refresh data
      await fetchData();
      setEditMode(false);
    } catch (error: any) {
      console.error("Error updating exchange rates:", error);
      NotificationsManager.error(`Failed to update: ${error.message || "Unknown error"}`);
    } finally {
      setLoading(false);
    }
  };

  const formatLastUpdated = (timestamp: string | null): string => {
    if (!timestamp) return "Never";
    try {
      const date = new Date(timestamp);
      return date.toLocaleString();
    } catch {
      return timestamp;
    }
  };

  if (!accessToken) {
    return (
      <Card>
        <Text>Please log in to access currency management.</Text>
      </Card>
    );
  }

  if (!isAdmin) {
    return (
      <Card>
        <Title>Currency Management</Title>
        <Text className="mt-4">
          This page is only accessible to administrators. You can view exchange rates but cannot modify them.
        </Text>
        <div className="mt-6">
          <Title className="text-lg">Current Exchange Rates</Title>
          <Text className="text-sm text-gray-500">Base Currency: USD</Text>
          <Table className="mt-4">
            <TableHead>
              <TableRow>
                <TableHeaderCell>Currency</TableHeaderCell>
                <TableHeaderCell>Name</TableHeaderCell>
                <TableHeaderCell>Exchange Rate</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {currencies.map((currency) => (
                <TableRow key={currency.code}>
                  <TableCell>
                    <Text className="font-semibold">{currency.code}</Text>
                  </TableCell>
                  <TableCell>
                    <Text>{currency.name}</Text>
                  </TableCell>
                  <TableCell>
                    <Text>
                      {currency.code === "USD"
                        ? "1.0000 (Base)"
                        : exchangeRates[currency.code]?.toFixed(4) || "N/A"}
                    </Text>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="mt-4">
            <Text className="text-sm text-gray-500">Last Updated: {formatLastUpdated(lastUpdated)}</Text>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <div className="w-full">
      <Card>
        <div className="flex justify-between items-center">
          <div>
            <Title>Currency Management</Title>
            <Text className="mt-2">
              Manage exchange rates for multi-currency billing. All rates are relative to USD.
            </Text>
          </div>
          <div className="flex gap-2">
            <TremorButton
              icon={ReloadOutlined}
              onClick={fetchData}
              loading={loading}
              variant="secondary"
              size="sm"
            >
              Refresh
            </TremorButton>
          </div>
        </div>

        <div className="mt-6">
          <div className="flex justify-between items-center mb-4">
            <div>
              <Badge color="blue">Base Currency: USD</Badge>
              <Text className="ml-4 text-sm text-gray-500">Last Updated: {formatLastUpdated(lastUpdated)}</Text>
            </div>
            {!editMode ? (
              <Button type="primary" onClick={() => setEditMode(true)}>
                Edit Exchange Rates
              </Button>
            ) : (
              <div className="flex gap-2">
                <Button onClick={() => {
                  setEditMode(false);
                  form.resetFields();
                }}>
                  Cancel
                </Button>
                <Button type="primary" onClick={() => form.submit()} loading={loading}>
                  Save Changes
                </Button>
              </div>
            )}
          </div>

          <Form form={form} onFinish={handleUpdate} layout="vertical">
            <Table className="mt-4">
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Currency Code</TableHeaderCell>
                  <TableHeaderCell>Currency Name</TableHeaderCell>
                  <TableHeaderCell>
                    Exchange Rate{" "}
                    <Tooltip title="1 USD = X units of this currency">
                      <InfoCircleOutlined style={{ marginLeft: "4px" }} />
                    </Tooltip>
                  </TableHeaderCell>
                  <TableHeaderCell>Example</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {currencies.map((currency) => {
                  const currentRate = currency.code === "USD" ? 1.0 : exchangeRates[currency.code];
                  return (
                    <TableRow key={currency.code}>
                      <TableCell>
                        <Text className="font-semibold">{currency.code}</Text>
                      </TableCell>
                      <TableCell>
                        <Text>{currency.name}</Text>
                      </TableCell>
                      <TableCell>
                        {currency.code === "USD" ? (
                          <Text className="text-gray-500">1.0000 (Base Currency)</Text>
                        ) : editMode ? (
                          <Form.Item
                            name={currency.code}
                            initialValue={currentRate}
                            rules={[
                              {
                                required: true,
                                message: "Rate is required",
                              },
                              {
                                type: "number",
                                min: 0.0001,
                                message: "Rate must be greater than 0",
                              },
                            ]}
                            className="mb-0"
                          >
                            <InputNumber
                              step={0.0001}
                              precision={4}
                              style={{ width: "150px" }}
                              min={0.0001}
                            />
                          </Form.Item>
                        ) : (
                          <Text>{currentRate?.toFixed(4) || "N/A"}</Text>
                        )}
                      </TableCell>
                      <TableCell>
                        {currency.code !== "USD" && currentRate && (
                          <Text className="text-sm text-gray-500">
                            $100 USD = {(100 * currentRate).toFixed(2)} {currency.code}
                          </Text>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </Form>

          <div className="mt-6 p-4 bg-blue-50 rounded-lg">
            <Title className="text-sm">Important Notes:</Title>
            <ul className="mt-2 text-sm text-gray-700 list-disc list-inside space-y-1">
              <li>All exchange rates are relative to USD (base currency = 1.0)</li>
              <li>Changes take effect immediately for new transactions</li>
              <li>Existing budgets and spend tracking remain in their original currency</li>
              <li>The system automatically converts between currencies using these rates</li>
              <li>Update rates regularly to maintain accuracy</li>
            </ul>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default CurrencyManagementPage;
