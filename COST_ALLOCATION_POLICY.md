# COST_ALLOCATION_POLICY — Shared Cost Allocation Engine
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