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
# Set a dummy value for the queue URL before importing the app.
# The app module reads this environment variable upon import.
# The actual value will be set and patched in the aws_resources fixture.
os.environ['ENROLLMENT_QUEUE_URL'] = 'dummy-queue-url-for-import'


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
        # Update the environment variable and the app's module-level variable with the real mock URL
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
