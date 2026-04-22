locals {
  task_types          = [for task_type in var.task_types : trimspace(task_type)]
  task_queue_name     = "${var.name_prefix}-queue.fifo"
  task_queue_dlq_name = "${var.name_prefix}-queue-dlq.fifo"
}

resource "aws_sqs_queue" "task_dlq" {
  name                        = local.task_queue_dlq_name
  fifo_queue                  = true
  content_based_deduplication = true
  tags                        = var.tags
}

resource "aws_sqs_queue" "task" {
  name                        = local.task_queue_name
  fifo_queue                  = true
  content_based_deduplication = true
  visibility_timeout_seconds  = var.queue_visibility_timeout_seconds
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.task_dlq.arn
    maxReceiveCount     = var.task_queue_max_receive_count
  })
  tags = var.tags
}

data "aws_iam_policy_document" "task_queue" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["sns.amazonaws.com"]
    }

    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.task.arn]

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [var.task_topic_arn]
    }
  }
}

resource "aws_sqs_queue_policy" "task" {
  queue_url = aws_sqs_queue.task.id
  policy    = data.aws_iam_policy_document.task_queue.json
}

resource "aws_sns_topic_subscription" "task" {
  topic_arn            = var.task_topic_arn
  protocol             = "sqs"
  endpoint             = aws_sqs_queue.task.arn
  raw_message_delivery = true
  filter_policy = jsonencode({
    task_type = local.task_types
  })

  depends_on = [aws_sqs_queue_policy.task]
}
