```python
# tests/test_age_groups.py
import os
import json
import boto3
import pytest
from moto import mock_aws

# Set environment variables before importing the app module to prevent initialization errors
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
os.environ['AWS_SECURITY_TOKEN'] = 'testing'
os.environ['AWS_SESSION_TOKEN'] = 'testing'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
TABLE_NAME = 'test-age-groups'
os.environ['AGE_GROUPS_TABLE'] = TABLE_NAME

# Now it's safe to import the app
from src.age_groups import app as age_groups_app

@pytest.fixture
def dynamodb_resource():
    """Mocked DynamoDB resource."""
    with mock_aws():
        yield boto3.resource('dynamodb', region_name=os.environ['AWS_DEFAULT_REGION'])

@pytest.fixture
def age_groups_table(dynamodb_resource):
    """Create a mock DynamoDB table and patch the app's table object."""
    table = dynamodb_resource.create_table(
        TableName=TABLE_NAME,
        KeySchema=[{'AttributeName': 'id', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'id', 'AttributeType': 'S'}],
        ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
    )
    # The app module is already loaded, so we need to patch its 'table' object
    # to use the mock table created in the test setup.
    age_groups_app.table = table
    yield table

def test_create_handler_success(age_groups_table):
    """Test successful creation of an age group."""
    event = {
        'body': json.dumps({'min_age': 20, 'max_age': 30})
    }
    response = age_groups_app.create_handler(event, None)
    body = json.loads(response['body'])

    assert response['statusCode'] == 201
    assert 'id' in body

    item = age_groups_table.get_item(Key={'id': body['id']})['Item']
    assert item['min_age'] == 20
    assert item['max_age'] == 30

def test_create_handler_invalid_input(age_groups_table):
    """Test creation with invalid input (min_age > max_age)."""
    event = {
        'body': json.dumps({'min_age': 30, 'max_age': 20})
    }
    response = age_groups_app.create_handler(event, None)
    assert response['statusCode'] == 400
    assert 'Invalid input' in json.loads(response['body'])['error']

def test_create_handler_bad_request(age_groups_table):
    """Test creation with missing keys."""
    event = {
        'body': json.dumps({'min_age': 30}) # Missing max_age
    }
    response = age_groups_app.create_handler(event, None)
    assert response['statusCode'] == 400
    assert 'Bad Request' in json.loads(response['body'])['error']

def test_list_handler(age_groups_table):
    """Test listing age groups."""
    # Test empty list
    response = age_groups_app.list_handler(None, None)
    assert response['statusCode'] == 200
    assert json.loads(response['body']) == []

    # Add items and test again
    age_groups_table.put_item(Item={'id': '1', 'min_age': 10, 'max_age': 20})
    age_groups_table.put_item(Item={'id': '2', 'min_age': 21, 'max_age': 30})

    response = age_groups_app.list_handler(None, None)
    body = json.loads(response['body'])
    assert response['statusCode'] == 200
    assert len(body) == 2
    # Check if ages are converted to int from Decimal
    assert isinstance(body[0]['min_age'], int)
    assert isinstance(body[0]['max_age'], int)

def test_delete_handler_success(age_groups_table):
    """Test successful deletion of an age group."""
    item_id = 'test-id-to-delete'
    age_groups_table.put_item(Item={'id': item_id, 'min_age': 25, 'max_age': 35})
    event = {
        'pathParameters': {'id': item_id}
    }
    response = age_groups_app.delete_handler(event, None)
    assert response['statusCode'] == 200
    assert 'deleted successfully' in json.loads(response['body'])['message']

    # Verify item is gone
    item_response = age_groups_table.get_item(Key={'id': item_id})
    assert 'Item' not in item_response

def test_delete_handler_not_found(age_groups_table):
    """Test deleting a non-existent item."""
    event = {
        'pathParameters': {'id': 'non-existent-id'}
    }
    # DynamoDB's delete_item is idempotent and doesn't fail if the item
    # doesn't exist (unless a ConditionExpression is used).
    # The app code reflects this by returning 200.
    response = age_groups_app.delete_handler(event, None)
    assert response['statusCode'] == 200
```
```python
# tests/test_enrollments.py
import os
import json
import boto3
import pytest
from moto import mock_aws

# Set environment variables before importing the app module
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
os.environ['AWS_SECURITY_TOKEN'] = 'testing'
os.environ['AWS_SESSION_TOKEN'] = 'testing'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
AGE_GROUPS_TABLE_NAME = 'test-age-groups'
ENROLLMENTS_TABLE_NAME = 'test-enrollments'
QUEUE_NAME = 'test-enrollment-queue'
os.environ['AGE_GROUPS_TABLE'] = AGE_GROUPS_TABLE_NAME
os.environ['ENROLLMENTS_TABLE'] = ENROLLMENTS_TABLE_NAME
# The SQS queue URL will be set dynamically in the fixture

# Now it's safe to import the app
from src.enrollments import app as enrollments_app

@pytest.fixture
def aws_resources():
    """Set up mock AWS resources (SQS, DynamoDB) and patch app-level clients."""
    with mock_aws():
        region = os.environ['AWS_DEFAULT_REGION']
        
        # SQS
        sqs = boto3.client('sqs', region_name=region)
        queue_url = sqs.create_queue(QueueName=QUEUE_NAME)['QueueUrl']
        os.environ['ENROLLMENT_QUEUE_URL'] = queue_url
        enrollments_app.queue_url = queue_url
        enrollments_app.sqs = sqs # Patch the client

        # DynamoDB
        dynamodb = boto3.resource('dynamodb', region_name=region)
        
        # Age Groups Table
        age_groups_table = dynamodb.create_table(
            TableName=AGE_GROUPS_TABLE_NAME,
            KeySchema=[{'AttributeName': 'id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'id', 'AttributeType': 'S'}],
            ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
        )
        enrollments_app.age_groups_table = age_groups_table

        # Enrollments Table
        enrollments_table = dynamodb.create_table(
            TableName=ENROLLMENTS_TABLE_NAME,
            KeySchema=[{'AttributeName': 'id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'id', 'AttributeType': 'S'}],
            ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
        )
        enrollments_app.enrollments_table = enrollments_table
        
        yield sqs, age_groups_table, enrollments_table

def test_request_handler_success(aws_resources):
    """Test a successful enrollment request."""
    sqs, age_groups_table, enrollments_table = aws_resources
    
    # Pre-populate a valid age group
    age_groups_table.put_item(Item={'id': '1', 'min_age': 20, 'max_age': 30})

    event = {
        'body': json.dumps({'name': 'Jane Doe', 'age': 25, 'cpf': '11122233344'})
    }
    response = enrollments_app.request_handler(event, None)
    body = json.loads(response['body'])

    assert response['statusCode'] == 202
    assert body['status'] == 'PENDING'
    enrollment_id = body['enrollment_id']

    # Verify DynamoDB record was created
    item = enrollments_table.get_item(Key={'id': enrollment_id})['Item']
    assert item['name'] == 'Jane Doe'
    assert item['status'] == 'PENDING'

    # Verify SQS message was sent
    messages = sqs.receive_message(QueueUrl=os.environ['ENROLLMENT_QUEUE_URL'])['Messages']
    assert len(messages) == 1
    message_body = json.loads(messages[0]['Body'])
    assert message_body['enrollment_id'] == enrollment_id

def test_request_handler_invalid_age(aws_resources):
    """Test an enrollment request where age is outside any defined group."""
    _, age_groups_table, _ = aws_resources
    age_groups_table.put_item(Item={'id': '1', 'min_age': 20, 'max_age': 30})

    event = {
        'body': json.dumps({'name': 'Old Man', 'age': 99, 'cpf': '11122233344'})
    }
    response = enrollments_app.request_handler(event, None)
    assert response['statusCode'] == 400
    assert 'age does not fit' in json.loads(response['body'])['error']

def test_request_handler_missing_fields(aws_resources):
    """Test an enrollment request with missing required fields."""
    event = {
        'body': json.dumps({'name': 'Jane Doe', 'age': 25}) # Missing CPF
    }
    response = enrollments_app.request_handler(event, None)
    assert response['statusCode'] == 400
    assert 'Missing required fields' in json.loads(response['body'])['error']

def test_get_status_handler_success(aws_resources):
    """Test successfully retrieving an enrollment status."""
    _, _, enrollments_table = aws_resources
    enrollment_id = 'test-id-123'
    enrollment_item = {
        'id': enrollment_id,
        'name': 'Test User',
        'age': 42,
        'cpf': '98765432100',
        'status': 'PROCESSED'
    }
    enrollments_table.put_item(Item=enrollment_item)

    event = {'pathParameters': {'id': enrollment_id}}
    response = enrollments_app.get_status_handler(event, None)
    body = json.loads(response['body'])

    assert response['statusCode'] == 200
    assert body['id'] == enrollment_id
    assert body['status'] == 'PROCESSED'
    assert body['age'] == 42 # Check for int conversion from Decimal

def test_get_status_handler_not_found(aws_resources):
    """Test retrieving a non-existent enrollment."""
    event = {'pathParameters': {'id': 'non-existent-id'}}
    response = enrollments_app.get_status_handler(event, None)
    assert response['statusCode'] == 404
    assert 'Enrollment not found' in json.loads(response['body'])['error']
```
```python
# tests/test_processor.py
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
```
