variable "name_prefix" {
  description = "Lowercase hyphen-safe prefix used to derive the orchestration resource names."
  type        = string

  validation {
    condition = (
      trimspace(var.name_prefix) != "" &&
      can(regex("^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", var.name_prefix)) &&
      length(var.name_prefix) <= 51
    )
    error_message = "name_prefix must be a non-empty lowercase hyphen-safe string no longer than 51 characters."
  }
}

variable "workflow_name" {
  description = "Workflow identifier passed to the orchestrator Lambda as WORKFLOW_NAME."
  type        = string

  validation {
    condition     = trimspace(var.workflow_name) != ""
    error_message = "workflow_name must be a non-empty string."
  }
}

variable "state_prefix" {
  description = "Optional logical prefix passed to the Lambda as STATE_PREFIX for future backend conventions; Phase 3 does not prepend it to graph_id when reading or writing taskdb snapshots."
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags applied to the AWS resources created by this module."
  type        = map(string)
  default     = {}
}

variable "lambda_timeout" {
  description = "Timeout for the orchestrator Lambda, in seconds."
  type        = number
  default     = 60

  validation {
    condition = (
      floor(var.lambda_timeout) == var.lambda_timeout &&
      var.lambda_timeout >= 1 &&
      var.lambda_timeout <= 900
    )
    error_message = "lambda_timeout must be a whole number between 1 and 900 seconds."
  }
}

variable "lambda_memory_size" {
  description = "Memory size for the orchestrator Lambda, in MB."
  type        = number
  default     = 512

  validation {
    condition = (
      floor(var.lambda_memory_size) == var.lambda_memory_size &&
      var.lambda_memory_size >= 128 &&
      var.lambda_memory_size <= 10240
    )
    error_message = "lambda_memory_size must be a whole number between 128 and 10240 MB."
  }
}

variable "dockerfile_dir" {
  description = "Directory containing the orchestrator Lambda Dockerfile."
  type        = string

  validation {
    condition     = trimspace(var.dockerfile_dir) != ""
    error_message = "dockerfile_dir must be a non-empty string."
  }
}

variable "build_context_dir" {
  description = "Docker build context directory passed through to lambda-deploy."
  type        = string

  validation {
    condition     = trimspace(var.build_context_dir) != ""
    error_message = "build_context_dir must be a non-empty string."
  }
}

variable "source_hash_paths" {
  description = "Files and directories whose contents should trigger a rebuild of the orchestrator Lambda image."
  type        = list(string)

  validation {
    condition = length(var.source_hash_paths) > 0 && alltrue([
      for path in var.source_hash_paths : trimspace(path) != ""
    ])
    error_message = "source_hash_paths must contain at least one non-empty file or directory path."
  }
}

variable "docker_platform" {
  description = "Docker build platform passed through to lambda-deploy."
  type        = string
  default     = "linux/amd64"

  validation {
    condition     = contains(["linux/amd64", "linux/arm64"], var.docker_platform)
    error_message = "docker_platform must be linux/amd64 or linux/arm64."
  }
}

variable "lambda_architecture" {
  description = "Lambda architecture passed through to lambda-deploy and the deployed Lambda function."
  type        = string
  default     = "x86_64"

  validation {
    condition     = contains(["x86_64", "arm64"], var.lambda_architecture)
    error_message = "lambda_architecture must be x86_64 or arm64."
  }
}

variable "orchestration_queue_max_receive_count" {
  description = "How many times SQS should retry an orchestration message before moving it to the DLQ."
  type        = number
  default     = 5

  validation {
    condition = (
      floor(var.orchestration_queue_max_receive_count) == var.orchestration_queue_max_receive_count &&
      var.orchestration_queue_max_receive_count >= 1
    )
    error_message = "orchestration_queue_max_receive_count must be a whole number greater than or equal to 1."
  }
}

variable "enable_state_bucket_versioning" {
  description = "Whether to enable S3 versioning on the taskdb state bucket. Disabled by default because taskdb snapshots churn frequently."
  type        = bool
  default     = false
}
