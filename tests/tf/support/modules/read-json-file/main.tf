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

variable "path" {
  type = string
}

data "external" "this" {
  program = [
    var.python_executable,
    "-m",
    "website_backend.testing.read_json_file",
    "--external-output",
    "--path",
    var.path,
  ]
  query = {}
}

output "result" {
  value = jsondecode(data.external.this.result.json)
}
