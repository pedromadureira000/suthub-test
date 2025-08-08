import json
import os
import uuid
import boto3
from botocore.exceptions import ClientError


if os.environ.get("AWS_SAM_LOCAL"):
    dynamodb = boto3.resource(
        'dynamodb',
        endpoint_url="http://dynamodb-local:8000",
        region_name="us-east-1",
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy"
    )
else:
    dynamodb = boto3.resource('dynamodb')

table = dynamodb.Table(os.environ['AGE_GROUPS_TABLE'])

def create_handler(event, context):
    """
    Creates a new age group.
    Input: {"min_age": 18, "max_age": 25}
    """
    try:
        body = json.loads(event.get('body', '{}'))
        min_age = int(body.get('min_age'))
        max_age = int(body.get('max_age'))

        if not all([isinstance(min_age, int), isinstance(max_age, int), min_age <= max_age]):
            return {'statusCode': 400, 'body': json.dumps({'error': 'Invalid input. min_age and max_age must be integers and min_age <= max_age.'})}

        item_id = str(uuid.uuid4())
        item = {
            'id': item_id,
            'min_age': min_age,
            'max_age': max_age
        }

        table.put_item(Item=item)

        return {
            'statusCode': 201,
            'body': json.dumps({'id': item_id})
        }
    except (ValueError, TypeError, KeyError) as e:
        return {'statusCode': 400, 'body': json.dumps({'error': f'Bad Request: {str(e)}'})}
    except ClientError as e:
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}


def list_handler(event, context):
    """
    Lists all age groups.
    """
    try:
        response = table.scan()
        items = response.get('Items', [])
        # DynamoDB scan returns numbers as Decimal, convert to int for JSON serialization
        for item in items:
            item['min_age'] = int(item['min_age'])
            item['max_age'] = int(item['max_age'])

        return {
            'statusCode': 200,
            'body': json.dumps(items)
        }
    except ClientError as e:
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}


def delete_handler(event, context):
    """
    Deletes a specific age group by its ID.
    """
    try:
        group_id = event.get('pathParameters', {}).get('id')
        if not group_id:
            return {'statusCode': 400, 'body': json.dumps({'error': 'ID is required'})}

        table.delete_item(
            Key={'id': group_id},
            ConditionExpression='attribute_exists(id)'
        )

        return {
            'statusCode': 200,
            'body': json.dumps({'message': f'Age group {group_id} deleted successfully'})
        }
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            return {'statusCode': 404, 'body': json.dumps({'error': 'Item not found'})}
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}
