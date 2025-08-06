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
1.  **Run the tests:**
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

**4. Check Enrollment Status**
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

# **Implementation Instructions: Serverless Enrollment System on AWS**

The goal is to implement the system described in the architecture diagram as a minimalist, serverless application on AWS. The implementation must adhere to the specified component choices and include infrastructure as code for easy deployment and testing.

## **1. Core Architecture & AWS Service Mapping**

Translate the components from the diagram into the following AWS services:

*   **FAST API (API Gateway + Lambda):**
    *   Use **Amazon API Gateway** (HTTP API type for simplicity and cost-effectiveness) to create the public-facing endpoints.
    *   Each API route will trigger a dedicated **AWS Lambda** function written in Python.

*   **Document DB (DynamoDB):**
    *   Use **Amazon DynamoDB** as the NoSQL database.
    *   Create two separate tables:
        1.  `AgeGroupsTable`: To store age group definitions.
        2.  `EnrollmentsTable`: To store enrollment requests and their status.

*   **Enrollment Queue (SQS):**
    *   Use **Amazon SQS (Simple Queue Service)** for the asynchronous processing queue. A standard queue is sufficient.

*   **Enrollment Processor (Lambda):**
    *   Use a separate **AWS Lambda** function for the processor. This function will be triggered by messages arriving in the SQS queue.

## **2. Detailed Component Implementation**

**A. API Layer (API Gateway + Lambda Functions)**

*   **Age Groups API:**
    *   `POST /age-groups`: A Lambda function that creates a new age group.
        *   **Input:** JSON body with `min_age` and `max_age`.
        *   **Action:** Writes the new age group definition to the `AgeGroupsTable`.
        *   **Returns:** The ID of the newly created group.
    *   `GET /age-groups`: A Lambda function that lists all existing age groups.
        *   **Action:** Reads all items from the `AgeGroupsTable`.
        *   **Returns:** A list of age group objects.
    *   `DELETE /age-groups/{id}`: A Lambda function that deletes a specific age group.
        *   **Action:** Deletes the item with the given `{id}` from the `AgeGroupsTable`.
        *   **Returns:** A success message.

*   **Enrollment API:**
    *   `POST /enrollments`: A Lambda function to request a new enrollment.
        *   **Input:** JSON body with `name`, `age`, and `cpf`.
        *   **Action 1 (Validation):** Reads from `AgeGroupsTable` to verify the user's `age` falls within at least one registered age group. If not, return a 400 Bad Request error.
        *   **Action 2 (Create Record):** Writes a new item to the `EnrollmentsTable` with a unique ID and an initial status (e.g., `PENDING`).
        *   **Action 3 (Publish to Queue):** Publishes a message to the SQS `EnrollmentQueue`. The message should contain the `enrollment_id` to be processed.
        *   **Returns:** The `enrollment_id` and a `PENDING` status.
    *   `GET /enrollments/{id}`: A Lambda function to check the status of an enrollment.
        *   **Action:** Reads the item with the given `{id}` from the `EnrollmentsTable`.
        *   **Returns:** The full enrollment object, including its current `status`.

**B. Asynchronous Processor (SQS + Lambda)**

*   **EnrollmentQueue (SQS):**
    *   A standard SQS queue. The Lambda function from `POST /enrollments` will be granted `sqs:SendMessage` permissions to this queue.

*   **EnrollmentProcessor (Lambda):**
    *   This Lambda function will be configured with the `EnrollmentQueue` as its event source (trigger).
    *   **Action 1 (Process):** Upon receiving a message, it extracts the `enrollment_id`.
    *   **Action 2 (Simulate Work):** Implement a `time.sleep(4)` to simulate a real-world workload.
    *   **Action 3 (Update Status):** Updates the corresponding item in the `EnrollmentsTable`, changing its status from `PENDING` to `PROCESSED`.
    *   The Lambda's IAM role must have permissions to read from the SQS queue and write to the `EnrollmentsTable`.

## **3. Infrastructure as Code (IaC)**

*   The entire cloud infrastructure (API Gateway, Lambdas, DynamoDB tables, SQS queue, IAM roles, and permissions) must be defined using AWS SAM.
*   The IaC code should correctly wire the permissions:
    *   API Lambdas need permissions to access their respective DynamoDB tables.
    *   The Enrollment API Lambda needs permission to send messages to the SQS queue.
    *   The Enrollment Processor Lambda needs permission to be invoked by SQS and to write to the Enrollments table.

## **4. Authentication & Testing**

*   **Authentication:** For this POC, implement API Gateway's **API Key** requirement on all endpoints. This is a simple, serverless way to secure the API and is a better practice than hardcoded Basic Auth credentials. The API Key should be passed in the `x-api-key` header.
*   **Integrated Tests:** Create a suite of integrated tests using **Pytest**. These tests should run locally, invoking the Lambda function handlers directly. They should not require deployment to AWS.
    *   Mock AWS services (e.g., using moto or pytest-mock).
    *   Cover the main logic paths: successful age group creation, successful enrollment request, enrollment validation failure, and status check.
