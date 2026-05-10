# Shared Cost Allocation Engine — Phase 3 Case Studies
**Project 4 | SQL Allocation Views**

These case studies guide you through building the 7 SQL views that implement the cost allocation logic. Each case study presents a business scenario, then asks you to design the SQL solution before writing code.

**Teaching approach:** Understand the business problem first, identify the tables and logic needed, then build the view. No tutorial follow-along — think through the design decisions yourself.

---

## Case Study 1: Foundation View (`v_usage_cost`)

**Business Context:**

You're the FinOps lead at a company running an AI platform. Your CFO just asked: *"What's our total platform spend — token costs AND infrastructure combined?"*

Right now, your cost data lives in two separate tables:
- `api_usage_raw` — 750k records of token costs (Claude API calls)
- `infra_usage_raw` — 20k records of infrastructure costs (RDS, ECS, S3, VPC, EC2)

Both tables have the same tagging schema (`business_unit`, `feature`, `product`, `component`, `environment`, `cost_type`) but completely different usage metrics:
- **Token costs:** `input_tokens`, `output_tokens`, `cost_per_1k_tokens`
- **Infra costs:** `usage_quantity`, `usage_unit` (instance-hours, GB-month, etc.)

Your allocation logic needs to work across BOTH cost streams. Finance doesn't care whether a cost came from tokens or infrastructure — they need to see:
- What did we spend in total?
- Which costs are direct (owned by a BU)?
- Which costs are shared (need to be split)?
- Which costs are unallocable (no tags)?

**Your task:** Design a view called `v_usage_cost` that combines token and infra costs into a single queryable cost stream.

---

### Questions to Answer Before Writing SQL

1. **What's the primary challenge** in combining these two tables? (Hint: think about the columns they have in common vs. the columns that differ)

2. **Which columns must appear in the final view** for downstream allocation logic to work? (Think about what Finance needs to GROUP BY and filter on)

3. **How should you handle the different usage metrics?** Token costs have `input_tokens` + `output_tokens`; infra has `usage_quantity` + `usage_unit`. Do you:
   - a) Create separate columns for each metric type?
   - b) Standardize to a generic `usage_metric` field?
   - c) Drop usage metrics entirely and just show `total_cost`?

4. **What SQL technique would you use** to combine two tables with different schemas? (UNION, JOIN, subquery, CTE, something else?)

---

### Design Checklist

Before you start writing the view, confirm your design includes:

- [ ] A way to distinguish token costs from infra costs in the result set
- [ ] All shared tag dimensions (business_unit, feature, product, component, environment)
- [ ] Cost type classification (direct, shared-platform, shared-inference, unallocable)
- [ ] Pool ID for allocation routing
- [ ] Invoice date for monthly chargeback grouping
- [ ] Total cost per record
- [ ] A decision on how to handle usage metrics (keep them, standardize them, or drop them)

---

### Business Requirements

The view must support these queries:

```sql
-- Total platform cost by month
SELECT invoice_date, SUM(total_cost)
FROM v_usage_cost
GROUP BY invoice_date;

-- Cost breakdown by source (token vs infra)
SELECT cost_source, SUM(total_cost)
FROM v_usage_cost
GROUP BY cost_source;

-- Direct costs by business unit
SELECT business_unit, SUM(total_cost)
FROM v_usage_cost
WHERE cost_type = 'direct'
GROUP BY business_unit;

-- Shared costs that need allocation
SELECT cost_type, pool_id, SUM(total_cost)
FROM v_usage_cost
WHERE cost_type IN ('shared-platform', 'shared-inference')
GROUP BY cost_type, pool_id;
```
**Next step:** Write down your approach to each question above. What tables will you query? How will you combine them? What columns will you select? Once you have your design, you're ready to write the SQL.

---

## Case Study 2: Direct Allocation (`v_direct_allocation`)

**Business Context:**
 
Your CFO just asked: *"Show me what each business unit actually owns — costs where there's zero ambiguity about attribution."*
 
Direct costs are the easiest to allocate because they already have a `business_unit` tag. There's no splitting, no weighting, no complex logic. If a cost is tagged `business_unit = 'eng-team'`, Engineering owns 100% of that cost.
 
You've already built `v_usage_cost`, which combines token and infra costs into one stream. Now you need to filter it down to just the direct costs and present them in a format Finance can use for chargeback.
 
**The allocation rule for direct costs:**
- `cost_type = 'direct'`
- `business_unit IS NOT NULL` (direct costs always have a BU tag)
- 100% of the cost goes to the tagged business unit
- No pool_id (direct costs don't go through allocation pools)
**Real-world example:**
- Engineering's code-review-bot makes 10,000 API calls using Sonnet
- Total cost: $145.00
- Tagged: `business_unit = 'eng-team'`, `product = 'code-review-bot'`, `feature = 'code-gen'`
- **Direct allocation result:** Engineering owes $145.00
---
 
### Questions to Answer Before Writing SQL
 
1. **What's your source table/view?** (Hint: you just built a view that has all costs in one place)
2. **What filtering logic do you need?** Think about:
   - Which `cost_type` value identifies direct costs?
   - Should you filter for `business_unit IS NOT NULL`? (Or is that redundant given the cost_type?)
3. **What should the output columns be?** Finance needs to see:
   - Which business unit owns the cost
   - When the cost occurred (for monthly chargeback)
   - How much they owe
   - (Optional) What product/feature/component drove the cost
4. **Do you need aggregation?** Should this view show:
   - Every individual usage record (770k rows), OR
   - Aggregated totals per BU per month (much fewer rows)?
5. **Should this view include cost_source (token vs infra)?** Or does Finance not care about the distinction for direct costs?
---
 
### Design Checklist
 
Before you start writing the view, confirm your design includes:
 
- [ ] Filters to only direct costs (`cost_type = 'direct'`)
- [ ] Business unit identification (which BU owns each cost)
- [ ] Time dimension (invoice_date for monthly grouping)
- [ ] Cost amount (total_cost)
- [ ] Optional context columns (product, feature, component, environment, cost_source)
- [ ] Decision on granularity (row-level detail vs aggregated)
---
 
### Business Requirements
 
The view must support these queries:
 
```sql
-- Total direct costs per BU for a specific month
SELECT business_unit, SUM(allocated_cost) AS total_direct
FROM v_direct_allocation
WHERE invoice_date = '2026-05-01'
GROUP BY business_unit;
 
-- Direct costs by product for Engineering
SELECT product, SUM(allocated_cost) AS total_cost
FROM v_direct_allocation
WHERE business_unit = 'eng-team'
  AND invoice_date BETWEEN '2026-02-01' AND '2026-04-01'
GROUP BY product;
 
-- Token vs infra breakdown of direct costs
SELECT cost_source, SUM(allocated_cost) AS total_cost
FROM v_direct_allocation
GROUP BY cost_source;
```

**Your task:** Design the view structure. What does the SELECT statement look like? What columns do you include? Do you aggregate or keep it at usage-record level?

---
## Case Study 3: Shared Allocation (`v_shared_allocation`)

**Business Context:**

Your CFO just asked: *"We have $20,000 in shared platform costs this month. How do we split that fairly across the business units?"*

Unlike direct costs (which have clear 1:1 attribution), shared costs need to be **allocated** using predefined rules. You have three types of shared costs:

1. **shared-inference** (`cost_type = 'shared-inference'`) — AI workloads that benefit multiple BUs
   - Example: Central embedding service used by search features across all products
   - Allocation pool: P001 (usage-based split)

2. **shared-platform** (`cost_type = 'shared-platform'`) — Foundational infrastructure
   - Example: Model gateway, prompt registry, shared monitoring
   - Allocation pools: P002 (flat split) or P003 (headcount-weighted split)

Each shared cost has a `pool_id` that determines HOW to split it. The `allocation_weights` table contains the split percentages per BU per pool.

**Example allocation scenario:**

Engineering runs a central embedding service that costs $5,000/month. It's tagged:
- `cost_type = 'shared-inference'`
- `pool_id = 'P001'`
- `feature = 'semantic-search'`
- `business_unit = NULL` (shared, no single owner)

The `allocation_weights` table says P001 splits are:
- eng-team: 35%
- data-science-team: 30%
- marketing-team: 20%
- cx-team: 15%

**Allocation result:**
- eng-team owes: $1,750 (35% of $5,000)
- data-science-team owes: $1,500 (30% of $5,000)
- marketing-team owes: $1,000 (20% of $5,000)
- cx-team owes: $750 (15% of $5,000)

**Your task:** Build a view that takes shared costs and splits them across BUs using the allocation_weights table.

---

### Questions to Answer Before Writing SQL

1. **What's your source table/view?** Where do shared costs live?

2. **How do you identify shared costs?** What's the filter logic? (Hint: there are TWO cost_type values that represent "shared")

3. **What table contains the split percentages?** You need to JOIN to another table to get the weight_value for each BU.

4. **What's the JOIN key?** How do you match shared costs to their allocation weights?
   - Shared costs have a `pool_id` (P001, P002, P003)
   - Allocation weights have `pool_id` + `bu_id` + `weight_value`
   - What column connects them?

5. **What's the allocated cost calculation?** If a shared cost is $5,000 and a BU's weight is 0.35 (35%), what's the allocated amount?

6. **One shared cost becomes multiple output rows.** If one embedding service cost ($5,000) splits across 4 BUs, how many rows should appear in the output?
   - 1 row (original cost) or 4 rows (one per BU)?

7. **What if a shared cost has no pool_id?** Should you filter those out, or handle them differently?

---

### Design Challenges

This view is more complex than the previous two because:

**Challenge 1: Data Explosion**  
One input row (shared cost) becomes multiple output rows (one per BU receiving allocation). A $5,000 shared cost split 4 ways creates 4 rows of allocated costs.

**Challenge 2: JOIN Logic**  
You need to join `v_usage_cost` (has the costs) to `allocation_weights` (has the percentages) on `pool_id`. But `allocation_weights` has multiple rows per pool_id (one per BU), so this is a **one-to-many join**.

**Challenge 3: Calculation**  
You need to multiply `total_cost * weight_value` for each BU. This happens in the SELECT, not the JOIN.

**Challenge 4: NULL Handling**  
Some shared costs might have `pool_id = NULL` (data quality issue). Should you:
- Filter them out (WHERE pool_id IS NOT NULL)?
- Include them but show NULL allocated amounts?
- Treat them as unallocable and exclude from this view?

---

### Design Checklist

Before you start writing the view, confirm your design includes:

- [ ] Source: `v_usage_cost` (foundation view with all costs)
- [ ] Filter: Only shared costs (`cost_type IN ('shared-inference', 'shared-platform')`)
- [ ] JOIN: `allocation_weights` table on `pool_id`
- [ ] Calculation: `total_cost * weight_value` = allocated amount per BU
- [ ] Output columns: invoice_date, pool_id, business_unit (from weights table), allocated_cost, plus context (product, feature, component, cost_source)
- [ ] NULL handling: Decision on how to handle shared costs without pool_id

---

### SQL Technique Hint: CTE Structure

This view is complex enough that you might want a **CTE (Common Table Expression)** to break it into steps:

```sql
WITH shared_costs AS (
    -- Step 1: Filter to just shared costs
    SELECT ...
    FROM v_usage_cost
    WHERE cost_type IN ('shared-inference', 'shared-platform')
)
SELECT 
    -- Step 2: Join to weights and calculate allocation
    ...
FROM shared_costs
JOIN allocation_weights ON ...
```

Or you could write it as one SELECT with a direct JOIN. Either approach works.

---

### Business Requirements

The view must support these queries:

```sql
-- Total shared costs allocated to each BU for a specific month
SELECT business_unit, SUM(allocated_cost) AS total_shared
FROM v_shared_allocation
WHERE invoice_date = '2026-03-01'
GROUP BY business_unit;

-- Breakdown by allocation pool (which pools drive the most cost?)
SELECT pool_id, SUM(allocated_cost) AS total_cost
FROM v_shared_allocation
GROUP BY pool_id;

-- Eng team's share of P001 (usage-based) costs
SELECT invoice_date, SUM(allocated_cost) AS p001_allocation
FROM v_shared_allocation
WHERE business_unit = 'eng-team'
  AND pool_id = 'P001'
GROUP BY invoice_date
ORDER BY invoice_date;

-- Token vs infra breakdown of shared allocations
SELECT cost_source, SUM(allocated_cost) AS total_cost
FROM v_shared_allocation
GROUP BY cost_source;
```

---

### Expected Output Structure

Your view should produce rows like this:

| cost_source | invoice_date | pool_id | business_unit | product | feature | component | allocated_cost |
|---|---|---|---|---|---|---|---|
| token | 2026-02-01 | P001 | eng-team | code-review-bot | semantic-search | embedding | $875.00 |
| token | 2026-02-01 | P001 | data-science-team | ml-platform | semantic-search | embedding | $750.00 |
| infra | 2026-02-01 | P002 | eng-team | NULL | NULL | database | $1,250.00 |
| infra | 2026-02-01 | P002 | marketing-team | NULL | NULL | database | $1,250.00 |

**Notice:**
- One shared cost becomes multiple rows (one per BU)
- `business_unit` comes from `allocation_weights`, not from the original cost (which was NULL or a platform team value)
- `allocated_cost` = original `total_cost` × `weight_value`

---

**Your task:** Design the query. What tables do you JOIN? What's the JOIN condition? How do you calculate `allocated_cost`? What columns do you include?

---

## Case Study 4: Unallocable Costs (`v_unallocable`)

*Coming soon...*

---

## Case Study 5: Full Chargeback (`v_full_chargeback`)

*Coming soon...*

---

## Case Study 6: Showback Report (`v_showback`)

*Coming soon...*

---

## Case Study 7: Untagged Usage Analysis (`v_untagged_usage`)

*Coming soon...*