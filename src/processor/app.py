import json
import os
import time
import boto3
from botocore.exceptions import ClientError

AWS_SAM_LOCAL = os.environ.get("AWS_SAM_LOCAL")

if AWS_SAM_LOCAL:
    dynamodb = boto3.resource(
        'dynamodb',
        endpoint_url="http://dynamodb-local:8000",
        region_name="us-east-1",
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy"
    )
else:
    dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['ENROLLMENTS_TABLE'])

def lambda_handler(event, context):
    """
    Processes enrollment messages from SQS.
    """
    # The event will be some changes in the field names when manually invoking the function when testing locally versus how the AWS Lambda service invokes it in production with the SQS trigger
    event_messages = event['Messages'] if AWS_SAM_LOCAL else event['Records']
    event_msg_body_key = 'Body' if AWS_SAM_LOCAL else 'body'
    event_msg_id_key = 'MessageId' if AWS_SAM_LOCAL else 'messageId'

    batch_item_failures = []
    items_successfully_processed = []

    for record in event_messages:
        enrollment_id = None
        message_id = record.get(event_msg_id_key)
        try:
            message_body = json.loads(record[event_msg_body_key])
            enrollment_id = message_body.get('enrollment_id')

            if not enrollment_id:
                print(f"Skipping message without enrollment_id: {message_id}")
                continue

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
            items_successfully_processed.append({"enrollment_id": enrollment_id})
            print(f"▶️"*16, f"Successfully processed enrollment_id: {enrollment_id}")
        except json.JSONDecodeError as e:
            print(f"▶️"*16, f"ERROR: Could not decode message body for messageId {message_id}. Error: {e}")
            if message_id:
                batch_item_failures.append({"itemIdentifier": message_id})
        except KeyError as e:
            print(f"▶️"*16, f"ERROR: Missing key in message for messageId {message_id}. Error: {e}")
            if message_id:
                batch_item_failures.append({"itemIdentifier": message_id})
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                print(f"▶️"*16, f"ERROR: Enrollment ID {enrollment_id} not found in table.")
            else:
                print(f"▶️"*16, f"ERROR: Boto3 client error processing messageId {message_id}. Error: {e}")
            if message_id:
                batch_item_failures.append({"itemIdentifier": message_id})
        except Exception as e:
            print(f"▶️"*16, f"FATAL: An unexpected error occurred processing messageId {message_id}. Error: {e}")
            if message_id:
                batch_item_failures.append({"itemIdentifier": message_id})

    return {'statusCode': 200, 'body': json.dumps({"itemsSuccessfullyProcessed": items_successfully_processed, "batchItemFailures": batch_item_failures})}
