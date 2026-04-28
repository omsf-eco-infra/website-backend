output "ecs_cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "ecs_cluster_arn" {
  value = aws_ecs_cluster.this.arn
}

output "ecs_task_definition_arn" {
  value = aws_ecs_task_definition.worker.arn
}

output "ecs_task_definition_family" {
  value = aws_ecs_task_definition.worker.family
}

output "worker_log_group_name" {
  value = aws_cloudwatch_log_group.worker.name
}

output "launcher_lambda_name" {
  value = aws_lambda_function.launcher.function_name
}

output "launcher_lambda_arn" {
  value = aws_lambda_function.launcher.arn
}

output "launcher_subscription_arn" {
  value = aws_sns_topic_subscription.launcher.arn
}

output "worker_task_role_arn" {
  value = aws_iam_role.worker_task.arn
}

output "worker_execution_role_arn" {
  value = aws_iam_role.worker_execution.arn
}

output "resolved_image_uri" {
  value = module.launcher_image.resolved_image_uri
}
