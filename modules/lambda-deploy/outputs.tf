output "repository_name" {
  value = aws_ecr_repository.this.name
}

output "repository_url" {
  value = aws_ecr_repository.this.repository_url
}

output "source_hash" {
  value = local.source_hash
}

output "image_tag" {
  value = local.image_tag
}

output "image_digest" {
  value = data.aws_ecr_image.this.image_digest
}

output "resolved_image_uri" {
  value = "${aws_ecr_repository.this.repository_url}@${data.aws_ecr_image.this.image_digest}"
}
