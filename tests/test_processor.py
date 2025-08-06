import json
import os
import boto3
import pytest
from moto import mock_aws

from src.processor import app as processor_app

@pytest.fixture
def aws_credentials():
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

@pytest.fixture
def mock_enrollments_table(aws_credentials, mocker):
    table_name = "test-enrollments-proc"
    mocker.patch.dict(os.environ, {"ENROLLMENTS_TABLE": table_name})
    with mock_aws():
        dynamodb = boto3.resource("dynamodb")
        dynamodb.create_table(
            TableName=table_name,
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield dynamodb.Table(table_name)

def test_processor_handler(mock_enrollments_table):
    # Setup: Create a PENDING enrollment
    enrollment_id = "proc-id-456"
    mock_enrollments_table.put_item(Item={
        "id": enrollment_id,
        "name": "To Be Processed",
        "age": 33,
        "status": "PENDING"
    })

    # Create a mock SQS event
    sqs_event = {
        "Records": [
            {
                "messageId": "msg1",
                "receiptHandle": "handle1",
                "body": json.dumps({"enrollment_id": enrollment_id}),
                "attributes": {},
                "messageAttributes": {},
                "md5OfBody": "...",
                "eventSource": "aws:sqs",
                "eventSourceARN": "arn:aws:sqs:us-east-1:123456789012:MyQueue",
                "awsRegion": "us-east-1",
            }
        ]
    }

    # Mock time.sleep to speed up the test
    with pytest.MonkeyPatch.context() as m:
        m.setattr(processor_app.time, 'sleep', lambda s: None)
        response = processor_app.lambda_handler(sqs_event, {})

    assert response["statusCode"] == 200

    # Verify the status was updated in DynamoDB
    item = mock_enrollments_table.get_item(Key={"id": enrollment_id})["Item"]
    assert item["status"] == "PROCESSED"
