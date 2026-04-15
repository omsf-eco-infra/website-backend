output "repository_name" {
  value = module.container_image.repository_name
}

output "repository_url" {
  value = module.container_image.repository_url
}

output "source_hash" {
  value = module.container_image.source_hash
}

output "image_tag" {
  value = module.container_image.image_tag
}

output "image_digest" {
  value = module.container_image.image_digest
}

output "resolved_image_uri" {
  value      = module.container_image.resolved_image_uri
  depends_on = [aws_ecr_repository_policy.lambda_pull]
}
