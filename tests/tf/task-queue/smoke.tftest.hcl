run "filter_and_redrive" {
  command = apply

  assert {
    condition     = output.task_queue_url != ""
    error_message = "The task-queue module did not return a task queue URL."
  }

  assert {
    condition     = output.task_queue_arn != ""
    error_message = "The task-queue module did not return a task queue ARN."
  }

  assert {
    condition     = output.task_queue_name != ""
    error_message = "The task-queue module did not return a task queue name."
  }

  assert {
    condition     = output.task_queue_dlq_url != ""
    error_message = "The task-queue module did not return a DLQ URL."
  }

  assert {
    condition     = output.task_queue_dlq_arn != ""
    error_message = "The task-queue module did not return a DLQ ARN."
  }

  assert {
    condition     = output.task_queue_dlq_name != ""
    error_message = "The task-queue module did not return a DLQ name."
  }

  assert {
    condition     = output.subscription_arn != ""
    error_message = "The task-queue module did not return an SNS subscription ARN."
  }

  assert {
    condition     = output.publish_matching_result.message_id != ""
    error_message = "Publishing the matching task message did not return an SNS message ID."
  }

  assert {
    condition     = output.publish_non_matching_result.message_id != ""
    error_message = "Publishing the non-matching task message did not return an SNS message ID."
  }

  assert {
    condition     = output.filter_match_result.message_count == 1
    error_message = "The task queue did not receive exactly one matching task message."
  }

  assert {
    condition     = output.filter_message != null
    error_message = "The matching task message was not available for inspection."
  }

  assert {
    condition     = output.filter_message.body.task_id == "task-match"
    error_message = "The matching task message did not preserve the expected task_id."
  }

  assert {
    condition     = output.filter_message.body.task_type == "prepare_inputs"
    error_message = "The matching task message did not preserve the expected task_type."
  }

  assert {
    condition     = output.filter_message.body.version == output.contract_version
    error_message = "The matching task message did not preserve the expected contract version."
  }

  assert {
    condition     = output.filter_message.message_attributes.task_type.StringValue == output.filter_message.body.task_type
    error_message = "The matching task message did not preserve the task_type AWS message attribute."
  }

  assert {
    condition     = output.filter_message.message_attributes.version.StringValue == output.filter_message.body.version
    error_message = "The matching task message did not preserve the version AWS message attribute."
  }

  assert {
    condition     = output.filter_empty_result.message_count == 0
    error_message = "A non-matching task message reached the filtered task queue."
  }

  assert {
    condition     = output.publish_redrive_result.message_id != ""
    error_message = "Publishing the redrive task message did not return an SNS message ID."
  }

  assert {
    condition     = output.exercise_redrive_result.receive_count >= 1
    error_message = "The redrive helper never received the source queue message."
  }

  assert {
    condition     = output.exercise_redrive_result.did_drain_from_source
    error_message = "The redrive helper did not observe the source queue draining after receives."
  }

  assert {
    condition     = output.redriven_dlq_result.message_count == 1
    error_message = "The task queue DLQ did not receive exactly one redriven task message."
  }

  assert {
    condition     = output.redriven_dlq_message != null
    error_message = "The redriven DLQ message was not available for inspection."
  }

  assert {
    condition     = output.redriven_dlq_message.body.task_id == "task-redrive"
    error_message = "The DLQ message did not preserve the expected task_id."
  }

  assert {
    condition     = output.redriven_dlq_message.body.task_type == "stage_inputs"
    error_message = "The DLQ message did not preserve the expected task_type."
  }

  assert {
    condition     = output.redriven_dlq_message.message_attributes.task_type.StringValue == output.redriven_dlq_message.body.task_type
    error_message = "The DLQ message did not preserve the task_type AWS message attribute."
  }
}
