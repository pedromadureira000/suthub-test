#!/bin/bash
# Script to set up local DynamoDB tables and SQS queue for development

set -e # Exit immediately if a command exits with a non-zero status.

PROFILE="--profile local"
DYNAMODB_ENDPOINT="--endpoint-url http://localhost:8000"
SQS_ENDPOINT="--endpoint-url http://localhost:9324"

echo "--- Creating DynamoDB tables ---"

aws dynamodb create-table \
    $PROFILE $DYNAMODB_ENDPOINT \
    --table-name AgeGroupsTable-local \
    --attribute-definitions AttributeName=id,AttributeType=S \
    --key-schema AttributeName=id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    || echo "Table AgeGroupsTable-local already exists."

aws dynamodb create-table \
    $PROFILE $DYNAMODB_ENDPOINT \
    --table-name EnrollmentsTable-local \
    --attribute-definitions AttributeName=id,AttributeType=S \
    --key-schema AttributeName=id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    || echo "Table EnrollmentsTable-local already exists."

echo "--- DynamoDB tables created/verified ---"
aws dynamodb list-tables $PROFILE $DYNAMODB_ENDPOINT

echo ""
echo "--- Creating SQS queue ---"

aws sqs create-queue \
    $PROFILE $SQS_ENDPOINT \
    --queue-name EnrollmentQueue-local \
    || echo "Queue EnrollmentQueue-local already exists."

echo "--- SQS queue created/verified ---"
aws sqs list-queues $PROFILE $SQS_ENDPOINT

echo ""
echo "Local setup complete!"
