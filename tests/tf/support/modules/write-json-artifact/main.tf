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
  default = "artifact"
}

variable "content_json" {
  type = string
}

locals {
  artifact_path = abspath("${var.artifacts_root}/${var.test_name}/${var.artifact_name}.json")
  content_sha1  = sha1(var.content_json)
}

resource "terraform_data" "write" {
  triggers_replace = {
    artifact_path = local.artifact_path
    content_json  = var.content_json
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
      set -euo pipefail
      "$PYTHON_EXECUTABLE" - <<'PY'
import json
import os
from pathlib import Path

artifact_path = Path(os.environ["ARTIFACT_PATH"])
payload = json.loads(os.environ["CONTENT_JSON"])
artifact_path.parent.mkdir(parents=True, exist_ok=True)
artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
    EOT
    environment = {
      ARTIFACT_PATH     = local.artifact_path
      CONTENT_JSON      = var.content_json
      PYTHON_EXECUTABLE = var.python_executable
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
  depends_on = [terraform_data.write]
}

output "artifact_path" {
  value = local.artifact_path
}

output "content_sha1" {
  value = local.content_sha1
}

output "result" {
  value = jsondecode(data.external.result.result.json)
}
