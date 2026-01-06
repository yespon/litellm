import React, { useEffect, useState } from "react";
import { Select } from "antd";
import { getSupportedCurrencies, getExchangeRates } from "../networking";

const { Option } = Select;

interface Currency {
  code: string;
  name: string;
}

interface CurrencySelectorProps {
  value?: string | null;
  onChange?: (value: string) => void;
  className?: string;
  style?: React.CSSProperties;
  accessToken?: string | null;
  disabled?: boolean;
  placeholder?: string;
  showExchangeRateInfo?: boolean;
}

/**
 * CurrencySelector Component
 *
 * A reusable currency selection dropdown that fetches supported currencies from the API.
 * Defaults to USD if no value is provided.
 *
 * @param value - Current selected currency code (e.g., "USD", "CNY")
 * @param onChange - Callback when currency changes
 * @param accessToken - API access token for fetching currencies
 * @param disabled - Whether the selector is disabled
 * @param placeholder - Placeholder text
 * @param showExchangeRateInfo - Show exchange rate information in options
 */
const CurrencySelector: React.FC<CurrencySelectorProps> = ({
  value,
  onChange,
  className = "",
  style = {},
  accessToken,
  disabled = false,
  placeholder = "Select currency",
  showExchangeRateInfo = false,
}) => {
  const [currencies, setCurrencies] = useState<Currency[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [exchangeRates, setExchangeRates] = useState<Record<string, number>>({});

  useEffect(() => {
    // Load currencies when component mounts
    const fetchCurrencies = async () => {
      if (!accessToken) {
        // Use default currencies if no access token
        setDefaultCurrencies();
        return;
      }

      setLoading(true);
      try {
        const data = await getSupportedCurrencies(accessToken);
        setCurrencies(data.currencies || []);
      } catch (error) {
        console.warn("Failed to fetch currencies, using defaults:", error);
        setDefaultCurrencies();
      } finally {
        setLoading(false);
      }
    };

    // Load exchange rates if needed
    const fetchExchangeRates = async () => {
      if (!accessToken || !showExchangeRateInfo) {
        return;
      }

      try {
        const data = await getExchangeRates(accessToken);
        setExchangeRates(data.rates || {});
      } catch (error) {
        console.error("Error fetching exchange rates:", error);
      }
    };

    fetchCurrencies();
    fetchExchangeRates();
  }, [accessToken, showExchangeRateInfo]);

  const setDefaultCurrencies = () => {
    setCurrencies([
      { code: "USD", name: "US Dollar" },
      { code: "CNY", name: "Chinese Yuan" },
      { code: "EUR", name: "Euro" },
      { code: "GBP", name: "British Pound" },
      { code: "JPY", name: "Japanese Yen" },
      { code: "KRW", name: "South Korean Won" },
      { code: "INR", name: "Indian Rupee" },
      { code: "AUD", name: "Australian Dollar" },
      { code: "CAD", name: "Canadian Dollar" },
    ]);
  };

  const getExchangeRateInfo = (currencyCode: string): string => {
    if (!showExchangeRateInfo || currencyCode === "USD") {
      return "";
    }
    const rate = exchangeRates[currencyCode];
    if (rate) {
      return ` (1 USD = ${rate} ${currencyCode})`;
    }
    return "";
  };

  return (
    <Select
      style={{ width: "100%", ...style }}
      value={value || "USD"}
      onChange={onChange}
      className={className}
      placeholder={placeholder}
      disabled={disabled}
      loading={loading}
      showSearch
      optionFilterProp="children"
      filterOption={(input, option) =>
        (option?.children?.toString() || "").toLowerCase().includes(input.toLowerCase())
      }
    >
      {currencies.map((currency) => (
        <Option key={currency.code} value={currency.code}>
          {currency.code} - {currency.name}
          {getExchangeRateInfo(currency.code)}
        </Option>
      ))}
    </Select>
  );
};

/**
 * Get currency symbol for display
 */
export const getCurrencySymbol = (currencyCode: string | null | undefined): string => {
  if (!currencyCode) return "$";

  const symbolMap: Record<string, string> = {
    USD: "$",
    CNY: "¥",
    EUR: "€",
    GBP: "£",
    JPY: "¥",
    KRW: "₩",
    INR: "₹",
    AUD: "A$",
    CAD: "C$",
  };

  return symbolMap[currencyCode] || currencyCode;
};

/**
 * Format amount with currency
 */
export const formatCurrency = (
  amount: number | null | undefined,
  currencyCode: string | null | undefined
): string => {
  if (amount === null || amount === undefined) {
    return "N/A";
  }

  const symbol = getCurrencySymbol(currencyCode);
  const code = currencyCode || "USD";

  // Format with appropriate decimal places
  const decimals = ["JPY", "KRW"].includes(code) ? 0 : 2;
  const formatted = amount.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

  return `${symbol}${formatted} ${code}`;
};

/**
 * Get currency label for a given code
 */
export const getCurrencyLabel = (currencyCode: string | null | undefined): string => {
  if (!currencyCode) return "USD";
  return currencyCode;
};

export default CurrencySelector;
