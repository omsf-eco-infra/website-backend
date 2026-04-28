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

variable "bucket" {
  type = string
}

variable "key" {
  type = string
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
    "website_backend.testing.read_s3_object",
    "--external-output",
    "--bucket",
    var.bucket,
    "--key",
    var.key,
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
