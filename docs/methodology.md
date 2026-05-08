# METHODOLOGY.md — Shared Cost Allocation Engine
*Project 4 | CostCenter: Project4*

This document defines the allocation policies governing how AI platform costs are attributed, split, and reported across business units. It is the plain-language companion to the SQL views. When the engine makes a decision, this document explains why.

---

## Cost Categories

Every record in `api_usage_raw` falls into one of four cost categories. The category determines which allocation policy applies.

| Cost Type | Definition | Policy |
|---|---|---|
| `direct` | Single BU owner, clean tags | Direct attribution — no split |
| `shared-inference` | Inference calls serving multiple BUs | Split by pool method (P001) |
| `shared-platform` | Platform overhead serving all BUs | Split by pool method (P002, P003) |
| `unallocable` | No owner, no pool match | Platform absorbs 100% (P004) |

`cost_type` is assigned by the platform at ingestion. It is not a tag applied by engineering teams.

---

## Direct Attribution Policy

Direct costs are attributed 1:1 to the owning BU using the `business_unit` tag on the usage record.

**Rules:**
- `business_unit` tag must be present and match a known BU ID
- No pool assignment required
- No weight calculation required
- Appears in `v_direct_allocation` and rolls into `v_full_chargeback`

**No pool ID is assigned to direct costs.** Direct attribution bypasses the `allocation_weights` table entirely. If a direct cost record has a NULL `business_unit` tag, it is reclassified as `unallocable` and routed to P004.

---

## Shared Cost Allocation Policy

Shared costs are grouped by `pool_id` and split using the method defined in `allocation_weights`. Different pools use different methods — the engine dispatches by pool, not by a single global formula.

### P001 — Shared Inference (Usage-Based)

**Method:** Split proportional to each BU's token consumption over the allocation period.

**Rationale:** BUs that consume more tokens drove more cost. Usage-based splits are defensible in engineering reviews and reflect actual platform load.

**Recipients:** All BUs.

### P002 — Platform Overhead (Flat Split)

**Method:** Equal split across all BUs regardless of usage.

**Rationale:** Platform overhead (infrastructure, tooling, maintenance) benefits all BUs equally. Usage-based splits for overhead create perverse incentives — low-usage BUs would appear to subsidize high-usage ones for costs they didn't drive.

**Recipients:** All BUs equally.

### P003 — Embedding Pipeline (Headcount-Weighted)

**Method:** Split by BU headcount weights.

**Rationale:** The embedding pipeline serves teams proportional to their size, not their token usage. Headcount weighting is a common enterprise proxy when usage data is unavailable or unreliable.

**Recipients:** Data Science (60%), Customer Support (40%).

---

## Unallocable Cost Policy

### P004 — Unallocable (Platform Absorbs)

**Definition:** Shared pool costs where no owner can be determined — missing tags, ambiguous attribution, or platform overhead with no BU mapping.

**Policy:** 100% of P004 costs are absorbed by the Platform BU as a separate budget line.

> *"If you can't identify ownership, Platform pays for it out of their budget."*

**Why Platform:**
Platform owns the shared infrastructure. Unallocable costs are a direct consequence of incomplete tagging or missing BU mappings — both of which are Platform's operational responsibility to resolve. Charging unallocable costs to Platform creates a financial incentive to improve tag coverage over time.

**Scope:** ~20% of shared pool costs. Direct costs are excluded — direct attribution failures are reclassified as unallocable at ingestion, not post-allocation.

**Auditability:** The absorption rule is defined in the `platform_unallocable_policy` table, not hardcoded in SQL. This makes the policy queryable, versionable, and auditable.

**Reporting:**
- `v_full_chargeback` — P004 appears as a Platform budget line alongside Platform's direct and allocated costs
- `v_showback` — P004 appears as its own line item so Finance can see the true unallocable pool before Platform absorption
- The delta between `v_showback` and `v_full_chargeback` is the unallocable amount — the number that drives tag hygiene investment conversations

---

## Attribution Conflict Resolution

Because tag dimensions are parallel (not hierarchical), attribution conflicts can occur — a `component` tag may point to one BU while a `feature` tag points to another on the same record.

**Resolution order:**
1. `business_unit` tag — highest priority, direct attribution if present
2. `component` → BU mapping via `component_bu_mapping` junction table
3. `feature` → BU mapping (lower priority, used when component is NULL)
4. If all dimensions are NULL → reclassify as `unallocable`, route to P004

Conflicts are surfaced in `v_untagged_usage` for review. They are not silently resolved.

---

## SaaS Extension

This policy extends to client billing without schema changes. Swap `business_unit` for `client_id` as the primary attribution dimension. Pool methods remain identical. P004 unallocable costs are absorbed by the platform vendor rather than an internal BU.

See `EXTENSION.md` for full implementation details.

---

## Policy Governance

| Policy | Owner | Table | Review Cadence |
|---|---|---|---|
| Direct attribution rule | Platform team | N/A — engine logic | On schema change |
| Pool split methods | Platform team | `allocation_weights` | Quarterly |
| Unallocable absorption | Platform team | `platform_unallocable_policy` | On policy change |
| Tag hygiene targets | All BUs | N/A — operational | Monthly |

---

## The Ingestion Layer

In this project, `cost_type` and `pool_id` are assigned by the data generator at record creation time. This simulates what a production ingestion layer would do — but collapses it into a single step for development purposes.

**What this project simulates:**

The generator applies classification logic at the point of data creation:
- Records are assigned a `cost_type` based on per-BU probability weights
- `pool_id` is derived deterministically from `cost_type` via `get_pool_id()`
- Unallocable records are routed to P004 automatically

This means the dataset arrives at the allocation engine already classified. The views can trust `cost_type` and `pool_id` as reliable inputs — they don't need to infer or derive them.

**Why this matters:**

Most shared cost allocation failures happen before the engine — not inside it. The classification step (deciding whether a cost is direct, shared, or unallocable) is the hardest problem. It requires:
- Tag completeness on the originating resource
- A classification ruleset that maps tag combinations to cost types
- A mechanism to assign pool membership for shared costs
- A fallback policy for unclassifiable records

This project makes the classification layer explicit by design. `cost_type` and `pool_id` are first-class columns, not derived fields. That's the architecture decision that makes the allocation views clean and maintainable.

---

## Tag Hygiene and Unattributable Costs

Tag hygiene directly determines allocation accuracy. A record with a NULL `business_unit` tag cannot be directly attributed — it becomes a candidate for the unallocable pool or falls through to `v_untagged_usage`.

**What happens to NULL tags by cost type:**

| cost_type | NULL business_unit | Outcome |
|---|---|---|
| `direct` | Not possible — generator enforces BU on direct costs | N/A |
| `shared-inference` | Allowed — BU attribution comes from pool split, not tag | Allocated via P001 weights |
| `shared-platform` | Allowed — same as above | Allocated via P002/P003 weights |
| `unallocable` | Expected — no owner by definition | Platform absorbs via P004 |

**NULL tags on other dimensions (`product`, `component`, `feature`):**

These don't block allocation but reduce attribution granularity. A record with NULL `component` can still be attributed to a BU — it just can't be broken down by component in reporting. These records surface in `v_untagged_usage` for hygiene tracking.

**Hygiene rates by BU** are defined in `DATA_DICTIONARY.md`. The distribution is deliberate — each BU has a characteristic hygiene signature that reflects realistic team behavior patterns.

---

## Infrastructure Costs

**Current scope:** This engine allocates AI token costs only. Infrastructure costs (compute, networking, storage) are out of scope for the current dataset.

**Why infra costs matter for shared cost allocation:**

A shared cost allocation model built on token costs alone is incomplete. A BU's token spend can be low while their infrastructure footprint is disproportionate — and vice versa. Without infra costs, the chargeback model understates the true platform cost and creates misleading BU cost profiles.

**Separate ingestion path required:**

Infrastructure costs originate from a different source system (AWS Cost and Usage Report, cloud billing APIs) and carry different dimensions than API token costs. They cannot be directly inserted into `api_usage_raw` without a schema extension or a parallel fact table.

A production implementation would require:
- A separate ingestion pipeline consuming CUR or billing API data
- A mapping layer translating cloud resource tags to allocation dimensions
- A unified cost view joining token costs and infra costs before allocation

**Current workaround:**

Infra costs are noted as a known gap. The allocation views are designed to accommodate infra costs when added — no view logic assumes token-only costs. The extension path is additive, not a rebuild.

---

## Known Limitations

| Limitation | Impact | Extension Path |
|---|---|---|
| Token costs only — no infra costs | Incomplete BU cost profiles | Separate ingestion pipeline + parallel fact table or schema extension |
| Static allocation weights | Weights don't adjust to actual usage in real time | Usage-based weight recalculation job (scheduled or event-driven) |
| No point-in-time allocation | Views always reflect current weights, not historical weights at time of cost | Add `effective_date` filtering to allocation weight joins |
| Synthetic data only | No real billing validation | Connect to live Anthropic API billing export |
| Single account | No cross-account allocation | Extend ingestion to consolidate multi-account CUR |
| No invoice period concept | Can't produce period-locked chargeback statements | Add `invoice_period` column + period-close mechanism |

---

## Extension Path — SaaS Client Billing

The allocation engine extends to client billing without a schema rebuild. The `client_id` column already exists on `api_usage_raw` — it was designed as a first-class dimension from the start.

**Column swap pattern:**

| Internal allocation | SaaS client billing |
|---|---|
| `business_unit` | `client_id` |
| BU budget impact | Client invoice line item |
| Internal chargeback | External invoice |
| Platform absorbs unallocable | Vendor absorbs unallocable |

**Phase 5 implementation:** A `client_billing` schema with views that use `client_id` as the primary attribution dimension. Pool methods remain identical. The allocation engine doesn't change — only the reporting layer changes.

See `EXTENSION.md` for full implementation details.