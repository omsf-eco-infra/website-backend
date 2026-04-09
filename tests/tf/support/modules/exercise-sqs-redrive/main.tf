terraform {
  required_providers {
    external = {
      source = "hashicorp/external"
    }
  }
}

variable "python_executable" {
  type    = string
  default = "python"
}

variable "artifacts_root" {
  type = string
}

variable "test_name" {
  type = string
}

variable "artifact_name" {
  type    = string
  default = "exercise-sqs-redrive"
}

variable "queue_url" {
  type = string
}

variable "min_receive_count" {
  type    = number
  default = 1
}

variable "max_number_of_messages" {
  type    = number
  default = 1
}

variable "wait_time_seconds" {
  type    = number
  default = 1
}

variable "required_empty_polls" {
  type    = number
  default = 2
}

variable "timeout_seconds" {
  type    = number
  default = 60
}

variable "poll_interval_seconds" {
  type    = number
  default = 2
}

locals {
  artifact_path = abspath("${var.artifacts_root}/${var.test_name}/${var.artifact_name}.json")
}

resource "terraform_data" "exercise" {
  triggers_replace = {
    artifact_path          = local.artifact_path
    max_number_of_messages = tostring(var.max_number_of_messages)
    min_receive_count      = tostring(var.min_receive_count)
    poll_interval_seconds  = tostring(var.poll_interval_seconds)
    queue_url              = var.queue_url
    required_empty_polls   = tostring(var.required_empty_polls)
    timeout_seconds        = tostring(var.timeout_seconds)
    wait_time_seconds      = tostring(var.wait_time_seconds)
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
      set -euo pipefail
      mkdir -p "$(dirname "$ARTIFACT_PATH")"
      "$PYTHON_EXECUTABLE" -m website_backend.testing.exercise_sqs_redrive \
        --queue-url "$QUEUE_URL" \
        --min-receive-count "$MIN_RECEIVE_COUNT" \
        --max-number-of-messages "$MAX_NUMBER_OF_MESSAGES" \
        --wait-time-seconds "$WAIT_TIME_SECONDS" \
        --required-empty-polls "$REQUIRED_EMPTY_POLLS" \
        --timeout-seconds "$TIMEOUT_SECONDS" \
        --poll-interval-seconds "$POLL_INTERVAL_SECONDS" \
        >"$ARTIFACT_PATH"
    EOT
    environment = {
      ARTIFACT_PATH          = local.artifact_path
      MAX_NUMBER_OF_MESSAGES = tostring(var.max_number_of_messages)
      MIN_RECEIVE_COUNT      = tostring(var.min_receive_count)
      POLL_INTERVAL_SECONDS  = tostring(var.poll_interval_seconds)
      PYTHON_EXECUTABLE      = var.python_executable
      QUEUE_URL              = var.queue_url
      REQUIRED_EMPTY_POLLS   = tostring(var.required_empty_polls)
      TIMEOUT_SECONDS        = tostring(var.timeout_seconds)
      WAIT_TIME_SECONDS      = tostring(var.wait_time_seconds)
    }
  }
}

data "external" "result" {
  program = [
    var.python_executable,
    "-m",
    "website_backend.testing.read_json_file",
    "--external-output",
    "--path",
    local.artifact_path,
  ]
  query      = {}
  depends_on = [terraform_data.exercise]
}

output "artifact_path" {
  value = local.artifact_path
}

output "result" {
  value = jsondecode(data.external.result.result.json)
}
