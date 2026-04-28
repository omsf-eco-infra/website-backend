run "fargate_compute_happy_path" {
  command = apply

  assert {
    condition     = output.ecs_cluster_name != ""
    error_message = "The fargate-compute module did not return an ECS cluster name."
  }

  assert {
    condition     = output.ecs_cluster_arn != ""
    error_message = "The fargate-compute module did not return an ECS cluster ARN."
  }

  assert {
    condition     = output.ecs_task_definition_arn != ""
    error_message = "The fargate-compute module did not return an ECS task definition ARN."
  }

  assert {
    condition     = output.ecs_task_definition_family != ""
    error_message = "The fargate-compute module did not return an ECS task definition family."
  }

  assert {
    condition     = output.worker_log_group_name != ""
    error_message = "The fargate-compute module did not return a worker log group name."
  }

  assert {
    condition     = output.launcher_lambda_name != ""
    error_message = "The fargate-compute module did not return a launcher Lambda name."
  }

  assert {
    condition     = output.launcher_lambda_arn != ""
    error_message = "The fargate-compute module did not return a launcher Lambda ARN."
  }

  assert {
    condition     = output.launcher_subscription_arn != ""
    error_message = "The fargate-compute module did not return an SNS subscription ARN."
  }

  assert {
    condition     = output.worker_task_role_arn != ""
    error_message = "The fargate-compute module did not return a worker task role ARN."
  }

  assert {
    condition     = output.worker_execution_role_arn != ""
    error_message = "The fargate-compute module did not return a worker execution role ARN."
  }

  assert {
    condition     = output.resolved_image_uri != ""
    error_message = "The fargate-compute module did not return a launcher image URI."
  }

  assert {
    condition     = output.worker_image_uri != ""
    error_message = "The test harness did not resolve a worker image URI."
  }

  assert {
    condition     = output.publish_task_result.message_id != ""
    error_message = "Publishing the task message did not return an SNS message ID."
  }

  assert {
    condition     = output.result_object_result.exists
    error_message = "The example worker did not write the expected S3 result object."
  }

  assert {
    condition     = output.result_object_json.workflow_name == output.workflow_name
    error_message = "The result object did not preserve the expected workflow name."
  }

  assert {
    condition     = output.result_object_json.env.graph_id == output.task_payload.graph_id
    error_message = "The worker env graph_id did not match the published task."
  }

  assert {
    condition     = output.result_object_json.env.task_id == output.task_payload.task_id
    error_message = "The worker env task_id did not match the published task."
  }

  assert {
    condition     = output.result_object_json.env.task_type == output.task_payload.task_type
    error_message = "The worker env task_type did not match the published task."
  }

  assert {
    condition     = output.result_object_json.env.task_attempt == output.task_payload.attempt
    error_message = "The worker env task_attempt did not match the published task."
  }

  assert {
    condition     = output.result_object_json.queue_body.graph_id == output.task_payload.graph_id
    error_message = "The queue body graph_id did not match the published task."
  }

  assert {
    condition     = output.result_object_json.queue_body.task_id == output.task_payload.task_id
    error_message = "The queue body task_id did not match the published task."
  }

  assert {
    condition     = output.result_object_json.queue_body.task_type == output.task_payload.task_type
    error_message = "The queue body task_type did not match the published task."
  }

  assert {
    condition     = output.result_object_json.queue_body.attempt == output.task_payload.attempt
    error_message = "The queue body attempt did not match the published task."
  }

  assert {
    condition     = output.queue_empty_result.message_count == 0
    error_message = "The worker task queue was not empty after the example worker completed."
  }
}
