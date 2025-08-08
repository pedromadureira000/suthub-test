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
    sqs = boto3.client(
        'sqs',
        endpoint_url="http://elasticmq-local:9324",
        region_name="us-east-1",
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy"
    )
else:
    dynamodb = boto3.resource('dynamodb')
    sqs = boto3.client('sqs')

age_groups_table = dynamodb.Table(os.environ['AGE_GROUPS_TABLE'])
enrollments_table = dynamodb.Table(os.environ['ENROLLMENTS_TABLE'])
queue_url = os.environ['ENROLLMENT_QUEUE_URL']

_age_groups_cache = None

def request_handler(event, context):
    """
    Requests a new enrollment.
    Input: {"name": "John Doe", "age": 22, "cpf": "12345678900"}
    """
    global _age_groups_cache
    try:
        body = json.loads(event.get('body', '{}'))
        name = body.get('name')
        age = int(body.get('age'))
        cpf = body.get('cpf')

        if not all([name, isinstance(age, int), cpf]):
            return {'statusCode': 400, 'body': json.dumps({'error': 'Missing required fields: name, age, cpf'})}

        if _age_groups_cache is None:
            print("Age groups cache is empty. Fetching from DynamoDB.")
            response = age_groups_table.scan()
            _age_groups_cache = response.get('Items', [])
        
        is_valid_age = any(int(group['min_age']) <= age <= int(group['max_age']) for group in _age_groups_cache)

        if not is_valid_age:
            return {'statusCode': 400, 'body': json.dumps({'error': 'User age does not fit into any available age group.'})}

        enrollment_id = str(uuid.uuid4())
        enrollment_item = {
            'id': enrollment_id,
            'name': name,
            'age': age,
            'cpf': cpf,
            'status': 'PENDING'
        }

        # 1. Create record in DynamoDB
        enrollments_table.put_item(Item=enrollment_item)

        # 2. Publish message to SQS
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps({'enrollment_id': enrollment_id})
        )

        return {
            'statusCode': 202,
            'body': json.dumps({'enrollment_id': enrollment_id, 'status': 'PENDING'})
        }
    except (ValueError, TypeError, KeyError) as e:
        return {'statusCode': 400, 'body': json.dumps({'error': f'Bad Request: {str(e)}'})}
    except ClientError as e:
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}


def get_status_handler(event, context):
    """
    Checks the status of an enrollment.
    """
    try:
        enrollment_id = event.get('pathParameters', {}).get('id')
        if not enrollment_id:
            return {'statusCode': 400, 'body': json.dumps({'error': 'ID is required'})}

        response = enrollments_table.get_item(Key={'id': enrollment_id})
        item = response.get('Item')

        if not item:
            return {'statusCode': 404, 'body': json.dumps({'error': 'Enrollment not found'})}
        
        # Convert Decimal to int for JSON serialization
        item['age'] = int(item['age'])

        return {
            'statusCode': 200,
            'body': json.dumps(item)
        }
    except ClientError as e:
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}
