import json
import os
import boto3
import pytest
from moto import mock_aws

from src.enrollments import app as enrollments_app

@pytest.fixture
def aws_credentials():
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

@pytest.fixture
def mock_env(aws_credentials, mocker):
    mocker.patch.dict(os.environ, {
        "AGE_GROUPS_TABLE": "test-age-groups",
        "ENROLLMENTS_TABLE": "test-enrollments",
        "ENROLLMENT_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
    })

@pytest.fixture
def mock_aws_services(mock_env):
    with mock_aws():
        dynamodb = boto3.resource("dynamodb")
        dynamodb.create_table(
            TableName="test-age-groups",
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        dynamodb.create_table(
            TableName="test-enrollments",
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        sqs = boto3.client("sqs")
        sqs.create_queue(QueueName="test-queue")
        yield

def test_request_handler_success(mock_aws_services):
    # Setup: Add a valid age group
    age_groups_table = boto3.resource("dynamodb").Table("test-age-groups")
    age_groups_table.put_item(Item={"id": "1", "min_age": 20, "max_age": 30})

    event = {"body": json.dumps({"name": "Jane Doe", "age": 25, "cpf": "11122233344"})}
    response = enrollments_app.request_handler(event, {})

    assert response["statusCode"] == 202
    body = json.loads(response["body"])
    assert "enrollment_id" in body
    assert body["status"] == "PENDING"

    # Verify DynamoDB record
    enrollments_table = boto3.resource("dynamodb").Table("test-enrollments")
    item = enrollments_table.get_item(Key={"id": body["enrollment_id"]})["Item"]
    assert item["name"] == "Jane Doe"
    assert item["status"] == "PENDING"

    # Verify SQS message
    sqs = boto3.client("sqs")
    queue_url = os.environ["ENROLLMENT_QUEUE_URL"]
    messages = sqs.receive_message(QueueUrl=queue_url)["Messages"]
    assert len(messages) == 1
    msg_body = json.loads(messages[0]["Body"])
    assert msg_body["enrollment_id"] == body["enrollment_id"]

def test_request_handler_invalid_age(mock_aws_services):
    age_groups_table = boto3.resource("dynamodb").Table("test-age-groups")
    age_groups_table.put_item(Item={"id": "1", "min_age": 20, "max_age": 30})

    event = {"body": json.dumps({"name": "Old Man", "age": 99, "cpf": "55566677788"})}
    response = enrollments_app.request_handler(event, {})

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "does not fit" in body["error"]

def test_get_status_handler(mock_aws_services):
    enrollments_table = boto3.resource("dynamodb").Table("test-enrollments")
    enrollment_id = "test-id-123"
    enrollments_table.put_item(Item={
        "id": enrollment_id,
        "name": "Test User",
        "age": 42,
        "status": "PENDING"
    })

    event = {"pathParameters": {"id": enrollment_id}}
    response = enrollments_app.get_status_handler(event, {})

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["id"] == enrollment_id
    assert body["status"] == "PENDING"
    assert body["age"] == 42
