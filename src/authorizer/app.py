import os
import base64

def lambda_handler(event, context):
    """
    Lambda Authorizer for Basic Authentication.
    Checks the 'Authorization' header against credentials stored in environment variables.
    """
    print(f"Authorizer event: {event}")

    try:
        expected_user = os.environ['BASIC_AUTH_USERNAME']
        expected_pass = os.environ['BASIC_AUTH_PASSWORD']

        auth_header = event.get('authorizationToken', '')
        if not auth_header.lower().startswith('basic '):
            print("Authorization header is missing or not Basic type")
            return generate_policy('user', 'Deny', event['methodArn'])

        encoded_creds = auth_header.split(' ')[1]
        decoded_creds = base64.b64decode(encoded_creds).decode('utf-8')
        provided_user, provided_pass = decoded_creds.split(':', 1)

        if provided_user == expected_user and provided_pass == expected_pass:
            print("Credentials are valid. Allowing access.")
            return generate_policy(provided_user, 'Allow', event['methodArn'])
        else:
            print("Invalid credentials provided.")
            return generate_policy(provided_user, 'Deny', event['methodArn'])

    except Exception as e:
        print(f"Error in authorizer: {e}")
        return generate_policy('user', 'Deny', event.get('methodArn', '*'))


def generate_policy(principal_id, effect, resource):
    """Helper function to generate an IAM policy."""
    res = resource if resource else '*'
    policy = {
        'principalId': principal_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [{
                'Action': 'execute-api:Invoke',
                'Effect': effect,
                'Resource': res
            }]
        }
    }
    print(f"Generated Policy: {policy}")
    return policy
