variable "repository_name" {
  type = string

  validation {
    condition     = trimspace(var.repository_name) != ""
    error_message = "repository_name must be a non-empty string."
  }
}

variable "dockerfile_dir" {
  type = string

  validation {
    condition     = trimspace(var.dockerfile_dir) != ""
    error_message = "dockerfile_dir must be a non-empty string."
  }
}

variable "build_context_dir" {
  type = string

  validation {
    condition     = trimspace(var.build_context_dir) != ""
    error_message = "build_context_dir must be a non-empty string."
  }
}

variable "source_hash_paths" {
  type = list(string)

  validation {
    condition = length(var.source_hash_paths) > 0 && alltrue([
      for path in var.source_hash_paths : trimspace(path) != ""
    ])
    error_message = "source_hash_paths must contain at least one non-empty file or directory path."
  }
}

variable "docker_platform" {
  type    = string
  default = "linux/amd64"

  validation {
    condition     = contains(["linux/amd64", "linux/arm64"], var.docker_platform)
    error_message = "docker_platform must be linux/amd64 or linux/arm64."
  }
}

variable "lambda_architecture" {
  type    = string
  default = "x86_64"

  validation {
    condition     = contains(["x86_64", "arm64"], var.lambda_architecture)
    error_message = "lambda_architecture must be x86_64 or arm64."
  }
}

variable "tags" {
  type    = map(string)
  default = {}
}
