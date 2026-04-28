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

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

locals {
  artifacts_root = abspath("${path.module}/../../../.tf-test-artifacts")
  repo_root      = abspath("${path.root}/../../..")
  test_name      = "fargate-compute"

  owner_segments  = regexall("[a-z0-9-]+", lower(var.owner))
  owner_joined    = length(local.owner_segments) > 0 ? join("-", local.owner_segments) : "local"
  owner_sanitized = substr(local.owner_joined, 0, 12)
  run_suffix      = substr(md5("${plantimestamp()}-${path.module}-${var.owner}"), 0, 8)
  run_id          = "${local.owner_sanitized}-${local.run_suffix}"
  created_at      = timestamp()
  expires_at      = timeadd(local.created_at, "24h")

  name_prefix            = "wb-fcomp-${local.owner_sanitized}-${local.run_suffix}"
  task_queue_name_prefix = "${local.name_prefix}-queue"
  worker_repository_name = "wb-example-worker-${local.owner_sanitized}-${local.run_suffix}"
  results_bucket_name    = "wb-fcomp-results-${local.owner_sanitized}-${local.run_suffix}"
  results_prefix         = "tests/fargate-compute/${local.owner_sanitized}/${local.run_id}"
  result_object_key      = "${local.results_prefix}/task-hello.json"
  task_topic_name        = "${local.name_prefix}-tasks.fifo"
  task_type              = "example_hello_world"
  workflow_name          = "example-workflow"
  worker_container_name  = "example-worker"

  contract_version = jsondecode(
    file("${local.repo_root}/examples/payloads/task_message.matching.json")
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

  task_payload = {
    version   = local.contract_version
    graph_id  = "graphs/${local.run_id}"
    task_id   = "task-hello"
    task_type = local.task_type
    attempt   = 1
    task_details = {
      hello = "world"
    }
  }

  task_attributes = {
    task_type = {
      DataType    = "String"
      StringValue = local.task_type
    }
    version = {
      DataType    = "String"
      StringValue = local.contract_version
    }
  }
}

resource "aws_security_group" "worker" {
  name        = "${local.name_prefix}-worker"
  description = "Outbound-only security group for the Phase 6 Fargate compute test."
  vpc_id      = data.aws_vpc.default.id
  tags        = local.common_tags

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_sns_topic" "tasks" {
  name                        = local.task_topic_name
  fifo_topic                  = true
  content_based_deduplication = true
  tags                        = local.common_tags
}

resource "aws_s3_bucket" "results" {
  bucket        = local.results_bucket_name
  force_destroy = true
  tags          = local.common_tags
}

resource "aws_s3_bucket_public_access_block" "results" {
  bucket = aws_s3_bucket.results.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

module "worker_image" {
  source = "../../../modules/container-image"

  repository_name   = local.worker_repository_name
  dockerfile_dir    = "${local.repo_root}/examples/containers/website-backend-example-worker"
  build_context_dir = local.repo_root
  source_hash_paths = [
    "${local.repo_root}/pyproject.toml",
    "${local.repo_root}/src/website_backend",
    "${local.repo_root}/examples/containers/website-backend-example-worker",
  ]
  docker_platform = "linux/amd64"
  tags            = local.common_tags
}

module "task_queue" {
  source = "../../../modules/task-queue"

  name_prefix    = local.task_queue_name_prefix
  task_topic_arn = aws_sns_topic.tasks.arn
  task_types     = [local.task_type]
  tags           = local.common_tags
}

module "module_under_test" {
  source = "../../../modules/fargate-compute"

  name_prefix           = local.name_prefix
  workflow_name         = local.workflow_name
  task_topic_arn        = aws_sns_topic.tasks.arn
  task_types            = [local.task_type]
  task_queue_url        = module.task_queue.task_queue_url
  task_queue_arn        = module.task_queue.task_queue_arn
  worker_image_uri      = module.worker_image.resolved_image_uri
  worker_container_name = local.worker_container_name
  worker_environment = {
    RESULTS_BUCKET = aws_s3_bucket.results.bucket
    RESULTS_PREFIX = local.results_prefix
  }
  worker_additional_policy_statements = [
    {
      sid = "AllowResultWrites"
      actions = [
        "s3:PutObject",
      ]
      resources = [
        "${aws_s3_bucket.results.arn}/${local.results_prefix}/*",
      ]
    }
  ]
  subnet_ids         = sort(data.aws_subnets.default.ids)
  security_group_ids = [aws_security_group.worker.id]
  assign_public_ip   = "ENABLED"
  dockerfile_dir     = "${local.repo_root}/modules/fargate-compute/lambda"
  build_context_dir  = local.repo_root
  source_hash_paths = [
    "${local.repo_root}/pyproject.toml",
    "${local.repo_root}/src/website_backend",
    "${local.repo_root}/modules/fargate-compute/lambda",
  ]
  tags = local.common_tags
}

module "payload_artifact" {
  source = "../support/modules/write-json-artifact"

  artifacts_root = local.artifacts_root
  test_name      = local.test_name
  artifact_name  = "task-payload"
  content_json   = jsonencode(local.task_payload)
}

module "attributes_artifact" {
  source = "../support/modules/write-json-artifact"

  artifacts_root = local.artifacts_root
  test_name      = local.test_name
  artifact_name  = "task-attributes"
  content_json   = jsonencode(local.task_attributes)
}

module "publish_task" {
  source = "../support/modules/publish-sns-message"

  artifacts_root                  = local.artifacts_root
  test_name                       = local.test_name
  artifact_name                   = "publish-task"
  topic_arn                       = aws_sns_topic.tasks.arn
  payload_file                    = module.payload_artifact.artifact_path
  payload_content_sha1            = module.payload_artifact.content_sha1
  message_group_id                = local.task_payload.graph_id
  message_deduplication_id        = "${local.run_id}-task-hello"
  message_attributes_file         = module.attributes_artifact.artifact_path
  message_attributes_content_sha1 = module.attributes_artifact.content_sha1

  depends_on = [
    module.task_queue,
    module.module_under_test,
  ]
}

module "read_result_object" {
  source = "../support/modules/read-s3-object"

  bucket                = aws_s3_bucket.results.bucket
  key                   = local.result_object_key
  timeout_seconds       = 300
  poll_interval_seconds = 5

  depends_on = [module.publish_task]
}

module "check_queue_empty" {
  source = "../support/modules/read-sqs-messages"

  queue_url             = module.task_queue.task_queue_url
  timeout_seconds       = 10
  poll_interval_seconds = 1
  wait_time_seconds     = 2

  depends_on = [module.read_result_object]
}

output "contract_version" {
  value = local.contract_version
}

output "workflow_name" {
  value = local.workflow_name
}

output "task_payload" {
  value = local.task_payload
}

output "task_queue_url" {
  value = module.task_queue.task_queue_url
}

output "worker_image_uri" {
  value = module.worker_image.resolved_image_uri
}

output "publish_task_result" {
  value = module.publish_task.result
}

output "result_object_key" {
  value = local.result_object_key
}

output "result_object_result" {
  value = module.read_result_object.result
}

output "result_object_json" {
  value = try(module.read_result_object.result.body_json, null)
}

output "queue_empty_result" {
  value = module.check_queue_empty.result
}

output "ecs_cluster_name" {
  value = module.module_under_test.ecs_cluster_name
}

output "ecs_cluster_arn" {
  value = module.module_under_test.ecs_cluster_arn
}

output "ecs_task_definition_arn" {
  value = module.module_under_test.ecs_task_definition_arn
}

output "ecs_task_definition_family" {
  value = module.module_under_test.ecs_task_definition_family
}

output "worker_log_group_name" {
  value = module.module_under_test.worker_log_group_name
}

output "launcher_lambda_name" {
  value = module.module_under_test.launcher_lambda_name
}

output "launcher_lambda_arn" {
  value = module.module_under_test.launcher_lambda_arn
}

output "launcher_subscription_arn" {
  value = module.module_under_test.launcher_subscription_arn
}

output "worker_task_role_arn" {
  value = module.module_under_test.worker_task_role_arn
}

output "worker_execution_role_arn" {
  value = module.module_under_test.worker_execution_role_arn
}

output "resolved_image_uri" {
  value = module.module_under_test.resolved_image_uri
}
