-- =============================================================
-- Shared Cost Allocation Engine — DDL
-- Project 4 | CostCenter: Project4
-- Database: shared_cost_db
-- PostgreSQL 18.3
-- =============================================================

-- =============================================================
-- SCHEMA
-- =============================================================

CREATE SCHEMA IF NOT EXISTS allocation;
CREATE SCHEMA IF NOT EXISTS client_billing;  -- Phase 5 SaaS extension (empty for now)

SET search_path TO allocation;

-- =============================================================
-- REFERENCE TABLES
-- =============================================================

-- -----------------------------------------------------------------
-- model_pricing
-- Source of truth for per-token pricing by model
-- -----------------------------------------------------------------
CREATE TABLE allocation.model_pricing (
    model_id            VARCHAR(60)     PRIMARY KEY,
    model_display_name  VARCHAR(100)    NOT NULL,
    tier                VARCHAR(20)     NOT NULL CHECK (tier IN ('low', 'mid', 'high')),
    input_cost_per_1k   NUMERIC(10, 6)  NOT NULL,
    output_cost_per_1k  NUMERIC(10, 6)  NOT NULL,
    effective_date      DATE            NOT NULL DEFAULT CURRENT_DATE,
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE allocation.model_pricing IS
    'Per-token pricing by model. Join to api_usage_raw on model_id to calculate cost per call.';

-- -----------------------------------------------------------------
-- business_units
-- Reference table for all known BUs
-- -----------------------------------------------------------------
CREATE TABLE allocation.business_units (
    bu_id               VARCHAR(30)     PRIMARY KEY,
    bu_name             VARCHAR(100)    NOT NULL,
    role                VARCHAR(30)     NOT NULL CHECK (role IN ('recipient', 'source', 'source-recipient-absorber')),
    primary_model_tier  VARCHAR(20)     CHECK (primary_model_tier IN ('low', 'mid', 'high', 'mixed')),
    hygiene_rate        NUMERIC(4, 2)   NOT NULL CHECK (hygiene_rate BETWEEN 0 AND 1),
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE allocation.business_units IS
    'Reference table for all BUs. hygiene_rate drives synthetic data generation — see DATA_DICTIONARY.md.';

-- -----------------------------------------------------------------
-- products
-- Products per BU — decorative but realistic
-- -----------------------------------------------------------------
CREATE TABLE allocation.products (
    product_id          VARCHAR(40)     PRIMARY KEY,
    product_name        VARCHAR(100)    NOT NULL,
    bu_id               VARCHAR(30)     NOT NULL REFERENCES allocation.business_units(bu_id),
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE allocation.products IS
    'Products within each BU. Tag dimension in api_usage_raw.';

-- -----------------------------------------------------------------
-- components
-- Platform components that consume the AI API
-- -----------------------------------------------------------------
CREATE TABLE allocation.components (
    component_id        VARCHAR(30)     PRIMARY KEY,
    description         TEXT            NOT NULL,
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE allocation.components IS
    'Platform components. Drives component_bu_mapping junction table.';

-- -----------------------------------------------------------------
-- features
-- Features per component
-- -----------------------------------------------------------------
CREATE TABLE allocation.features (
    feature_id          VARCHAR(30)     PRIMARY KEY,
    component_id        VARCHAR(30)     NOT NULL REFERENCES allocation.components(component_id),
    description         TEXT,
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE allocation.features IS
    'Features scoped to components. Tag dimension in api_usage_raw.';

-- =============================================================
-- MAPPING / JUNCTION TABLES
-- =============================================================

-- -----------------------------------------------------------------
-- component_bu_mapping
-- Junction table: component ownership weights per BU
-- Intentionally blurs the line with allocation_weights
-- -----------------------------------------------------------------
CREATE TABLE allocation.component_bu_mapping (
    mapping_id          SERIAL          PRIMARY KEY,
    component_id        VARCHAR(30)     NOT NULL REFERENCES allocation.components(component_id),
    bu_id               VARCHAR(30)     NOT NULL REFERENCES allocation.business_units(bu_id),
    ownership_weight    NUMERIC(5, 4)   NOT NULL CHECK (ownership_weight BETWEEN 0 AND 1),
    effective_date      DATE            NOT NULL DEFAULT CURRENT_DATE,
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW(),
    UNIQUE (component_id, bu_id)
);

COMMENT ON TABLE allocation.component_bu_mapping IS
    'Component ownership weights per BU. A component can be owned by multiple BUs.
     Weights per component should sum to 1.0 but edge cases (not summing) are valid
     test data for the allocation engine.';

-- =============================================================
-- COST POOL TABLES
-- =============================================================

-- -----------------------------------------------------------------
-- allocation_weights
-- Shared cost pool definitions and split weights per BU
-- P001: shared-inference (usage-based)
-- P002: platform-overhead (flat)
-- P003: embedding-pipeline (headcount-weighted)
-- P004: unallocable (platform absorbs) → see platform_unallocable_policy
-- -----------------------------------------------------------------
CREATE TABLE allocation.allocation_weights (
    weight_id           SERIAL          PRIMARY KEY,
    pool_id             VARCHAR(10)     NOT NULL,
    pool_name           VARCHAR(60)     NOT NULL,
    bu_id               VARCHAR(30)     REFERENCES allocation.business_units(bu_id),
    allocation_method   VARCHAR(30)     NOT NULL CHECK (allocation_method IN (
                                            'usage-based',
                                            'flat',
                                            'headcount-weighted',
                                            'platform-absorb'
                                        )),
    weight_value        NUMERIC(5, 4)   CHECK (weight_value BETWEEN 0 AND 1),
    effective_date      DATE            NOT NULL DEFAULT CURRENT_DATE,
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE allocation.allocation_weights IS
    'Cost pool definitions and BU split weights.
     P001–P003: shared pools with BU recipients.
     P004: unallocable — bu_id is NULL, platform absorbs via platform_unallocable_policy.
     Weights per pool_id should sum to 1.0 for P001–P003.';

-- -----------------------------------------------------------------
-- platform_unallocable_policy
-- Makes the P004 absorption rule explicit, queryable, and auditable
-- -----------------------------------------------------------------
CREATE TABLE allocation.platform_unallocable_policy (
    policy_id           SERIAL          PRIMARY KEY,
    pool_id             VARCHAR(10)     NOT NULL DEFAULT 'P004',
    absorbing_bu_id     VARCHAR(30)     NOT NULL REFERENCES allocation.business_units(bu_id),
    absorption_rate     NUMERIC(5, 4)   NOT NULL DEFAULT 1.0,
    policy_description  TEXT            NOT NULL,
    effective_date      DATE            NOT NULL DEFAULT CURRENT_DATE,
    created_by          VARCHAR(60)     NOT NULL DEFAULT 'platform-team',
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE allocation.platform_unallocable_policy IS
    'Defines the rule that Platform absorbs 100% of P004 unallocable costs.
     Queryable and auditable — policy changes are versioned here, not hardcoded in SQL.';

-- =============================================================
-- CORE FACT TABLE
-- =============================================================

-- -----------------------------------------------------------------
-- api_usage_raw
-- One row per API call. Central fact table for the allocation engine.
-- Tag columns mirror the tag hierarchy: business_unit → product → component → feature
-- NULL values in tag columns are intentional — see DATA_DICTIONARY.md hygiene profiles
-- -----------------------------------------------------------------
CREATE TABLE allocation.api_usage_raw (
    usage_id            UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    call_timestamp      TIMESTAMP       NOT NULL,
    model_id            VARCHAR(60)     NOT NULL REFERENCES allocation.model_pricing(model_id),
    environment         VARCHAR(10)     NOT NULL CHECK (environment IN ('dev', 'si', 'prod')),
    cost_type           VARCHAR(20)     NOT NULL CHECK (cost_type IN (
                                            'direct',
                                            'shared-inference',
                                            'shared-platform',
                                            'unallocable'
                                        )),
    pool_id             VARCHAR(10),
    client_id           VARCHAR(20),
    business_unit       VARCHAR(30)     REFERENCES allocation.business_units(bu_id),
    product             VARCHAR(40)     REFERENCES allocation.products(product_id),
    component           VARCHAR(30)     REFERENCES allocation.components(component_id),
    feature             VARCHAR(30)     REFERENCES allocation.features(feature_id),
    input_tokens        INTEGER         NOT NULL CHECK (input_tokens >= 0),
    output_tokens       INTEGER         NOT NULL CHECK (output_tokens >= 0),
    total_tokens        INTEGER         GENERATED ALWAYS AS (input_tokens + output_tokens) STORED,
    input_cost          NUMERIC(12, 8)  NOT NULL,
    output_cost         NUMERIC(12, 8)  NOT NULL,
    total_cost          NUMERIC(12, 8)  GENERATED ALWAYS AS (input_cost + output_cost) STORED,
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW()
);

-- =============================================================
-- INDEXES
-- =============================================================

-- api_usage_raw — primary query patterns
CREATE INDEX idx_usage_timestamp        ON allocation.api_usage_raw (call_timestamp);
CREATE INDEX idx_usage_bu               ON allocation.api_usage_raw (business_unit);
CREATE INDEX idx_usage_cost_type        ON allocation.api_usage_raw (cost_type);
CREATE INDEX idx_usage_pool             ON allocation.api_usage_raw (pool_id);
CREATE INDEX idx_usage_model            ON allocation.api_usage_raw (model_id);
CREATE INDEX idx_usage_environment      ON allocation.api_usage_raw (environment);
CREATE INDEX idx_usage_component        ON allocation.api_usage_raw (component);
CREATE INDEX idx_usage_client           ON allocation.api_usage_raw (client_id);

-- Composite: most common allocation query pattern
CREATE INDEX idx_usage_bu_cost_type     ON allocation.api_usage_raw (business_unit, cost_type);
CREATE INDEX idx_usage_pool_env         ON allocation.api_usage_raw (pool_id, environment);

-- component_bu_mapping
CREATE INDEX idx_mapping_component      ON allocation.component_bu_mapping (component_id);
CREATE INDEX idx_mapping_bu             ON allocation.component_bu_mapping (bu_id);

-- allocation_weights
CREATE INDEX idx_weights_pool           ON allocation.allocation_weights (pool_id);
CREATE INDEX idx_weights_bu             ON allocation.allocation_weights (bu_id);

-- =============================================================
-- UNIQUE CONSTRAINT: pool_id on allocation_weights
-- Allows api_usage_raw.pool_id FK to reference the pool
-- =============================================================
ALTER TABLE allocation.allocation_weights
    ADD CONSTRAINT uq_pool_id UNIQUE (pool_id, bu_id);

-- =============================================================
-- VERIFY
-- =============================================================

SELECT
    table_schema,
    table_name
FROM information_schema.tables
WHERE table_schema = 'allocation'
ORDER BY table_name;