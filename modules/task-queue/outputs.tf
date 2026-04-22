output "task_queue_url" {
  value = aws_sqs_queue.task.id
}

output "task_queue_arn" {
  value = aws_sqs_queue.task.arn
}

output "task_queue_name" {
  value = aws_sqs_queue.task.name
}

output "task_queue_dlq_url" {
  value = aws_sqs_queue.task_dlq.id
}

output "task_queue_dlq_arn" {
  value = aws_sqs_queue.task_dlq.arn
}

output "task_queue_dlq_name" {
  value = aws_sqs_queue.task_dlq.name
}

output "subscription_arn" {
  value = aws_sns_topic_subscription.task.arn
}
