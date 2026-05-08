# DATA_DICTIONARY — Shared Cost Allocation Engine
*Project 4 | CostCenter: Project4*

This document defines the synthetic dataset schema used in the allocation engine. All data is generated — no real customer, usage, or billing data is present.

---

## Tag Keys

These four tags are applied to every record in `api_usage_raw`. They drive all allocation views. NULL values are valid and intentional — see hygiene profiles per BU.

| Tag Key | Purpose | Valid Values |
|---|---|---|
| `business_unit` | Business unit that owns or consumes the API usage | `eng-team`, `data-science-team`, `marketing-team`, `cx-team`, `platform-team` |
| `product` | Product within the BU driving the usage | See Products by BU table below |
| `component` | Platform component being consumed | `inference`, `embedding`, `fine-tuning`, `evaluation`, `prompt-management`, `vector-store`, `data-pipeline`, `monitoring`, `gateway` |
| `feature` | Specific feature driving the API call | See Features by Component table below |

---

## Features by Component

| Component | Feature Values |
|---|---|
| `inference` | `content-gen`, `summarization`, `chat`, `code-gen`, `translation` |
| `embedding` | `semantic-search`, `document-retrieval`, `recommendation` |
| `fine-tuning` | `domain-adaptation`, `tone-calibration`, `task-specialization` |
| `evaluation` | `benchmark-testing`, `regression-testing`, `ab-testing` |
| `prompt-management` | `prompt-versioning`, `prompt-testing`, `template-library` |
| `vector-store` | `index-management`, `similarity-search`, `chunk-storage` |
| `data-pipeline` | `ingestion`, `preprocessing`, `enrichment` |
| `monitoring` | `drift-detection`, `cost-alerting`, `performance-tracking` |
| `gateway` | `rate-limiting`, `auth`, `routing` |

---

## Business Units

| BU ID | BU Name | Role | Primary Model Usage |
|---|---|---|---|
| `eng-team` | Engineering | Recipient | Mixed |
| `data-science-team` | Data Science | Recipient | Heavy Sonnet/Opus |
| `marketing-team` | Marketing | Recipient | Heavy Haiku |
| `cx-team` | Customer Support | Recipient | Heavy Haiku |
| `platform-team` | Platform | Source + Recipient + Absorber | Mixed |

---

## Products by BU

| BU | Product ID | Product Name |
|---|---|---|
| Customer Support | `cx-chat` | CX Chat |
| Customer Support | `speech-bot` | Speech Bot |
| Customer Support | `doc-processing` | Document Processing |
| Data Science | `ml-platform` | ML Platform |
| Data Science | `experiment-tracker` | Experiment Tracker |
| Data Science | `feature-store` | Feature Store |
| Marketing | `content-studio` | Content Studio |
| Marketing | `campaign-gen` | Campaign Generator |
| Marketing | `seo-optimizer` | SEO Optimizer |
| Engineering | `dev-assist` | Dev Assist |
| Engineering | `code-review-bot` | Code Review Bot |
| Engineering | `incident-analyzer` | Incident Analyzer |
| Platform | `model-gateway` | Model Gateway |
| Platform | `cost-observatory` | Cost Observatory |
| Platform | `prompt-registry` | Prompt Registry |

---

## Components

| Component ID | Description | Typical BU Owners |
|---|---|---|
| `inference` | Real-time API calls | All BUs |
| `embedding` | Vector generation | Data Science, Engineering, Platform |
| `fine-tuning` | Model customization runs | Data Science, Platform |
| `evaluation` | Model assessment before promotion | Data Science, Engineering, Platform |
| `prompt-management` | Prompt versioning, testing, storage | All BUs |
| `vector-store` | Hosting and querying embedding indexes | Data Science, Engineering |
| `data-pipeline` | Ingestion and preprocessing | Data Science, Platform |
| `monitoring` | Model performance tracking, drift detection | Platform, Engineering |
| `gateway` | API routing, rate limiting, auth | Platform |

**Note:** Component → BU ownership is modeled as a junction table with ownership weights. A component can be owned by multiple BUs with different weight splits. See `component_bu_mapping` table.

---

## Models

| Model Identifier | Tier | Typical Usage |
|---|---|---|
| `claude-haiku-4-5-20251001` | Low cost | High volume, simple tasks — CX, Marketing |
| `claude-sonnet-4-6` | Mid tier | Balanced — Engineering, mixed workloads |
| `claude-opus-4-6` | High cost | Complex reasoning — Data Science, fine-tuning |

---

## Cost Types (Attribution Types)

| Cost Type | Description | Allocation Method |
|---|---|---|
| `direct` | Single BU owner, clean tags | Direct attribution — no split required |
| `shared-inference` | Inference calls serving multiple BUs | Split by usage weights per pool |
| `shared-platform` | Platform overhead serving all BUs | Flat or headcount split |
| `unallocable` | No owner, no pool match | Platform absorbs 100% by policy |

**Note:** `cost_type` is a classification column applied by the platform, not a tag applied by teams.

---

## Environments

| Environment | Description | Cost Behavior |
|---|---|---|
| `dev` | Development and experimentation | Higher unallocable %, more sandbox usage |
| `si` | Systems integration / staging | Inherits dev allocation weights |
| `prod` | Production | Cleanest attribution, highest volume |

---

## Tag Hierarchy

```
client_id → business_unit → product → component → feature
```

Tags are applied as independent dimensions on each `api_usage_raw` record. Attribution conflicts between dimensions are intentional — the allocation engine resolves them. See `COST_ALLOCATION_POLICY.md` for full attribution rules.

---

## Allocation Weights — Cost Pools

| Pool ID | Pool Name | Allocation Method | Recipients |
|---|---|---|---|
| `P001` | shared-inference | Usage-based | All BUs proportional to token consumption |
| `P002` | platform-overhead | Flat split | All BUs equally |
| `P003` | embedding-pipeline | Headcount-weighted | Data Science (60%), CX (40%) |
| `P004` | unallocable | Platform absorb | 100% Platform — see `platform_unallocable_policy` table |

---

## Dataset Parameters

| Parameter | Value |
|---|---|
| Time range | 9 months |
| Total BUs | 5 (Engineering, Data Science, Marketing, Customer Support, Platform) |
| Total products | 15 |
| Total components | 9 |
| Models | 3 (Haiku, Sonnet, Opus) |
| Environments | 3 (dev, si, prod) |
| Cost types | 4 (direct, shared-inference, shared-platform, unallocable) |
| Unallocable % | ~20% of shared pool costs |
| Client IDs | Numeric format: `client_001` through `client_NNN` |

Resource identification:

resource_arn — AWS's unique ID for the resource. Example: arn:aws:rds:us-east-1:848747536965:db:shared-cost-eng-db. This is how you'd trace back to the actual AWS resource if needed.
service — the AWS service name. Example: rds, ecs, s3. Easier to filter than parsing the ARN.
region — which AWS region. We're using us-east-1 for everything per ADR-017.

Time dimension:

usage_start_time / usage_end_time — the period this cost covers. Example: midnight to 1 AM on May 7.
billing_period — the date this cost shows up on a bill. Daily granularity matches how AWS CUR works.

Usage metrics:

usage_quantity — the number. Example: 72 or 500 or 1024.
usage_unit — what that number measures. Example: instance_hours, storage_gb, data_transfer_gb.