locals {
  state_bucket_name                = "${var.name_prefix}-state"
  orchestration_queue_name         = "${var.name_prefix}-orchestration.fifo"
  orchestration_dead_letter_name   = "${var.name_prefix}-orchestration-dlq.fifo"
  task_topic_name                  = "${var.name_prefix}-tasks.fifo"
  orchestrator_function_name       = "${var.name_prefix}-orchestrator"
  orchestrator_log_group_name      = "/aws/lambda/${local.orchestrator_function_name}"
  log_retention_days               = 14
  queue_visibility_timeout_seconds = max(180, var.lambda_timeout * 6)
}

module "orchestrator_image" {
  source = "../lambda-deploy"

  repository_name     = local.orchestrator_function_name
  dockerfile_dir      = var.dockerfile_dir
  build_context_dir   = var.build_context_dir
  source_hash_paths   = var.source_hash_paths
  docker_platform     = var.docker_platform
  lambda_architecture = var.lambda_architecture
  tags                = var.tags
}

resource "aws_s3_bucket" "state" {
  bucket        = local.state_bucket_name
  force_destroy = var.state_bucket_force_destroy
  tags          = var.tags
}

resource "aws_s3_bucket_versioning" "state" {
  count  = var.enable_state_bucket_versioning ? 1 : 0
  bucket = aws_s3_bucket.state.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket = aws_s3_bucket.state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_sns_topic" "tasks" {
  name                        = local.task_topic_name
  fifo_topic                  = true
  content_based_deduplication = true
  tags                        = var.tags
}

resource "aws_sqs_queue" "orchestration_dlq" {
  name                        = local.orchestration_dead_letter_name
  fifo_queue                  = true
  content_based_deduplication = true
  tags                        = var.tags
}

resource "aws_sqs_queue" "orchestration" {
  name                        = local.orchestration_queue_name
  fifo_queue                  = true
  content_based_deduplication = true
  visibility_timeout_seconds  = local.queue_visibility_timeout_seconds
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.orchestration_dlq.arn
    maxReceiveCount     = var.orchestration_queue_max_receive_count
  })
  tags = var.tags
}

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "orchestrator" {
  name               = local.orchestrator_function_name
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "basic_execution" {
  role       = aws_iam_role.orchestrator.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "orchestrator" {
  statement {
    sid    = "AllowStateBucketList"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
    ]
    resources = [aws_s3_bucket.state.arn]
  }

  statement {
    sid    = "AllowStateObjectAccess"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = ["${aws_s3_bucket.state.arn}/*"]
  }

  statement {
    sid    = "AllowTaskTopicPublish"
    effect = "Allow"
    actions = [
      "sns:Publish",
    ]
    resources = [aws_sns_topic.tasks.arn]
  }

  statement {
    sid    = "AllowOrchestrationQueueConsume"
    effect = "Allow"
    actions = [
      "sqs:ChangeMessageVisibility",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:ReceiveMessage",
    ]
    resources = [aws_sqs_queue.orchestration.arn]
  }
}

resource "aws_iam_role_policy" "orchestrator" {
  name   = "${local.orchestrator_function_name}-access"
  role   = aws_iam_role.orchestrator.id
  policy = data.aws_iam_policy_document.orchestrator.json
}

resource "aws_cloudwatch_log_group" "orchestrator" {
  name              = local.orchestrator_log_group_name
  retention_in_days = local.log_retention_days
  tags              = var.tags
}

resource "aws_lambda_function" "orchestrator" {
  function_name = local.orchestrator_function_name
  role          = aws_iam_role.orchestrator.arn
  package_type  = "Image"
  image_uri     = module.orchestrator_image.resolved_image_uri
  architectures = [var.lambda_architecture]
  timeout       = var.lambda_timeout
  memory_size   = var.lambda_memory_size

  reserved_concurrent_executions = 1

  environment {
    variables = {
      WORKFLOW_NAME  = var.workflow_name
      STATE_BUCKET   = aws_s3_bucket.state.bucket
      STATE_PREFIX   = var.state_prefix
      TASK_TOPIC_ARN = aws_sns_topic.tasks.arn
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.orchestrator,
    aws_iam_role_policy_attachment.basic_execution,
    aws_iam_role_policy.orchestrator,
  ]

  tags = var.tags
}

resource "aws_lambda_event_source_mapping" "orchestration" {
  event_source_arn = aws_sqs_queue.orchestration.arn
  function_name    = aws_lambda_function.orchestrator.arn
  batch_size       = 1
  enabled          = true

  depends_on = [aws_iam_role_policy.orchestrator]
}
