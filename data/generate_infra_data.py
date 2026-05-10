"""
generate_infra_data.py — Shared Cost Allocation Engine
Project 4 | CostCenter: Project4

Generates ~10,000 synthetic infrastructure cost records across 9 months
and loads them into allocation.infra_usage_raw in RDS PostgreSQL.

Infrastructure services: RDS, ECS/Fargate, S3, VPC/Networking, EC2
Cost distribution varies by service (see SERVICES.cost_type_weights)
Infra costs represent ~30-40% of total platform cost (token + infra combined)

Key features:
- Longitudinal resources (50-100 distinct resources reporting daily)
- Environment-based lifecycle distributions
- launch_date tracks when resource was created
- invoice_date = first day of following month
- Dev one-shots biased toward untagged
- Realistic usage patterns per service type
- BU-specific service usage patterns and tag hygiene rates

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
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv("config/.env", override=True)

# ── Config ────────────────────────────────────────────────────────
TOTAL_RESOURCES = 60  # Total distinct longitudinal resources
ONE_SHOT_COUNT = 5  # Dev one-shot resources
BATCH_SIZE = 500
REGION = "us-east-1"
ACCOUNT_ID = "848747536965"

# Date range: Aug 1, 2025 - Apr 30, 2026 (9 months, 273 days)
START_DATE = date(2025, 8, 1)
END_DATE = date(2026, 4, 30)
TOTAL_DAYS = (END_DATE - START_DATE).days + 1


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

# Features from AI platform components (for feature tagging on infra)
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
        "pattern": "steady",
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
        "pattern": "variable",
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
        "pattern": "growing",
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
        "pattern": "steady",
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
        "pattern": "burst",
    },
}

# Service distribution — how many resources per service
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


# ── Helper Functions ──────────────────────────────────────────────


def weighted_choice(options: list, weights: list):
    """Select item from options based on weights."""
    return random.choices(options, weights=weights, k=1)[0]


def maybe_null(value, rate: float):
    """Return value with probability=rate, else None."""
    return value if random.random() < rate else None


def calculate_launch_date(environment: str, reference_date: date) -> date:
    """
    Calculate launch_date based on environment-specific distributions.
    Returns a date between START_DATE and reference_date.
    """
    days_ago_from_ref = (reference_date - START_DATE).days

    if environment == "prod":
        # 72% >= 168 days old, 28% >= 30 days old
        if random.random() < 0.72:
            days_ago = random.randint(168, max(168, days_ago_from_ref))
        else:
            days_ago = random.randint(30, 167)

    elif environment == "si":
        # 55% >= 168 days, 35% 90-167 days, 10% 30-89 days
        rand = random.random()
        if rand < 0.55:
            days_ago = random.randint(168, max(168, days_ago_from_ref))
        elif rand < 0.90:
            days_ago = random.randint(90, 167)
        else:
            days_ago = random.randint(30, 89)

    else:  # dev
        # 9% > 220 days, 15% 120-200 days, 35% 90-119 days,
        # 20% 14-60 days, 20% < 7 days, 1% one-shots (handled separately)
        rand = random.random()
        if rand < 0.09:
            days_ago = random.randint(220, max(220, days_ago_from_ref))
        elif rand < 0.24:
            days_ago = random.randint(120, 200)
        elif rand < 0.59:
            days_ago = random.randint(90, 119)
        elif rand < 0.79:
            days_ago = random.randint(14, 60)
        else:
            days_ago = random.randint(1, 7)

    # Ensure we don't go before START_DATE
    days_ago = min(days_ago, days_ago_from_ref)
    launch_date = reference_date - timedelta(days=days_ago)

    return max(launch_date, START_DATE)


def generate_resource_id(service: str, environment: str, index: int) -> str:
    """Generate realistic AWS resource IDs."""
    suffix = uuid.uuid4().hex[:8]
    if service == "rds":
        return f"db-{environment}-{suffix}"
    elif service == "ecs":
        return f"ecs-task-{environment}-{suffix}"
    elif service == "s3":
        return f"s3-bucket-{environment}-{suffix}"
    elif service == "vpc":
        return f"nat-{environment}-{suffix}"
    elif service == "ec2":
        return f"i-{suffix}"


def generate_resource_arn(service: str, resource_id: str) -> str:
    """Generate realistic AWS ARN."""
    if service == "rds":
        return f"arn:aws:rds:{REGION}:{ACCOUNT_ID}:db:{resource_id}"
    elif service == "ecs":
        return f"arn:aws:ecs:{REGION}:{ACCOUNT_ID}:task/{resource_id}"
    elif service == "s3":
        return f"arn:aws:s3:::{resource_id}"
    elif service == "vpc":
        return f"arn:aws:ec2:{REGION}:{ACCOUNT_ID}:natgateway/{resource_id}"
    elif service == "ec2":
        return f"arn:aws:ec2:{REGION}:{ACCOUNT_ID}:instance/{resource_id}"


def assign_tags(bu_id: str, cost_type: str, hygiene: dict, is_one_shot: bool = False):
    """
    Assign tags based on cost type and hygiene rates.
    One-shots are biased toward untagged (80% chance of NULL tags).
    """
    if is_one_shot and random.random() < 0.80:
        # One-shot untagged
        return {
            "client_id": None,
            "business_unit": None,
            "product": None,
            "feature": None,
        }

    # Direct costs always have a BU
    if cost_type == "direct":
        business_unit = bu_id
    else:
        business_unit = maybe_null(bu_id, hygiene["overall"])

    client_id = maybe_null(f"client_{random.randint(1, 50):03d}", hygiene["client_id"])
    product = (
        maybe_null(random.choice(PRODUCTS[bu_id]), hygiene["product"])
        if business_unit
        else None
    )

    # Feature selection based on component type
    # This will be determined by service, so return None here and set later
    feature = None

    return {
        "client_id": client_id,
        "business_unit": business_unit,
        "product": product,
        "feature": feature,  # Set later based on component
    }


def get_feature_for_component(component: str, hygiene_rate: float):
    """Get feature based on component mapping."""
    component_feature_map = {
        "database": "inference",
        "container": "inference",
        "storage": "vector-store",
        "networking": "gateway",
        "compute": "fine-tuning",
    }

    ai_component = component_feature_map.get(component, "inference")
    feature = (
        random.choice(FEATURES[ai_component]) if ai_component in FEATURES else None
    )
    return maybe_null(feature, hygiene_rate)


def calculate_usage_quantity(
    service: str, usage_unit: str, usage_date: date, launch_date: date, pattern: str
) -> float:
    """Calculate realistic usage quantity based on service type and pattern."""
    days_since_launch = (usage_date - launch_date).days
    service_config = SERVICES[service]
    avg_qty = service_config["avg_quantity"][usage_unit]

    if pattern == "steady":
        # RDS instance_hours, VPC nat_gateway_hours: consistent 24/7
        if usage_unit in ["instance_hours", "nat_gateway_hours"]:
            return 24.0
        # RDS storage_gb: slight growth over time
        elif usage_unit == "storage_gb":
            return avg_qty + (days_since_launch * 0.1)
        # VPC data_transfer_gb: steady with variance
        else:
            return round(random.gauss(avg_qty, avg_qty * 0.2), 2)

    elif pattern == "growing":
        # S3 storage_gb: monotonic growth
        if usage_unit == "storage_gb":
            return avg_qty + (days_since_launch * 5)
        # S3 requests/data_transfer: correlated with storage size
        else:
            growth_factor = 1 + (days_since_launch / 100)
            return round(avg_qty * growth_factor * random.uniform(0.8, 1.2), 2)

    elif pattern == "variable":
        # ECS: weekday/weekend scaling
        is_weekend = usage_date.weekday() >= 5
        base_qty = avg_qty * 0.6 if is_weekend else avg_qty
        return round(base_qty * random.uniform(0.8, 1.2), 4)

    elif pattern == "burst":
        # EC2: batch processing patterns
        is_weekend = usage_date.weekday() >= 5
        if random.random() < 0.30 and not is_weekend:
            return round(random.uniform(8, 12), 2)
        else:
            return round(random.uniform(0.5, 2), 2)

    # Fallback
    return round(random.gauss(avg_qty, avg_qty * 0.3), 4)


def generate_longitudinal_resources() -> list[dict]:
    """Generate distinct resources that will report usage over time."""
    resources = []

    # Calculate resources per service based on weights
    for service, weight in SERVICE_WEIGHTS.items():
        num_resources = int(TOTAL_RESOURCES * weight)
        service_config = SERVICES[service]

        for i in range(num_resources):
            # Select BU based on volume weights
            bu_id = weighted_choice(
                BUSINESS_UNITS,
                [BU_PROFILES[bu]["volume_weight"] for bu in BUSINESS_UNITS],
            )
            profile = BU_PROFILES[bu_id]

            # Environment
            environment = weighted_choice(
                list(profile["env_weights"].keys()),
                list(profile["env_weights"].values()),
            )

            # Cost type
            cost_type = weighted_choice(
                list(service_config["cost_type_weights"].keys()),
                list(service_config["cost_type_weights"].values()),
            )

            # Pool ID
            pool_id = None
            if cost_type == "shared-platform":
                pool_id = random.choice(["P002", "P003"])
            elif cost_type == "unallocable":
                pool_id = "P004"

            # Resource identification
            resource_id = generate_resource_id(service, environment, i)
            resource_arn = generate_resource_arn(service, resource_id)

            # Tags (feature will be set per usage record)
            tags = assign_tags(bu_id, cost_type, profile["hygiene"], is_one_shot=False)

            resource = {
                "resource_id": resource_id,
                "resource_arn": resource_arn,
                "service": service,
                "component": service_config["component"],
                "pattern": service_config["pattern"],
                "environment": environment,
                "cost_type": cost_type,
                "pool_id": pool_id,
                "bu_id": bu_id,
                "tags": tags,
                "hygiene": profile["hygiene"],
                "usage_units": service_config["usage_units"],
                "cost_per_unit": service_config["cost_per_unit"],
                "launch_date": None,  # Set during usage generation
            }

            resources.append(resource)

    return resources


def generate_one_shot_resources() -> list[dict]:
    """Generate dev one-shot resources biased toward untagged."""
    one_shots = []

    for _ in range(ONE_SHOT_COUNT):
        # Random date in the window
        random_days = random.randint(0, TOTAL_DAYS - 1)
        usage_date = START_DATE + timedelta(days=random_days)

        # Bias toward EC2 for batch jobs
        service = (
            "ec2" if random.random() < 0.60 else random.choice(list(SERVICES.keys()))
        )
        service_config = SERVICES[service]

        # Random BU (for hygiene calculation even if tags are NULL)
        bu_id = random.choice(BUSINESS_UNITS)
        profile = BU_PROFILES[bu_id]

        resource_id = generate_resource_id(service, "dev", 999)
        resource_arn = generate_resource_arn(service, resource_id)

        # One-shots are 80% untagged
        tags = assign_tags(bu_id, "unallocable", profile["hygiene"], is_one_shot=True)

        one_shot = {
            "resource_id": resource_id,
            "resource_arn": resource_arn,
            "service": service,
            "component": service_config["component"],
            "environment": "dev",
            "cost_type": "unallocable",
            "pool_id": "P004",
            "tags": tags,
            "usage_date": usage_date,
            "launch_date": usage_date,
            "usage_unit": random.choice(service_config["usage_units"]),
            "usage_quantity": round(random.uniform(2, 8), 2),
            "cost_per_unit": service_config["cost_per_unit"],
        }

        one_shots.append(one_shot)

    return one_shots


# ── Database Insert ───────────────────────────────────────────────

INSERT_SQL = """
INSERT INTO allocation.infra_usage_raw (
    infra_usage_id, usage_start_time, usage_end_time, billing_period,
    resource_arn, service, region, cost_type, pool_id,
    client_id, business_unit, product, component, feature, environment,
    usage_quantity, usage_unit, total_cost, launch_date, invoice_date
) VALUES %s
ON CONFLICT (infra_usage_id) DO NOTHING;
"""


def insert_batch(cursor, batch: list[dict]):
    """Insert batch of records using execute_values."""
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
            r["launch_date"],
            r["invoice_date"],
        )
        for r in batch
    ]
    psycopg2.extras.execute_values(cursor, INSERT_SQL, values, page_size=BATCH_SIZE)


# ── Main ──────────────────────────────────────────────────────────


def main():
    print(f"Shared Cost Allocation Engine — Infrastructure Data Generator")
    print(
        f"Target: {TOTAL_RESOURCES} longitudinal resources + {ONE_SHOT_COUNT} one-shots"
    )
    print(f"Date range: {START_DATE} → {END_DATE} ({TOTAL_DAYS} days)")
    print("=" * 70)

    # Generate base resources
    resources = generate_longitudinal_resources()
    print(f"✓ Generated {len(resources)} longitudinal resources")

    # Generate one-shots
    one_shots = generate_one_shot_resources()
    print(f"✓ Generated {len(one_shots)} one-shot resources")

    # Generate daily usage records for longitudinal resources
    usage_records = []

    for resource in resources:
        # Determine launch date
        resource["launch_date"] = calculate_launch_date(
            resource["environment"], END_DATE
        )

        # Generate daily usage from launch_date through END_DATE
        current_date = resource["launch_date"]

        while current_date <= END_DATE:
            # Each service may have multiple usage_units (RDS has instance_hours + storage_gb)
            for usage_unit in resource["usage_units"]:
                usage_quantity = calculate_usage_quantity(
                    resource["service"],
                    usage_unit,
                    current_date,
                    resource["launch_date"],
                    resource["pattern"],
                )

                unit_cost = resource["cost_per_unit"][usage_unit]
                total_cost = round(
                    Decimal(str(usage_quantity)) * Decimal(str(unit_cost)), 8
                )

                # Calculate invoice_date (first day of following month)
                if current_date.month == 12:
                    invoice_date = date(current_date.year + 1, 1, 1)
                else:
                    invoice_date = date(current_date.year, current_date.month + 1, 1)

                # Set feature based on component
                feature = (
                    get_feature_for_component(
                        resource["component"], resource["hygiene"]["feature"]
                    )
                    if resource["tags"]["business_unit"]
                    else None
                )

                # Usage times
                usage_start = datetime.combine(current_date, datetime.min.time())
                usage_end = usage_start + timedelta(hours=24)

                record = {
                    "infra_usage_id": str(uuid.uuid4()),
                    "usage_start_time": usage_start,
                    "usage_end_time": usage_end,
                    "billing_period": current_date,
                    "resource_arn": resource["resource_arn"],
                    "service": resource["service"],
                    "region": REGION,
                    "cost_type": resource["cost_type"],
                    "pool_id": resource["pool_id"],
                    "client_id": resource["tags"]["client_id"],
                    "business_unit": resource["tags"]["business_unit"],
                    "product": resource["tags"]["product"],
                    "component": resource["component"],
                    "feature": feature,
                    "environment": resource["environment"],
                    "usage_quantity": usage_quantity,
                    "usage_unit": usage_unit,
                    "total_cost": total_cost,
                    "launch_date": resource["launch_date"],
                    "invoice_date": invoice_date,
                }

                usage_records.append(record)

            current_date += timedelta(days=1)

    # Add one-shot records
    for one_shot in one_shots:
        usage_unit = one_shot["usage_unit"]
        unit_cost = one_shot["cost_per_unit"][usage_unit]
        total_cost = round(
            Decimal(str(one_shot["usage_quantity"])) * Decimal(str(unit_cost)), 8
        )

        # Calculate invoice_date
        usage_date = one_shot["usage_date"]
        if usage_date.month == 12:
            invoice_date = date(usage_date.year + 1, 1, 1)
        else:
            invoice_date = date(usage_date.year, usage_date.month + 1, 1)

        usage_start = datetime.combine(usage_date, datetime.min.time())
        usage_end = usage_start + timedelta(hours=24)

        record = {
            "infra_usage_id": str(uuid.uuid4()),
            "usage_start_time": usage_start,
            "usage_end_time": usage_end,
            "billing_period": usage_date,
            "resource_arn": one_shot["resource_arn"],
            "service": one_shot["service"],
            "region": REGION,
            "cost_type": one_shot["cost_type"],
            "pool_id": one_shot["pool_id"],
            "client_id": one_shot["tags"]["client_id"],
            "business_unit": one_shot["tags"]["business_unit"],
            "product": one_shot["tags"]["product"],
            "component": one_shot["component"],
            "feature": one_shot["tags"]["feature"],
            "environment": one_shot["environment"],
            "usage_quantity": one_shot["usage_quantity"],
            "usage_unit": usage_unit,
            "total_cost": total_cost,
            "launch_date": one_shot["launch_date"],
            "invoice_date": invoice_date,
        }

        usage_records.append(record)

    print(f"✓ Generated {len(usage_records):,} total usage records")

    # Calculate summary
    total_cost = sum(float(r["total_cost"]) for r in usage_records)
    print(f"✓ Total infrastructure cost: ${total_cost:,.2f}")

    # Connect and insert
    print("\nConnecting to database...")
    conn = psycopg2.connect(
        host=os.getenv("PGHOST"),
        port=os.getenv("PGPORT", 5432),
        dbname=os.getenv("PGDATABASE"),
        user=os.getenv("PGUSER"),
        password=os.getenv("PGPASSWORD"),
        sslmode="require",
    )

    try:
        cursor = conn.cursor()

        # Clear existing data
        cursor.execute("DELETE FROM allocation.infra_usage_raw")
        conn.commit()
        print("✓ Cleared existing infra usage data")

        # Insert in batches
        batch = []
        total_inserted = 0
        batch_count = 0

        for record in usage_records:
            batch.append(record)

            if len(batch) >= BATCH_SIZE:
                insert_batch(cursor, batch)
                conn.commit()
                total_inserted += len(batch)
                batch_count += 1
                print(
                    f"  Batch {batch_count:>4} | {total_inserted:>9,} records inserted"
                )
                batch = []

        # Final partial batch
        if batch:
            insert_batch(cursor, batch)
            conn.commit()
            total_inserted += len(batch)
            print(f"  Final batch  | {total_inserted:>9,} records inserted")

        cursor.close()
        print("\n" + "=" * 70)
        print(f"✅ Complete — {total_inserted:,} records loaded")
        print(f"   Total cost: ${total_cost:,.2f}")
        print(f"   Date range: {START_DATE} → {END_DATE}")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
