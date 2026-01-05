-- Rollback Migration: Remove Multi-Currency Support from LiteLLM
-- Date: 2026-01-04
-- Description: Rollback script to remove currency fields if needed

-- WARNING: This will remove all currency-related columns
-- Make sure to backup your data before running this rollback!

-- =====================================================
-- Part 1: Drop indexes first
-- =====================================================

DROP INDEX IF EXISTS "LiteLLM_BudgetTable_budget_currency_idx";

DROP INDEX IF EXISTS "LiteLLM_TeamTable_budget_currency_idx";
DROP INDEX IF EXISTS "LiteLLM_TeamTable_spend_currency_idx";

DROP INDEX IF EXISTS "LiteLLM_UserTable_budget_currency_idx";
DROP INDEX IF EXISTS "LiteLLM_UserTable_spend_currency_idx";

DROP INDEX IF EXISTS "LiteLLM_VerificationToken_budget_currency_idx";
DROP INDEX IF EXISTS "LiteLLM_VerificationToken_spend_currency_idx";

DROP INDEX IF EXISTS "LiteLLM_SpendLogs_spend_currency_idx";

DROP INDEX IF EXISTS "LiteLLM_DailyUserSpend_spend_currency_idx";
DROP INDEX IF EXISTS "LiteLLM_DailyOrganizationSpend_spend_currency_idx";
DROP INDEX IF EXISTS "LiteLLM_DailyEndUserSpend_spend_currency_idx";
DROP INDEX IF EXISTS "LiteLLM_DailyAgentSpend_spend_currency_idx";
DROP INDEX IF EXISTS "LiteLLM_DailyTeamSpend_spend_currency_idx";
DROP INDEX IF EXISTS "LiteLLM_DailyTagSpend_spend_currency_idx";

-- =====================================================
-- Part 2: Drop columns
-- =====================================================

-- Remove currency from LiteLLM_BudgetTable
ALTER TABLE "LiteLLM_BudgetTable"
DROP COLUMN IF EXISTS "budget_currency";

-- Remove currency from LiteLLM_TeamTable
ALTER TABLE "LiteLLM_TeamTable"
DROP COLUMN IF EXISTS "budget_currency",
DROP COLUMN IF EXISTS "spend_currency";

-- Remove currency from LiteLLM_UserTable
ALTER TABLE "LiteLLM_UserTable"
DROP COLUMN IF EXISTS "budget_currency",
DROP COLUMN IF EXISTS "spend_currency";

-- Remove currency from LiteLLM_VerificationToken
ALTER TABLE "LiteLLM_VerificationToken"
DROP COLUMN IF EXISTS "budget_currency",
DROP COLUMN IF EXISTS "spend_currency";

-- Remove currency from LiteLLM_SpendLogs
ALTER TABLE "LiteLLM_SpendLogs"
DROP COLUMN IF EXISTS "spend_currency",
DROP COLUMN IF EXISTS "model_currency",
DROP COLUMN IF EXISTS "spend_original",
DROP COLUMN IF EXISTS "exchange_rate";

-- Remove currency from daily spend tables
ALTER TABLE "LiteLLM_DailyUserSpend"
DROP COLUMN IF EXISTS "spend_currency";

ALTER TABLE "LiteLLM_DailyOrganizationSpend"
DROP COLUMN IF EXISTS "spend_currency";

ALTER TABLE "LiteLLM_DailyEndUserSpend"
DROP COLUMN IF EXISTS "spend_currency";

ALTER TABLE "LiteLLM_DailyAgentSpend"
DROP COLUMN IF EXISTS "spend_currency";

ALTER TABLE "LiteLLM_DailyTeamSpend"
DROP COLUMN IF EXISTS "spend_currency";

ALTER TABLE "LiteLLM_DailyTagSpend"
DROP COLUMN IF EXISTS "spend_currency";

-- =====================================================
-- Rollback Complete
-- =====================================================
