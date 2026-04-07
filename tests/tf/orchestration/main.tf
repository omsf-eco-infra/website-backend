terraform {
  required_version = ">= 1.11.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }
}

provider "aws" {}

variable "owner" {
  type    = string
  default = "local"
}

locals {
  artifacts_root = abspath("${path.module}/../../../.tf-test-artifacts")
  repo_root      = abspath("${path.root}/../../..")
  test_name      = "orchestration"

  owner_segments  = regexall("[a-z0-9-]+", lower(var.owner))
  owner_joined    = length(local.owner_segments) > 0 ? join("-", local.owner_segments) : "local"
  owner_sanitized = substr(local.owner_joined, 0, 12)
  run_suffix      = substr(md5("${plantimestamp()}-${path.module}-${var.owner}"), 0, 8)
  run_id          = "${local.owner_sanitized}-${local.run_suffix}"
  created_at      = timestamp()
  expires_at      = timeadd(local.created_at, "24h")

  name_prefix    = "wb-orch-${local.owner_sanitized}-${local.run_suffix}"
  graph_id       = "runs/${local.run_id}/taskdb.sqlite"
  observer_queue = "${local.name_prefix}-observer.fifo"

  contract_version = jsondecode(
    file("${local.repo_root}/examples/payloads/orchestration_message.add_tasks.valid.json")
  ).version

  common_tags = {
    managed_by = "test-website-backend"
    repo       = "website-backend"
    module     = local.test_name
    test_name  = local.test_name
    owner      = local.owner_sanitized
    run_id     = local.run_id
    created_at = local.created_at
    expires_at = local.expires_at
  }

  add_tasks_payload = {
    version      = local.contract_version
    graph_id     = local.graph_id
    message_type = "ADD_TASKS"
    details = {
      tasks = [
        {
          task_id      = "task-a"
          requirements = []
          max_tries    = 1
          task_type    = "prepare_inputs"
          details = {
            stage = "a"
          }
        },
        {
          task_id      = "task-b"
          requirements = []
          max_tries    = 1
          task_type    = "stage_inputs"
          details = {
            stage = "b"
          }
        },
        {
          task_id      = "task-c"
          requirements = ["task-a", "task-b"]
          max_tries    = 1
          task_type    = "collect_outputs"
          details = {
            stage = "c"
          }
        },
      ]
    }
  }

  task_a_completed_payload = {
    version      = local.contract_version
    graph_id     = local.graph_id
    message_type = "TASK_COMPLETED"
    details = {
      task_id = "task-a"
    }
  }

  task_b_completed_payload = {
    version      = local.contract_version
    graph_id     = local.graph_id
    message_type = "TASK_COMPLETED"
    details = {
      task_id = "task-b"
    }
  }
}

module "module_under_test" {
  source = "../../../modules/orchestration"

  name_prefix       = local.name_prefix
  workflow_name     = "example-workflow"
  dockerfile_dir    = "${local.repo_root}/modules/orchestration/lambda"
  build_context_dir = local.repo_root
  source_hash_paths = [
    "${local.repo_root}/pyproject.toml",
    "${local.repo_root}/src/website_backend",
    "${local.repo_root}/modules/orchestration/lambda",
  ]
  tags = local.common_tags
}

resource "aws_sqs_queue" "observer" {
  name                        = local.observer_queue
  fifo_queue                  = true
  content_based_deduplication = true

  tags = local.common_tags
}

data "aws_iam_policy_document" "observer_queue" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["sns.amazonaws.com"]
    }

    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.observer.arn]

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [module.module_under_test.task_topic_arn]
    }
  }
}

resource "aws_sqs_queue_policy" "observer" {
  queue_url = aws_sqs_queue.observer.id
  policy    = data.aws_iam_policy_document.observer_queue.json
}

resource "aws_sns_topic_subscription" "observer" {
  topic_arn            = module.module_under_test.task_topic_arn
  protocol             = "sqs"
  endpoint             = aws_sqs_queue.observer.arn
  raw_message_delivery = true

  depends_on = [aws_sqs_queue_policy.observer]
}

module "publish_add_tasks" {
  source = "../support/modules/publish-sqs-message"

  artifacts_root           = local.artifacts_root
  test_name                = local.test_name
  artifact_name            = "publish-add-tasks"
  queue_url                = module.module_under_test.orchestration_queue_url
  payload                  = jsonencode(local.add_tasks_payload)
  message_group_id         = local.graph_id
  message_deduplication_id = "${local.run_id}-add-tasks"

  depends_on = [
    aws_sns_topic_subscription.observer,
    module.module_under_test,
  ]
}

module "inspect_initial_snapshot" {
  source = "../support/modules/inspect-taskdb-snapshot"

  bucket                = module.module_under_test.state_bucket_name
  key                   = local.graph_id
  timeout_seconds       = 180
  poll_interval_seconds = 2

  depends_on = [module.publish_add_tasks]
}

module "read_initial_messages" {
  source = "../support/modules/read-sqs-messages"

  queue_url             = aws_sqs_queue.observer.id
  min_message_count     = 2
  timeout_seconds       = 180
  poll_interval_seconds = 2
  delete_after_read     = true

  depends_on = [module.inspect_initial_snapshot]
}

module "check_empty_after_initial_fanout" {
  source = "../support/modules/read-sqs-messages"

  queue_url             = aws_sqs_queue.observer.id
  timeout_seconds       = 10
  poll_interval_seconds = 1
  wait_time_seconds     = 2

  depends_on = [module.read_initial_messages]
}

module "publish_task_a_completed" {
  source = "../support/modules/publish-sqs-message"

  artifacts_root           = local.artifacts_root
  test_name                = local.test_name
  artifact_name            = "publish-task-a-completed"
  queue_url                = module.module_under_test.orchestration_queue_url
  payload                  = jsonencode(local.task_a_completed_payload)
  message_group_id         = local.graph_id
  message_deduplication_id = "${local.run_id}-task-a-completed"

  depends_on = [
    module.check_empty_after_initial_fanout,
  ]
}

module "inspect_after_task_a_snapshot" {
  source = "../support/modules/inspect-taskdb-snapshot"

  bucket                = module.module_under_test.state_bucket_name
  key                   = local.graph_id
  previous_etag         = module.inspect_initial_snapshot.result.etag
  timeout_seconds       = 180
  poll_interval_seconds = 2

  depends_on = [module.publish_task_a_completed]
}

module "check_empty_after_task_a" {
  source = "../support/modules/read-sqs-messages"

  queue_url             = aws_sqs_queue.observer.id
  timeout_seconds       = 10
  poll_interval_seconds = 1
  wait_time_seconds     = 2

  depends_on = [module.inspect_after_task_a_snapshot]
}

module "publish_task_b_completed" {
  source = "../support/modules/publish-sqs-message"

  artifacts_root           = local.artifacts_root
  test_name                = local.test_name
  artifact_name            = "publish-task-b-completed"
  queue_url                = module.module_under_test.orchestration_queue_url
  payload                  = jsonencode(local.task_b_completed_payload)
  message_group_id         = local.graph_id
  message_deduplication_id = "${local.run_id}-task-b-completed"

  depends_on = [
    module.check_empty_after_task_a,
  ]
}

module "inspect_final_snapshot" {
  source = "../support/modules/inspect-taskdb-snapshot"

  bucket                = module.module_under_test.state_bucket_name
  key                   = local.graph_id
  previous_etag         = module.inspect_after_task_a_snapshot.result.etag
  timeout_seconds       = 180
  poll_interval_seconds = 2

  depends_on = [module.publish_task_b_completed]
}

module "read_final_message" {
  source = "../support/modules/read-sqs-messages"

  queue_url             = aws_sqs_queue.observer.id
  min_message_count     = 1
  timeout_seconds       = 180
  poll_interval_seconds = 2
  delete_after_read     = true

  depends_on = [module.inspect_final_snapshot]
}

locals {
  initial_task_bodies = [
    for message in module.read_initial_messages.result.messages : jsondecode(message.Body)
  ]
  initial_tasks_by_id = {
    for message in module.read_initial_messages.result.messages :
    jsondecode(message.Body).task_id => {
      body               = jsondecode(message.Body)
      message_attributes = message.MessageAttributes
    }
  }
  final_task_bodies = [
    for message in module.read_final_message.result.messages : jsondecode(message.Body)
  ]
  final_tasks_by_id = {
    for message in module.read_final_message.result.messages :
    jsondecode(message.Body).task_id => {
      body               = jsondecode(message.Body)
      message_attributes = message.MessageAttributes
    }
  }
}

output "run_id" {
  value = local.run_id
}

output "graph_id" {
  value = local.graph_id
}

output "orchestration_queue_url" {
  value = module.module_under_test.orchestration_queue_url
}

output "task_topic_arn" {
  value = module.module_under_test.task_topic_arn
}

output "state_bucket_name" {
  value = module.module_under_test.state_bucket_name
}

output "orchestrator_lambda_name" {
  value = module.module_under_test.orchestrator_lambda_name
}

output "resolved_image_uri" {
  value = module.module_under_test.resolved_image_uri
}

output "publish_add_tasks_result" {
  value = module.publish_add_tasks.result
}

output "publish_task_a_completed_result" {
  value = module.publish_task_a_completed.result
}

output "publish_task_b_completed_result" {
  value = module.publish_task_b_completed.result
}

output "initial_snapshot_result" {
  value = module.inspect_initial_snapshot.result
}

output "after_task_a_snapshot_result" {
  value = module.inspect_after_task_a_snapshot.result
}

output "final_snapshot_result" {
  value = module.inspect_final_snapshot.result
}

output "initial_task_messages_result" {
  value = module.read_initial_messages.result
}

output "empty_after_initial_fanout_result" {
  value = module.check_empty_after_initial_fanout.result
}

output "empty_after_task_a_result" {
  value = module.check_empty_after_task_a.result
}

output "final_task_messages_result" {
  value = module.read_final_message.result
}

output "initial_task_ids" {
  value = sort([for body in local.initial_task_bodies : body.task_id])
}

output "initial_task_graph_ids" {
  value = sort(distinct([for body in local.initial_task_bodies : body.graph_id]))
}

output "initial_tasks_by_id" {
  value = local.initial_tasks_by_id
}

output "final_task_ids" {
  value = sort([for body in local.final_task_bodies : body.task_id])
}

output "final_tasks_by_id" {
  value = local.final_tasks_by_id
}
