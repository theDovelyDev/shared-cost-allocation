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

## Synthetic Dataset Tags
*(Modeled in generated data only — not applied to real AWS resources)*

| Tag Key | Purpose | Example Values |
|---|---|---|
| `Owner` | Business unit owner | `marketing-team`, `eng-team`, `data-science-team`, `cx-team` |
| `Component` | Platform component consuming the API | `inference`, `embedding`, `fine-tuning` |
| `Feature` | Product feature driving API usage | `content-gen`, `search`, `summarization`, `support-bot` |
| `NotSet` | Intentionally null on ~15% of records | Simulates real-world tag hygiene issues |

---

## Tag Hygiene Notes

- `tagged=FALSE` on ~15% of synthetic `api_usage_raw` records — these feed `v_untagged_usage` and drive the tag audit story in the article
- Customer Support BU: heaviest Haiku usage
- Data Science BU: heaviest Sonnet/Opus usage
- All real AWS resources must pass the Lambda tag audit report before phase close

---

## Lambda Tag Audit Filters (add at Phase 1 setup)

```
Filter: Project = shared-cost-allocation
Filter: CostCenter = Project4
Flag: any resource missing Component or CreatedDate
```