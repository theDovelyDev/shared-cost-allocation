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

A SQL-based cost allocation engine that models three cost types — direct, shared, and unallocable — across five business units plus a Platform team that operates as both cost source and cost recipient. Shared pools use different allocation methods depending on the nature of the cost: usage-based splits for inference, flat splits for platform overhead, headcount-weighted splits for embedding pipelines. Unallocable costs surface explicitly in reporting and are absorbed by Platform by policy — not silently buried.

The engine extends to SaaS client billing without a rebuild. Swap `business_unit` for `client_id`, add `contract_tier` and `invoice_period`, and the same views produce client invoices. That's the point: this isn't a reporting tool, it's a billing primitive.

---

## The FinOps Angle

Rate limiting is not cost protection. Tagging is not cost allocation. Most AI platform teams know what they're spending — they don't know *who* drove it or *why*. This project builds the instrumentation layer that makes shared AI costs visible, attributable, and defensible. The same discipline that governs cloud infrastructure spend applies one layer up: tag your cost pools, define your allocation policy, make the unallocable explicit. Nobody has a blank check for tokens, and "shared platform" is not an acceptable answer when the CFO asks whose budget this hits.

---

## Key Metrics

| Metric | Value |
|---|---|
| Synthetic dataset size | 6 months of API usage data |
| Business units modeled | 5 BUs + Platform (source + recipient) |
| Cost types | Direct · Shared · Unallocable |
| Allocation methods | Usage-based · Flat · Headcount |
| Shared cost pools | 3 (inference · platform overhead · embedding pipeline) |
| Unallocable spend | ~20% of shared pool costs → absorbed by Platform |
| SQL views | 7 |
| Estimated build cost | $4.16 (most likely) · $12.47 (ceiling) |
| Primary cost driver | RDS db.t3.micro uptime |

---

## Architecture

```
                   ┌─────────────────────────┐
                   │   Python Data Generator  │
                   │   (Faker + custom logic) │
                   └────────────┬────────────┘
                                │
             ┌──────────────────┼──────────────────┐
             ▼                  ▼                   ▼
      api_usage_raw        model_pricing     allocation_weights
      (direct /            (haiku /          (pool_id /
       shared /             sonnet /          method /
       unallocable)         opus pricing)     weight_value)
                                │
                   ┌────────────┼────────────┐
                   ▼            ▼            ▼
         platform_unallocable_policy    (policy table —
                   makes absorption rule queryable + auditable)
                                │
                   ┌────────────▼────────────┐
                   │        SQL Views         │
                   │  v_usage_cost            │
                   │  v_direct_allocation     │
                   │  v_shared_allocation     │
                   │  v_unallocable           │
                   │  v_full_chargeback       │
                   │  v_showback              │
                   │  v_untagged_usage        │
                   └────────────┬────────────┘
                                │
                   ┌────────────▼────────────┐
                   │   Dashboard (Phase 4)    │
                   │   Looker Studio or HTML  │
                   └─────────────────────────┘

Infrastructure: RDS PostgreSQL (db.t3.micro)
Account: AWS Sandbox (848747536965)
IAM User: shared-cost-eng-dev (least privilege)
```

---

## Business Unit Model

| BU | Role | Primary Model Usage | Cost Behavior |
|---|---|---|---|
| Marketing | Recipient | Heavy Haiku | Predictable, feature-driven |
| Engineering | Recipient | Mixed | Moderate, spiky |
| Data Science | Recipient | Heavy Sonnet/Opus | High cost, high value |
| Customer Support | Recipient | Heavy Haiku | High volume, low cost per call |
| Platform | Source + Recipient + Absorber | Mixed | Most complex chargeback report |
| Unallocated | Policy sink | N/A | ~20% of shared pool costs; charged to Platform by policy |

Platform is both the origin of shared cost pools (they run the infrastructure everyone consumes) and a recipient of shared costs for their own tooling. They also absorb 100% of unallocable spend as a separate budget line. Platform's chargeback report is intentionally the most complex in the dataset.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Data generation | Python 3.11 · Faker |
| Database | PostgreSQL (RDS db.t3.micro) |
| Allocation logic | SQL (views + CTEs) |
| Visualization | Looker Studio or HTML dashboard (decided post-Phase 3) |
| Infrastructure | AWS RDS · S3 · Lambda · IAM |
| Dev environment | Windows · VSCode · Git Bash |
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
│   ├── setup.sh                  ← Environment variables + AWS profile
│   ├── fix-tags.sh               ← Bulk tag remediation
│   └── verify-tag-audit.sh       ← Lambda audit verification
│
├── data/
│   └── generate_usage_data.py    ← Synthetic dataset generator
│
├── sql/
│   ├── schema/
│   │   ├── create_tables.sql     ← api_usage_raw, model_pricing, allocation_weights
│   │   └── platform_policy.sql  ← platform_unallocable_policy table
│   ├── views/
│   │   ├── v_usage_cost.sql
│   │   ├── v_direct_allocation.sql
│   │   ├── v_shared_allocation.sql
│   │   ├── v_unallocable.sql
│   │   ├── v_full_chargeback.sql
│   │   ├── v_showback.sql
│   │   └── v_untagged_usage.sql
│   └── validation/
│       └── reconciliation_checks.sql
│
├── docs/
│   ├── METHODOLOGY.md            ← Allocation logic in plain language
│   └── EXTENSION.md             ← SaaS client billing adaptation
│
└── dashboard/                    ← Phase 4 (Looker Studio config or HTML)
```

---

## How the Allocation Engine Works

Every API call in `api_usage_raw` carries a `cost_type` field: `direct`, `shared`, or `unallocable`. Direct costs are attributed to a single BU using the `owner` tag — no math required. Shared costs flow through the allocation engine.

Shared costs are grouped by `pool_id` in `api_usage_raw`. Each pool has its own allocation method defined in `allocation_weights`: the inference pool splits by actual token usage across recipient BUs, the platform overhead pool uses a flat equal split, and the embedding pipeline splits by headcount weights. This means `v_shared_allocation` isn't a single formula — it's a dispatching layer that applies the right method per pool and joins the results. Unallocable costs (roughly 20% of shared pool spend) have no owner row in `allocation_weights`. The `platform_unallocable_policy` table makes the absorption rule explicit and queryable: Platform absorbs these costs as a separate budget line, not a rounding error.

`v_full_chargeback` is the final allocations view — direct attribution plus shared pool splits, with Platform carrying the unallocable line. `v_showback` shows the same data plus the unallocable pool as its own line item, so Finance can see the true platform cost including the black hole. The delta between the two is the number that drives the conversation about tag hygiene investment.

---

## Sample Output

```
-- v_full_chargeback (sample rows)
business_unit    | direct_cost | allocated_shared | unallocable_absorbed | total_chargeback
-----------------|-------------|------------------|----------------------|------------------
Marketing        |      $412.30|           $189.44|                $0.00 |           $601.74
Engineering      |      $634.80|           $218.63|                $0.00 |           $853.43
Data Science     |    $1,847.20|           $312.91|                $0.00 |         $2,160.11
Customer Support |      $298.60|           $143.77|                $0.00 |           $442.37
Platform         |      $521.40|           $267.15|               $384.20|         $1,172.75

-- v_showback vs v_full_chargeback delta
total_direct_cost     | total_shared_allocated | total_unallocable | platform_absorption
----------------------|------------------------|-------------------|--------------------
           $3,714.30  |              $1,131.90 |            $384.20|              $384.20
```

---

## Infrastructure Guardrails

**RDS cost control:**
- Stop RDS instance when not actively querying (primary cost driver)
- Instance type: db.t3.micro — smallest available, sufficient for 6 months of synthetic data
- No Multi-AZ (dev environment, not needed)
- Automated backups: disabled (synthetic data, restorable from generator script)

**Tag audit:**
- Lambda tag audit updated with `Project=shared-cost-allocation`, `CostCenter=Project4` filters
- Weekly scan flags any resource missing `Component` or `CreatedDate`

**IAM least privilege:**
- `shared-cost-eng-dev` scoped to: RDS access · S3 (CSV exports) · CloudWatch (RDS monitoring)
- No admin access, no cross-account permissions

---

## Setup

```bash
# 1. Clone
git clone https://github.com/theDovelyDev/shared-cost-allocation.git
cd shared-cost-allocation

# 2. Load environment
source config/setup.sh

# 3. Install dependencies
pip install psycopg2-binary faker python-dotenv

# 4. Configure credentials
# Copy .env.example to .env and set PGPASSWORD + AWS credentials
# Never commit .env

# 5. Create database schema
psql -h $PGHOST -U $PGUSER -d $PGDATABASE -f sql/schema/create_tables.sql
psql -h $PGHOST -U $PGUSER -d $PGDATABASE -f sql/schema/platform_policy.sql

# 6. Generate synthetic data
python data/generate_usage_data.py

# 7. Build views
psql -h $PGHOST -U $PGUSER -d $PGDATABASE -f sql/views/v_usage_cost.sql
# (repeat for remaining views — see sql/views/)

# 8. Validate
psql -h $PGHOST -U $PGUSER -d $PGDATABASE -f sql/validation/reconciliation_checks.sql
```

---

## Cost Breakdown

| Phase | Description | Estimated | Actual |
|---|---|---|---|
| Phase 1 | Setup + RDS spin-up | $0.00 | TBD |
| Phase 2 | Data generation (local Python) | $0.00 | TBD |
| Phase 3 | Allocation logic (RDS active) | $4.01 | TBD |
| Phase 4 | Dashboard | $0.00 | TBD |
| Phase 5 | SaaS extension (RDS active) | $0.00–$4.00 | TBD |
| Phase 6 | Write + publish | $0.15 | TBD |
| **Total** | | **$4.16 (most likely)** | **TBD** |

Three-point estimate: Floor $0.00 · Most Likely $4.16 · Ceiling $12.47. Primary cost driver is RDS uptime. Stop the instance when not querying.

---

## Status

| Phase | Description | Status |
|---|---|---|
| Phase 1 | Setup — repo, config, RDS, schema | 🚧 In Progress |
| Phase 2 | Data generation — 6 months synthetic data | ⬜ Not Started |
| Phase 3 | Allocation logic — 7 SQL views | ⬜ Not Started |
| Phase 4 | Dashboard — Looker Studio or HTML | ⬜ Not Started |
| Phase 5 | SaaS extension — working client billing proof | ⬜ Not Started |
| Phase 6 | Write + publish — Substack + LinkedIn | ⬜ Not Started |

---

## Connect

**Portfolio:** [theprojectfolder.com](https://theprojectfolder.com?utm_source=github&utm_medium=profile&utm_campaign=portfolio)
**Build log:** [Carlandra in the Cloud — Substack](https://carlandrainthecloud.substack.com?utm_source=github&utm_medium=profile&utm_campaign=portfolio)
**Thought leadership:** [LinkedIn](https://linkedin.com/in/carlandra-williams?utm_source=github&utm_medium=profile&utm_campaign=portfolio)