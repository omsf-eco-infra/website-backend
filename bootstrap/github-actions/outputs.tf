output "role_arn" {
  description = "ARN of the GitHub Actions role."
  value       = aws_iam_role.github_actions.arn
}

output "aws_region" {
  description = "AWS region configured for the GitHub Actions workflows."
  value       = var.aws_region
}

output "oidc_provider_arn" {
  description = "ARN of the GitHub OIDC provider used by the role."
  value       = local.oidc_provider_arn
}
