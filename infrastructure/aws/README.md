# Staging Environment Setup on AWS ECS + RDS

> **Note**: The project runs entirely on local Docker Compose during Phases 1-3. This guide applies only when transitioning to cloud hosting in Phase 4 and beyond.

This document outlines the conceptual steps and considerations for deploying the GymGenius application to a staging environment using AWS Elastic Container Service (ECS) and AWS Relational Database Service (RDS) for PostgreSQL.

## Overview

The staging environment aims to replicate the production setup as closely as possible to test new features and changes before they go live. It will consist of:

1.  **AWS ECS**: To run containerized versions of the `engine` (backend API) and `webapp` (frontend).
    *   Each service will have its own Task Definition.
    *   Services will be deployed within a VPC, likely in private subnets.
    *   An Application Load Balancer (ALB) will distribute traffic to the services.
2.  **AWS RDS**: To host the PostgreSQL database.
    *   The RDS instance should be in a private subnet, accessible only by the ECS tasks.
    *   Regular backups and appropriate instance sizing are crucial.
3.  **AWS ECR (Elastic Container Registry)**: To store Docker images for the `engine` and `webapp`.

## Conceptual `docker-compose.staging.yml`

The `docker-compose.staging.yml` file in this directory provides an *illustrative* configuration. It is **not** used directly by ECS but helps conceptualize how services might be defined. In practice, these definitions translate to ECS Task Definitions and Service configurations.

Key differences from local `docker-compose.yml`:
*   **Database**: The `db` service is removed. The `engine` service is configured to connect to an external AWS RDS instance using `DATABASE_URL`.
*   **Image Sources**: Images are pulled from AWS ECR.
*   **Logging**: Configured to use `awslogs` driver to send logs to AWS CloudWatch.
*   **Environment Variables**: Placeholder for production/staging specific configurations and secrets.

## Deployment Steps (Conceptual)

### 1. Prerequisites
*   AWS Account and AWS CLI configured.
*   Docker installed locally for building and pushing images.
*   Application code packaged into Docker images for `engine` and `webapp`.

### 2. AWS ECR (Elastic Container Registry)
*   Create ECR repositories for `gymgenius-engine` and `gymgenius-webapp`.
*   Build Docker images for each service locally.
*   Tag the images appropriately (e.g., `YOUR_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com/gymgenius-engine:staging-latest`).
*   Push the images to their respective ECR repositories.

### 3. AWS RDS (Relational Database Service)
*   Launch a PostgreSQL RDS instance.
    *   **Instance Size**: Choose an appropriate size for staging needs (e.g., `db.t3.micro` or `db.t3.small` to start).
    *   **Storage**: Configure adequate storage with auto-scaling if desired.
    *   **VPC & Subnets**: Place the RDS instance in private subnets within your VPC.
    *   **Security Group**: Create a security group for RDS that only allows inbound PostgreSQL traffic (port 5432) from the ECS services' security group.
    *   **Database Name, User, Password**: Securely note these credentials.
*   Run schema creation scripts (`database/create_schema.py`) and seed data (`database/seed_data.py`) against the staging RDS instance. This might be done via a bastion host, a temporary EC2 instance, or a Lambda function with VPC access.

### 4. AWS ECS (Elastic Container Service)

*   **Create an ECS Cluster**: E.g., `gymgenius-staging-cluster`. Choose the Fargate launch type for serverless container management or EC2 launch type if more control over instances is needed.
*   **Task Definitions**:
    *   Create a Task Definition for the `engine` service:
        *   Link to the ECR image for `gymgenius-engine`.
        *   Define CPU and memory allocations.
        *   Configure port mappings (e.g., map container port 5000).
        *   Set environment variables, including `DATABASE_URL` (pointing to RDS) and `FLASK_ENV=production`. Use AWS Secrets Manager or Parameter Store for sensitive variables like database credentials.
        *   Configure CloudWatch logging.
    *   Create a Task Definition for the `webapp` service:
        *   Link to the ECR image for `gymgenius-webapp`.
        *   Define CPU and memory.
        *   Configure port mappings (e.g., map container port 80).
        *   Set environment variables, like `API_BASE_URL` pointing to the ALB DNS for the engine.
        *   Configure CloudWatch logging.
*   **Application Load Balancer (ALB)**:
    *   Set up an ALB in public subnets.
    *   Configure listeners (e.g., HTTP on port 80, HTTPS on port 443).
    *   Create target groups for `engine` and `webapp` services.
    *   Define routing rules:
        *   Requests to `/api/*` (or a dedicated API subdomain like `api.staging.yourdomain.com`) could route to the `engine` target group.
        *   Default requests (or a web subdomain like `staging.yourdomain.com`) route to the `webapp` target group.
*   **ECS Services**:
    *   Create an ECS Service for `engine`:
        *   Link to the `engine` Task Definition.
        *   Associate with the ALB target group for the engine.
        *   Configure desired task count and auto-scaling policies.
        *   Assign to appropriate VPC subnets and security groups (ensure it can reach RDS and be reached by the ALB).
    *   Create an ECS Service for `webapp`:
        *   Link to the `webapp` Task Definition.
        *   Associate with the ALB target group for the webapp.
        *   Configure desired task count and auto-scaling.
        *   Assign to appropriate VPC subnets and security groups.

### 5. DNS Configuration
*   Configure DNS records (e.g., in Route 53) to point your staging domain(s) to the ALB.

### 6. Secrets Management
*   **AWS Secrets Manager** or **AWS Systems Manager Parameter Store** should be used to store sensitive information like database credentials, API keys, etc.
*   ECS Task Definitions can be configured to inject these secrets as environment variables into the containers.

### 7. Logging and Monitoring
*   **CloudWatch Logs**: Container logs from ECS tasks should be streamed to CloudWatch Logs for debugging and monitoring.
*   **CloudWatch Metrics**: Monitor CPU/memory utilization, ALB request counts, RDS performance, etc.
*   **CloudWatch Alarms**: Set up alarms for critical issues (e.g., high error rates, unhealthy hosts).

### 8. CI/CD Integration
*   The existing GitHub Actions CI workflow (`.github/workflows/ci.yml`) should be extended for deployment to staging.
*   After successful build and test, the CI/CD pipeline should:
    1.  Build and push new Docker images to ECR.
    2.  Update ECS Service definitions to use the new image versions, triggering a new deployment.

## Cost Considerations
*   ECS Fargate pricing is based on vCPU and memory used per second.
*   RDS costs depend on instance type, storage, and data transfer.
*   ALB costs are based on usage hours and LCUs.
*   Data transfer costs can also apply.
*   Use the AWS Pricing Calculator to estimate costs and set up budget alerts.

## Security Best Practices
*   **Principle of Least Privilege**: IAM roles for ECS tasks should have only the necessary permissions.
*   **Security Groups**: Restrict traffic as much as possible (e.g., RDS only accessible from ECS, ALB only allowing HTTP/HTTPS).
*   **VPC Subnets**: Use private subnets for RDS and ECS tasks, public subnets for ALBs.
*   **Secrets Management**: Avoid hardcoding secrets.
*   **Regular Patching/Updates**: Keep Docker images and underlying infrastructure (if using EC2 launch type for ECS) updated.
