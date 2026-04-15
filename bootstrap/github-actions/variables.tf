variable "aws_region" {
  description = "AWS region used for the bootstrap provider configuration."
  type        = string
}

variable "github_org" {
  description = "GitHub organization that owns the repository."
  type        = string
  default     = "omsf-eco-infra"
}

variable "github_repo" {
  description = "GitHub repository name."
  type        = string
  default     = "website-backend"
}

variable "role_name" {
  description = "IAM role name for GitHub Actions."
  type        = string
}

variable "allowed_branch_names" {
  description = "Git refs in this repository that may assume the role outside pull_request runs."
  type        = list(string)
  default     = ["main"]
}

variable "existing_oidc_provider_arn" {
  description = "Optional ARN for an existing GitHub Actions OIDC provider."
  type        = string
  default     = null
}

variable "oidc_thumbprint_list" {
  description = "Thumbprints trusted for the GitHub Actions OIDC provider."
  type        = list(string)
  default = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd",
  ]
}
