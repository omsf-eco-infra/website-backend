# task-queue

This module deploys a reusable FIFO SQS worker lane behind the shared task SNS
topic:

- one FIFO SQS queue for task delivery
- one FIFO SQS dead-letter queue with redrive configuration
- one queue policy that allows only the configured task topic to publish
- one SNS subscription with raw delivery and `task_type` filter routing

The module keeps worker-specific routing details out of downstream compute
modules. Callers provide the shared task topic ARN plus the `task_type` values
that should land in this queue.

## Inputs

- `name_prefix`: lowercase, hyphen-safe prefix used to derive queue names;
  capped at 65 characters so every derived SQS name stays within AWS limits
- `task_topic_arn`: ARN of the shared FIFO SNS task topic
- `task_types`: non-empty list of unique `task_type` routing keys accepted by
  this queue
- `task_queue_max_receive_count`: SQS retry threshold before a message is moved
  to the DLQ
- `queue_visibility_timeout_seconds`: SQS visibility timeout for the main queue
- `tags`: tags applied to created resources

Derived resource names:

- `${name_prefix}-queue.fifo`
- `${name_prefix}-queue-dlq.fifo`

## Outputs

- `task_queue_url`
- `task_queue_arn`
- `task_queue_name`
- `task_queue_dlq_url`
- `task_queue_dlq_arn`
- `task_queue_dlq_name`
- `subscription_arn`

## Notes

- The SNS subscription uses `raw_message_delivery = true` so queue consumers
  receive canonical `TaskMessage` JSON bodies instead of SNS envelopes.
- Routing uses the SNS `task_type` message attribute, matching the shared AWS
  transport conventions documented in `PLAN.md`.
- The queue policy is intentionally narrow: only `sns.amazonaws.com` publishing
  from the configured topic ARN is allowed.
