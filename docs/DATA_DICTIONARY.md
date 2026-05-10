# Data Dictionary — Shared Cost Allocation Engine
**Project 4 | CostCenter: Project4**

This data dictionary documents all tables, columns, data types, business definitions, and relationships in the shared cost allocation database.

**Database:** `shared_cost_db`  
**Schema:** `allocation`  
**DBMS:** PostgreSQL 18.3  
**Last updated:** 2026-05-08

---

## Table of Contents

1. [Fact Tables](#fact-tables)
2. [Dimension Tables](#dimension-tables)
3. [Reference Tables](#reference-tables)
4. [Tag Key Definitions](#tag-key-definitions)
5. [Business Term Glossary](#business-term-glossary)
6. [Table Relationships](#table-relationships)

---

## Fact Tables

### `api_usage_raw`
**Purpose:** Stores token-based API usage records for Claude LLM calls. One row per API call.

**Business definition:** Records every interaction with the Claude API, capturing token consumption, model used, and associated business context tags for cost allocation.

| Column Name | Data Type | Definition | Constraints | Notes |
|---|---|---|---|---|
| `usage_id` | UUID | Unique identifier for each API call | PRIMARY KEY, NOT NULL | Generated via uuid_generate_v4() |
| `timestamp` | TIMESTAMP | Date and time when the API call occurred | NOT NULL | Format: YYYY-MM-DD HH:MM:SS |
| `model` | VARCHAR(50) | Claude model used for the API call | NOT NULL | Values: haiku-3-5, sonnet-3-5, opus-3-5 |
| `input_tokens` | INTEGER | Number of tokens in the prompt/request | NOT NULL, CHECK (input_tokens >= 0) | Minimum value: 0 |
| `output_tokens` | INTEGER | Number of tokens in the model's response | NOT NULL, CHECK (output_tokens >= 0) | Minimum value: 0 |
| `cost_per_1k_tokens_input` | NUMERIC(10, 6) | Cost per 1,000 input tokens in USD | NOT NULL | Varies by model |
| `cost_per_1k_tokens_output` | NUMERIC(10, 6) | Cost per 1,000 output tokens in USD | NOT NULL | Varies by model |
| `total_cost` | NUMERIC(10, 2) | Total cost of this API call in USD | NOT NULL | Calculated: (input_tokens/1000 * cost_per_1k_input) + (output_tokens/1000 * cost_per_1k_output) |
| `business_unit` | VARCHAR(100) | Business unit that owns this usage | NULL allowed (hygiene) | FK to business_units.bu_id; NULL for shared/unallocable costs |
| `feature` | VARCHAR(100) | AI platform feature consuming the API | NULL allowed (hygiene) | FK to features.feature_id; describes functional capability |
| `product` | VARCHAR(100) | Product leveraging this feature | NULL allowed (hygiene) | FK to products.product_id; end-user facing product |
| `component` | VARCHAR(100) | AI platform component category | NOT NULL | FK to components.component_id; always tagged |
| `environment` | VARCHAR(20) | Deployment environment | NOT NULL | Values: dev, si, prod |
| `cost_type` | VARCHAR(50) | Cost attribution classification | NOT NULL | Values: direct, shared-inference, shared-platform, unallocable |
| `pool_id` | VARCHAR(10) | Allocation pool identifier | NULL allowed | NULL for direct costs; P001-P004 for shared/unallocable |
| `client_id` | VARCHAR(50) | External customer identifier (if applicable) | NULL allowed | Reserved for SaaS extension; currently unused |
| `invoice_date` | DATE | First day of the month following usage | NOT NULL, INDEX | Format: YYYY-MM-DD; used for monthly chargeback grouping |

**Primary Key:** `usage_id`  
**Foreign Keys:** 
- `model` → `models.model_id`
- `business_unit` → `business_units.bu_id`
- `feature` → `features.feature_id`
- `product` → `products.product_id`
- `component` → `components.component_id`

**Indexes:**
- `idx_api_usage_invoice_date` on `invoice_date`
- Implicit index on `usage_id` (PRIMARY KEY)

**Record count:** ~750,000 (9 months: Aug 2025 - Apr 2026)

---

### `infra_usage_raw`
**Purpose:** Stores infrastructure usage records for AWS services supporting the AI platform. One row per resource per usage unit per day.

**Business definition:** Records daily resource consumption for infrastructure services (RDS, ECS, S3, VPC, EC2), capturing usage metrics, costs, and business context tags for allocation alongside token costs.

| Column Name | Data Type | Definition | Constraints | Notes |
|---|---|---|---|---|
| `infra_usage_id` | UUID | Unique identifier for each infrastructure usage record | PRIMARY KEY, NOT NULL | Generated via uuid_generate_v4() |
| `usage_start_time` | TIMESTAMP | Start of the usage period | NOT NULL | Typically 00:00:00 of billing_period date |
| `usage_end_time` | TIMESTAMP | End of the usage period | NOT NULL | Typically 23:59:59 of billing_period date |
| `billing_period` | DATE | Date of usage for daily billing | NOT NULL | Format: YYYY-MM-DD |
| `resource_arn` | VARCHAR(255) | AWS ARN of the resource | NOT NULL | Format: arn:aws:service:region:account:resource-type/resource-id |
| `service` | VARCHAR(50) | AWS service name | NOT NULL | Values: rds, ecs, s3, vpc, ec2 |
| `region` | VARCHAR(50) | AWS region where resource is deployed | NOT NULL | Currently all resources in us-east-1 |
| `cost_type` | VARCHAR(50) | Cost attribution classification | NOT NULL | Values: direct, shared-platform, unallocable |
| `pool_id` | VARCHAR(10) | Allocation pool identifier | NULL allowed | NULL for direct costs; P002-P004 for shared/unallocable |
| `client_id` | VARCHAR(50) | External customer identifier (if applicable) | NULL allowed | Reserved for SaaS extension; currently 80% NULL for one-shots |
| `business_unit` | VARCHAR(100) | Business unit that owns this resource | NULL allowed (hygiene) | FK to business_units.bu_id; NULL for shared/unallocable |
| `product` | VARCHAR(100) | Product using this infrastructure | NULL allowed (hygiene) | FK to products.product_id |
| `component` | VARCHAR(100) | Infrastructure component type | NOT NULL | Values: database, container, storage, networking, compute |
| `feature` | VARCHAR(100) | AI platform feature supported by this infra | NULL allowed (hygiene) | FK to features.feature_id; mapped from component type |
| `environment` | VARCHAR(20) | Deployment environment | NOT NULL | Values: dev, si, prod |
| `usage_quantity` | NUMERIC(12, 4) | Amount of resource consumed | NOT NULL, CHECK (usage_quantity >= 0) | Units vary by usage_unit |
| `usage_unit` | VARCHAR(50) | Unit of measurement for usage | NOT NULL | Examples: instance_hours, storage_gb, vcpu_hours, requests |
| `total_cost` | NUMERIC(10, 2) | Total cost of this usage in USD | NOT NULL | Calculated: usage_quantity * unit_cost |
| `launch_date` | DATE | Date when the AWS resource was created | NOT NULL, INDEX | Format: YYYY-MM-DD; tracks resource age |
| `invoice_date` | DATE | First day of the month following usage | NOT NULL, INDEX | Format: YYYY-MM-DD; used for monthly chargeback grouping |

**Primary Key:** `infra_usage_id`  
**Foreign Keys:**
- `business_unit` → `business_units.bu_id`
- `product` → `products.product_id`
- `component` → `components.component_id`
- `feature` → `features.feature_id`

**Indexes:**
- `idx_infra_usage_invoice_date` on `invoice_date`
- `idx_infra_usage_launch_date` on `launch_date`
- Implicit index on `infra_usage_id` (PRIMARY KEY)

**Record count:** ~20,600 (60 longitudinal resources + 5 one-shots across 9 months)

---

## Dimension Tables

### `models`
**Purpose:** Reference data for Claude model types and their pricing.

| Column Name | Data Type | Definition | Constraints | Notes |
|---|---|---|---|---|
| `model_id` | VARCHAR(50) | Unique identifier for the model | PRIMARY KEY, NOT NULL | Values: haiku-3-5, sonnet-3-5, opus-3-5 |
| `model_name` | VARCHAR(100) | Display name of the model | NOT NULL | Full model name for reporting |
| `input_cost_per_1k` | NUMERIC(10, 6) | Cost per 1,000 input tokens in USD | NOT NULL | Current Anthropic pricing as of Jan 2025 |
| `output_cost_per_1k` | NUMERIC(10, 6) | Cost per 1,000 output tokens in USD | NOT NULL | Current Anthropic pricing as of Jan 2025 |
| `tier` | VARCHAR(20) | Model tier classification | NOT NULL | Values: standard, advanced |

**Primary Key:** `model_id`  
**Record count:** 3

---

### `business_units`
**Purpose:** Business unit dimension for cost allocation.

| Column Name | Data Type | Definition | Constraints | Notes |
|---|---|---|---|---|
| `bu_id` | VARCHAR(100) | Unique identifier for the business unit | PRIMARY KEY, NOT NULL | Values: eng-team, data-science-team, marketing-team, cx-team, platform-team |
| `bu_name` | VARCHAR(200) | Full display name of the business unit | NOT NULL | Human-readable name |
| `bu_description` | TEXT | Description of BU's function and scope | NULL allowed | Business context |

**Primary Key:** `bu_id`  
**Record count:** 5

---

### `products`
**Purpose:** Product dimension representing end-user facing applications.

| Column Name | Data Type | Definition | Constraints | Notes |
|---|---|---|---|---|
| `product_id` | VARCHAR(100) | Unique identifier for the product | PRIMARY KEY, NOT NULL | Examples: cx-chat, ml-platform, content-studio |
| `product_name` | VARCHAR(200) | Full display name of the product | NOT NULL | Human-readable name |
| `bu_id` | VARCHAR(100) | Business unit that owns this product | NOT NULL | FK to business_units.bu_id |
| `product_description` | TEXT | Description of product functionality | NULL allowed | Business context |

**Primary Key:** `product_id`  
**Foreign Keys:**
- `bu_id` → `business_units.bu_id`  
**Record count:** 15 (3 products per BU)

---

### `components`
**Purpose:** AI platform component taxonomy for architectural categorization.

| Column Name | Data Type | Definition | Constraints | Notes |
|---|---|---|---|---|
| `component_id` | VARCHAR(100) | Unique identifier for the component | PRIMARY KEY, NOT NULL | Examples: inference, embedding, fine-tuning, database, container |
| `component_name` | VARCHAR(200) | Full display name of the component | NOT NULL | Human-readable name |
| `component_category` | VARCHAR(50) | High-level category grouping | NOT NULL | Values: ai-platform, infrastructure |
| `component_description` | TEXT | Description of component function | NULL allowed | Technical context |

**Primary Key:** `component_id`  
**Record count:** 14 (9 AI platform + 5 infrastructure)

---

### `features`
**Purpose:** Feature dimension representing functional capabilities of the AI platform.

| Column Name | Data Type | Definition | Constraints | Notes |
|---|---|---|---|---|
| `feature_id` | VARCHAR(100) | Unique identifier for the feature | PRIMARY KEY, NOT NULL | Examples: content-gen, summarization, chat, semantic-search |
| `feature_name` | VARCHAR(200) | Full display name of the feature | NOT NULL | Human-readable name |
| `feature_description` | TEXT | Description of feature functionality | NULL allowed | Business context |

**Primary Key:** `feature_id`  
**Record count:** 29

---

## Reference Tables

### `component_bu_mapping`
**Purpose:** Maps components to business units that actively use them, enabling component-based allocation logic.

| Column Name | Data Type | Definition | Constraints | Notes |
|---|---|---|---|---|
| `component_id` | VARCHAR(100) | Component identifier | COMPOSITE PRIMARY KEY, NOT NULL | FK to components.component_id |
| `bu_id` | VARCHAR(100) | Business unit identifier | COMPOSITE PRIMARY KEY, NOT NULL | FK to business_units.bu_id |
| `usage_weight` | NUMERIC(5, 4) | Proportion of component usage by this BU | NOT NULL, CHECK (usage_weight >= 0 AND usage_weight <= 1) | Decimal 0.0000-1.0000; weights per component sum to 1.0 |

**Primary Key:** (`component_id`, `bu_id`)  
**Foreign Keys:**
- `component_id` → `components.component_id`
- `bu_id` → `business_units.bu_id`  
**Record count:** 24

---

### `allocation_weights`
**Purpose:** Defines allocation pool rules and per-BU weight distributions for shared cost splitting.

| Column Name | Data Type | Definition | Constraints | Notes |
|---|---|---|---|---|
| `pool_id` | VARCHAR(10) | Allocation pool identifier | COMPOSITE PRIMARY KEY, NOT NULL | Values: P001-P004 |
| `bu_id` | VARCHAR(100) | Business unit identifier | COMPOSITE PRIMARY KEY, NOT NULL | FK to business_units.bu_id |
| `allocation_method` | VARCHAR(50) | Method used to calculate weights | NOT NULL | Values: usage-based, flat, headcount-weighted, platform-absorb |
| `weight_value` | NUMERIC(5, 4) | Proportion of pool allocated to this BU | NOT NULL, CHECK (weight_value >= 0 AND weight_value <= 1) | Decimal 0.0000-1.0000; weights per pool sum to 1.0 (except P004) |

**Primary Key:** (`pool_id`, `bu_id`)  
**Foreign Keys:**
- `bu_id` → `business_units.bu_id`  
**Record count:** 14 (P001: 5 rows, P002: 4 rows, P003: 4 rows, P004: 1 row)

**Pool definitions:**
- **P001:** Usage-based allocation (token consumption drives split)
- **P002:** Flat allocation (equal split regardless of usage)
- **P003:** Headcount-weighted allocation (team size drives split)
- **P004:** Platform absorbs unallocable costs (no chargeback)

---

## Tag Key Definitions

### Real AWS Resource Tags
Applied to actual infrastructure deployed for this project.

| Tag Key | Definition | Valid Values | Required |
|---|---|---|---|
| `Project` | Identifies which portfolio project owns this resource | `shared-cost-allocation` | Yes |
| `CostCenter` | Maps to project number for cost tracking | `Project4` | Yes |
| `Environment` | Deployment environment tier | `dev`, `staging`, `prod` | Yes |
| `ManagedBy` | How this resource is provisioned and maintained | `manual`, `cloudformation`, `terraform` | Yes |
| `Component` | Infrastructure component type | `database`, `storage`, `compute`, `iam`, `networking` | Yes |
| `CreatedDate` | Date resource was created (YYYY-MM-DD) | ISO 8601 date | No (excluded from remediated resources) |

### Synthetic Dataset Tags
Used in `api_usage_raw` and `infra_usage_raw` for cost allocation modeling.

| Tag Key | Definition | Valid Values | Business Rule |
|---|---|---|---|
| `business_unit` | Identifies which BU owns or consumes this cost | `eng-team`, `data-science-team`, `marketing-team`, `cx-team`, `platform-team` | NULL allowed for shared/unallocable; always present for direct costs |
| `feature` | AI platform feature driving this usage | 29 valid feature values (see features table) | NULL allowed based on hygiene profile |
| `product` | End-user product consuming this resource | 15 valid product values (see products table) | NULL allowed based on hygiene profile; must align with BU when present |
| `component` | Platform or infrastructure component | 14 valid component values (see components table) | Always present (NOT NULL) |
| `environment` | Deployment environment | `dev`, `si`, `prod` | Always present (NOT NULL) |
| `cost_type` | Cost attribution classification | `direct`, `shared-inference`, `shared-platform`, `unallocable` | Always present (NOT NULL) |
| `client_id` | External customer identifier | `client_001` - `client_050` | NULL allowed; reserved for SaaS extension |

---

## Business Term Glossary

### Cost Attribution Types

**Direct Cost**  
Usage owned by a single business unit with clear 1:1 attribution. Example: Marketing's content-gen API calls for their blog automation product.

**Shared-Inference Cost**  
Infrastructure or platform costs shared across multiple BUs for inference workloads. Split using usage-based or headcount-weighted allocation. Example: Shared embedding service supporting search features across all products.

**Shared-Platform Cost**  
Foundational platform costs that benefit all BUs but cannot be directly tied to usage patterns. Split using flat or headcount-weighted allocation. Example: Central model gateway, prompt registry, monitoring infrastructure.

**Unallocable Cost**  
Costs with insufficient tagging to determine ownership. Not charged back to BUs; absorbed by Platform team. Example: Experimental dev workloads with no BU tag, orphaned resources from decommissioned projects.

### Allocation Methods

**Usage-Based (P001)**  
Shared costs split proportionally based on direct usage volume (token consumption, API calls, storage GB). Reflects actual consumption patterns.

**Flat (P002)**  
Shared costs split equally across all participating BUs. Used when usage tracking is infeasible or usage variance is minimal.

**Headcount-Weighted (P003)**  
Shared costs split based on relative team sizes. Proxy for organizational footprint when direct usage metrics unavailable.

**Platform-Absorb (P004)**  
Unallocable costs absorbed by Platform team's budget. No chargeback to consuming BUs.

### Resource Lifecycle Terms

**Launch Date**  
Date when an AWS infrastructure resource was first provisioned. Used to analyze resource age, identify long-running resources, and model realistic infrastructure patterns.

**Invoice Date**  
First day of the month following usage. All usage in April 2026 has `invoice_date = 2026-05-01`. Used to group costs into monthly billing cycles for chargeback.

**Longitudinal Resource**  
An infrastructure resource that persists over time and reports usage across multiple days. Opposite of a one-shot resource. Example: An RDS instance that runs continuously for 6 months.

**One-Shot Resource**  
A dev environment resource that exists for exactly one day then disappears. Typically experimental workloads or batch jobs. Biased 80% toward untagged/unallocable costs.

### Tag Hygiene

**Tag Hygiene Profile**  
The percentage of records where optional tags (`business_unit`, `feature`, `product`, `client_id`) are populated vs. NULL. Varies by BU to model real-world tagging discipline. Example: Data Science team has 95% hygiene; CX team has 60% hygiene.

**Hygiene Nulling**  
Intentional removal of tag values on shared/unallocable costs to simulate real-world tagging gaps. Direct costs always retain `business_unit` tag regardless of hygiene profile.

---

## Table Relationships

### Entity Relationship Diagram (Textual)

```
api_usage_raw
  ├─ model             → models.model_id
  ├─ business_unit     → business_units.bu_id (NULL allowed)
  ├─ feature           → features.feature_id (NULL allowed)
  ├─ product           → products.product_id (NULL allowed)
  └─ component         → components.component_id

infra_usage_raw
  ├─ business_unit     → business_units.bu_id (NULL allowed)
  ├─ feature           → features.feature_id (NULL allowed)
  ├─ product           → products.product_id (NULL allowed)
  └─ component         → components.component_id

products
  └─ bu_id             → business_units.bu_id

component_bu_mapping
  ├─ component_id      → components.component_id
  └─ bu_id             → business_units.bu_id

allocation_weights
  └─ bu_id             → business_units.bu_id
```

### Shared Dimensions

Both fact tables (`api_usage_raw` and `infra_usage_raw`) share the same tag dimension structure:
- `business_unit` (nullable for shared/unallocable)
- `feature` (nullable based on hygiene)
- `product` (nullable based on hygiene)
- `component` (always present)
- `environment` (always present)
- `cost_type` (always present)

This parallel structure enables views to combine token + infra costs using UNION ALL while maintaining consistent allocation logic.

---

## Data Quality Rules

### Referential Integrity

1. All non-NULL `business_unit` values must exist in `business_units.bu_id`
2. All non-NULL `product` values must exist in `products.product_id`
3. All non-NULL `feature` values must exist in `features.feature_id`
4. All `component` values must exist in `components.component_id`
5. All `model` values (api_usage_raw) must exist in `models.model_id`

### Business Logic Constraints

1. **Direct costs must have business_unit:** `cost_type = 'direct'` → `business_unit IS NOT NULL`
2. **Products must align with BU:** If `product IS NOT NULL` and `business_unit IS NOT NULL`, then `product.bu_id = business_unit`
3. **Pool assignment by cost type:**
   - `cost_type = 'direct'` → `pool_id IS NULL`
   - `cost_type IN ('shared-inference', 'shared-platform')` → `pool_id IN ('P001', 'P002', 'P003')`
   - `cost_type = 'unallocable'` → `pool_id = 'P004'`
4. **Allocation weights sum to 1.0 per pool:** For each `pool_id` (except P004), `SUM(weight_value) = 1.0000`
5. **Component BU weights sum to 1.0 per component:** For each `component_id`, `SUM(usage_weight) = 1.0000`
6. **Invoice date logic:** `invoice_date = DATE_TRUNC('month', billing_period or timestamp) + INTERVAL '1 month'`

### Data Volume Expectations

| Table | Expected Record Count | Growth Pattern |
|---|---|---|
| `api_usage_raw` | ~750,000 (9 months) | ~83k per month |
| `infra_usage_raw` | ~20,600 (9 months) | ~2.3k per month |
| `models` | 3 | Static reference data |
| `business_units` | 5 | Static reference data |
| `products` | 15 | Slow growth (1-2 per quarter) |
| `components` | 14 | Slow growth (1-2 per year) |
| `features` | 29 | Moderate growth (3-5 per quarter) |
| `component_bu_mapping` | 24 | Updates when components/BUs change |
| `allocation_weights` | 14 | Updates when policy changes |

---

## Change Log

| Date | Change | Updated By |
|---|---|---|
| 2026-05-05 | Initial data dictionary created | Carlandra Williams |
| 2026-05-07 | Added token usage tables and dimensions | Carlandra Williams |
| 2026-05-08 | Added infrastructure tables, invoice_date, launch_date columns | Carlandra Williams |