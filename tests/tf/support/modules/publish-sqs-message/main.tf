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
  default = "publish-sqs-message"
}

variable "queue_url" {
  type = string
}

variable "payload_file" {
  type = string
}

variable "message_group_id" {
  type    = string
  default = null
}

variable "message_deduplication_id" {
  type    = string
  default = null
}

locals {
  artifact_path = abspath("${var.artifacts_root}/${var.test_name}/${var.artifact_name}.json")
}

resource "terraform_data" "publish" {
  triggers_replace = {
    queue_url                = var.queue_url
    payload_sha1             = filesha1(var.payload_file)
    message_group_id         = coalesce(var.message_group_id, "")
    message_deduplication_id = coalesce(var.message_deduplication_id, "")
    artifact_path            = local.artifact_path
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
      set -euo pipefail
      mkdir -p "$(dirname "$ARTIFACT_PATH")"
      args=("-m" "website_backend.testing.publish_sqs_message" "--queue-url" "$QUEUE_URL" "--payload-file" "$PAYLOAD_FILE")
      if [[ -n "$MESSAGE_GROUP_ID" ]]; then
        args+=("--message-group-id" "$MESSAGE_GROUP_ID")
      fi
      if [[ -n "$MESSAGE_DEDUPLICATION_ID" ]]; then
        args+=("--message-deduplication-id" "$MESSAGE_DEDUPLICATION_ID")
      fi
      "$PYTHON_EXECUTABLE" "$${args[@]}" >"$ARTIFACT_PATH"
    EOT
    environment = {
      ARTIFACT_PATH            = local.artifact_path
      MESSAGE_DEDUPLICATION_ID = coalesce(var.message_deduplication_id, "")
      MESSAGE_GROUP_ID         = coalesce(var.message_group_id, "")
      PAYLOAD_FILE             = var.payload_file
      PYTHON_EXECUTABLE        = var.python_executable
      QUEUE_URL                = var.queue_url
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
  depends_on = [terraform_data.publish]
}

output "artifact_path" {
  value = local.artifact_path
}

output "result" {
  value = jsondecode(data.external.result.result.json)
}
