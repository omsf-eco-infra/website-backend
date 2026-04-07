terraform {
  required_version = ">= 1.11.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }
}

provider "aws" {}

variable "owner" {
  type    = string
  default = "local"
}

locals {
  test_name       = "lambda-deploy"
  owner_segments  = regexall("[a-z0-9-]+", lower(var.owner))
  owner_joined    = length(local.owner_segments) > 0 ? join("-", local.owner_segments) : "local"
  owner_sanitized = substr(local.owner_joined, 0, 12)
  run_suffix      = substr(md5("${plantimestamp()}-${path.module}-${var.owner}"), 0, 8)
  run_id          = "${local.owner_sanitized}-${local.run_suffix}"
  created_at      = timestamp()
  expires_at      = timeadd(local.created_at, "24h")
  repository_name = "wb-orchestrator-${local.owner_sanitized}-${local.run_suffix}"
  repo_root       = abspath("${path.root}/../../..")
  common_tags = {
    managed_by = "test-website-backend"
    repo       = "website-backend"
    module     = local.test_name
    test_name  = local.test_name
    owner      = local.owner_sanitized
    run_id     = local.run_id
    created_at = local.created_at
    expires_at = local.expires_at
  }
}

module "this" {
  source = "../../../modules/lambda-deploy"

  repository_name   = local.repository_name
  dockerfile_dir    = "${local.repo_root}/modules/orchestration/lambda"
  build_context_dir = local.repo_root
  source_hash_paths = [
    "${local.repo_root}/pyproject.toml",
    "${local.repo_root}/src/website_backend",
    "${local.repo_root}/modules/orchestration/lambda",
  ]
  tags = local.common_tags
}

data "aws_ecr_image" "resolved_by_tag" {
  repository_name = local.repository_name
  image_tag       = module.this.image_tag

  depends_on = [module.this]
}

output "repository_name" {
  value = module.this.repository_name
}

output "repository_url" {
  value = module.this.repository_url
}

output "source_hash" {
  value = module.this.source_hash
}

output "image_tag" {
  value = module.this.image_tag
}

output "image_digest" {
  value = module.this.image_digest
}

output "resolved_image_uri" {
  value = module.this.resolved_image_uri
}

output "resolved_by_tag_digest" {
  value = data.aws_ecr_image.resolved_by_tag.image_digest
}

output "run_id" {
  value = local.run_id
}
