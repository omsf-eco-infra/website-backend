data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

data "aws_region" "current" {}

locals {
  lambda_source_arn_pattern = "arn:${data.aws_partition.current.partition}:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:*"
}

resource "terraform_data" "lambda_platform" {
  input = {
    docker_platform     = var.docker_platform
    lambda_architecture = var.lambda_architecture
  }

  lifecycle {
    precondition {
      condition = (
        (var.lambda_architecture == "x86_64" && var.docker_platform == "linux/amd64") ||
        (var.lambda_architecture == "arm64" && var.docker_platform == "linux/arm64")
      )
      error_message = "docker_platform must match lambda_architecture."
    }
  }
}

module "container_image" {
  source = "../container-image"

  repository_name   = var.repository_name
  dockerfile_dir    = var.dockerfile_dir
  build_context_dir = var.build_context_dir
  source_hash_paths = var.source_hash_paths
  docker_platform   = var.docker_platform
  tags              = var.tags

  depends_on = [terraform_data.lambda_platform]
}

# Allow Lambda to keep pulling published images from this repository.
data "aws_iam_policy_document" "lambda_pull" {
  statement {
    sid    = "AllowLambdaImageRetrieval"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]

    condition {
      test     = "StringLike"
      variable = "aws:sourceArn"
      values   = [local.lambda_source_arn_pattern]
    }
  }
}

resource "aws_ecr_repository_policy" "lambda_pull" {
  repository = module.container_image.repository_name
  policy     = data.aws_iam_policy_document.lambda_pull.json
}
