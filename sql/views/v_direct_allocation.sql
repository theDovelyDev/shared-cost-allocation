-- v_direct_allocation.sql
-- Shared Cost Allocation Engine | Project 4
-- 
-- Direct allocation view: Costs with 1:1 attribution to business units.
-- Aggregates direct costs by month, BU, product, feature, and component for chargeback.
--
-- Business purpose:
--   - Shows costs owned 100% by a single business unit
--   - No splitting or weighting required
--   - Defensible chargeback with drill-down capability
--
-- Allocation rule:
--   - cost_type = 'direct' → 100% attributed to tagged business_unit
--   - Always has business_unit tag (direct costs never NULL)
--   - No pool_id (direct costs don't go through allocation pools)
--
-- Granularity decision:
--   - Aggregated by: cost_source, invoice_date, business_unit, product, feature, component
--   - Finance needs monthly summary, but detail supports drill-down for disputes
--   - ~7,676 rows (vs 770k raw records)
--
-- Dependencies:
--   - allocation.v_usage_cost (foundation view)
--
-- Created: 2026-05-09
-- Last modified: 2026-05-09

CREATE OR REPLACE VIEW allocation.v_direct_allocation AS
SELECT 
    cost_source,
    invoice_date,
    business_unit,
    product,
    feature,
    component,
    SUM(total_cost) AS allocated_cost
FROM allocation.v_usage_cost 
WHERE cost_type = 'direct'
GROUP BY cost_source, invoice_date, business_unit, product, feature, component;

-- Validation queries:
--
-- Total direct costs per BU for a specific month:
-- SELECT business_unit, SUM(allocated_cost) AS total_direct
-- FROM allocation.v_direct_allocation
-- WHERE invoice_date = '2026-05-01'
-- GROUP BY business_unit;
--
-- Direct costs by product for Engineering (Q1 2026):
-- SELECT product, SUM(allocated_cost) AS total_cost
-- FROM allocation.v_direct_allocation
-- WHERE business_unit = 'eng-team'
--   AND invoice_date BETWEEN '2026-02-01' AND '2026-04-01'
-- GROUP BY product
-- ORDER BY total_cost DESC;
--
-- Token vs infra breakdown of direct costs:
-- SELECT cost_source, SUM(allocated_cost) AS total_cost
-- FROM allocation.v_direct_allocation
-- GROUP BY cost_source;
--
-- Record count and total:
-- SELECT COUNT(*) AS row_count, SUM(allocated_cost) AS total_allocated
-- FROM allocation.v_direct_allocation;