-- v_usage_cost.sql
-- Shared Cost Allocation Engine | Project 4
-- 
-- Foundation view: Combines token and infrastructure costs into a single queryable cost stream.
-- This view is the base for all downstream allocation views.
--
-- Business purpose:
--   - Unified cost visibility (token + infra in one place)
--   - Enables cross-cost-type analysis and allocation
--   - Abstracts two fact tables behind one interface
--
-- Design decisions:
--   - UNION ALL (not UNION) to preserve all rows without deduplication overhead
--   - cost_source column distinguishes token vs infra
--   - Usage metrics (tokens, quantity, units) excluded — Finance only needs total_cost
--   - invoice_date for monthly chargeback grouping
--
-- Dependencies:
--   - allocation.api_usage_raw (token costs)
--   - allocation.infra_usage_raw (infrastructure costs)
--
-- Created: 2026-05-09
-- Last modified: 2026-05-09

CREATE OR REPLACE VIEW allocation.v_usage_cost AS
SELECT 
    'token' AS cost_source,
    usage_id,
    business_unit,
    product,
    component,
    feature,
    cost_type,
    pool_id,
    environment,
    invoice_date,
    total_cost
FROM allocation.api_usage_raw

UNION ALL

SELECT 
    'infra' AS cost_source,
    infra_usage_id AS usage_id,
    business_unit,
    product,
    component,
    feature,
    cost_type,
    pool_id,
    environment,
    invoice_date,
    total_cost
FROM allocation.infra_usage_raw;

-- Validation queries:
--
-- Total platform cost by month:
-- SELECT invoice_date, SUM(total_cost) AS total_cost
-- FROM allocation.v_usage_cost
-- GROUP BY invoice_date
-- ORDER BY invoice_date;
--
-- Cost breakdown by source (token vs infra):
-- SELECT cost_source, SUM(total_cost) AS total_cost
-- FROM allocation.v_usage_cost
-- GROUP BY cost_source;
--
-- Record count check (should be ~770k rows):
-- SELECT COUNT(*) FROM allocation.v_usage_cost;