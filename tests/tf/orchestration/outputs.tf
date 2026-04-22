output "run_id" {
  value = local.run_id
}

output "graph_id" {
  value = local.graph_id
}

output "orchestration_queue_url" {
  value = module.module_under_test.orchestration_queue_url
}

output "task_topic_arn" {
  value = module.module_under_test.task_topic_arn
}

output "state_bucket_name" {
  value = module.module_under_test.state_bucket_name
}

output "orchestrator_lambda_name" {
  value = module.module_under_test.orchestrator_lambda_name
}

output "resolved_image_uri" {
  value = module.module_under_test.resolved_image_uri
}

output "publish_add_tasks_result" {
  value = module.publish_add_tasks.result
}

output "publish_task_a_completed_result" {
  value = module.publish_task_a_completed.result
}

output "publish_task_b_completed_result" {
  value = module.publish_task_b_completed.result
}

output "initial_snapshot_result" {
  value = module.inspect_initial_snapshot.result
}

output "after_task_a_snapshot_result" {
  value = module.inspect_after_task_a_snapshot.result
}

output "final_snapshot_result" {
  value = module.inspect_final_snapshot.result
}

output "initial_task_messages_result" {
  value = module.read_initial_messages.result
}

output "empty_after_initial_fanout_result" {
  value = module.check_empty_after_initial_fanout.result
}

output "empty_after_task_a_result" {
  value = module.check_empty_after_task_a.result
}

output "final_task_messages_result" {
  value = module.read_final_message.result
}

output "initial_task_ids" {
  value = sort([for body in local.initial_task_bodies : body.task_id])
}

output "initial_task_graph_ids" {
  value = sort(distinct([for body in local.initial_task_bodies : body.graph_id]))
}

output "initial_tasks_by_id" {
  value = local.initial_tasks_by_id
}

output "final_task_ids" {
  value = sort([for body in local.final_task_bodies : body.task_id])
}

output "final_tasks_by_id" {
  value = local.final_tasks_by_id
}
