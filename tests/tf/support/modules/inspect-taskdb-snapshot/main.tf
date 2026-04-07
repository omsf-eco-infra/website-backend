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

variable "previous_etag" {
  type    = string
  default = null
}

variable "timeout_seconds" {
  type    = number
  default = 180
}

variable "poll_interval_seconds" {
  type    = number
  default = 5
}

locals {
  program = concat(
    [
      var.python_executable,
      "-m",
      "website_backend.testing.inspect_taskdb_snapshot",
      "--external-output",
      "--bucket",
      var.bucket,
      "--key",
      var.key,
      "--timeout-seconds",
      tostring(var.timeout_seconds),
      "--poll-interval-seconds",
      tostring(var.poll_interval_seconds),
    ],
    var.previous_etag == null ? [] : ["--previous-etag", var.previous_etag],
  )
}

data "external" "this" {
  program = local.program
  query   = {}
}

output "result" {
  value = jsondecode(data.external.this.result.json)
}
