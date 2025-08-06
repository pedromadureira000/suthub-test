import os
import json
import boto3
import pytest
from moto import mock_aws

os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
os.environ['AWS_SECURITY_TOKEN'] = 'testing'
os.environ['AWS_SESSION_TOKEN'] = 'testing'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
TABLE_NAME = 'test-age-groups'
os.environ['AGE_GROUPS_TABLE'] = TABLE_NAME

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
    # The application code has been updated to use a ConditionExpression,
    # which causes a ClientError ('ConditionalCheckFailedException') when the
    # item doesn't exist. The handler correctly catches this and returns 404.
    response = age_groups_app.delete_handler(event, None)
    assert response['statusCode'] == 404
    assert 'Item not found' in json.loads(response['body'])['error']
