-- 验证多货币迁移的 SQL 脚本
-- 运行此脚本来检查迁移是否成功

\echo '========================================='
\echo '多货币迁移验证脚本'
\echo '========================================='
\echo ''

-- 检查 1: 所有表的货币字段
\echo '检查 1: 验证所有表的货币字段...'
SELECT
    table_name,
    column_name,
    data_type,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND column_name LIKE '%currency%'
ORDER BY table_name, column_name;

\echo ''

-- 检查 2: 所有货币相关索引
\echo '检查 2: 验证所有货币索引...'
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND indexname LIKE '%currency%'
ORDER BY tablename, indexname;

\echo ''

-- 检查 3: 数据完整性（所有现有记录应该是 USD）
\echo '检查 3: 验证数据完整性...'
SELECT
    'LiteLLM_BudgetTable' as table_name,
    COUNT(*) as total_rows,
    COUNT(CASE WHEN budget_currency = 'USD' THEN 1 END) as usd_rows,
    COUNT(CASE WHEN budget_currency IS NULL THEN 1 END) as null_rows
FROM "LiteLLM_BudgetTable"
UNION ALL
SELECT
    'LiteLLM_TeamTable',
    COUNT(*),
    COUNT(CASE WHEN budget_currency = 'USD' AND spend_currency = 'USD' THEN 1 END),
    COUNT(CASE WHEN budget_currency IS NULL OR spend_currency IS NULL THEN 1 END)
FROM "LiteLLM_TeamTable"
UNION ALL
SELECT
    'LiteLLM_UserTable',
    COUNT(*),
    COUNT(CASE WHEN budget_currency = 'USD' AND spend_currency = 'USD' THEN 1 END),
    COUNT(CASE WHEN budget_currency IS NULL OR spend_currency IS NULL THEN 1 END)
FROM "LiteLLM_UserTable"
UNION ALL
SELECT
    'LiteLLM_VerificationToken',
    COUNT(*),
    COUNT(CASE WHEN budget_currency = 'USD' AND spend_currency = 'USD' THEN 1 END),
    COUNT(CASE WHEN budget_currency IS NULL OR spend_currency IS NULL THEN 1 END)
FROM "LiteLLM_VerificationToken"
UNION ALL
SELECT
    'LiteLLM_SpendLogs',
    COUNT(*),
    COUNT(CASE WHEN spend_currency = 'USD' THEN 1 END),
    COUNT(CASE WHEN spend_currency IS NULL THEN 1 END)
FROM "LiteLLM_SpendLogs"
UNION ALL
SELECT
    'LiteLLM_DailyUserSpend',
    COUNT(*),
    COUNT(CASE WHEN spend_currency = 'USD' THEN 1 END),
    COUNT(CASE WHEN spend_currency IS NULL THEN 1 END)
FROM "LiteLLM_DailyUserSpend";

\echo ''

-- 检查 4: 字段约束和默认值
\echo '检查 4: 验证字段约束...'
SELECT
    c.table_name,
    c.column_name,
    c.is_nullable,
    c.column_default
FROM information_schema.columns c
WHERE c.table_schema = 'public'
  AND c.column_name LIKE '%currency%'
  AND c.table_name LIKE 'LiteLLM_%'
ORDER BY c.table_name, c.column_name;

\echo ''

-- 检查 5: 索引大小和性能
\echo '检查 5: 索引统计信息...'
SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
  AND indexrelname LIKE '%currency%'
ORDER BY tablename, indexrelname;

\echo ''
\echo '========================================='
\echo '验证完成！'
\echo ''
\echo '预期结果:'
\echo '- 11 个表应该各有相应的货币字段'
\echo '- 17 个索引应该全部创建'
\echo '- 所有现有数据的货币应该是 USD'
\echo '- null_rows 应该全部为 0'
\echo '========================================='
