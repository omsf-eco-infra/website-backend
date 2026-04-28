variable "name_prefix" {
  description = "Lowercase hyphen-safe prefix used to derive the Fargate compute resource names."
  type        = string

  validation {
    condition = (
      trimspace(var.name_prefix) != "" &&
      can(regex("^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", var.name_prefix)) &&
      length(var.name_prefix) <= 47
    )
    error_message = "name_prefix must be a non-empty lowercase hyphen-safe string no longer than 47 characters."
  }
}

variable "workflow_name" {
  description = "Workflow identifier passed to the worker task definition as WORKFLOW_NAME."
  type        = string

  validation {
    condition     = trimspace(var.workflow_name) != ""
    error_message = "workflow_name must be a non-empty string."
  }
}

variable "task_topic_arn" {
  description = "ARN of the shared FIFO SNS task topic that publishes TaskMessage payloads."
  type        = string

  validation {
    condition     = trimspace(var.task_topic_arn) != ""
    error_message = "task_topic_arn must be a non-empty string."
  }
}

variable "task_types" {
  description = "Unique task_type routing keys that should trigger the launcher Lambda."
  type        = list(string)

  validation {
    condition = (
      length(var.task_types) > 0 &&
      alltrue([
        for task_type in var.task_types : trimspace(task_type) != ""
      ]) &&
      length(distinct([
        for task_type in var.task_types : trimspace(task_type)
      ])) == length(var.task_types)
    )
    error_message = "task_types must contain one or more unique non-empty task_type strings."
  }
}

variable "task_queue_url" {
  description = "URL of the task queue consumed by the worker container."
  type        = string

  validation {
    condition     = trimspace(var.task_queue_url) != ""
    error_message = "task_queue_url must be a non-empty string."
  }
}

variable "task_queue_arn" {
  description = "ARN of the task queue consumed by the worker container."
  type        = string

  validation {
    condition     = trimspace(var.task_queue_arn) != ""
    error_message = "task_queue_arn must be a non-empty string."
  }
}

variable "worker_image_uri" {
  description = "Digest-pinned image URI for the ECS worker container."
  type        = string

  validation {
    condition     = trimspace(var.worker_image_uri) != ""
    error_message = "worker_image_uri must be a non-empty string."
  }
}

variable "worker_container_name" {
  description = "Name of the ECS worker container."
  type        = string

  validation {
    condition = (
      trimspace(var.worker_container_name) != "" &&
      can(regex("^[A-Za-z0-9][A-Za-z0-9_-]*$", var.worker_container_name))
    )
    error_message = "worker_container_name must be a non-empty ECS-compatible container name."
  }
}

variable "worker_cpu" {
  description = "CPU units for the Fargate worker task definition."
  type        = number
  default     = 256

  validation {
    condition = (
      floor(var.worker_cpu) == var.worker_cpu &&
      var.worker_cpu > 0
    )
    error_message = "worker_cpu must be a whole number greater than zero."
  }
}

variable "worker_memory" {
  description = "Memory for the Fargate worker task definition, in MiB."
  type        = number
  default     = 512

  validation {
    condition = (
      floor(var.worker_memory) == var.worker_memory &&
      var.worker_memory > 0
    )
    error_message = "worker_memory must be a whole number greater than zero."
  }
}

variable "worker_environment" {
  description = "Additional environment variables merged onto the worker task definition."
  type        = map(string)
  default     = {}
}

variable "worker_additional_policy_statements" {
  description = "Additional IAM policy statements appended to the worker task role."
  type = list(object({
    sid       = optional(string)
    actions   = list(string)
    resources = list(string)
  }))
  default = []

  validation {
    condition = alltrue([
      for statement in var.worker_additional_policy_statements : (
        length(statement.actions) > 0 &&
        length(statement.resources) > 0 &&
        alltrue([for action in statement.actions : trimspace(action) != ""]) &&
        alltrue([for resource in statement.resources : trimspace(resource) != ""])
      )
    ])
    error_message = "worker_additional_policy_statements must contain non-empty action and resource lists."
  }
}

variable "subnet_ids" {
  description = "Subnet IDs passed to the launcher Lambda for ECS awsvpc networking."
  type        = list(string)

  validation {
    condition = (
      length(var.subnet_ids) > 0 &&
      alltrue([for subnet_id in var.subnet_ids : trimspace(subnet_id) != ""])
    )
    error_message = "subnet_ids must contain one or more non-empty subnet IDs."
  }
}

variable "security_group_ids" {
  description = "Security group IDs passed to the launcher Lambda for ECS awsvpc networking."
  type        = list(string)

  validation {
    condition = (
      length(var.security_group_ids) > 0 &&
      alltrue([for security_group_id in var.security_group_ids : trimspace(security_group_id) != ""])
    )
    error_message = "security_group_ids must contain one or more non-empty security group IDs."
  }
}

variable "assign_public_ip" {
  description = "Whether ECS awsvpc tasks should receive a public IP."
  type        = string
  default     = "DISABLED"

  validation {
    condition     = contains(["ENABLED", "DISABLED"], var.assign_public_ip)
    error_message = "assign_public_ip must be ENABLED or DISABLED."
  }
}

variable "launcher_timeout" {
  description = "Timeout for the launcher Lambda, in seconds."
  type        = number
  default     = 60

  validation {
    condition = (
      floor(var.launcher_timeout) == var.launcher_timeout &&
      var.launcher_timeout >= 1 &&
      var.launcher_timeout <= 900
    )
    error_message = "launcher_timeout must be a whole number between 1 and 900 seconds."
  }
}

variable "launcher_memory_size" {
  description = "Memory size for the launcher Lambda, in MB."
  type        = number
  default     = 512

  validation {
    condition = (
      floor(var.launcher_memory_size) == var.launcher_memory_size &&
      var.launcher_memory_size >= 128 &&
      var.launcher_memory_size <= 10240
    )
    error_message = "launcher_memory_size must be a whole number between 128 and 10240 MB."
  }
}

variable "dockerfile_dir" {
  description = "Directory containing the launcher Lambda Dockerfile."
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
  description = "Files and directories whose contents should trigger a rebuild of the launcher Lambda image."
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
  description = "Lambda architecture passed through to lambda-deploy and the deployed launcher Lambda."
  type        = string
  default     = "x86_64"

  validation {
    condition     = contains(["x86_64", "arm64"], var.lambda_architecture)
    error_message = "lambda_architecture must be x86_64 or arm64."
  }
}

variable "tags" {
  description = "Tags applied to the AWS resources created by this module."
  type        = map(string)
  default     = {}
}
