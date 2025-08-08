# Serverless Enrollment System POC Documentation

This project is a minimalist Proof of Concept for a serverless enrollment system, built on AWS using the Serverless Application Model (SAM). It supports both local development and production deployments.

## Architecture

![Architecture diagram](architecture-diagram.png)

The system uses API Gateway with a Lambda Authorizer for Basic Authentication, Lambda for compute, SQS for asynchronous processing, and DynamoDB for data storage.

## Prerequisites
*   AWS CLI (configured with `production` and `local` profiles)
*   AWS SAM CLI
*   Python 3.9+
*   Docker

## Local Development Workflow
### 1. Configure AWS Profiles
Ensure your `~/.aws/credentials` and `~/.aws/config` files are set up with `[production]` and `[local]` profiles.
```bash
aws configure --profile local
aws configure --profile production
```

### 2. Start Local AWS Services
This command starts Docker containers for DynamoDB-Local and ElasticMQ (for SQS).
```bash
docker-compose up -d
```
Check logs
```bash
docker logs dynamodb-local
```

### 4. Create Local Resources
Run the provided script to create the DynamoDB tables and SQS queue inside the running Docker containers.
```bash
chmod +x setup-local.sh
./setup-local.sh
```

### 5. Create virtual env and run sam build
```bash
pyenv install 3.9.21
pyenv local 3.9.21
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt # just for linting on code editor

sam build --use-container --profile local --debug
```

### 5. Start the Local API
This command starts a local API Gateway that hot-reloads your Lambda code.
```bash
sam local start-api --env-vars .local.env.json --profile local --docker-network suthub-test_default
```
The API will be available at `http://127.0.0.1:3000`.

### 5. Test the Local API
**1. Create an Age Group**
```bash
curl -X POST \
  http://127.0.0.1:3000/age-groups \
  -u "localadmin:localpassword123" \
  -H "Content-Type: application/json" \
  -d '{"min_age": 18, "max_age": 30}'
```

**2. View All Age Groups**
```bash
curl http://127.0.0.1:3000/age-groups \
  -u "localadmin:localpassword123"
```

**3. Delete an Age Group**
```bash
curl -X DELETE http://127.0.0.1:3000/age-groups/{age_group_id} \
  -u "localadmin:localpassword123"
```

**4. Request an Enrollment**
```bash
curl -X POST \
  http://127.0.0.1:3000/enrollments \
  -u "localadmin:localpassword123" \
  -H "Content-Type: application/json" \
  -d '{"name": "John Doe", "age": 22, "cpf": "12345678900"}'
```

**5. Get queue url**
```bash
aws sqs get-queue-url --queue-name EnrollmentQueue-local --profile local --endpoint-url http://localhost:9324
```

**6. Use the queue url to get event**
```bash
aws sqs receive-message --queue-url {queue_url} --profile local --endpoint-url http://localhost:9324
```

**7. If the event is being successfully returned, save it at event.json file**
```bash
aws sqs receive-message --queue-url {queue_url} --profile local --endpoint-url http://localhost:9324 > event.json
```

**8. Run ProcessEnrollmentFunction using the event at event.json**
```bash
sam local invoke ProcessEnrollmentFunction --env-vars .local.env.json --event event.json --profile local --docker-network suthub-test_default
```

**9. Check Enrollment Status**
```bash
curl http://127.0.0.1:3000/enrollments/4eec8a27-3f45-4095-8a45-463c56cbc023 \
  -u "localadmin:localpassword123"
```

## Production Deployment Workflow

#### 1. Build the Application
```bash
sam build --use-container --profile production
```

#### 2. Deploy to AWS
The guided deploy will prompt you for parameters, including the `BasicAuthUsername` and `BasicAuthPassword` for your production environment.
```bash
sam deploy --guided --config-env production --profile production
```
When prompted:
*   **Stack Name:** `suthub-prod` (or your choice)
*   **AWS Region:** `us-east-1`
*   **Parameter BasicAuthUsername:** Enter your desired production username.
*   **Parameter BasicAuthPassword:** Enter your secure production password.
*   Confirm changes.

Take note of the `ApiEndpoint` from the command's output.

## Cleanup

To delete the production application and all associated AWS resources, run:
```bash
aws cloudformation delete-stack --stack-name suthub-prod --profile production
```

To stop the local services, run:
```bash
docker-compose down
