run "dag_progression" {
  command = apply

  assert {
    condition     = output.orchestration_queue_url != ""
    error_message = "The orchestration module did not return an orchestration queue URL."
  }

  assert {
    condition     = output.task_topic_arn != ""
    error_message = "The orchestration module did not return a task topic ARN."
  }

  assert {
    condition     = output.state_bucket_name != ""
    error_message = "The orchestration module did not return a state bucket name."
  }

  assert {
    condition     = output.orchestrator_lambda_name != ""
    error_message = "The orchestration module did not return an orchestrator Lambda name."
  }

  assert {
    condition     = output.resolved_image_uri != ""
    error_message = "The orchestration module did not return a resolved image URI."
  }

  assert {
    condition     = output.publish_add_tasks_result.message_id != ""
    error_message = "Publishing the ADD_TASKS message did not return an SQS message ID."
  }

  assert {
    condition     = output.initial_snapshot_result.exists
    error_message = "The initial taskdb snapshot was not written to S3."
  }

  assert {
    condition     = output.initial_snapshot_result.task_count == 3
    error_message = "The initial taskdb snapshot did not contain the expected three tasks."
  }

  assert {
    condition     = output.initial_snapshot_result.task_ids == ["task-a", "task-b", "task-c"]
    error_message = "The initial taskdb snapshot did not contain the expected task IDs."
  }

  assert {
    condition     = output.initial_snapshot_result.tasks_by_id["task-a"].task_type == "prepare_inputs"
    error_message = "task-a did not round-trip with the expected task type."
  }

  assert {
    condition     = output.initial_snapshot_result.tasks_by_id["task-b"].task_type == "stage_inputs"
    error_message = "task-b did not round-trip with the expected task type."
  }

  assert {
    condition     = output.initial_snapshot_result.tasks_by_id["task-c"].task_type == "collect_outputs"
    error_message = "task-c did not round-trip with the expected task type."
  }

  assert {
    condition     = output.initial_snapshot_result.tasks_by_id["task-a"].task_details == { stage = "a" }
    error_message = "task-a did not round-trip with the expected task details."
  }

  assert {
    condition     = output.initial_snapshot_result.tasks_by_id["task-b"].task_details == { stage = "b" }
    error_message = "task-b did not round-trip with the expected task details."
  }

  assert {
    condition     = output.initial_snapshot_result.tasks_by_id["task-c"].task_details == { stage = "c" }
    error_message = "task-c did not round-trip with the expected task details."
  }

  assert {
    condition     = output.initial_snapshot_result.tasks_by_id["task-a"].attempt == 1
    error_message = "task-a should have been checked out exactly once after ADD_TASKS."
  }

  assert {
    condition     = output.initial_snapshot_result.tasks_by_id["task-b"].attempt == 1
    error_message = "task-b should have been checked out exactly once after ADD_TASKS."
  }

  assert {
    condition     = output.initial_snapshot_result.tasks_by_id["task-c"].attempt == 0
    error_message = "task-c should still be unattempted after ADD_TASKS."
  }

  assert {
    condition     = output.initial_task_messages_result.message_count == 2
    error_message = "The observer queue did not receive exactly two initial runnable tasks."
  }

  assert {
    condition     = output.initial_task_ids == tolist(["task-a", "task-b"])
    error_message = "The initial runnable tasks were not task-a and task-b."
  }

  assert {
    condition     = output.initial_task_graph_ids == tolist([output.graph_id])
    error_message = "The initial task messages did not all carry the expected graph_id."
  }

  assert {
    condition     = output.initial_tasks_by_id["task-a"].body.task_type == output.initial_tasks_by_id["task-a"].message_attributes.task_type.StringValue
    error_message = "task-a did not preserve the task_type body and message attribute contract."
  }

  assert {
    condition     = output.initial_tasks_by_id["task-b"].body.task_type == output.initial_tasks_by_id["task-b"].message_attributes.task_type.StringValue
    error_message = "task-b did not preserve the task_type body and message attribute contract."
  }

  assert {
    condition     = output.empty_after_initial_fanout_result.message_count == 0
    error_message = "The observer queue was not empty after consuming the initial runnable tasks."
  }

  assert {
    condition     = output.publish_task_a_completed_result.message_id != ""
    error_message = "Publishing the task-a completion message did not return an SQS message ID."
  }

  assert {
    condition     = output.after_task_a_snapshot_result.exists
    error_message = "The taskdb snapshot was not readable after completing task-a."
  }

  assert {
    condition     = output.after_task_a_snapshot_result.etag != output.initial_snapshot_result.etag
    error_message = "Completing task-a did not produce a new taskdb snapshot."
  }

  assert {
    condition     = output.empty_after_task_a_result.message_count == 0
    error_message = "A downstream task was published after only task-a completed."
  }

  assert {
    condition     = output.publish_task_b_completed_result.message_id != ""
    error_message = "Publishing the task-b completion message did not return an SQS message ID."
  }

  assert {
    condition     = output.final_snapshot_result.exists
    error_message = "The final taskdb snapshot was not readable after completing task-b."
  }

  assert {
    condition     = output.final_snapshot_result.etag != output.after_task_a_snapshot_result.etag
    error_message = "Completing task-b did not produce a new taskdb snapshot."
  }

  assert {
    condition     = output.final_task_messages_result.message_count == 1
    error_message = "The observer queue did not receive exactly one final runnable task."
  }

  assert {
    condition     = output.final_task_ids == tolist(["task-c"])
    error_message = "The final runnable task was not task-c."
  }

  assert {
    condition     = output.final_tasks_by_id["task-c"].body.graph_id == output.graph_id
    error_message = "task-c did not carry the expected graph_id."
  }

  assert {
    condition     = output.final_tasks_by_id["task-c"].body.attempt == 1
    error_message = "task-c should have been emitted with attempt 1."
  }

  assert {
    condition     = output.final_tasks_by_id["task-c"].body.task_type == output.final_tasks_by_id["task-c"].message_attributes.task_type.StringValue
    error_message = "task-c did not preserve the task_type body and message attribute contract."
  }

  assert {
    condition     = output.final_snapshot_result.tasks_by_id["task-c"].attempt == 1
    error_message = "The final snapshot did not record task-c with attempt 1."
  }
}
