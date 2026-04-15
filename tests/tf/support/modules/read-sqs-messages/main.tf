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

variable "queue_url" {
  type = string
}

variable "min_message_count" {
  type    = number
  default = 1
}

variable "max_number_of_messages" {
  type    = number
  default = 10
}

variable "wait_time_seconds" {
  type    = number
  default = 5
}

variable "timeout_seconds" {
  type    = number
  default = 180
}

variable "poll_interval_seconds" {
  type    = number
  default = 5
}

data "external" "this" {
  program = [
    var.python_executable,
    "-m",
    "website_backend.testing.read_sqs_messages",
    "--external-output",
    "--queue-url",
    var.queue_url,
    "--min-message-count",
    tostring(var.min_message_count),
    "--max-number-of-messages",
    tostring(var.max_number_of_messages),
    "--wait-time-seconds",
    tostring(var.wait_time_seconds),
    "--timeout-seconds",
    tostring(var.timeout_seconds),
    "--poll-interval-seconds",
    tostring(var.poll_interval_seconds),
  ]
  query = {}
}

output "result" {
  value = jsondecode(data.external.this.result.json)
}
