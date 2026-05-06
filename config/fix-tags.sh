#!/bin/bash
# Apply standard Project 4 tags to any resource by ARN
# Usage: bash fix-tags.sh <resource-arn> <component-value>
# Example: bash fix-tags.sh arn:aws:s3:::my-bucket container

source config/setup.sh

RESOURCE_ARN=$1
COMPONENT=$2

if [ -z "$RESOURCE_ARN" ] || [ -z "$COMPONENT" ]; then
  echo "❌ Usage: bash fix-tags.sh <resource-arn> <component-value>"
  echo "   Component values: database | storage | monitoring | iam | infrastructure"
  exit 1
fi

echo "🏷️  Applying tags to: ${RESOURCE_ARN}"
echo "   Component: ${COMPONENT}"
echo ""

aws resourcegroupstaggingapi tag-resources \
  --resource-arn-list "${RESOURCE_ARN}" \
  --tags \
    Project="${PROJECT}" \
    CostCenter="${COST_CENTER}" \
    Environment="${ENVIRONMENT}" \
    CreatedDate="${CREATED_DATE}" \
    ManagedBy="${MANAGED_BY}" \
    Component="${COMPONENT}" \
  --region "${REGION}" \
  --profile "${AWS_PROFILE}"

echo ""
echo "✅ Tags applied. Verify with: bash config/verify-tag-audit.sh"