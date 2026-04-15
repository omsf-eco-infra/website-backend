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
  default = "publish-sns-message"
}

variable "topic_arn" {
  type = string
}

variable "payload_file" {
  type = string
}

variable "subject" {
  type    = string
  default = null
}

variable "message_group_id" {
  type    = string
  default = null
}

variable "message_deduplication_id" {
  type    = string
  default = null
}

variable "message_attributes_file" {
  type    = string
  default = null
}

locals {
  artifact_path                 = abspath("${var.artifacts_root}/${var.test_name}/${var.artifact_name}.json")
  normalized_subject            = var.subject == null ? "" : var.subject
  normalized_message_group_id   = var.message_group_id == null ? "" : var.message_group_id
  normalized_message_dedup_id   = var.message_deduplication_id == null ? "" : var.message_deduplication_id
  normalized_message_attrs_file = var.message_attributes_file == null ? "" : var.message_attributes_file
  payload_sha1                  = fileexists(var.payload_file) ? filesha1(var.payload_file) : sha1(var.payload_file)
  message_attributes_file_sha1  = local.normalized_message_attrs_file == "" ? "" : (fileexists(local.normalized_message_attrs_file) ? filesha1(local.normalized_message_attrs_file) : sha1(local.normalized_message_attrs_file))
}

resource "terraform_data" "publish" {
  triggers_replace = {
    topic_arn                = var.topic_arn
    payload_sha1             = local.payload_sha1
    subject                  = local.normalized_subject
    message_group_id         = local.normalized_message_group_id
    message_deduplication_id = local.normalized_message_dedup_id
    message_attributes_sha1  = local.message_attributes_file_sha1
    artifact_path            = local.artifact_path
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
      set -euo pipefail
      mkdir -p "$(dirname "$ARTIFACT_PATH")"
      args=("-m" "website_backend.testing.publish_sns_message" "--topic-arn" "$TOPIC_ARN" "--payload-file" "$PAYLOAD_FILE")
      if [[ -n "$SUBJECT" ]]; then
        args+=("--subject" "$SUBJECT")
      fi
      if [[ -n "$MESSAGE_GROUP_ID" ]]; then
        args+=("--message-group-id" "$MESSAGE_GROUP_ID")
      fi
      if [[ -n "$MESSAGE_DEDUPLICATION_ID" ]]; then
        args+=("--message-deduplication-id" "$MESSAGE_DEDUPLICATION_ID")
      fi
      if [[ -n "$MESSAGE_ATTRIBUTES_FILE" ]]; then
        args+=("--message-attributes-file" "$MESSAGE_ATTRIBUTES_FILE")
      fi
      "$PYTHON_EXECUTABLE" "$${args[@]}" >"$ARTIFACT_PATH"
    EOT
    environment = {
      ARTIFACT_PATH            = local.artifact_path
      MESSAGE_ATTRIBUTES_FILE  = local.normalized_message_attrs_file
      MESSAGE_DEDUPLICATION_ID = local.normalized_message_dedup_id
      MESSAGE_GROUP_ID         = local.normalized_message_group_id
      PAYLOAD_FILE             = var.payload_file
      PYTHON_EXECUTABLE        = var.python_executable
      SUBJECT                  = local.normalized_subject
      TOPIC_ARN                = var.topic_arn
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
