# fargate-compute

This module deploys the reusable Fargate compute plane behind the shared task
SNS topic:

- one ECS cluster
- one Fargate task definition for the worker container
- one worker task role plus one worker execution role
- one CloudWatch Logs group for the worker container
- one image-based launcher Lambda built through `modules/lambda-deploy`
- one FIFO SQS launcher queue subscribed to the task topic
- one Lambda event-source mapping that routes matching `task_type` values from
  the launcher queue into the launcher Lambda

The module stays generic at the worker boundary. Callers provide the worker
container image URI, usually from `modules/container-image`, plus the task queue
and networking details required by the launcher/runtime contract.

## Inputs

- `name_prefix`: lowercase, hyphen-safe prefix used to derive resource names;
  capped at 47 characters so `${name_prefix}-fargate-launcher` stays within the
  Lambda function-name limit
- `workflow_name`: value passed to the worker task definition as
  `WORKFLOW_NAME`
- `task_topic_arn`: ARN of the shared FIFO SNS task topic
- `task_types`: non-empty list of unique `task_type` routing keys that should
  trigger the launcher Lambda
- `task_queue_url`: value passed to the worker task definition as
  `TASK_QUEUE_URL`
- `task_queue_arn`: ARN used for the worker task-role SQS permissions
- `worker_image_uri`: digest-pinned worker container image URI
- `worker_container_name`: ECS container name used in the task definition and
  launcher overrides
- `worker_cpu`: worker task CPU units, default `256`
- `worker_memory`: worker task memory in MiB, default `512`
- `worker_environment`: additional environment variables merged onto the worker
  task definition after the required `WORKFLOW_NAME` and `TASK_QUEUE_URL`
- `worker_additional_policy_statements`: optional extra IAM policy statements
  appended to the worker task role
- `subnet_ids`: non-empty list of subnet IDs passed to the launcher Lambda as
  `SUBNET_IDS`
- `security_group_ids`: non-empty list of security group IDs passed to the
  launcher Lambda as `SECURITY_GROUP_IDS`
- `assign_public_ip`: `ENABLED` or `DISABLED`, default `DISABLED`
- `launcher_timeout`: launcher Lambda timeout in seconds, default `60`
- `launcher_memory_size`: launcher Lambda memory size in MB, default `512`
- `dockerfile_dir`: directory that contains the launcher Lambda `Dockerfile`
- `build_context_dir`: Docker build context directory passed to
  `lambda-deploy`
- `source_hash_paths`: local files and directories whose contents should
  trigger a launcher image rebuild
- `docker_platform`: Docker build platform passed to `lambda-deploy`
- `lambda_architecture`: launcher Lambda architecture passed to
  `lambda-deploy`
- `tags`: tags applied to created resources

Derived resource names:

- `${name_prefix}-cluster`
- `${name_prefix}-worker`
- `${name_prefix}-fargate-launcher`

## Outputs

- `ecs_cluster_name`
- `ecs_cluster_arn`
- `ecs_task_definition_arn`
- `ecs_task_definition_family`
- `worker_log_group_name`
- `launcher_lambda_name`
- `launcher_lambda_arn`
- `launcher_subscription_arn`
- `worker_task_role_arn`
- `worker_execution_role_arn`
- `resolved_image_uri`

## Notes

- The launcher Lambda environment matches the Phase 5 Python contract exactly:
  `ECS_CLUSTER_ARN`, `ECS_TASK_DEFINITION_ARN`, `ECS_CONTAINER_NAME`,
  `SUBNET_IDS`, `SECURITY_GROUP_IDS`, and `ASSIGN_PUBLIC_IP`.
- Because the shared task topic is FIFO, the launcher Lambda is fed through a
  dedicated FIFO SQS subscription queue rather than a direct SNS-to-Lambda
  subscription.
- The worker task definition always includes `WORKFLOW_NAME` and
  `TASK_QUEUE_URL`; task-specific values stay launch-time-only and are injected
  by the launcher through ECS container overrides.
- The module does not own VPC resources. Callers must provide subnet and
  security-group IDs that can run Fargate tasks.
