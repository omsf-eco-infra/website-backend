# orchestration

This module deploys the reusable orchestration control plane for the Phase 2
runtime:

- one S3 bucket for taskdb SQLite snapshots
- one FIFO orchestration SQS queue plus FIFO DLQ
- one FIFO SNS topic for runnable task fanout
- one image-based orchestrator Lambda built through `modules/lambda-deploy`

The deployed Lambda consumes SQS events from the orchestration queue, reopens
task state from S3 using the incoming `graph_id` as the exact object key, and
publishes runnable `TaskMessage` payloads to the shared task topic.

## Inputs

- `name_prefix`: lowercase, hyphen-safe prefix used to derive AWS resource
  names; capped at 51 characters so every derived name stays within AWS limits
- `workflow_name`: value passed to the orchestrator Lambda as
  `WORKFLOW_NAME`
- `state_prefix`: value passed through to the Lambda as `STATE_PREFIX`;
  it exists for future backend conventions, and Phase 3 does not prepend it to
  `graph_id`
- `tags`: tags applied to created resources
- `lambda_timeout`: orchestrator Lambda timeout in seconds
- `lambda_memory_size`: orchestrator Lambda memory size in MB
- `dockerfile_dir`: directory that contains the orchestrator Lambda
  `Dockerfile`
- `build_context_dir`: Docker build context directory passed to
  `lambda-deploy`
- `source_hash_paths`: local files and directories whose contents should
  trigger a Lambda image rebuild
- `docker_platform`: Docker build platform passed to `lambda-deploy`
- `lambda_architecture`: Lambda architecture passed to `lambda-deploy`
- `orchestration_queue_max_receive_count`: SQS retry threshold before a
  message is moved to the orchestration DLQ
- `enable_state_bucket_versioning`: enables S3 versioning on the taskdb bucket;
  disabled by default because the state snapshots are high-churn
- `state_bucket_force_destroy`: allows Terraform to destroy the taskdb bucket
  even when snapshot objects remain; disabled by default for production safety

Derived resource names:

- `${name_prefix}-state`
- `${name_prefix}-orchestration.fifo`
- `${name_prefix}-orchestration-dlq.fifo`
- `${name_prefix}-tasks.fifo`
- `${name_prefix}-orchestrator`

## Outputs

- `orchestration_queue_url`
- `orchestration_queue_arn`
- `orchestration_queue_name`
- `task_topic_arn`
- `task_topic_name`
- `state_bucket_name`
- `state_bucket_arn`
- `orchestrator_lambda_name`
- `orchestrator_lambda_arn`
- `resolved_image_uri`

## Notes

- The orchestrator Lambda runs with reserved concurrency `1` because the
  current S3-backed SQLite implementation assumes a single active writer.
- The orchestration queue uses `batch_size = 1` because the current Lambda
  handler only accepts one SQS record at a time.
- The Lambda role includes `s3:ListBucket` on the state bucket in addition to
  object reads and writes so its initial `HeadObject` checks can distinguish a
  missing snapshot from an access error on a new graph.
- The task SNS topic is FIFO with content-based deduplication. The runtime
  publishes `MessageGroupId = graph_id` so later FIFO task queues can subscribe
  without changing the message contract.
- Bucket versioning is off by default because taskdb snapshots are rewritten
  frequently; callers can enable it explicitly if they need object history for
  recovery or audit purposes.
