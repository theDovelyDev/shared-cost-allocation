# Architecture Decision Record — Shared Cost Allocation Engine
*Project 4 | CostCenter: Project4*

Formal log of key design decisions made during the pre-build architecture session (2026-05-05). Each entry follows ADR format: Context → Decision → Rationale → Consequences.

---

## ADR-001: PostgreSQL over DuckDB

**Status:** Accepted

**Context:**
A local analytical database was needed for development. DuckDB is a lightweight, zero-cost option well-suited for analytical workloads. PostgreSQL requires more setup and has infrastructure cost implications.

**Decision:**
Use PostgreSQL (RDS db.t3.micro) over DuckDB.

**Rationale:**
Portfolio alignment with BI/Analytics project stack. PostgreSQL demonstrates deeper hands-on database skills and is more representative of enterprise environments. RDS also provides realistic infrastructure cost to document and manage.

**Consequences:**
- Primary cost driver for the project (~$4 estimated)
- Must stop RDS instance when not actively querying
- Hands-on RDS experience added to portfolio

---

## ADR-002: RDS from Day One vs. Local Docker

**Status:** Accepted

**Context:**
Local Docker was the original spec for zero-cost dev. RDS incurs cost but provides a more realistic environment.

**Decision:**
Run RDS from the start of the project.

**Rationale:**
Hands-on RDS practice is a portfolio goal, not just a means to an end. A realistic dev environment produces more honest cost documentation and demonstrates infrastructure discipline.

**Consequences:**
- Cost increases from $0 to ~$4 (most likely scenario)
- More realistic architecture to document and present
- Forces good cost hygiene habits (stop instance when idle)

---

## ADR-003: Both Token Costs and Infrastructure Costs in Scope

**Status:** Accepted

**Context:**
Initial scope considered token costs only (Anthropic API billing). Infrastructure costs (RDS, compute, networking) are a separate cost category.

**Decision:**
Include both token costs and infrastructure costs in the allocation engine.

**Rationale:**
A BU's token spend can be low while their infrastructure footprint is disproportionate. That gap is a real conversation in every AI platform team. Modeling both creates a more complete and defensible allocation story.

**Consequences:**
- Two cost streams require two allocation approaches
- Richer dataset — more realistic cost complexity
- More interesting dashboard with natural tension between cost types

---

## ADR-004: cost_type is a Classification Column, Not a Tag

**Status:** Accepted

**Context:**
Early design conflated cost type (direct, shared, unallocable) with resource tags applied by engineering teams.

**Decision:**
`cost_type` is a platform-derived classification column on `api_usage_raw`, not a tag.

**Rationale:**
Tags are what teams apply. `cost_type` is what the allocation engine assigns based on attribution rules. Conflating the two creates governance ambiguity — a tag implies team ownership, a classification column implies platform policy.

**Consequences:**
- Clean separation between tagging strategy and allocation logic
- `cost_type` documented as a platform concern in `METHODOLOGY.md`
- Tags remain team-applied; classifications remain engine-applied

---

## ADR-005: Four Attribution Types

**Status:** Accepted

**Context:**
Initial design had seven attribution types including `dev-sandbox` and `evaluation`. These were reconsidered during the design session.

**Decision:**
Four attribution types: `direct` · `shared-inference` · `shared-platform` · `unallocable`

**Rationale:**
- `dev-sandbox` belongs in the `environment` dimension, not cost type
- `fine-tuning` and `evaluation` belong in the `component` dimension
- Four clean types cover the full attribution spectrum without overlap

**Consequences:**
- Simpler allocation logic — fewer branching paths
- `environment` and `component` dimensions carry more semantic weight
- Cleaner SQL views

---

## ADR-006: Full Tag Hierarchy — Client → BU → Product → Component → Feature

**Status:** Accepted

**Context:**
Initial hierarchy was BU → Component → Feature. During the design session, two layers were identified as missing.

**Decision:**
Full hierarchy: `client_id` → `business_unit` → `product` → `component` → `feature`

**Rationale:**
- `product` was the missing layer — a BU running multiple products has wildly different cost profiles per product. Without it, component → BU is an unexplainable many-to-many.
- `client_id` represents external paying customers — internal charge codes already live in the BU layer. Adds Phase 5 SaaS billing extensibility without a schema rebuild.

**Consequences:**
- More complex data generator
- Richer attribution story — allocation conflicts exist at multiple levels
- Phase 5 SaaS extension becomes a natural add-on, not a retrofit

---

## ADR-007: Option 2 Tag Model — Parallel Dimensions

**Status:** Accepted

**Context:**
Two tag modeling options were evaluated:
- Option 1: Component is parent, features are children (hierarchical)
- Option 2: Component and feature are independent dimensions (parallel)

**Decision:**
Option 2 — parallel dimensions.

**Rationale:**
Attribution conflicts between dimensions (e.g., `inference` owned by Data Science at the component level, but `content-gen` owned by Marketing at the feature level) are real in production environments. Option 2 forces the allocation engine to resolve genuine conflicts rather than sanitize them away. That resolution logic is the interview talking point.

**Consequences:**
- More complex SQL views — `v_shared_allocation` dispatches by dimension, not just pool
- Richer dataset — conflicts surface naturally
- `v_untagged_usage` catches NULL tags; a separate concern catches valid values in wrong dimensions

---

## ADR-008: Component → BU Mapping as Junction Table with Ownership Weights

**Status:** Accepted

**Context:**
Components could be mapped exclusively to one BU (simple lookup) or shared across multiple BUs with weights (junction table).

**Decision:**
Junction table with ownership weights. The line between `component_bu_mapping` and `allocation_weights` is intentionally blurred.

**Rationale:**
This blurred line is the allocation problem the engine is solving. A component like `inference` owned 60% by Data Science and 40% by Engineering creates real attribution complexity. Keeping these concerns cleanly separated would produce a less realistic and less interesting dataset.

**Consequences:**
- `v_shared_allocation` must reconcile component ownership weights against pool allocation weights
- Edge cases where weights don't sum to 100% are intentional data quality issues to surface
- More complex but more defensible allocation logic

---

## ADR-009: Platform as a Full BU

**Status:** Accepted

**Context:**
Early design treated Platform as a separate entity outside the BU structure.

**Decision:**
Platform is a BU with three cost buckets: direct costs, allocated-in shared costs, and unallocable absorption.

**Platform cost buckets:**
- **Direct costs** — Platform's own API usage, clean tags
- **Allocated in** — Platform's share of shared pools it receives as a recipient
- **Unallocable absorption** — 100% of P004 unallocable pool, charged to Platform budget by policy

**Platform BU behavior in the dataset:**
- Generates shared cost pools (P001, P002, P003) consumed by other BUs
- Also appears as a recipient in those same pools for its own tooling
- Absorbs P004 unallocable as a separate budget line — not silently buried
- Most complex chargeback report in the dataset by design
- Tag hygiene: 65% overall — worst of all BUs, reflects real platform team behavior

**Rationale:**
Treating Platform as a separate entity created artificial clean separation that doesn't exist in real environments. Platform teams consume AI infrastructure while also running it. Making them a full BU with the most complex chargeback report produces the most interesting data story.

**Consequences:**
- Platform's chargeback report is the most complex in the dataset — intentional
- Unallocable absorption is a Platform budget line, not a system artifact
- `platform_unallocable_policy` table makes the absorption rule queryable and auditable

---

## ADR-010: Unallocable Spend = 20% of Shared Pool Costs Only

**Status:** Accepted

**Context:**
Unallocable spend percentage needed to be defined. Options included applying it to total spend or shared pool costs only.

**Decision:**
~20% of shared pool costs only. Direct costs are 100% attributable.

**Rationale:**
In a controlled dev environment, direct costs have clean tags by design. Applying unallocable percentage to direct costs would model tag hygiene failures on owned resources — a separate problem from shared cost attribution. Scoping to shared pools keeps the unallocable story clean and focused.

**Consequences:**
- Direct cost allocation is straightforward
- Shared pool allocation carries the complexity
- 20% unallocable is realistic for enterprise shared infrastructure

---

## ADR-011: Deliberate + Randomized Tag Hygiene Profiles

**Status:** Accepted

**Context:**
Tag hygiene distribution could be uniform random across all BUs or deliberately patterned per BU.

**Decision:**
Combine both — deliberate hygiene profiles per BU with randomization within those profiles.

**Hygiene rates by BU:**

| BU | Overall Rate | Pattern |
|---|---|---|
| Data Science | 95% | Best hygiene, all dimensions consistent |
| Engineering | 78% | Component/model clean, client_id/feature messy |
| Marketing | 65% | Feature 88%, other dimensions drag it down |
| Platform | 65% | Worst overall — rushing infrastructure |
| Customer Support | ~60% | client_id 97%, everything else inconsistent |

**Tag hygiene distribution patterns:**

| Pattern | Example |
|---|---|
| All tags set | `client_001 → eng-team → dev-assist → inference → content-gen` |
| Feature NULL | `client_002 → marketing-team → content-studio → inference → NULL` |
| Component + Feature NULL | `client_003 → data-science-team → ml-platform → NULL → NULL` |
| Only BU set | `NULL → cx-team → NULL → NULL → NULL` |
| Fully untagged | `NULL → NULL → NULL → NULL → NULL` |

NULL values apply to shared pool costs only (~20%). Direct costs are fully tagged by design.

**Rationale:**
Pure randomization is realistic but produces no story. Pure deliberate patterns are unrealistic. Combining both gives each BU a characteristic hygiene signature (Data Science is disciplined; Platform is chaotic) while maintaining statistical plausibility within each profile.

**Consequences:**
- `v_untagged_usage` tells a richer story — hygiene gaps are attributable to specific BUs
- Data generator requires per-BU hygiene parameters, not a single global rate
- Interview question "why does Platform have the worst hygiene?" has a real answer

---

## ADR-012: client_id = External Paying Customer

**Status:** Accepted

**Context:**
`client_id` could represent internal charge codes or external paying customers.

**Decision:**
External paying customer, numeric format (`client_001`, `client_002`, etc.).

**Rationale:**
Internal charge codes already live in the BU layer. Using `client_id` for external customers creates a natural reason why Platform runs shared infrastructure (serving multiple clients simultaneously) and makes Phase 5 SaaS billing a direct extension of the existing data model rather than a schema change.

**Consequences:**
- Phase 5 SaaS billing uses the same `client_id` column — no migration required
- Allocation engine can report cost by client without schema changes
- `client_id` is the highest-level dimension in the hierarchy

---

## ADR-013: Separate Table for Infrastructure Costs
 
**Status:** Accepted
 
**Context:**
Infrastructure costs (RDS, ECS/Fargate, S3, VPC/Networking, EC2) needed to be added to the dataset. Two options were evaluated: adding infra costs to `api_usage_raw` with nullable token columns, or a separate `infra_usage_raw` table.
 
**Decision:**
Separate table — `infra_usage_raw`.
 
**Rationale:**
Token costs and infrastructure costs have fundamentally different schemas. Token costs are per API call with input/output token counts. Infrastructure costs are per resource per billing period with service-specific usage metrics. Combining them in one table would produce structural NULLs across every row — either token columns NULL for infra records or infra columns NULL for token records. Separate tables reflect the real-world separation between AI API billing and cloud infrastructure billing.
 
**Consequences:**
- Allocation views that combine both cost streams require a UNION or a unified cost view
- `allocation.products` reference table serves both fact tables — no duplication
- Schema is extensible — additional cost streams (e.g., third-party SaaS) can follow the same pattern
---
 
## ADR-014: No Direct FK Between infra_usage_raw and api_usage_raw
 
**Status:** Accepted
 
**Context:**
Initial design proposed using `usage_id` from `api_usage_raw` as a FK in `infra_usage_raw` to link token costs to infrastructure costs.
 
**Decision:**
No direct FK between the two fact tables. Join through shared tag dimensions instead.
 
**Rationale:**
Token costs are per API call. Infrastructure costs are per resource per billing period (hourly/daily). The relationship is many-to-many at different granularities — one RDS instance hour supports thousands of API calls. A FK would imply a 1:1 relationship that doesn't exist in cloud billing. This is the same pattern as AWS CUR — resources share a tag key space, they don't point to each other via FK.
 
**Consequences:**
- Allocation views join `api_usage_raw` and `infra_usage_raw` through shared dimensions (`business_unit`, `product`, `component`, `client_id`, `environment`)
- No referential integrity between fact tables — tag consistency is enforced by the generator, not the database
- Matches real-world cloud billing architecture
---
 
## ADR-015: Generic Usage Metrics (usage_quantity + usage_unit)
 
**Status:** Accepted
 
**Context:**
Infrastructure costs have different usage dimensions per service:
- RDS → instance_hours, storage_gb
- ECS/Fargate → vcpu_hours, memory_gb_hours
- S3 → storage_gb, requests, data_transfer_gb
- VPC → data_transfer_gb
- EC2 → instance_hours
Two options: service-specific columns (more NULLs, cleaner queries) or generic columns (flexible, consistent schema).
 
**Decision:**
Generic columns — `usage_quantity` (NUMERIC) and `usage_unit` (VARCHAR).
 
**Rationale:**
For a demo dataset, generic columns avoid structural NULLs across service-specific columns while still capturing the usage story. Example: `72, 'instance_hours'` or `500, 'storage_gb'`. Queryable by filtering on `usage_unit`. Matches the pattern used in AWS CUR `lineItem/UsageAmount` + `lineItem/UsageType`.
 
**Consequences:**
- Schema stays clean — no NULLs for unused service columns
- Filtering by usage type requires a WHERE on `usage_unit` rather than a dedicated column
- Extension to service-specific columns is additive if needed
---
 
## ADR-016: Infra Components Added to Existing Components Table
 
**Status:** Accepted
 
**Context:**
Infrastructure resources need component classification. Options were a separate infra component table or adding infra components to the existing `allocation.components` table.
 
**Decision:**
Add infra components to `allocation.components` as new rows.
 
**Rationale:**
Component is a shared tag dimension across both fact tables. Keeping one components reference table means both `api_usage_raw` and `infra_usage_raw` FK to the same table — consistent taxonomy, no duplication. The `components` table already has a general `description` field that accommodates both AI platform and infrastructure component types.
 
**New infra component values:**
- `storage` → S3 buckets
- `database` → RDS instances
- `networking` → VPC, data transfer, NAT Gateway
- `container` → ECS/Fargate tasks
- `compute` → EC2 instances
**Consequences:**
- `components` table contains both AI platform components and infrastructure components
- Allocation views can filter by component type if needed
- Tag taxonomy is unified across token and infra cost streams
---
 
## ADR-017: All Infrastructure Modeled in us-east-1
 
**Status:** Accepted
 
**Context:**
AWS pricing varies by region. Modeling infrastructure across multiple regions adds complexity without meaningful analytical benefit for this dataset.
 
**Decision:**
All infrastructure costs modeled in `us-east-1`. Region is captured as a column on `infra_usage_raw` but all synthetic records use `us-east-1`.
 
**Rationale:**
Simplifies cost calculation — one pricing table per service, no regional multipliers. `us-east-1` is the most common default region and the region where the real RDS instance runs. Region is still a queryable dimension for future extension.
 
**Consequences:**
- `region` column present on `infra_usage_raw` — data model is extensible to multi-region
- All synthetic pricing uses `us-east-1` rates
- Noted as a known limitation in `METHODOLOGY.md`
---
 
## ADR-018: All BUs Generate Infrastructure Costs
 
**Status:** Accepted
 
**Context:**
Initial design had Platform as the primary infra cost owner. Question was whether individual BUs should generate their own infra costs.
 
**Decision:**
All BUs generate infrastructure costs. Platform owns shared infrastructure and absorbs unallocable infra costs by the same P004 policy as token costs.
 
**Rationale:**
BUs run their own products on the platform — those products consume infrastructure. Customer Support's `cx-chat` product consumes ECS/Fargate. Data Science's `ml-platform` consumes RDS and S3. Limiting infra costs to Platform only would understate BU cost profiles and defeat the purpose of the allocation engine.
 
**ECS/Fargate and VPC shared resources:** Multi-tenant deployments where one resource serves multiple BUs use `cost_type = shared-platform` and route through existing pool allocation (P002 flat split or P003 headcount-weighted). Same allocation logic as shared token costs.
 
**Consequences:**
- `infra_usage_raw` has the same cost_type distribution as `api_usage_raw`
- Shared ECS/Fargate and VPC records use P002/P003 pool splits
- Platform absorbs unallocable infra costs via P004 — same policy, both cost streams