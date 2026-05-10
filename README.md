# Shared Cost Allocation Engine

Chargeback/showback for a multi-team AI platform — because "shared infrastructure" is not a cost center.

---

> *"If you can't identify ownership, Platform pays for it out of their budget."*

---

## The Problem

Shared AI platform costs are invisible until you instrument them. When four business units consume LLM API calls through a central platform team, the bill lands in one place and the question — whose usage drove this? — has no answer. Most teams either split it evenly (wrong) or let Platform absorb it silently (also wrong, and unsustainable).

The deeper problem: not all shared costs can be attributed. Platform overhead, batch jobs that serve everyone, infrastructure that has no single owner — these costs exist, they compound, and most allocation engines paper over them entirely.

---

## The Solution

A SQL-based cost allocation engine that models three cost types — direct, shared, and unallocable — across token costs (Claude API usage) and infrastructure costs (RDS, ECS, S3, VPC, EC2). The engine allocates $79,108 in platform spend across five business units using different methods depending on cost type: usage-based splits for inference, flat splits for platform overhead, headcount-weighted splits for shared services. Unallocable costs surface explicitly in reporting and are absorbed by Platform by policy — not silently buried.

The engine extends to SaaS client billing without a rebuild. Swap `business_unit` for `client_id`, add `contract_tier` and `invoice_period`, and the same views produce client invoices. That's the point: this isn't a reporting tool, it's a billing primitive.

---

## The FinOps Angle

Rate limiting is not cost protection. Tagging is not cost allocation. Most AI platform teams know what they're spending — they don't know *who* drove it or *why*. This project builds the instrumentation layer that makes shared AI costs visible, attributable, and defensible. The same discipline that governs cloud infrastructure spend applies one layer up: tag your cost pools, define your allocation policy, make the unallocable explicit.

---

## Key Metrics

| Metric | Value |
|---|---|
| Synthetic dataset period | 9 months (Aug 2025 - Apr 2026) |
| Total platform cost | $79,108 (token $16,236 + infra $62,872) |
| Token usage records | 750,000 API calls |
| Infrastructure records | 20,601 usage records |
| Longitudinal resources | 60 resources (prod stable, dev churny) |
| Business units modeled | 5 BUs (eng, data-science, marketing, cx, platform) |
| Cost types | Direct · Shared-Platform · Shared-Inference · Unallocable |
| Allocation methods | Usage-based (P001) · Flat (P002) · Headcount (P003) · Platform-Absorb (P004) |
| Allocation pools | 4 pools |
| Direct cost attribution | $48,089 (60% of total platform spend) |
| SQL views | 7 (2 complete: v_usage_cost, v_direct_allocation) |
| Actual build cost | $0.65 (Phases 1-2.5) |
| Primary cost driver | RDS db.t3.micro uptime |

---

## Architecture

```
                   ┌─────────────────────────────────┐
                   │   Python Data Generators         │
                   │   (Faker + custom logic)         │
                   │   - generate_api_data.py         │
                   │   - generate_infra_data.py       │
                   └────────────┬────────────────────┘
                                │
             ┌──────────────────┼──────────────────────┐
             ▼                  ▼                       ▼
      api_usage_raw      infra_usage_raw         allocation_weights
      (token costs:      (infrastructure:        (pool_id /
       750k records,      RDS, ECS, S3,          method /
       direct/shared/     VPC, EC2:              weight_value
       unallocable)       20.6k records)         per BU)
             │                  │                       │
             └──────────────────┼───────────────────────┘
                                │
                   ┌────────────▼────────────┐
                   │        SQL Views         │
                   │  ✅ v_usage_cost         │ ← Combines token + infra
                   │  ✅ v_direct_allocation  │ ← 1:1 BU attribution
                   │  🚧 v_shared_allocation  │ ← Pool-based splits
                   │  ⬜ v_unallocable        │
                   │  ⬜ v_full_chargeback    │
                   │  ⬜ v_showback           │
                   │  ⬜ v_untagged_usage     │
                   └────────────┬────────────┘
                                │
                   ┌────────────▼────────────┐
                   │   Dashboard (Phase 4)    │
                   │   Looker Studio or HTML  │
                   └─────────────────────────┘

Infrastructure: RDS PostgreSQL 18.3 (db.t3.micro)
Query Tool: pgAdmin 4
```

---

## Business Unit Model

| BU | Role | Primary Model Usage | Token Cost | Infra Cost | Tag Hygiene |
|---|---|---|---|---|---|
| eng-team | Recipient | Mixed Haiku/Sonnet | Moderate | Heavy ECS/EC2 | 78% overall |
| data-science-team | Recipient | Heavy Sonnet/Opus | High | Heavy S3/RDS | 95% overall |
| marketing-team | Recipient | Heavy Haiku | Predictable | Heavy ECS/S3 | 65% overall |
| cx-team | Recipient | Heavy Haiku | High volume, low cost | Moderate RDS/ECS | 60% overall |
| platform-team | Source + Recipient + Absorber | Mixed | Complex | Shared infra | 65% overall |

**Platform's unique role:**
- **Source:** Runs shared infrastructure consumed by all BUs
- **Recipient:** Has its own products that consume token + infra
- **Absorber:** Absorbs 100% of unallocable costs by policy

Platform's chargeback report is intentionally the most complex in the dataset.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Data generation | Python 3.11 · Faker · python-dotenv |
| Database | PostgreSQL 18.3 (RDS db.t3.micro) |
| Allocation logic | SQL (views + CTEs) |
| Query tool | pgAdmin 4 |
| Visualization | Looker Studio or HTML dashboard (Phase 4) |
| Infrastructure | AWS RDS · IAM |
| Dev environment | Windows · VSCode · Git Bash · GitHub Desktop |
| Version control | GitHub (`theDovelyDev/shared-cost-allocation`) |

---

## Project Structure

```
shared-cost-allocation/
├── README.md
├── .gitignore
├── tagging-dictionary.md
├── Project4_Dev_Log.md
│
├── config/
│   ├── .env                       ← DB credentials (never committed)
│   └── setup.sh                   ← Environment variables + AWS profile
│
├── data/
│   ├── generate_api_data.py       ← Token usage synthetic dataset (750k records)
│   └── generate_infra_data.py     ← Infrastructure usage synthetic dataset (20.6k records)
│
├── sql/
│   ├── schema/
│   │   ├── create_tables.sql      ← DDL for all tables (api_usage_raw, infra_usage_raw, dimensions)
│   │   └── seed_reference.sql     ← Reference data (models, BUs, products, features, components)
│   ├── views/
│   │   ├── v_usage_cost.sql       ← ✅ Foundation view (combines token + infra)
│   │   ├── v_direct_allocation.sql← ✅ Direct costs (1:1 BU attribution)
│   │   ├── v_shared_allocation.sql← 🚧 Shared costs (pool-based splits)
│   │   ├── v_unallocable.sql      ← ⬜ Unallocable costs view
│   │   ├── v_full_chargeback.sql  ← ⬜ Final chargeback (direct + shared)
│   │   ├── v_showback.sql         ← ⬜ Showback (includes unallocable line)
│   │   └── v_untagged_usage.sql   ← ⬜ Tag hygiene analysis
│   └── validation/
│       └── reconciliation_checks.sql ← ⬜ Cost reconciliation queries
│
├── docs/
│   ├── DATA_DICTIONARY.md         ← Complete schema documentation (all tables, columns, types)
│   ├── ARCHITECTURE_DECISIONS.md  ← ADRs (18 decisions documented)
│   ├── METHODOLOGY.md             ← Allocation logic in plain language
│   └── Phase3_Case_Studies.md     ← SQL view case studies with business scenarios
│
├── dashboard/                     ← Phase 4 (Looker Studio config or HTML)
│
└── case_studies/
    ├── business_case_study.md     ← Learning material for portfolio users
    └── answer_key.md              ← Solutions to case study questions

```

---

## How the Allocation Engine Works

**Foundation Layer: Unified Cost Stream**

Both token costs (`api_usage_raw`) and infrastructure costs (`infra_usage_raw`) share the same tagging schema: `business_unit`, `feature`, `product`, `component`, `environment`, `cost_type`, `pool_id`. The `v_usage_cost` view combines them via UNION ALL into a single queryable cost stream — Finance doesn't care if a cost came from API tokens or EC2 instances, they need total platform spend.

**Direct Allocation: 1:1 Attribution**

Direct costs (`cost_type = 'direct'`) already have a `business_unit` tag. `v_direct_allocation` filters to direct costs and aggregates by month, BU, product, feature, and component. No math required — if Engineering's code-review-bot made 10,000 API calls, Engineering owes 100% of that cost. This represents 60% of total platform spend ($48,089 of $79,108).

**Shared Allocation: Pool-Based Splits**

Shared costs flow through allocation pools defined in `allocation_weights`:
- **P001 (usage-based):** Shared-inference costs split by actual token consumption across BUs
- **P002 (flat):** Platform overhead split equally across all BUs
- **P003 (headcount-weighted):** Shared services split by team size
- **P004 (platform-absorb):** Unallocable costs absorbed by Platform's budget

`v_shared_allocation` isn't a single formula — it's a JOIN to `allocation_weights` that applies the correct method per pool. One shared cost becomes multiple output rows (one per BU receiving allocation).

**Unallocable Costs: Explicit Surfacing**

Costs with insufficient tagging land in `cost_type = 'unallocable'` with `pool_id = 'P004'`. Platform absorbs these costs as a separate budget line. The delta between `v_full_chargeback` (absorbed costs hidden) and `v_showback` (unallocable as its own line) drives the conversation about tag hygiene investment.

**View Design Principles:**
- **Storage efficiency:** Views store query definitions, not data — no duplication overhead
- **Data freshness:** Always reflects current state of underlying tables; no sync lag
- **Abstraction layer:** Finance queries one unified cost stream without knowing implementation details

---

## Sample Output

```sql
-- v_usage_cost: Combined token + infra costs
SELECT cost_source, COUNT(*) AS records, SUM(total_cost) AS total
FROM allocation.v_usage_cost
GROUP BY cost_source;

cost_source | records  | total
------------|----------|------------
token       |  750,000 | $16,236.00
infra       |   20,601 | $62,872.00
TOTAL       |  770,601 | $79,108.00

-- v_direct_allocation: Direct costs by BU (aggregated)
SELECT business_unit, SUM(allocated_cost) AS total_direct
FROM allocation.v_direct_allocation
GROUP BY business_unit
ORDER BY total_direct DESC;

business_unit      | total_direct
-------------------|-------------
[actual data TBD]  |
```

---

## Infrastructure Guardrails

**RDS cost control:**
- Stop RDS instance when not actively querying (primary cost driver at $0.017/hour)
- Instance type: db.t3.micro — smallest available, sufficient for 770k records
- No Multi-AZ (dev environment, not needed)
- Automated backups: disabled (synthetic data, restorable from generator scripts)
- Storage: 20 GB gp2 (room for growth)

**Schema design:**
- `NUMERIC(10, 2)` for all cost columns — enforces 2 decimal precision for currency
- Indexes on `invoice_date` (monthly grouping), `launch_date` (resource age analysis)
- Foreign keys enforce referential integrity on dimension tables

**Tag audit:**
- All AWS resources tagged: `Project=shared-cost-allocation`, `CostCenter=Project4`
- Lambda tag audit scans weekly for missing `Component` or `CreatedDate`

**IAM least privilege:**
- `shared-cost-eng-dev` scoped to: RDS access · CloudWatch (RDS monitoring)
- No admin access, no cross-account permissions

---

## Setup

```bash
# 1. Clone
git clone https://github.com/theDovelyDev/shared-cost-allocation.git
cd shared-cost-allocation

# 2. Load environment
source config/setup.sh

# 3. Create virtual environment
python -m venv venv
source venv/Scripts/activate  # Windows Git Bash
# OR: source venv/bin/activate  # Linux/Mac

# 4. Install dependencies
pip install psycopg2-binary faker python-dotenv

# 5. Configure credentials
# Copy config/.env.example to config/.env
# Set: PGHOST, PGDATABASE, PGUSER, PGPASSWORD, AWS_PROFILE, AWS_DEFAULT_REGION
# Never commit .env

# 6. Create database schema
psql -h $PGHOST -U $PGUSER -d $PGDATABASE -f sql/schema/create_tables.sql

# 7. Seed reference data
psql -h $PGHOST -U $PGUSER -d $PGDATABASE -f sql/schema/seed_reference.sql

# 8. Generate synthetic usage data
python data/generate_api_data.py       # ~750k token records
python data/generate_infra_data.py     # ~20k infra records

# 9. Build allocation views
psql -h $PGHOST -U $PGUSER -d $PGDATABASE -f sql/views/v_usage_cost.sql
psql -h $PGHOST -U $PGUSER -d $PGDATABASE -f sql/views/v_direct_allocation.sql
# (continue with remaining views as they're built)

# 10. Validate
psql -h $PGHOST -U $PGUSER -d $PGDATABASE -f sql/validation/reconciliation_checks.sql
```

---

## Live Interface

**Coming in Phase 4:** Dashboard at theprojectfolder.com/shared-cost-allocation

---

## Cost Breakdown

| Phase | Description | Estimated | Actual | Notes |
|---|---|---|---|---|
| Phase 1 | RDS setup, IAM, tagging, scaffolding | $0.00 | $0.06 | 2 hours, minimal RDS uptime |
| Phase 2 | DDL, seed data, token dataset (750k) | $0.50 | $0.44 | 2.5 hours, Python local + RDS |
| Phase 2.5 | Infrastructure dataset (20.6k) | $0.20 | $0.15 | 2 hours, schema updates + data gen |
| Phase 3 | SQL allocation views (7 views) | $2.00 | TBD | 🚧 In progress (2/7 views complete) |
| Phase 4 | Dashboard (Looker or HTML) | $0.00 | TBD | Zero-cost visualization layer |
| Phase 5 | SaaS extension proof | $0.50 | TBD | Schema adaptation, no new infra |
| Phase 6 | Write + publish | $0.00 | TBD | Local writing, S3 hosting existing |
| **Total** | | **$3.20** | **$0.65** | Stop RDS between sessions to minimize cost |

---

## Status

| Phase | Description | Status |
|---|---|---|---|
| Phase 1 | Setup — RDS, IAM, schema, tagging | ✅ Complete |
| Phase 2 | Token dataset — 750k API call records | ✅ Complete |
| Phase 2.5 | Infrastructure dataset — 20.6k usage records | ✅ Complete |
| Phase 3 | Allocation views — 7 SQL views | 🚧 In Progress (2/7 complete) |
| Phase 4 | Dashboard — Looker Studio or HTML | ⬜ Not Started |
| Phase 5 | SaaS extension — client billing proof | ⬜ Not Started |
| Phase 6 | Write + publish — Substack + LinkedIn | ⬜ Not Started |

**Phase 3 Progress:**
- ✅ `v_usage_cost` — foundation view (combines token + infra)
- ✅ `v_direct_allocation` — direct cost attribution
- 🚧 `v_shared_allocation` — shared pool splits (Case Study 3 in progress)
- ⬜ `v_unallocable` — unallocable costs view
- ⬜ `v_full_chargeback` — final chargeback totals
- ⬜ `v_showback` — showback with unallocable line
- ⬜ `v_untagged_usage` — tag hygiene analysis

---

## Connect

**Portfolio:** [theprojectfolder.com](https://theprojectfolder.com?utm_source=github&utm_medium=profile&utm_campaign=portfolio)  
**Build log:** [Carlandra in the Cloud — Substack](https://carlandrainthecloud.substack.com?utm_source=github&utm_medium=profile&utm_campaign=portfolio)  
**Thought leadership:** [LinkedIn](https://linkedin.com/in/carlandra-williams?utm_source=github&utm_medium=profile&utm_campaign=portfolio)