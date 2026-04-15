run "sqs_message_round_trip" {
  command = apply

  assert {
    condition     = output.publish_result.message_id != ""
    error_message = "The helper wrapper did not return an SQS message ID."
  }

  assert {
    condition     = output.read_result.message_count == 1
    error_message = "The SQS smoke test did not read exactly one message."
  }

  assert {
    condition     = output.read_result.message_count == 1 && jsonencode(jsondecode(output.read_result.messages[0].Body)) == jsonencode(jsondecode(output.expected_body))
    error_message = "The SQS smoke test did not round-trip the expected JSON payload."
  }
}
