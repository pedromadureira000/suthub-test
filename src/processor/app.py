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
