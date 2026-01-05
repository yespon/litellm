-- Migration: Add Multi-Currency Support to LiteLLM
-- Date: 2026-01-04
-- Description: Adds currency fields to all relevant models for multi-currency billing support

-- =====================================================
-- Part 1: Budget Tables
-- =====================================================

-- Add currency field to LiteLLM_BudgetTable
ALTER TABLE "LiteLLM_BudgetTable"
ADD COLUMN IF NOT EXISTS "budget_currency" TEXT NOT NULL DEFAULT 'USD';

-- Add index for budget_currency
CREATE INDEX IF NOT EXISTS "LiteLLM_BudgetTable_budget_currency_idx"
ON "LiteLLM_BudgetTable"("budget_currency");

-- =====================================================
-- Part 2: Team Table
-- =====================================================

-- Add currency fields to LiteLLM_TeamTable
ALTER TABLE "LiteLLM_TeamTable"
ADD COLUMN IF NOT EXISTS "budget_currency" TEXT NOT NULL DEFAULT 'USD',
ADD COLUMN IF NOT EXISTS "spend_currency" TEXT NOT NULL DEFAULT 'USD';

-- Add indexes for team currency fields
CREATE INDEX IF NOT EXISTS "LiteLLM_TeamTable_budget_currency_idx"
ON "LiteLLM_TeamTable"("budget_currency");

CREATE INDEX IF NOT EXISTS "LiteLLM_TeamTable_spend_currency_idx"
ON "LiteLLM_TeamTable"("spend_currency");

-- =====================================================
-- Part 3: User Table
-- =====================================================

-- Add currency fields to LiteLLM_UserTable
ALTER TABLE "LiteLLM_UserTable"
ADD COLUMN IF NOT EXISTS "budget_currency" TEXT NOT NULL DEFAULT 'USD',
ADD COLUMN IF NOT EXISTS "spend_currency" TEXT NOT NULL DEFAULT 'USD';

-- Add indexes for user currency fields
CREATE INDEX IF NOT EXISTS "LiteLLM_UserTable_budget_currency_idx"
ON "LiteLLM_UserTable"("budget_currency");

CREATE INDEX IF NOT EXISTS "LiteLLM_UserTable_spend_currency_idx"
ON "LiteLLM_UserTable"("spend_currency");

-- =====================================================
-- Part 4: Verification Token (API Keys)
-- =====================================================

-- Add currency fields to LiteLLM_VerificationToken
ALTER TABLE "LiteLLM_VerificationToken"
ADD COLUMN IF NOT EXISTS "budget_currency" TEXT NOT NULL DEFAULT 'USD',
ADD COLUMN IF NOT EXISTS "spend_currency" TEXT NOT NULL DEFAULT 'USD';

-- Add indexes for token currency fields
CREATE INDEX IF NOT EXISTS "LiteLLM_VerificationToken_budget_currency_idx"
ON "LiteLLM_VerificationToken"("budget_currency");

CREATE INDEX IF NOT EXISTS "LiteLLM_VerificationToken_spend_currency_idx"
ON "LiteLLM_VerificationToken"("spend_currency");

-- =====================================================
-- Part 5: Spend Logs (Audit Trail)
-- =====================================================

-- Add currency fields to LiteLLM_SpendLogs for detailed tracking
ALTER TABLE "LiteLLM_SpendLogs"
ADD COLUMN IF NOT EXISTS "spend_currency" TEXT NOT NULL DEFAULT 'USD',
ADD COLUMN IF NOT EXISTS "model_currency" TEXT,
ADD COLUMN IF NOT EXISTS "spend_original" DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS "exchange_rate" DOUBLE PRECISION;

-- Add index for spend logs currency
CREATE INDEX IF NOT EXISTS "LiteLLM_SpendLogs_spend_currency_idx"
ON "LiteLLM_SpendLogs"("spend_currency");

-- =====================================================
-- Part 6: Daily Spend Tracking Tables
-- =====================================================

-- Add spend_currency to LiteLLM_DailyUserSpend
ALTER TABLE "LiteLLM_DailyUserSpend"
ADD COLUMN IF NOT EXISTS "spend_currency" TEXT NOT NULL DEFAULT 'USD';

CREATE INDEX IF NOT EXISTS "LiteLLM_DailyUserSpend_spend_currency_idx"
ON "LiteLLM_DailyUserSpend"("spend_currency");

-- Add spend_currency to LiteLLM_DailyOrganizationSpend
ALTER TABLE "LiteLLM_DailyOrganizationSpend"
ADD COLUMN IF NOT EXISTS "spend_currency" TEXT NOT NULL DEFAULT 'USD';

CREATE INDEX IF NOT EXISTS "LiteLLM_DailyOrganizationSpend_spend_currency_idx"
ON "LiteLLM_DailyOrganizationSpend"("spend_currency");

-- Add spend_currency to LiteLLM_DailyEndUserSpend
ALTER TABLE "LiteLLM_DailyEndUserSpend"
ADD COLUMN IF NOT EXISTS "spend_currency" TEXT NOT NULL DEFAULT 'USD';

CREATE INDEX IF NOT EXISTS "LiteLLM_DailyEndUserSpend_spend_currency_idx"
ON "LiteLLM_DailyEndUserSpend"("spend_currency");

-- Add spend_currency to LiteLLM_DailyAgentSpend
ALTER TABLE "LiteLLM_DailyAgentSpend"
ADD COLUMN IF NOT EXISTS "spend_currency" TEXT NOT NULL DEFAULT 'USD';

CREATE INDEX IF NOT EXISTS "LiteLLM_DailyAgentSpend_spend_currency_idx"
ON "LiteLLM_DailyAgentSpend"("spend_currency");

-- Add spend_currency to LiteLLM_DailyTeamSpend
ALTER TABLE "LiteLLM_DailyTeamSpend"
ADD COLUMN IF NOT EXISTS "spend_currency" TEXT NOT NULL DEFAULT 'USD';

CREATE INDEX IF NOT EXISTS "LiteLLM_DailyTeamSpend_spend_currency_idx"
ON "LiteLLM_DailyTeamSpend"("spend_currency");

-- Add spend_currency to LiteLLM_DailyTagSpend
ALTER TABLE "LiteLLM_DailyTagSpend"
ADD COLUMN IF NOT EXISTS "spend_currency" TEXT NOT NULL DEFAULT 'USD';

CREATE INDEX IF NOT EXISTS "LiteLLM_DailyTagSpend_spend_currency_idx"
ON "LiteLLM_DailyTagSpend"("spend_currency");

-- =====================================================
-- Part 7: Comments and Documentation
-- =====================================================

COMMENT ON COLUMN "LiteLLM_BudgetTable"."budget_currency" IS 'Currency code for budget amounts (e.g., USD, CNY, EUR)';

COMMENT ON COLUMN "LiteLLM_TeamTable"."budget_currency" IS 'Currency code for budget amounts';
COMMENT ON COLUMN "LiteLLM_TeamTable"."spend_currency" IS 'Currency code for spend tracking';

COMMENT ON COLUMN "LiteLLM_UserTable"."budget_currency" IS 'Currency code for budget amounts';
COMMENT ON COLUMN "LiteLLM_UserTable"."spend_currency" IS 'Currency code for spend tracking';

COMMENT ON COLUMN "LiteLLM_VerificationToken"."budget_currency" IS 'Currency code for budget amounts';
COMMENT ON COLUMN "LiteLLM_VerificationToken"."spend_currency" IS 'Currency code for spend tracking';

COMMENT ON COLUMN "LiteLLM_SpendLogs"."spend_currency" IS 'Currency code for recorded spend';
COMMENT ON COLUMN "LiteLLM_SpendLogs"."model_currency" IS 'Original currency from model provider';
COMMENT ON COLUMN "LiteLLM_SpendLogs"."spend_original" IS 'Original spend amount before currency conversion';
COMMENT ON COLUMN "LiteLLM_SpendLogs"."exchange_rate" IS 'Exchange rate used for currency conversion';

-- =====================================================
-- Migration Complete
-- =====================================================
-- Total changes:
-- - 1 budget table modified
-- - 3 core tables (Team, User, Token) modified
-- - 1 spend logs table modified (with audit fields)
-- - 6 daily spend tracking tables modified
-- - Total: 11 tables, 23 new fields, 17 new indexes
-- =====================================================
