# Serverless Enrollment System POC

This project is a minimalist Proof of Concept for a serverless enrollment system, built on AWS using the Serverless Application Model (SAM).

## Architecture

![Architecture diagram](architecture-diagram.png)

The system uses API Gateway for REST endpoints, Lambda for compute, SQS for asynchronous processing, and DynamoDB for data storage.

## Prerequisites

*   AWS CLI
*   AWS SAM CLI
*   Python 3.9+
*   Docker (for local testing with `sam local invoke`)

## Project Structure

```
.
├── src
│   ├── age_groups         # Lambda code for age group functions
│   │   └── app.py
│   ├── enrollments        # Lambda code for enrollment request function
│   │   └── app.py
│   └── processor          # Lambda code for the enrollment processor
│       └── app.py
├── tests
│   ├── test_age_groups.py
│   ├── test_enrollments.py
│   └── test_processor.py
├── template.yaml          # AWS SAM template
├── requirements.txt       # Python dependencies
└── README.md
```

## Deployment

1.  **Build the application:** This command compiles your code and prepares it for deployment.
    ```bash
    sam build
    ```

2.  **Deploy to AWS:** The guided deploy will prompt you for parameters like a stack name and AWS region.
    ```bash
    sam deploy --guided
    ```
    Take note of the API Gateway endpoint URL and the API Key from the command's output.

## Running Tests
1.  **Install dependencies:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```
2.  **Run the tests:**
    ```bash
    pytest
    ```

## API Usage

Replace `YOUR_API_ENDPOINT_URL` and `YOUR_API_KEY` with the values from the deployment output.

**1. Create an Age Group**
```bash
curl -X POST \
  https://{YOUR_API_ENDPOINT_URL}/age-groups \
  -H "Content-Type: application/json" \
  -H "x-api-key: {YOUR_API_KEY}" \
  -d '{"min_age": 18, "max_age": 25}'
```

**2. View All Age Groups**
```bash
curl https://{YOUR_API_ENDPOINT_URL}/age-groups \
  -H "x-api-key: {YOUR_API_KEY}"
```

**3. Delete an Age Group**
```bash
curl -X DELETE https://{YOUR_API_ENDPOINT_URL}/age-groups/{age_group_id} \
  -H "x-api-key: {YOUR_API_KEY}"
```

**4. Request an Enrollment**
```bash
curl -X POST \
  https://{YOUR_API_ENDPOINT_URL}/enrollments \
  -H "Content-Type: application/json" \
  -H "x-api-key: {YOUR_API_KEY}" \
  -d '{"name": "John Doe", "age": 22, "cpf": "12345678900"}'
```
*(Save the returned `enrollment_id`)*

**5. Check Enrollment Status**
Wait a few seconds for the processor to run, then check the status.
```bash
curl https://{YOUR_API_ENDPOINT_URL}/enrollments/{enrollment_id} \
  -H "x-api-key: {YOUR_API_KEY}"
```

## Cleanup

To delete the application and all associated AWS resources, run the following command, replacing `<stack-name>` with the name you provided during deployment.

```bash
aws cloudformation delete-stack --stack-name <stack-name>
```

# Code
age_groups/app.py
```python
import json
import os
import uuid
import boto3
from botocore.exceptions import ClientError

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

        table.delete_item(Key={'id': group_id})

        return {
            'statusCode': 200,
            'body': json.dumps({'message': f'Age group {group_id} deleted successfully'})
        }
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            return {'statusCode': 404, 'body': json.dumps({'error': 'Item not found'})}
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}
```

enrollments/app.py
```python
import json
import os
import uuid
import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb')
sqs = boto3.client('sqs')

age_groups_table = dynamodb.Table(os.environ['AGE_GROUPS_TABLE'])
enrollments_table = dynamodb.Table(os.environ['ENROLLMENTS_TABLE'])
queue_url = os.environ['ENROLLMENT_QUEUE_URL']

def request_handler(event, context):
    """
    Requests a new enrollment.
    Input: {"name": "John Doe", "age": 22, "cpf": "12345678900"}
    """
    try:
        body = json.loads(event.get('body', '{}'))
        name = body.get('name')
        age = int(body.get('age'))
        cpf = body.get('cpf')

        if not all([name, isinstance(age, int), cpf]):
            return {'statusCode': 400, 'body': json.dumps({'error': 'Missing required fields: name, age, cpf'})}

        # Validate age against registered age groups
        response = age_groups_table.scan()
        age_groups = response.get('Items', [])
        is_valid_age = any(int(group['min_age']) <= age <= int(group['max_age']) for group in age_groups)

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
```

processor/app.py
```python
import json
import os
import time
import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['ENROLLMENTS_TABLE'])

def lambda_handler(event, context):
    """
    Processes enrollment messages from SQS.
    """
    for record in event['Records']:
        try:
            message_body = json.loads(record['body'])
            enrollment_id = message_body.get('enrollment_id')

            if not enrollment_id:
                print(f"Skipping message without enrollment_id: {record['messageId']}")
                continue

            print(f"Processing enrollment_id: {enrollment_id}")

            # Simulate a real-world workload
            time.sleep(4)

            # Update the enrollment status in DynamoDB
            table.update_item(
                Key={'id': enrollment_id},
                UpdateExpression='SET #status = :status',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={':status': 'PROCESSED'},
                ConditionExpression='attribute_exists(id)'
            )

            print(f"Successfully processed enrollment_id: {enrollment_id}")

        except json.JSONDecodeError as e:
            print(f"ERROR: Could not decode message body for messageId {record.get('messageId')}. Error: {e}")
        except KeyError as e:
            print(f"ERROR: Missing key in message body for messageId {record.get('messageId')}. Error: {e}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                print(f"ERROR: Enrollment ID {enrollment_id} not found in table.")
            else:
                print(f"ERROR: Boto3 client error processing messageId {record.get('messageId')}. Error: {e}")
        except Exception as e:
            print(f"FATAL: An unexpected error occurred processing messageId {record.get('messageId')}. Error: {e}")
            # Re-raise the exception to signal failure to SQS, so it can be retried or sent to a DLQ
            raise e

    return {'statusCode': 200, 'body': json.dumps('Processing complete')}
```

template.yaml:
```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: >
  serverless-enrollment-poc

  A minimalist Proof of Concept for a serverless enrollment system.

Globals:
  Function:
    Timeout: 10
    MemorySize: 128
    Runtime: python3.9
    Environment:
      Variables:
        AGE_GROUPS_TABLE: !Ref AgeGroupsTable
        ENROLLMENTS_TABLE: !Ref EnrollmentsTable
        ENROLLMENT_QUEUE_URL: !Ref EnrollmentQueue

Resources:
  # API Gateway HTTP API
  EnrollmentsApi:
    Type: AWS::Serverless::HttpApi
    Properties:
      Auth:
        ApiKeyRequired: true
        DefaultAuthorizer: AWS_IAM # This is a placeholder, actual API key auth is managed by Usage Plan
      UsagePlan:
        CreateUsagePlan: PER_API
        UsagePlanName: EnrollmentSystemUsagePlan
        Description: Usage plan for the Enrollment System API

  # DynamoDB Tables
  AgeGroupsTable:
    Type: AWS::DynamoDB::Table
    Properties:
      AttributeDefinitions:
        - AttributeName: id
          AttributeType: S
      KeySchema:
        - AttributeName: id
          KeyType: HASH
      BillingMode: PAY_PER_REQUEST

  EnrollmentsTable:
    Type: AWS::DynamoDB::Table
    Properties:
      AttributeDefinitions:
        - AttributeName: id
          AttributeType: S
      KeySchema:
        - AttributeName: id
          KeyType: HASH
      BillingMode: PAY_PER_REQUEST

  # SQS Queue
  EnrollmentQueue:
    Type: AWS::SQS::Queue

  # --- Lambda Functions ---

  # Age Group Functions
  CreateAgeGroupFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/age_groups/
      Handler: app.create_handler
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref AgeGroupsTable
      Events:
        ApiEvent:
          Type: HttpApi
          Properties:
            Path: /age-groups
            Method: POST
            ApiId: !Ref EnrollmentsApi

  ListAgeGroupsFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/age_groups/
      Handler: app.list_handler
      Policies:
        - DynamoDBReadPolicy:
            TableName: !Ref AgeGroupsTable
      Events:
        ApiEvent:
          Type: HttpApi
          Properties:
            Path: /age-groups
            Method: GET
            ApiId: !Ref EnrollmentsApi

  DeleteAgeGroupFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/age_groups/
      Handler: app.delete_handler
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref AgeGroupsTable
      Events:
        ApiEvent:
          Type: HttpApi
          Properties:
            Path: /age-groups/{id}
            Method: DELETE
            ApiId: !Ref EnrollmentsApi

  # Enrollment Functions
  RequestEnrollmentFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/enrollments/
      Handler: app.request_handler
      Policies:
        - DynamoDBReadPolicy:
            TableName: !Ref AgeGroupsTable
        - DynamoDBCrudPolicy:
            TableName: !Ref EnrollmentsTable
        - SQSSendMessagePolicy:
            QueueName: !GetAtt EnrollmentQueue.QueueName
      Events:
        ApiEvent:
          Type: HttpApi
          Properties:
            Path: /enrollments
            Method: POST
            ApiId: !Ref EnrollmentsApi

  GetEnrollmentFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/enrollments/
      Handler: app.get_status_handler
      Policies:
        - DynamoDBReadPolicy:
            TableName: !Ref EnrollmentsTable
      Events:
        ApiEvent:
          Type: HttpApi
          Properties:
            Path: /enrollments/{id}
            Method: GET
            ApiId: !Ref EnrollmentsApi

  # Processor Function
  ProcessEnrollmentFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/processor/
      Handler: app.lambda_handler
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref EnrollmentsTable
      Events:
        SQSEvent:
          Type: SQS
          Properties:
            Queue: !GetAtt EnrollmentQueue.Arn
            BatchSize: 1

Outputs:
  ApiEndpoint:
    Description: "API Gateway endpoint URL"
    Value: !Sub "https://${EnrollmentsApi}.execute-api.${AWS::Region}.amazonaws.com"
  ApiKey:
    Description: "API Key for the Enrollment System API"
    Value: !Ref EnrollmentsApiApiKey
```

# Task
Make a code analysis, looking for errors in the code, or in the project as a whole.
