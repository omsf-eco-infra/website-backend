variable "repository_name" {
  description = "ECR repository name to create and publish into."
  type        = string

  validation {
    condition     = trimspace(var.repository_name) != ""
    error_message = "repository_name must be a non-empty string."
  }
}

variable "dockerfile_dir" {
  description = "Directory containing the Dockerfile."
  type        = string

  validation {
    condition     = trimspace(var.dockerfile_dir) != ""
    error_message = "dockerfile_dir must be a non-empty string."
  }
}

variable "build_context_dir" {
  description = "Docker build context directory."
  type        = string

  validation {
    condition     = trimspace(var.build_context_dir) != ""
    error_message = "build_context_dir must be a non-empty string."
  }
}

variable "source_hash_paths" {
  description = "Files and directories whose contents should trigger an image rebuild."
  type        = list(string)

  validation {
    condition = length(var.source_hash_paths) > 0 && alltrue([
      for path in var.source_hash_paths : trimspace(path) != ""
    ])
    error_message = "source_hash_paths must contain at least one non-empty file or directory path."
  }
}

variable "docker_platform" {
  description = "Docker build platform."
  type        = string
  default     = "linux/amd64"

  validation {
    condition     = contains(["linux/amd64", "linux/arm64"], var.docker_platform)
    error_message = "docker_platform must be linux/amd64 or linux/arm64."
  }
}

variable "tags" {
  description = "Tags applied to the ECR repository."
  type        = map(string)
  default     = {}
}
