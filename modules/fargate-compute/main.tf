data "aws_region" "current" {}

locals {
  cluster_name                        = "${var.name_prefix}-cluster"
  task_definition_family              = "${var.name_prefix}-worker"
  worker_log_group_name               = "/aws/ecs/${var.name_prefix}-worker"
  launcher_function_name              = "${var.name_prefix}-fargate-launcher"
  launcher_queue_name                 = "${var.name_prefix}-launcher.fifo"
  launcher_log_group_name             = "/aws/lambda/${local.launcher_function_name}"
  log_retention_days                  = 14
  launcher_visibility_timeout_seconds = max(var.launcher_timeout * 6, 60)
  task_types                          = [for task_type in var.task_types : trimspace(task_type)]
  worker_environment = merge(
    var.worker_environment,
    {
      TASK_QUEUE_URL = var.task_queue_url
      WORKFLOW_NAME  = var.workflow_name
    },
  )
  worker_environment_list = [
    for name in sort(keys(local.worker_environment)) : {
      name  = name
      value = local.worker_environment[name]
    }
  ]
}

module "launcher_image" {
  source = "../lambda-deploy"

  repository_name     = local.launcher_function_name
  dockerfile_dir      = var.dockerfile_dir
  build_context_dir   = var.build_context_dir
  source_hash_paths   = var.source_hash_paths
  docker_platform     = var.docker_platform
  lambda_architecture = var.lambda_architecture
  tags                = var.tags
}

resource "aws_ecs_cluster" "this" {
  name = local.cluster_name
  tags = var.tags
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = local.worker_log_group_name
  retention_in_days = local.log_retention_days
  tags              = var.tags
}

resource "aws_cloudwatch_log_group" "launcher" {
  name              = local.launcher_log_group_name
  retention_in_days = local.log_retention_days
  tags              = var.tags
}

resource "aws_sqs_queue" "launcher" {
  name                        = local.launcher_queue_name
  fifo_queue                  = true
  content_based_deduplication = true
  visibility_timeout_seconds  = local.launcher_visibility_timeout_seconds
  tags                        = var.tags
}

data "aws_iam_policy_document" "launcher_queue" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["sns.amazonaws.com"]
    }

    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.launcher.arn]

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [var.task_topic_arn]
    }
  }
}

resource "aws_sqs_queue_policy" "launcher" {
  queue_url = aws_sqs_queue.launcher.id
  policy    = data.aws_iam_policy_document.launcher_queue.json
}

data "aws_iam_policy_document" "ecs_tasks_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "worker_execution" {
  name               = "${var.name_prefix}-worker-exec"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume_role.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "worker_execution" {
  role       = aws_iam_role.worker_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "worker_task" {
  name               = "${var.name_prefix}-worker-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume_role.json
  tags               = var.tags
}

data "aws_iam_policy_document" "worker_task" {
  statement {
    sid    = "AllowTaskQueueConsume"
    effect = "Allow"
    actions = [
      "sqs:ChangeMessageVisibility",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:ReceiveMessage",
    ]
    resources = [var.task_queue_arn]
  }

  dynamic "statement" {
    for_each = var.worker_additional_policy_statements

    content {
      sid       = try(statement.value.sid, null)
      effect    = "Allow"
      actions   = statement.value.actions
      resources = statement.value.resources
    }
  }
}

resource "aws_iam_role_policy" "worker_task" {
  name   = "${var.name_prefix}-worker-task-access"
  role   = aws_iam_role.worker_task.id
  policy = data.aws_iam_policy_document.worker_task.json
}

resource "aws_ecs_task_definition" "worker" {
  family                   = local.task_definition_family
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = tostring(var.worker_cpu)
  memory                   = tostring(var.worker_memory)
  execution_role_arn       = aws_iam_role.worker_execution.arn
  task_role_arn            = aws_iam_role.worker_task.arn

  container_definitions = jsonencode([
    {
      essential   = true
      image       = var.worker_image_uri
      name        = var.worker_container_name
      environment = local.worker_environment_list
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.worker.name
          awslogs-region        = data.aws_region.current.name
          awslogs-stream-prefix = "worker"
        }
      }
    }
  ])

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

resource "aws_iam_role" "launcher" {
  name               = local.launcher_function_name
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "launcher_basic_execution" {
  role       = aws_iam_role.launcher.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "launcher" {
  statement {
    sid    = "AllowRunWorkerTask"
    effect = "Allow"
    actions = [
      "ecs:RunTask",
    ]
    resources = [aws_ecs_task_definition.worker.arn]
  }

  statement {
    sid    = "AllowPassWorkerRoles"
    effect = "Allow"
    actions = [
      "iam:PassRole",
    ]
    resources = [
      aws_iam_role.worker_execution.arn,
      aws_iam_role.worker_task.arn,
    ]
  }

  statement {
    sid    = "AllowLauncherQueueConsume"
    effect = "Allow"
    actions = [
      "sqs:ChangeMessageVisibility",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:ReceiveMessage",
    ]
    resources = [aws_sqs_queue.launcher.arn]
  }
}

resource "aws_iam_role_policy" "launcher" {
  name   = "${local.launcher_function_name}-access"
  role   = aws_iam_role.launcher.id
  policy = data.aws_iam_policy_document.launcher.json
}

resource "aws_lambda_function" "launcher" {
  function_name = local.launcher_function_name
  role          = aws_iam_role.launcher.arn
  package_type  = "Image"
  image_uri     = module.launcher_image.resolved_image_uri
  architectures = [var.lambda_architecture]
  timeout       = var.launcher_timeout
  memory_size   = var.launcher_memory_size

  environment {
    variables = {
      ASSIGN_PUBLIC_IP        = var.assign_public_ip
      ECS_CLUSTER_ARN         = aws_ecs_cluster.this.arn
      ECS_CONTAINER_NAME      = var.worker_container_name
      ECS_TASK_DEFINITION_ARN = aws_ecs_task_definition.worker.arn
      SECURITY_GROUP_IDS      = jsonencode(var.security_group_ids)
      SUBNET_IDS              = jsonencode(var.subnet_ids)
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.launcher,
    aws_iam_role_policy_attachment.launcher_basic_execution,
    aws_iam_role_policy.launcher,
  ]

  tags = var.tags
}

resource "aws_sns_topic_subscription" "launcher" {
  topic_arn            = var.task_topic_arn
  protocol             = "sqs"
  endpoint             = aws_sqs_queue.launcher.arn
  raw_message_delivery = true
  filter_policy = jsonencode({
    task_type = local.task_types
  })

  depends_on = [aws_sqs_queue_policy.launcher]
}

resource "aws_lambda_event_source_mapping" "launcher" {
  event_source_arn = aws_sqs_queue.launcher.arn
  function_name    = aws_lambda_function.launcher.arn
  batch_size       = 1
  enabled          = true
}
