-- =============================================================
-- Shared Cost Allocation Engine — Seed Data
-- Project 4 | CostCenter: Project4
-- Database: shared_cost_db
-- Run after create_tables.sql
-- =============================================================

SET search_path TO allocation;

-- =============================================================
-- model_pricing
-- Current Anthropic pricing as of 2026-05
-- =============================================================

INSERT INTO allocation.model_pricing
    (model_id, model_display_name, tier, input_cost_per_1k, output_cost_per_1k)
VALUES
    ('claude-haiku-4-5-20251001', 'Claude Haiku 4.5',  'low',  0.000800, 0.004000),
    ('claude-sonnet-4-6',         'Claude Sonnet 4.6',  'mid',  0.003000, 0.015000),
    ('claude-opus-4-6',           'Claude Opus 4.6',    'high', 0.015000, 0.075000);

-- =============================================================
-- business_units
-- =============================================================

INSERT INTO allocation.business_units
    (bu_id, bu_name, role, primary_model_tier, hygiene_rate)
VALUES
    ('eng-team',          'Engineering',       'recipient',                  'mixed',  0.78),
    ('data-science-team', 'Data Science',      'recipient',                  'high',   0.95),
    ('marketing-team',    'Marketing',         'recipient',                  'low',    0.65),
    ('cx-team',           'Customer Support',  'recipient',                  'low',    0.60),
    ('platform-team',     'Platform',          'source-recipient-absorber',  'mixed',  0.65);

-- =============================================================
-- products
-- =============================================================

INSERT INTO allocation.products (product_id, product_name, bu_id)
VALUES
    -- Customer Support
    ('cx-chat',             'CX Chat',              'cx-team'),
    ('speech-bot',          'Speech Bot',           'cx-team'),
    ('doc-processing',      'Document Processing',  'cx-team'),
    -- Data Science
    ('ml-platform',         'ML Platform',          'data-science-team'),
    ('experiment-tracker',  'Experiment Tracker',   'data-science-team'),
    ('feature-store',       'Feature Store',        'data-science-team'),
    -- Marketing
    ('content-studio',      'Content Studio',       'marketing-team'),
    ('campaign-gen',        'Campaign Generator',   'marketing-team'),
    ('seo-optimizer',       'SEO Optimizer',        'marketing-team'),
    -- Engineering
    ('dev-assist',          'Dev Assist',           'eng-team'),
    ('code-review-bot',     'Code Review Bot',      'eng-team'),
    ('incident-analyzer',   'Incident Analyzer',    'eng-team'),
    -- Platform
    ('model-gateway',       'Model Gateway',        'platform-team'),
    ('cost-observatory',    'Cost Observatory',     'platform-team'),
    ('prompt-registry',     'Prompt Registry',      'platform-team');

-- =============================================================
-- components
-- =============================================================

INSERT INTO allocation.components (component_id, description)
VALUES
    ('inference',         'Real-time API calls'),
    ('embedding',         'Vector generation'),
    ('fine-tuning',       'Model customization runs'),
    ('evaluation',        'Model assessment before promotion'),
    ('prompt-management', 'Prompt versioning, testing, and storage'),
    ('vector-store',      'Hosting and querying embedding indexes'),
    ('data-pipeline',     'Ingestion and preprocessing before model consumption'),
    ('monitoring',        'Model performance tracking, drift detection, cost observability'),
    ('gateway',           'API gateway layer managing routing, rate limiting, auth');

-- =============================================================
-- features
-- =============================================================

INSERT INTO allocation.features (feature_id, component_id, description)
VALUES
    -- inference
    ('content-gen',         'inference',          'Content generation'),
    ('summarization',       'inference',          'Text summarization'),
    ('chat',                'inference',          'Conversational interface'),
    ('code-gen',            'inference',          'Code generation and completion'),
    ('translation',         'inference',          'Language translation'),
    -- embedding
    ('semantic-search',     'embedding',          'Semantic similarity search'),
    ('document-retrieval',  'embedding',          'Document retrieval from vector index'),
    ('recommendation',      'embedding',          'Embedding-based recommendations'),
    -- fine-tuning
    ('domain-adaptation',   'fine-tuning',        'Adapting model to domain-specific data'),
    ('tone-calibration',    'fine-tuning',        'Adjusting model tone and style'),
    ('task-specialization', 'fine-tuning',        'Specializing model for a specific task'),
    -- evaluation
    ('benchmark-testing',   'evaluation',         'Benchmarking model performance'),
    ('regression-testing',  'evaluation',         'Regression testing after model updates'),
    ('ab-testing',          'evaluation',         'A/B testing model variants'),
    -- prompt-management
    ('prompt-versioning',   'prompt-management',  'Version control for prompts'),
    ('prompt-testing',      'prompt-management',  'Testing prompt variations'),
    ('template-library',    'prompt-management',  'Shared prompt template library'),
    -- vector-store
    ('index-management',    'vector-store',       'Managing vector indexes'),
    ('similarity-search',   'vector-store',       'Similarity search against vector store'),
    ('chunk-storage',       'vector-store',       'Storing and retrieving document chunks'),
    -- data-pipeline
    ('ingestion',           'data-pipeline',      'Data ingestion from source systems'),
    ('preprocessing',       'data-pipeline',      'Data preprocessing and cleaning'),
    ('enrichment',          'data-pipeline',      'Data enrichment before model consumption'),
    -- monitoring
    ('drift-detection',     'monitoring',         'Detecting model drift over time'),
    ('cost-alerting',       'monitoring',         'Alerting on cost anomalies'),
    ('performance-tracking','monitoring',         'Tracking model performance metrics'),
    -- gateway
    ('rate-limiting',       'gateway',            'Rate limiting API consumers'),
    ('auth',                'gateway',            'Authentication and authorization'),
    ('routing',             'gateway',            'Routing requests to appropriate models');

-- =============================================================
-- component_bu_mapping
-- Ownership weights per component per BU
-- Weights per component should sum to 1.0
-- =============================================================

INSERT INTO allocation.component_bu_mapping
    (component_id, bu_id, ownership_weight)
VALUES
    -- inference: all BUs consume, Data Science and Engineering heaviest
    ('inference', 'data-science-team',  0.30),
    ('inference', 'eng-team',           0.25),
    ('inference', 'cx-team',            0.20),
    ('inference', 'marketing-team',     0.15),
    ('inference', 'platform-team',      0.10),

    -- embedding: Data Science, Engineering, Platform
    ('embedding', 'data-science-team',  0.50),
    ('embedding', 'eng-team',           0.30),
    ('embedding', 'platform-team',      0.20),

    -- fine-tuning: Data Science owns majority, Platform supports
    ('fine-tuning', 'data-science-team', 0.70),
    ('fine-tuning', 'platform-team',     0.30),

    -- evaluation: Data Science and Engineering split
    ('evaluation', 'data-science-team',  0.60),
    ('evaluation', 'eng-team',           0.40),

    -- prompt-management: all BUs, Platform owns the registry
    ('prompt-management', 'platform-team',      0.30),
    ('prompt-management', 'data-science-team',  0.25),
    ('prompt-management', 'eng-team',           0.20),
    ('prompt-management', 'marketing-team',     0.15),
    ('prompt-management', 'cx-team',            0.10),

    -- vector-store: Data Science and Engineering
    ('vector-store', 'data-science-team',  0.60),
    ('vector-store', 'eng-team',           0.40),

    -- data-pipeline: Data Science and Platform
    ('data-pipeline', 'data-science-team', 0.60),
    ('data-pipeline', 'platform-team',     0.40),

    -- monitoring: Platform owns, Engineering consumes
    ('monitoring', 'platform-team',  0.70),
    ('monitoring', 'eng-team',       0.30),

    -- gateway: Platform owns entirely
    ('gateway', 'platform-team', 1.00);

-- =============================================================
-- allocation_weights
-- Cost pool definitions and BU split weights
-- P001: shared-inference (usage-based)
-- P002: platform-overhead (flat)
-- P003: embedding-pipeline (headcount-weighted)
-- P004: unallocable (platform absorbs)
-- =============================================================

INSERT INTO allocation.allocation_weights
    (pool_id, pool_name, bu_id, allocation_method, weight_value)
VALUES
    -- P001: shared-inference — usage-based, all BUs
    ('P001', 'shared-inference', 'data-science-team', 'usage-based', 0.35),
    ('P001', 'shared-inference', 'eng-team',          'usage-based', 0.25),
    ('P001', 'shared-inference', 'cx-team',           'usage-based', 0.20),
    ('P001', 'shared-inference', 'marketing-team',    'usage-based', 0.12),
    ('P001', 'shared-inference', 'platform-team',     'usage-based', 0.08),

    -- P002: platform-overhead — flat split, all BUs equally
    ('P002', 'platform-overhead', 'data-science-team', 'flat', 0.20),
    ('P002', 'platform-overhead', 'eng-team',           'flat', 0.20),
    ('P002', 'platform-overhead', 'cx-team',            'flat', 0.20),
    ('P002', 'platform-overhead', 'marketing-team',     'flat', 0.20),
    ('P002', 'platform-overhead', 'platform-team',      'flat', 0.20),

    -- P003: embedding-pipeline — headcount-weighted
    ('P003', 'embedding-pipeline', 'data-science-team', 'headcount-weighted', 0.60),
    ('P003', 'embedding-pipeline', 'cx-team',           'headcount-weighted', 0.40),

    -- P004: unallocable — platform absorbs, no BU split
    ('P004', 'unallocable', NULL, 'platform-absorb', 1.00);

-- =============================================================
-- VERIFY
-- =============================================================

SELECT 'model_pricing'              AS table_name, COUNT(*) AS row_count FROM allocation.model_pricing
UNION ALL
SELECT 'business_units',                           COUNT(*) FROM allocation.business_units
UNION ALL
SELECT 'products',                                 COUNT(*) FROM allocation.products
UNION ALL
SELECT 'components',                               COUNT(*) FROM allocation.components
UNION ALL
SELECT 'features',                                 COUNT(*) FROM allocation.features
UNION ALL
SELECT 'component_bu_mapping',                     COUNT(*) FROM allocation.component_bu_mapping
UNION ALL
SELECT 'allocation_weights',                       COUNT(*) FROM allocation.allocation_weights
UNION ALL;
