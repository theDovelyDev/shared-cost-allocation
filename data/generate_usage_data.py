"""
generate_usage_data.py — Shared Cost Allocation Engine
Project 4 | CostCenter: Project4

Generates 750,000 synthetic API usage records across 9 months and loads
them into allocation.api_usage_raw in RDS PostgreSQL.

Tag hygiene profiles per BU (from DATA_DICTIONARY.md):
    data-science-team : 95% overall, all dimensions consistent
    eng-team          : 78% overall, component/model clean, client_id/feature messy
    marketing-team    : 65% overall, feature 88%, other dims drag it down
    cx-team           : 60% overall, client_id 97%, everything else inconsistent
    platform-team     : 65% overall, worst overall hygiene

Usage:
    source venv/Scripts/activate
    source config/setup.sh
    python data/generate_usage_data.py
"""

import os
import uuid
import random
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv("config/.env", override=True)

# ── Config ────────────────────────────────────────────────────────

TOTAL_RECORDS = 750_000
BATCH_SIZE = 5_000
START_DATE = datetime(2025, 8, 1)  # 9 months back from May 2026
END_DATE = datetime(2026, 4, 30)

# ── Reference Data ────────────────────────────────────────────────

MODELS = {
    "claude-haiku-4-5-20251001": {
        "tier": "low",
        "input_cost_per_1k": 0.000800,
        "output_cost_per_1k": 0.004000,
        "avg_input_tokens": 500,
        "avg_output_tokens": 300,
    },
    "claude-sonnet-4-6": {
        "tier": "mid",
        "input_cost_per_1k": 0.003000,
        "output_cost_per_1k": 0.015000,
        "avg_input_tokens": 800,
        "avg_output_tokens": 600,
    },
    "claude-opus-4-6": {
        "tier": "high",
        "input_cost_per_1k": 0.015000,
        "output_cost_per_1k": 0.075000,
        "avg_input_tokens": 1200,
        "avg_output_tokens": 900,
    },
}

BUSINESS_UNITS = [
    "eng-team",
    "data-science-team",
    "marketing-team",
    "cx-team",
    "platform-team",
]

PRODUCTS = {
    "cx-team": ["cx-chat", "speech-bot", "doc-processing"],
    "data-science-team": ["ml-platform", "experiment-tracker", "feature-store"],
    "marketing-team": ["content-studio", "campaign-gen", "seo-optimizer"],
    "eng-team": ["dev-assist", "code-review-bot", "incident-analyzer"],
    "platform-team": ["model-gateway", "cost-observatory", "prompt-registry"],
}

COMPONENTS = [
    "inference",
    "embedding",
    "fine-tuning",
    "evaluation",
    "prompt-management",
    "vector-store",
    "data-pipeline",
    "monitoring",
    "gateway",
]

FEATURES = {
    "inference": ["content-gen", "summarization", "chat", "code-gen", "translation"],
    "embedding": ["semantic-search", "document-retrieval", "recommendation"],
    "fine-tuning": ["domain-adaptation", "tone-calibration", "task-specialization"],
    "evaluation": ["benchmark-testing", "regression-testing", "ab-testing"],
    "prompt-management": ["prompt-versioning", "prompt-testing", "template-library"],
    "vector-store": ["index-management", "similarity-search", "chunk-storage"],
    "data-pipeline": ["ingestion", "preprocessing", "enrichment"],
    "monitoring": ["drift-detection", "cost-alerting", "performance-tracking"],
    "gateway": ["rate-limiting", "auth", "routing"],
}

ENVIRONMENTS = ["dev", "si", "prod"]

COST_TYPES = ["direct", "shared-inference", "shared-platform", "unallocable"]

POOL_MAP = {
    "direct": None,
    "shared-inference": "P001",
    "shared-platform": random.choice(["P002", "P003"]),
    "unallocable": "P004",
}

# ── BU Profiles ───────────────────────────────────────────────────
# Controls model mix, cost type distribution, environment distribution,
# tag hygiene rates, and volume weight per BU

BU_PROFILES = {
    "data-science-team": {
        "volume_weight": 0.22,
        "model_weights": {
            "claude-haiku-4-5-20251001": 0.10,
            "claude-sonnet-4-6": 0.45,
            "claude-opus-4-6": 0.45,
        },
        "cost_type_weights": {
            "direct": 0.55,
            "shared-inference": 0.20,
            "shared-platform": 0.10,
            "unallocable": 0.15,
        },
        "env_weights": {"dev": 0.25, "si": 0.20, "prod": 0.55},
        "hygiene": {
            "overall": 0.95,
            "client_id": 0.95,
            "product": 0.95,
            "component": 0.96,
            "feature": 0.94,
        },
    },
    "eng-team": {
        "volume_weight": 0.20,
        "model_weights": {
            "claude-haiku-4-5-20251001": 0.30,
            "claude-sonnet-4-6": 0.50,
            "claude-opus-4-6": 0.20,
        },
        "cost_type_weights": {
            "direct": 0.40,
            "shared-inference": 0.30,
            "shared-platform": 0.10,
            "unallocable": 0.20,
        },
        "env_weights": {"dev": 0.30, "si": 0.20, "prod": 0.50},
        "hygiene": {
            "overall": 0.78,
            "client_id": 0.65,  # messy
            "product": 0.80,
            "component": 0.90,  # clean
            "feature": 0.65,  # messy
        },
    },
    "marketing-team": {
        "volume_weight": 0.18,
        "model_weights": {
            "claude-haiku-4-5-20251001": 0.70,
            "claude-sonnet-4-6": 0.25,
            "claude-opus-4-6": 0.05,
        },
        "cost_type_weights": {
            "direct": 0.35,
            "shared-inference": 0.30,
            "shared-platform": 0.10,
            "unallocable": 0.25,
        },
        "env_weights": {"dev": 0.20, "si": 0.15, "prod": 0.65},
        "hygiene": {
            "overall": 0.65,
            "client_id": 0.60,
            "product": 0.65,
            "component": 0.65,
            "feature": 0.88,  # best dimension for marketing
        },
    },
    "cx-team": {
        "volume_weight": 0.22,
        "model_weights": {
            "claude-haiku-4-5-20251001": 0.80,
            "claude-sonnet-4-6": 0.18,
            "claude-opus-4-6": 0.02,
        },
        "cost_type_weights": {
            "direct": 0.60,
            "shared-inference": 0.25,
            "shared-platform": 0.10,
            "unallocable": 0.05,
        },
        "env_weights": {"dev": 0.15, "si": 0.10, "prod": 0.75},
        "hygiene": {
            "overall": 0.60,
            "client_id": 0.97,  # very clean
            "product": 0.55,  # inconsistent
            "component": 0.55,
            "feature": 0.55,
        },
    },
    "platform-team": {
        "volume_weight": 0.18,
        "model_weights": {
            "claude-haiku-4-5-20251001": 0.35,
            "claude-sonnet-4-6": 0.40,
            "claude-opus-4-6": 0.25,
        },
        "cost_type_weights": {
            "direct": 0.30,
            "shared-inference": 0.35,
            "shared-platform": 0.20,
            "unallocable": 0.15,
        },
        "env_weights": {"dev": 0.35, "si": 0.25, "prod": 0.40},
        "hygiene": {
            "overall": 0.65,
            "client_id": 0.60,
            "product": 0.65,
            "component": 0.68,
            "feature": 0.60,  # worst
        },
    },
}

# ── Helpers ───────────────────────────────────────────────────────


def random_timestamp(start: datetime, end: datetime) -> datetime:
    delta = end - start
    seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=seconds)


def weighted_choice(options: list, weights: list) -> str:
    return random.choices(options, weights=weights, k=1)[0]


def maybe_null(value, rate: float):
    """Return value with probability=rate, else None."""
    return value if random.random() < rate else None


def generate_tokens(model_id: str) -> tuple[int, int]:
    """Generate realistic token counts with variance."""
    profile = MODELS[model_id]
    input_tokens = max(
        1,
        int(
            random.gauss(profile["avg_input_tokens"], profile["avg_input_tokens"] * 0.3)
        ),
    )
    output_tokens = max(
        1,
        int(
            random.gauss(
                profile["avg_output_tokens"], profile["avg_output_tokens"] * 0.3
            )
        ),
    )
    return input_tokens, output_tokens


def calculate_cost(
    model_id: str, input_tokens: int, output_tokens: int
) -> tuple[float, float]:
    profile = MODELS[model_id]
    input_cost = (input_tokens / 1000) * profile["input_cost_per_1k"]
    output_cost = (output_tokens / 1000) * profile["output_cost_per_1k"]
    return round(input_cost, 8), round(output_cost, 8)


def get_pool_id(cost_type: str) -> str | None:
    if cost_type == "direct":
        return None
    elif cost_type == "shared-inference":
        return "P001"
    elif cost_type == "shared-platform":
        return random.choice(["P002", "P003"])
    elif cost_type == "unallocable":
        return "P004"


def generate_record(bu_id: str) -> dict:
    profile = BU_PROFILES[bu_id]
    hygiene = profile["hygiene"]

    # Cost type
    cost_type = weighted_choice(
        list(profile["cost_type_weights"].keys()),
        list(profile["cost_type_weights"].values()),
    )

    # Model — unallocable biases toward expensive models
    if cost_type == "unallocable":
        model_id = weighted_choice(
            list(MODELS.keys()), [0.10, 0.40, 0.50]  # Haiku 10%, Sonnet 40%, Opus 50%
        )
    else:
        model_id = weighted_choice(
            list(profile["model_weights"].keys()),
            list(profile["model_weights"].values()),
        )

    # Environment
    environment = weighted_choice(
        list(profile["env_weights"].keys()), list(profile["env_weights"].values())
    )

    # Pool ID
    pool_id = get_pool_id(cost_type)

    # Tag dimensions — apply hygiene rates
    client_id = maybe_null(f"client_{random.randint(1, 50):03d}", hygiene["client_id"])
    # Direct costs always have a BU — hygiene only applies to shared/unallocable
    if cost_type == "direct":
        business_unit = bu_id
    else:
        business_unit = maybe_null(bu_id, hygiene["overall"])
    product = (
        maybe_null(random.choice(PRODUCTS[bu_id]), hygiene["product"])
        if business_unit
        else None
    )

    component = maybe_null(random.choice(COMPONENTS), hygiene["component"])

    feature = (
        maybe_null(
            random.choice(FEATURES[component]) if component else None,
            hygiene["feature"],
        )
        if component
        else None
    )

    # Tokens and cost
    input_tokens, output_tokens = generate_tokens(model_id)
    input_cost, output_cost = calculate_cost(model_id, input_tokens, output_tokens)

    return {
        "usage_id": str(uuid.uuid4()),
        "call_timestamp": random_timestamp(START_DATE, END_DATE),
        "model_id": model_id,
        "environment": environment,
        "cost_type": cost_type,
        "pool_id": pool_id,
        "client_id": client_id,
        "business_unit": business_unit,
        "product": product,
        "component": component,
        "feature": feature,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "input_cost": input_cost,
        "output_cost": output_cost,
    }


# ── DB Connection ─────────────────────────────────────────────────


def get_connection():
    return psycopg2.connect(
        host=os.getenv("PGHOST"),
        port=os.getenv("PGPORT", 5432),
        dbname=os.getenv("PGDATABASE"),
        user=os.getenv("PGUSER"),
        password=os.getenv("PGPASSWORD"),
        sslmode="require",
    )


# ── Insert ────────────────────────────────────────────────────────

INSERT_SQL = """
INSERT INTO allocation.api_usage_raw (
    usage_id, call_timestamp, model_id, environment, cost_type, pool_id,
    client_id, business_unit, product, component, feature,
    input_tokens, output_tokens, input_cost, output_cost
) VALUES %s
ON CONFLICT (usage_id) DO NOTHING;
"""


def insert_batch(cursor, batch: list[dict]):
    values = [
        (
            r["usage_id"],
            r["call_timestamp"],
            r["model_id"],
            r["environment"],
            r["cost_type"],
            r["pool_id"],
            r["client_id"],
            r["business_unit"],
            r["product"],
            r["component"],
            r["feature"],
            r["input_tokens"],
            r["output_tokens"],
            r["input_cost"],
            r["output_cost"],
        )
        for r in batch
    ]
    psycopg2.extras.execute_values(cursor, INSERT_SQL, values, page_size=BATCH_SIZE)


# ── Main ──────────────────────────────────────────────────────────


def main():
    print(f"Shared Cost Allocation Engine — Data Generator")
    print(f"Target: {TOTAL_RECORDS:,} records | Batch size: {BATCH_SIZE:,}")
    print(f"Date range: {START_DATE.date()} → {END_DATE.date()}")
    print("=" * 55)

    # Build BU distribution based on volume weights
    bu_weights = [BU_PROFILES[bu]["volume_weight"] for bu in BUSINESS_UNITS]

    conn = get_connection()
    cursor = conn.cursor()

    batch = []
    total_inserted = 0
    batch_count = 0

    try:
        for i in range(TOTAL_RECORDS):
            bu_id = weighted_choice(BUSINESS_UNITS, bu_weights)
            record = generate_record(bu_id)
            batch.append(record)

            if len(batch) >= BATCH_SIZE:
                insert_batch(cursor, batch)
                conn.commit()
                total_inserted += len(batch)
                batch_count += 1
                batch = []
                print(
                    f"  Batch {batch_count:>4} | {total_inserted:>9,} / {TOTAL_RECORDS:,} records inserted"
                )

        # Final partial batch
        if batch:
            insert_batch(cursor, batch)
            conn.commit()
            total_inserted += len(batch)
            print(
                f"  Final batch  | {total_inserted:>9,} / {TOTAL_RECORDS:,} records inserted"
            )

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

    print("=" * 55)
    print(
        f"✅ Complete — {total_inserted:,} records loaded into allocation.api_usage_raw"
    )

    # Quick distribution check
    print("\nRunning distribution check...")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            business_unit,
            COUNT(*)                                    AS record_count,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) AS pct,
            ROUND(SUM(total_cost)::numeric, 2)          AS total_cost,
            COUNT(*) FILTER (WHERE business_unit IS NULL)::float
                / COUNT(*) * 100                        AS null_bu_pct
        FROM allocation.api_usage_raw
        GROUP BY business_unit
        ORDER BY record_count DESC;
    """)
    rows = cursor.fetchall()
    print(f"\n{'BU':<22} {'Records':>10} {'%':>6} {'Total Cost':>12} {'NULL BU%':>10}")
    print("-" * 65)
    for row in rows:
        bu = row[0] or "NULL"
        print(f"{bu:<22} {row[1]:>10,} {row[2]:>6}% ${row[3]:>11} {row[4]:>9.1f}%")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
