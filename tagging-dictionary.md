# Tagging Dictionary — Shared Cost Allocation Engine
*Project 4 | CostCenter: Project4*

---

## Project Tag Values

| Tag Key | Value |
|---|---|
| `Project` | `shared-cost-allocation` |
| `CostCenter` | `Project4` |
| `Environment` | `dev` |
| `CreatedDate` | Set at resource creation |
| `ManagedBy` | `manual` |
| `Component` | See table below |

**Note:** No `Owner` tag on real AWS resources (single-user account). `CreatedDate` is set at creation only — not applied during remediation.

---

## Component Values by Resource

| Resource Type | Component Value |
|---|---|
| RDS PostgreSQL instance | `database` |
| S3 bucket (CSV exports) | `storage` |
| Lambda (tag audit updates) | `monitoring` |
| IAM roles and policies | `iam` |
| CloudFormation stacks (if used) | `infrastructure` |
| VPC | `infrastructure` |
| Subnet group | `infrastructure`|
| Security group | `infrastructure` |
| Parameter group | `infrastructure` |


---
