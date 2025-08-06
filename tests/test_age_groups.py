import json
import os
import boto3
import pytest
from moto import mock_aws

from src.age_groups import app as age_groups_app

@pytest.fixture
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

@pytest.fixture
def dynamodb_table(aws_credentials, mocker):
    table_name = "test-age-groups-table"
    mocker.patch.dict(os.environ, {"AGE_GROUPS_TABLE": table_name})
    with mock_aws():
        dynamodb = boto3.resource("dynamodb")
        dynamodb.create_table(
            TableName=table_name,
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield dynamodb.Table(table_name)

def test_create_handler_success(dynamodb_table):
    event = {"body": json.dumps({"min_age": 20, "max_age": 30})}
    response = age_groups_app.create_handler(event, {})
    
    assert response["statusCode"] == 201
    body = json.loads(response["body"])
    assert "id" in body
    
    item = dynamodb_table.get_item(Key={"id": body["id"]})["Item"]
    assert item["min_age"] == 20
    assert item["max_age"] == 30

def test_create_handler_bad_request(dynamodb_table):
    event = {"body": json.dumps({"min_age": "twenty"})} # Invalid type
    response = age_groups_app.create_handler(event, {})
    assert response["statusCode"] == 400

def test_list_handler(dynamodb_table):
    dynamodb_table.put_item(Item={"id": "1", "min_age": 10, "max_age": 20})
    dynamodb_table.put_item(Item={"id": "2", "min_age": 21, "max_age": 30})
    
    response = age_groups_app.list_handler({}, {})
    assert response["statusCode"] == 200
    items = json.loads(response["body"])
    assert len(items) == 2
    assert {"id": "1", "min_age": 10, "max_age": 20} in items
    assert {"id": "2", "min_age": 21, "max_age": 30} in items

def test_delete_handler(dynamodb_table):
    dynamodb_table.put_item(Item={"id": "123", "min_age": 10, "max_age": 20})
    
    event = {"pathParameters": {"id": "123"}}
    response = age_groups_app.delete_handler(event, {})
    
    assert response["statusCode"] == 200
    
    item = dynamodb_table.get_item(Key={"id": "123"})
    assert "Item" not in item
