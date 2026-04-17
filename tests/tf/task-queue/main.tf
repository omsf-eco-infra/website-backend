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
  test_name      = "task-queue"

  owner_segments  = regexall("[a-z0-9-]+", lower(var.owner))
  owner_joined    = length(local.owner_segments) > 0 ? join("-", local.owner_segments) : "local"
  owner_sanitized = substr(local.owner_joined, 0, 12)
  run_suffix      = substr(md5("${plantimestamp()}-${path.module}-${var.owner}"), 0, 8)
  run_id          = "${local.owner_sanitized}-${local.run_suffix}"
  created_at      = timestamp()
  expires_at      = timeadd(local.created_at, "24h")

  name_prefix = "wb-taskq-${local.owner_sanitized}-${local.run_suffix}"
  topic_name  = "${local.name_prefix}-tasks.fifo"

  task_types             = ["prepare_inputs", "stage_inputs"]
  matching_task_type     = local.task_types[0]
  redrive_task_type      = local.task_types[1]
  non_matching_task_type = "collect_outputs"
  contract_version       = jsondecode(file("${local.repo_root}/examples/payloads/task_message.matching.json")).version
  matching_graph_id      = "graphs/${local.run_id}/matching"
  non_matching_graph_id  = "graphs/${local.run_id}/non-matching"
  redrive_graph_id       = "graphs/${local.run_id}/redrive"

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

  matching_payload = {
    version   = local.contract_version
    graph_id  = local.matching_graph_id
    task_id   = "task-match"
    task_type = local.matching_task_type
    attempt   = 1
    task_details = {
      stage = "matching"
    }
  }

  non_matching_payload = {
    version   = local.contract_version
    graph_id  = local.non_matching_graph_id
    task_id   = "task-ignore"
    task_type = local.non_matching_task_type
    attempt   = 1
    task_details = {
      stage = "filtered"
    }
  }

  redrive_payload = {
    version   = local.contract_version
    graph_id  = local.redrive_graph_id
    task_id   = "task-redrive"
    task_type = local.redrive_task_type
    attempt   = 1
    task_details = {
      stage = "redrive"
    }
  }

  matching_attributes = {
    task_type = {
      DataType    = "String"
      StringValue = local.matching_task_type
    }
    version = {
      DataType    = "String"
      StringValue = local.contract_version
    }
  }

  non_matching_attributes = {
    task_type = {
      DataType    = "String"
      StringValue = local.non_matching_task_type
    }
    version = {
      DataType    = "String"
      StringValue = local.contract_version
    }
  }

  redrive_attributes = {
    task_type = {
      DataType    = "String"
      StringValue = local.redrive_task_type
    }
    version = {
      DataType    = "String"
      StringValue = local.contract_version
    }
  }
}

resource "aws_sns_topic" "tasks" {
  name                        = local.topic_name
  fifo_topic                  = true
  content_based_deduplication = true
  tags                        = local.common_tags
}

module "module_under_test" {
  source = "../../../modules/task-queue"

  name_prefix                      = local.name_prefix
  task_topic_arn                   = aws_sns_topic.tasks.arn
  task_types                       = local.task_types
  task_queue_max_receive_count     = 1
  queue_visibility_timeout_seconds = 1
  tags                             = local.common_tags
}

module "matching_payload_artifact" {
  source = "../support/modules/write-json-artifact"

  artifacts_root = local.artifacts_root
  test_name      = local.test_name
  artifact_name  = "matching-payload"
  content_json   = jsonencode(local.matching_payload)
}

module "matching_attributes_artifact" {
  source = "../support/modules/write-json-artifact"

  artifacts_root = local.artifacts_root
  test_name      = local.test_name
  artifact_name  = "matching-attributes"
  content_json   = jsonencode(local.matching_attributes)
}

module "non_matching_payload_artifact" {
  source = "../support/modules/write-json-artifact"

  artifacts_root = local.artifacts_root
  test_name      = local.test_name
  artifact_name  = "non-matching-payload"
  content_json   = jsonencode(local.non_matching_payload)
}

module "non_matching_attributes_artifact" {
  source = "../support/modules/write-json-artifact"

  artifacts_root = local.artifacts_root
  test_name      = local.test_name
  artifact_name  = "non-matching-attributes"
  content_json   = jsonencode(local.non_matching_attributes)
}

module "redrive_payload_artifact" {
  source = "../support/modules/write-json-artifact"

  artifacts_root = local.artifacts_root
  test_name      = local.test_name
  artifact_name  = "redrive-payload"
  content_json   = jsonencode(local.redrive_payload)
}

module "redrive_attributes_artifact" {
  source = "../support/modules/write-json-artifact"

  artifacts_root = local.artifacts_root
  test_name      = local.test_name
  artifact_name  = "redrive-attributes"
  content_json   = jsonencode(local.redrive_attributes)
}

module "publish_matching" {
  source = "../support/modules/publish-sns-message"

  artifacts_root                  = local.artifacts_root
  test_name                       = local.test_name
  artifact_name                   = "publish-matching"
  topic_arn                       = aws_sns_topic.tasks.arn
  payload_file                    = module.matching_payload_artifact.artifact_path
  payload_content_sha1            = module.matching_payload_artifact.content_sha1
  message_group_id                = local.matching_graph_id
  message_deduplication_id        = "${local.run_id}-matching"
  message_attributes_file         = module.matching_attributes_artifact.artifact_path
  message_attributes_content_sha1 = module.matching_attributes_artifact.content_sha1

  depends_on = [module.module_under_test]
}

module "publish_non_matching" {
  source = "../support/modules/publish-sns-message"

  artifacts_root                  = local.artifacts_root
  test_name                       = local.test_name
  artifact_name                   = "publish-non-matching"
  topic_arn                       = aws_sns_topic.tasks.arn
  payload_file                    = module.non_matching_payload_artifact.artifact_path
  payload_content_sha1            = module.non_matching_payload_artifact.content_sha1
  message_group_id                = local.non_matching_graph_id
  message_deduplication_id        = "${local.run_id}-non-matching"
  message_attributes_file         = module.non_matching_attributes_artifact.artifact_path
  message_attributes_content_sha1 = module.non_matching_attributes_artifact.content_sha1

  depends_on = [module.publish_matching]
}

module "read_filter_match" {
  source = "../support/modules/read-sqs-messages"

  queue_url             = module.module_under_test.task_queue_url
  min_message_count     = 1
  timeout_seconds       = 180
  poll_interval_seconds = 2
  delete_after_read     = true

  depends_on = [module.publish_non_matching]
}

module "check_empty_after_filter" {
  source = "../support/modules/read-sqs-messages"

  queue_url             = module.module_under_test.task_queue_url
  timeout_seconds       = 10
  poll_interval_seconds = 1
  wait_time_seconds     = 2

  depends_on = [module.read_filter_match]
}

module "publish_redrive" {
  source = "../support/modules/publish-sns-message"

  artifacts_root                  = local.artifacts_root
  test_name                       = local.test_name
  artifact_name                   = "publish-redrive"
  topic_arn                       = aws_sns_topic.tasks.arn
  payload_file                    = module.redrive_payload_artifact.artifact_path
  payload_content_sha1            = module.redrive_payload_artifact.content_sha1
  message_group_id                = local.redrive_graph_id
  message_deduplication_id        = "${local.run_id}-redrive"
  message_attributes_file         = module.redrive_attributes_artifact.artifact_path
  message_attributes_content_sha1 = module.redrive_attributes_artifact.content_sha1

  depends_on = [module.check_empty_after_filter]
}

module "exercise_redrive" {
  source = "../support/modules/exercise-sqs-redrive"

  artifacts_root         = local.artifacts_root
  test_name              = local.test_name
  queue_url              = module.module_under_test.task_queue_url
  min_receive_count      = 1
  max_number_of_messages = 1
  wait_time_seconds      = 1
  required_empty_polls   = 2
  timeout_seconds        = 60
  poll_interval_seconds  = 2

  depends_on = [module.publish_redrive]
}

module "read_redriven_dlq" {
  source = "../support/modules/read-sqs-messages"

  queue_url             = module.module_under_test.task_queue_dlq_url
  min_message_count     = 1
  timeout_seconds       = 60
  poll_interval_seconds = 2
  wait_time_seconds     = 2

  depends_on = [module.exercise_redrive]
}

locals {
  filter_messages = module.read_filter_match.result.messages
  filter_message = length(local.filter_messages) > 0 ? {
    body               = jsondecode(local.filter_messages[0].Body)
    message_attributes = local.filter_messages[0].MessageAttributes
  } : null

  dlq_messages = module.read_redriven_dlq.result.messages
  dlq_message = length(local.dlq_messages) > 0 ? {
    body               = jsondecode(local.dlq_messages[0].Body)
    message_attributes = local.dlq_messages[0].MessageAttributes
  } : null
}

output "run_id" {
  value = local.run_id
}

output "contract_version" {
  value = local.contract_version
}

output "task_queue_url" {
  value = module.module_under_test.task_queue_url
}

output "task_queue_arn" {
  value = module.module_under_test.task_queue_arn
}

output "task_queue_name" {
  value = module.module_under_test.task_queue_name
}

output "task_queue_dlq_url" {
  value = module.module_under_test.task_queue_dlq_url
}

output "task_queue_dlq_arn" {
  value = module.module_under_test.task_queue_dlq_arn
}

output "task_queue_dlq_name" {
  value = module.module_under_test.task_queue_dlq_name
}

output "subscription_arn" {
  value = module.module_under_test.subscription_arn
}

output "publish_matching_result" {
  value = module.publish_matching.result
}

output "publish_non_matching_result" {
  value = module.publish_non_matching.result
}

output "filter_match_result" {
  value = module.read_filter_match.result
}

output "filter_empty_result" {
  value = module.check_empty_after_filter.result
}

output "filter_message" {
  value = local.filter_message
}

output "publish_redrive_result" {
  value = module.publish_redrive.result
}

output "exercise_redrive_result" {
  value = module.exercise_redrive.result
}

output "redriven_dlq_result" {
  value = module.read_redriven_dlq.result
}

output "redriven_dlq_message" {
  value = local.dlq_message
}
