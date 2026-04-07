output "orchestration_queue_url" {
  value = aws_sqs_queue.orchestration.id
}

output "orchestration_queue_arn" {
  value = aws_sqs_queue.orchestration.arn
}

output "orchestration_queue_name" {
  value = aws_sqs_queue.orchestration.name
}

output "task_topic_arn" {
  value = aws_sns_topic.tasks.arn
}

output "task_topic_name" {
  value = aws_sns_topic.tasks.name
}

output "state_bucket_name" {
  value = aws_s3_bucket.state.bucket
}

output "state_bucket_arn" {
  value = aws_s3_bucket.state.arn
}

output "orchestrator_lambda_name" {
  value = aws_lambda_function.orchestrator.function_name
}

output "orchestrator_lambda_arn" {
  value = aws_lambda_function.orchestrator.arn
}

output "resolved_image_uri" {
  value = module.orchestrator_image.resolved_image_uri
}
