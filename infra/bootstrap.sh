#!/usr/bin/env bash
set -euo pipefail

BUCKET="dockship-tfstate-$RANDOM$RANDOM"
REGION="${AWS_REGION:-ap-south-1}"

aws s3api create-bucket \
  --bucket "$BUCKET" \
  --region "$REGION" \
  --create-bucket-configuration "LocationConstraint=$REGION"
aws s3api put-bucket-versioning \
  --bucket "$BUCKET" \
  --versioning-configuration Status=Enabled
aws s3api put-public-access-block \
  --bucket "$BUCKET" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

printf 'Set backend bucket to: %s\n' "$BUCKET"
