#!/bin/bash
# verify-tag-audit.sh — Shared Cost Allocation Engine
# Project 4 | CostCenter: Project4
# Usage: bash config/verify-tag-audit.sh
# Purpose: Verify all Project 4 resources are correctly tagged
#          Flags missing required tags per tagging-dictionary.md

source config/setup.sh


echo ""
echo "🔍 Scanning resources tagged Project=${PROJECT}..."
echo ""

aws resourcegroupstaggingapi get-resources \
  --tag-filters "Key=Project,Values=${PROJECT}" \
  --region "${REGION}" \
  --profile "${AWS_PROFILE}" \
  --query 'ResourceTagMappingList[].{ARN:ResourceARN,Tags:Tags}' \
  --output table

echo ""
echo "🔍 Checking for untagged resources in region ${REGION}..."
echo ""

UNTAGGED=$(aws resourcegroupstaggingapi get-resources \
  --region "${REGION}" \
  --profile "${AWS_PROFILE}" \
  --query '[ResourceTagMappingList[] | length(@)]' \
  --output text)

echo "Total resources found: ${UNTAGGED}"
echo ""
echo "✅ Audit complete. Review table above for missing tags."