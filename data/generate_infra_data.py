"""
generate_infra_data.py — Shared Cost Allocation Engine
Project 4 | CostCenter: Project4

Generates ~10,000 synthetic infrastructure cost records across 9 months
and loads them into allocation.infra_usage_raw in RDS PostgreSQL.

Infrastructure services: RDS, ECS/Fargate, S3, VPC/Networking, EC2
Cost distribution: 60% direct, 35% shared-platform, 5% unallocable
Infra costs represent ~30-40% of total platform cost (token + infra combined)

Usage:
    source venv/Scripts/activate
    source config/setup.sh
    python data/generate_infra_data.py
"""

import os
import uuid
import random
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta, date
from dotenv import load_dotenv

load_dotenv("config/.env", override=True)

# ── Config ────────────────────────────────────────────────────────

TOTAL_RECORDS = 10_000
BATCH_SIZE = 500
START_DATE = date(2025, 8, 1)
END_DATE = date(2026, 4, 30)
REGION = "us-east-1"

# ── Reference Data ────────────────────────────────────────────────

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

# Infra-specific components
INFRA_COMPONENTS = {
    "database": ["database"],
    "container": ["container"],
    "storage": ["storage"],
    "networking": ["networking"],
    "compute": ["compute"],
}

ENVIRONMENTS = ["dev", "si", "prod"]

COST_TYPES = ["direct", "shared-platform", "unallocable"]

# ── Service Definitions ───────────────────────────────────────────

SERVICES = {
    "rds": {
        "component": "database",
        "usage_units": ["instance_hours", "storage_gb"],
        "cost_per_unit": {
            "instance_hours": 0.0416,
            "storage_gb": 0.10,
        },  # db.t3.micro pricing
        "avg_quantity": {"instance_hours": 24, "storage_gb": 20},
        "cost_type_weights": {
            "direct": 0.70,
            "shared-platform": 0.25,
            "unallocable": 0.05,
        },
    },
    "ecs": {
        "component": "container",
        "usage_units": ["vcpu_hours", "memory_gb_hours"],
        "cost_per_unit": {
            "vcpu_hours": 0.04048,
            "memory_gb_hours": 0.004445,
        },  # Fargate pricing
        "avg_quantity": {"vcpu_hours": 0.25, "memory_gb_hours": 0.5},
        "cost_type_weights": {
            "direct": 0.30,
            "shared-platform": 0.65,
            "unallocable": 0.05,
        },
    },
    "s3": {
        "component": "storage",
        "usage_units": ["storage_gb", "requests", "data_transfer_gb"],
        "cost_per_unit": {
            "storage_gb": 0.023,
            "requests": 0.0004,
            "data_transfer_gb": 0.09,
        },
        "avg_quantity": {"storage_gb": 100, "requests": 1000, "data_transfer_gb": 10},
        "cost_type_weights": {
            "direct": 0.60,
            "shared-platform": 0.35,
            "unallocable": 0.05,
        },
    },
    "vpc": {
        "component": "networking",
        "usage_units": ["data_transfer_gb", "nat_gateway_hours"],
        "cost_per_unit": {"data_transfer_gb": 0.09, "nat_gateway_hours": 0.045},
        "avg_quantity": {"data_transfer_gb": 50, "nat_gateway_hours": 24},
        "cost_type_weights": {
            "direct": 0.10,
            "shared-platform": 0.85,
            "unallocable": 0.05,
        },
    },
    "ec2": {
        "component": "compute",
        "usage_units": ["instance_hours"],
        "cost_per_unit": {"instance_hours": 0.0116},  # t3.micro pricing
        "avg_quantity": {"instance_hours": 24},
        "cost_type_weights": {
            "direct": 0.70,
            "shared-platform": 0.25,
            "unallocable": 0.05,
        },
    },
}

# Service distribution — how many records per service
SERVICE_WEIGHTS = {
    "rds": 0.15,
    "ecs": 0.35,
    "s3": 0.30,
    "vpc": 0.10,
    "ec2": 0.10,
}

# ── BU Profiles ───────────────────────────────────────────────────

BU_PROFILES = {
    "data-science-team": {
        "volume_weight": 0.25,
        "service_weights": {
            "rds": 0.25,
            "ecs": 0.20,
            "s3": 0.35,
            "vpc": 0.10,
            "ec2": 0.10,
        },
        "env_weights": {"dev": 0.25, "si": 0.20, "prod": 0.55},
        "hygiene": {
            "overall": 0.95,
            "client_id": 0.95,
            "product": 0.95,
            "feature": 0.94,
        },
    },
    "eng-team": {
        "volume_weight": 0.20,
        "service_weights": {
            "rds": 0.20,
            "ecs": 0.35,
            "s3": 0.25,
            "vpc": 0.10,
            "ec2": 0.10,
        },
        "env_weights": {"dev": 0.30, "si": 0.20, "prod": 0.50},
        "hygiene": {
            "overall": 0.78,
            "client_id": 0.65,
            "product": 0.80,
            "feature": 0.65,
        },
    },
    "marketing-team": {
        "volume_weight": 0.15,
        "service_weights": {
            "rds": 0.10,
            "ecs": 0.40,
            "s3": 0.35,
            "vpc": 0.10,
            "ec2": 0.05,
        },
        "env_weights": {"dev": 0.20, "si": 0.15, "prod": 0.65},
        "hygiene": {
            "overall": 0.65,
            "client_id": 0.60,
            "product": 0.65,
            "feature": 0.88,
        },
    },
    "cx-team": {
        "volume_weight": 0.20,
        "service_weights": {
            "rds": 0.20,
            "ecs": 0.40,
            "s3": 0.25,
            "vpc": 0.10,
            "ec2": 0.05,
        },
        "env_weights": {"dev": 0.15, "si": 0.10, "prod": 0.75},
        "hygiene": {
            "overall": 0.60,
            "client_id": 0.97,
            "product": 0.55,
            "feature": 0.55,
        },
    },
    "platform-team": {
        "volume_weight": 0.20,
        "service_weights": {
            "rds": 0.15,
            "ecs": 0.30,
            "s3": 0.30,
            "vpc": 0.15,
            "ec2": 0.10,
        },
        "env_weights": {"dev": 0.35, "si": 0.25, "prod": 0.40},
        "hygiene": {
            "overall": 0.65,
            "client_id": 0.60,
            "product": 0.65,
            "feature": 0.60,
        },
    },
}

# ── Helpers ───────────────────────────────────────────────────────


def weighted_choice(options: list, weights: list) -> str:
    return random.choices(options, weights=weights, k=1)[0]


def maybe_null(value, rate: float):
    """Return value with probability=rate, else None."""
    return value if random.random() < rate else None


def generate_resource_arn(
    service: str, account_id: str, region: str, resource_name: str
) -> str:
    """Generate realistic AWS ARN."""
    if service == "rds":
        return f"arn:aws:rds:{region}:{account_id}:db:{resource_name}"
    elif service == "ecs":
        return f"arn:aws:ecs:{region}:{account_id}:task/{resource_name}"
    elif service == "s3":
        return f"arn:aws:s3:::{resource_name}"
    elif service == "vpc":
        return f"arn:aws:ec2:{region}:{account_id}:natgateway/{resource_name}"
    elif service == "ec2":
        return f"arn:aws:ec2:{region}:{account_id}:instance/{resource_name}"
    return f"arn:aws:{service}:{region}:{account_id}:{resource_name}"


def get_pool_id(cost_type: str) -> str | None:
    if cost_type == "direct":
        return None
    elif cost_type == "shared-platform":
        return random.choice(["P002", "P003"])
    elif cost_type == "unallocable":
        return "P004"


def generate_record(bu_id: str, billing_date: date) -> dict:
    profile = BU_PROFILES[bu_id]
    hygiene = profile["hygiene"]

    # Service
    service = weighted_choice(
        list(profile["service_weights"].keys()),
        list(profile["service_weights"].values()),
    )
    service_profile = SERVICES[service]

    # Cost type
    cost_type = weighted_choice(
        list(service_profile["cost_type_weights"].keys()),
        list(service_profile["cost_type_weights"].values()),
    )

    # Pool ID
    pool_id = get_pool_id(cost_type)

    # Environment
    environment = weighted_choice(
        list(profile["env_weights"].keys()), list(profile["env_weights"].values())
    )

    # Resource identification
    resource_name = f"{bu_id}-{service}-{uuid.uuid4().hex[:8]}"
    resource_arn = generate_resource_arn(service, "848747536965", REGION, resource_name)

    # Usage metrics
    usage_unit = random.choice(service_profile["usage_units"])
    avg_qty = service_profile["avg_quantity"][usage_unit]
    usage_quantity = max(0.01, random.gauss(avg_qty, avg_qty * 0.3))

    # Cost calculation
    cost_per_unit = service_profile["cost_per_unit"][usage_unit]
    total_cost = round(usage_quantity * cost_per_unit, 8)

    # Timestamps — daily billing period
    usage_start = datetime.combine(billing_date, datetime.min.time())
    usage_end = usage_start + timedelta(hours=24)

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

    component = service_profile["component"]

    # Feature is NULL for infra — infra doesn't use features
    feature = None

    return {
        "infra_usage_id": str(uuid.uuid4()),
        "usage_start_time": usage_start,
        "usage_end_time": usage_end,
        "billing_period": billing_date,
        "resource_arn": resource_arn,
        "service": service,
        "region": REGION,
        "cost_type": cost_type,
        "pool_id": pool_id,
        "client_id": client_id,
        "business_unit": business_unit,
        "product": product,
        "component": component,
        "feature": feature,
        "environment": environment,
        "usage_quantity": round(usage_quantity, 4),
        "usage_unit": usage_unit,
        "total_cost": total_cost,
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
INSERT INTO allocation.infra_usage_raw (
    infra_usage_id, usage_start_time, usage_end_time, billing_period,
    resource_arn, service, region, cost_type, pool_id,
    client_id, business_unit, product, component, feature, environment,
    usage_quantity, usage_unit, total_cost
) VALUES %s
ON CONFLICT (infra_usage_id) DO NOTHING;
"""


def insert_batch(cursor, batch: list[dict]):
    values = [
        (
            r["infra_usage_id"],
            r["usage_start_time"],
            r["usage_end_time"],
            r["billing_period"],
            r["resource_arn"],
            r["service"],
            r["region"],
            r["cost_type"],
            r["pool_id"],
            r["client_id"],
            r["business_unit"],
            r["product"],
            r["component"],
            r["feature"],
            r["environment"],
            r["usage_quantity"],
            r["usage_unit"],
            r["total_cost"],
        )
        for r in batch
    ]
    psycopg2.extras.execute_values(cursor, INSERT_SQL, values, page_size=BATCH_SIZE)


# ── Main ──────────────────────────────────────────────────────────


def main():
    print(f"Shared Cost Allocation Engine — Infrastructure Data Generator")
    print(f"Target: {TOTAL_RECORDS:,} records | Batch size: {BATCH_SIZE:,}")
    print(f"Date range: {START_DATE} → {END_DATE}")
    print("=" * 55)

    # Build BU distribution
    bu_weights = [BU_PROFILES[bu]["volume_weight"] for bu in BUSINESS_UNITS]

    # Build date range — one record per resource per day
    date_range = []
    current_date = START_DATE
    while current_date <= END_DATE:
        date_range.append(current_date)
        current_date += timedelta(days=1)

    conn = get_connection()
    cursor = conn.cursor()

    batch = []
    total_inserted = 0
    batch_count = 0

    try:
        for i in range(TOTAL_RECORDS):
            bu_id = weighted_choice(BUSINESS_UNITS, bu_weights)
            billing_date = random.choice(date_range)
            record = generate_record(bu_id, billing_date)
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
        f"✅ Complete — {total_inserted:,} records loaded into allocation.infra_usage_raw"
    )

    # Distribution check
    print("\nRunning distribution check...")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            service,
            cost_type,
            COUNT(*)                               AS record_count,
            ROUND(SUM(total_cost)::numeric, 2)     AS total_cost
        FROM allocation.infra_usage_raw
        GROUP BY service, cost_type
        ORDER BY service, cost_type;
    """)
    rows = cursor.fetchall()
    print(f"\n{'Service':<12} {'Cost Type':<18} {'Records':>10} {'Total Cost':>12}")
    print("-" * 60)
    for row in rows:
        print(f"{row[0]:<12} {row[1]:<18} {row[2]:>10,} ${row[3]:>11}")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
