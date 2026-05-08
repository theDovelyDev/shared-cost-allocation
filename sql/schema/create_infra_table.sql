-- =============================================================
-- Shared Cost Allocation Engine — Infrastructure Costs DDL
-- Project 4 | CostCenter: Project4
-- Database: shared_cost_db
-- Run after create_tables.sql
-- =============================================================

SET search_path TO allocation;

-- =============================================================
-- INFRASTRUCTURE USAGE FACT TABLE
-- =============================================================

CREATE TABLE allocation.infra_usage_raw (
    infra_usage_id      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Timestamps
    usage_start_time    TIMESTAMP       NOT NULL,
    usage_end_time      TIMESTAMP       NOT NULL,
    billing_period      DATE            NOT NULL,
    
    -- AWS resource identification
    resource_arn        VARCHAR(255)    NOT NULL,
    service             VARCHAR(30)     NOT NULL CHECK (service IN ('rds', 'ecs', 's3', 'vpc', 'ec2')),
    region              VARCHAR(20)     NOT NULL DEFAULT 'us-east-1',
    
    -- Cost classification
    cost_type           VARCHAR(20)     NOT NULL CHECK (cost_type IN (
                                            'direct',
                                            'shared-platform',
                                            'unallocable'
                                        )),
    pool_id             VARCHAR(10),
    
    -- Tag dimensions (shared with api_usage_raw)
    client_id           VARCHAR(20),
    business_unit       VARCHAR(30)     REFERENCES allocation.business_units(bu_id),
    product             VARCHAR(40)     REFERENCES allocation.products(product_id),
    component           VARCHAR(30)     REFERENCES allocation.components(component_id),
    feature             VARCHAR(30)     REFERENCES allocation.features(feature_id),
    environment         VARCHAR(10)     NOT NULL CHECK (environment IN ('dev', 'si', 'prod')),
    
    -- Usage metrics (generic)
    usage_quantity      NUMERIC(12, 4)  NOT NULL CHECK (usage_quantity > 0),
    usage_unit          VARCHAR(50)     NOT NULL,
    
    -- Cost
    total_cost          NUMERIC(12, 8)  NOT NULL CHECK (total_cost >= 0),
    
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE allocation.infra_usage_raw IS
    'Infrastructure cost fact table. One row per resource per billing period.
     Separate from api_usage_raw due to different schema (no token counts).
     Joins to api_usage_raw through shared tag dimensions for unified allocation.';

COMMENT ON COLUMN allocation.infra_usage_raw.resource_arn IS
    'AWS ARN uniquely identifying the resource generating this cost.';

COMMENT ON COLUMN allocation.infra_usage_raw.service IS
    'AWS service name: rds, ecs, s3, vpc, ec2.';

COMMENT ON COLUMN allocation.infra_usage_raw.billing_period IS
    'Date this cost appears on the bill. Daily granularity.';

COMMENT ON COLUMN allocation.infra_usage_raw.usage_quantity IS
    'Generic usage metric quantity. Pair with usage_unit.';

COMMENT ON COLUMN allocation.infra_usage_raw.usage_unit IS
    'Unit of measure for usage_quantity. Examples: instance_hours, storage_gb, data_transfer_gb.';

-- =============================================================
-- INDEXES
-- =============================================================

CREATE INDEX idx_infra_usage_billing_period ON allocation.infra_usage_raw (billing_period);
CREATE INDEX idx_infra_usage_bu               ON allocation.infra_usage_raw (business_unit);
CREATE INDEX idx_infra_usage_cost_type        ON allocation.infra_usage_raw (cost_type);
CREATE INDEX idx_infra_usage_pool             ON allocation.infra_usage_raw (pool_id);
CREATE INDEX idx_infra_usage_service          ON allocation.infra_usage_raw (service);
CREATE INDEX idx_infra_usage_environment      ON allocation.infra_usage_raw (environment);
CREATE INDEX idx_infra_usage_component        ON allocation.infra_usage_raw (component);
CREATE INDEX idx_infra_usage_resource         ON allocation.infra_usage_raw (resource_arn);

-- Composite indexes
CREATE INDEX idx_infra_usage_bu_cost_type     ON allocation.infra_usage_raw (business_unit, cost_type);
CREATE INDEX idx_infra_usage_service_period   ON allocation.infra_usage_raw (service, billing_period);

-- =============================================================
-- VERIFY
-- =============================================================

SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'allocation'
  AND table_name = 'infra_usage_raw'
ORDER BY ordinal_position;