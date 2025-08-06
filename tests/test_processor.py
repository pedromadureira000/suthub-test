import os
import json
import boto3
import pytest
from moto import mock_aws
from unittest.mock import patch

# Set environment variables before importing the app module
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
os.environ['AWS_SECURITY_TOKEN'] = 'testing'
os.environ['AWS_SESSION_TOKEN'] = 'testing'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
TABLE_NAME = 'test-enrollments-proc'
os.environ['ENROLLMENTS_TABLE'] = TABLE_NAME

# Now it's safe to import the app
from src.processor import app as processor_app

@pytest.fixture
def dynamodb_table():
    """Create a mock DynamoDB table and patch the app's table object."""
    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name=os.environ['AWS_DEFAULT_REGION'])
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{'AttributeName': 'id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'id', 'AttributeType': 'S'}],
            ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
        )
        # Patch the app's table object to use the mock table
        processor_app.table = table
        yield table

# Mock time.sleep to speed up tests and avoid waiting
@patch('time.sleep', return_value=None)
def test_lambda_handler_success(mock_sleep, dynamodb_table):
    """Test successful processing of an SQS message."""
    enrollment_id = 'proc-id-1'
    dynamodb_table.put_item(Item={
        'id': enrollment_id,
        'name': 'Proc User',
        'age': 50,
        'cpf': '55566677788',
        'status': 'PENDING'
    })

    sqs_event = {
        'Records': [
            {
                'messageId': 'msg1',
                'body': json.dumps({'enrollment_id': enrollment_id})
            }
        ]
    }

    response = processor_app.lambda_handler(sqs_event, None)
    assert response['statusCode'] == 200

    # Verify status was updated in DynamoDB
    item = dynamodb_table.get_item(Key={'id': enrollment_id})['Item']
    assert item['status'] == 'PROCESSED'
    mock_sleep.assert_called_once_with(4)

@patch('time.sleep', return_value=None)
def test_lambda_handler_item_not_found(mock_sleep, dynamodb_table, capsys):
    """Test processing a message for a non-existent enrollment item."""
    enrollment_id = 'non-existent-id'
    sqs_event = {
        'Records': [
            {
                'messageId': 'msg2',
                'body': json.dumps({'enrollment_id': enrollment_id})
            }
        ]
    }

    response = processor_app.lambda_handler(sqs_event, None)
    assert response['statusCode'] == 200

    # Capture stdout to verify error logging
    captured = capsys.readouterr()
    assert f"ERROR: Enrollment ID {enrollment_id} not found in table." in captured.out

@patch('time.sleep', return_value=None)
def test_lambda_handler_bad_message_format(mock_sleep, dynamodb_table, capsys):
    """Test processing a message with invalid JSON."""
    sqs_event_bad_json = {
        'Records': [
            {
                'messageId': 'msg3',
                'body': 'this is not valid json'
            }
        ]
    }
    response = processor_app.lambda_handler(sqs_event_bad_json, None)
    assert response['statusCode'] == 200
    captured = capsys.readouterr()
    assert "ERROR: Could not decode message body for messageId msg3" in captured.out

@patch('time.sleep', return_value=None)
def test_lambda_handler_missing_enrollment_id(mock_sleep, dynamodb_table, capsys):
    """Test processing a message that is missing the 'enrollment_id' key."""
    sqs_event_missing_key = {
        'Records': [
            {
                'messageId': 'msg4',
                'body': json.dumps({'some_other_key': 'some_value'})
            }
        ]
    }
    response = processor_app.lambda_handler(sqs_event_missing_key, None)
    assert response['statusCode'] == 200
    captured = capsys.readouterr()
    # The app code is designed to skip these messages
    assert "Skipping message without enrollment_id: msg4" in captured.out
