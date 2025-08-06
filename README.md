# Serverless Enrollment System POC

This project is a minimalist Proof of Concept for a serverless enrollment system, built on AWS using the Serverless Application Model (SAM).

## Architecture

![Architecture diagram](architecture-diagram.png)

The system uses API Gateway for REST endpoints, Lambda for compute, SQS for asynchronous processing, and DynamoDB for data storage.

## Prerequisites
*   AWS CLI
*   AWS SAM CLI
*   Python 3.9+
*   Docker

## Project Structure
```
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
│   ├── test_processor.py
│   └── requirements.txt   # Test-specific Python dependencies
├── pytest.ini
├── template.yaml          # AWS SAM template
├── README.md
├── samconfig.toml
└── docker-compose.yml
```

## Installing Prerequisites on Arch Linux

1. Install AWS CLI
    ```bash
    sudo pacman -S aws-cli
    ```
2. Get you AWS Access Key ID.
    1. Go to IAM menu
    2. Ceate a user with 'AdministratorAccess' policy. (In production it should have more restrict permissions)
    3. Selecte the IAM user and create an Access key
        - You can select use case 'Command Line Interface (CLI)'

3. After installation, configure your AWS credentials:
    ```bash
    aws configure
    ```
    * it will ask for:
        - AWS Access Key ID: This identifies your AWS user or role.
        - AWS Secret Access Key: This is the corresponding secret key that authenticates your Access Key ID.
        - Default Region Name: This specifies the AWS region you primarily want to interact with (e.g., us-east-1, eu-west-2).
        - Default Output Format: This determines how the AWS CLI displays the results of commands (e.g., json, text, table).
    * This stores your credentials in:
        - `~/.aws/credentials`
        - `~/.aws/config`
    * Test if it worked
    ```bash
    aws sts get-caller-identity
    ```
4. Install SAM CLI
    *  [Tutorial](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
    * For Linux
        1. Download the AWS SAM CLI .zip file in the tutorial.
        2. Unzip it
            ```bash
            unzip aws-sam-cli-linux-x86_64.zip -d sam-installation
            ```
        3. Install the AWS SAM CLI
            ```bash
            sudo ./sam-installation/install
            ```
        4. Verify the installation.
            ```bash
            sam --version
            ```

## Deployment

1.  **Build the application:** This command compiles your code and prepares it for deployment.
    ```bash
    sam build --use-container
    ```

2.  **Deploy to AWS:** The guided deploy will prompt you for parameters like a stack name and AWS region.
    ```bash
    sam deploy --guided
    ```
    Take note of the API Gateway endpoint URL and the API Key from the command's output.

3. **Get the API key (x-api-key header)**
    * Go to 'API Gateway' menu
    * On the left navigation pane, click on **Usage Plans**.
    * You should see a usage plan created by SAM. Its name will be based on your stack and resource name, something like `suthub-EnrollmentsApiUsagePlan-XXXXXXXXXX`. Click on it.
    *  Inside the usage plan, click at Associated API Keys.
    * Copy the 'API key'

4. **If you need to rebuild**
    ```bash
    sam build --use-container
    sam deploy
    ```

## Running Tests
1.  **Install dependencies:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate && sudo systemctl start docker
    pip install -r test/requirements.txt
    ```
2.  **Run the tests:**
    ```bash
    pytest -v
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

# More about AWS CLI
## **Basic AWS CLI Usage**

Here are some common commands to try:

### List all S3 buckets:

```bash
aws s3 ls
```

### List all EC2 instances:

```bash
aws ec2 describe-instances
```

### Check current IAM user:

```bash
aws iam get-user
```

### Upload a file to S3:

```bash
aws s3 cp myfile.txt s3://my-bucket-name/
```

### Download a file from S3:

```bash
aws s3 cp s3://my-bucket-name/myfile.txt .
```

---

## Other things

* You can have multiple profiles using `--profile`, e.g.:

  ```bash
  aws s3 ls --profile my-other-account
  ```

* You can override the region and output with flags:

  ```bash
  aws s3 ls --region us-west-2 --output table
  ```
