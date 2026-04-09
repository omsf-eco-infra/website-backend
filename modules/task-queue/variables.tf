variable "name_prefix" {
  description = "Lowercase hyphen-safe prefix used to derive the task queue resource names."
  type        = string

  validation {
    condition = (
      trimspace(var.name_prefix) != "" &&
      can(regex("^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", var.name_prefix)) &&
      length(var.name_prefix) <= 65
    )
    error_message = "name_prefix must be a non-empty lowercase hyphen-safe string no longer than 65 characters."
  }
}

variable "task_topic_arn" {
  description = "ARN of the shared task SNS topic that publishes TaskMessage payloads."
  type        = string

  validation {
    condition     = trimspace(var.task_topic_arn) != ""
    error_message = "task_topic_arn must be a non-empty string."
  }
}

variable "task_types" {
  description = "Unique task_type routing keys that should be delivered to this queue."
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

variable "task_queue_max_receive_count" {
  description = "How many times SQS should retry a task message before moving it to the DLQ."
  type        = number
  default     = 5

  validation {
    condition = (
      floor(var.task_queue_max_receive_count) == var.task_queue_max_receive_count &&
      var.task_queue_max_receive_count >= 1
    )
    error_message = "task_queue_max_receive_count must be a whole number greater than or equal to 1."
  }
}

variable "queue_visibility_timeout_seconds" {
  description = "Visibility timeout for the task queue, in seconds."
  type        = number
  default     = 300

  validation {
    condition = (
      floor(var.queue_visibility_timeout_seconds) == var.queue_visibility_timeout_seconds &&
      var.queue_visibility_timeout_seconds >= 0 &&
      var.queue_visibility_timeout_seconds <= 43200
    )
    error_message = "queue_visibility_timeout_seconds must be a whole number between 0 and 43200 seconds."
  }
}

variable "tags" {
  description = "Tags applied to the AWS resources created by this module."
  type        = map(string)
  default     = {}
}
