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
  artifacts_root  = abspath("${path.module}/../../../.tf-test-artifacts")
  test_name       = "ci-smoke"
  owner_segments  = regexall("[a-z0-9-]+", lower(var.owner))
  owner_joined    = length(local.owner_segments) > 0 ? join("-", local.owner_segments) : "local"
  owner_sanitized = substr(local.owner_joined, 0, 12)
  run_suffix      = substr(md5("${plantimestamp()}-${path.module}-${var.owner}"), 0, 8)
  run_id          = "${local.owner_sanitized}-${local.run_suffix}"
  created_at      = timestamp()
  expires_at      = timeadd(local.created_at, "24h")
  queue_name      = "wb-ci-smoke-${local.owner_sanitized}-${local.run_suffix}.fifo"
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
  expected_body = file("${path.module}/message.json")
}

resource "aws_sqs_queue" "queue" {
  name                        = local.queue_name
  fifo_queue                  = true
  content_based_deduplication = false

  tags = local.common_tags
}

module "publish_message" {
  source = "../support/modules/publish-sqs-message"

  artifacts_root           = local.artifacts_root
  test_name                = local.test_name
  artifact_name            = "publish-result"
  queue_url                = aws_sqs_queue.queue.id
  payload_file             = "${path.module}/message.json"
  message_group_id         = "ci-smoke"
  message_deduplication_id = local.run_id
}

module "read_messages" {
  source = "../support/modules/read-sqs-messages"

  queue_url             = aws_sqs_queue.queue.id
  min_message_count     = 1
  timeout_seconds       = 60
  poll_interval_seconds = 2

  depends_on = [module.publish_message]
}

output "expected_body" {
  value = local.expected_body
}

output "publish_result" {
  value = module.publish_message.result
}

output "queue_name" {
  value = aws_sqs_queue.queue.name
}

output "read_result" {
  value = module.read_messages.result
}

output "run_id" {
  value = local.run_id
}
