data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

data "aws_region" "current" {}

locals {
  normalized_build_context_dir = abspath(var.build_context_dir)
  normalized_dockerfile_dir    = abspath(var.dockerfile_dir)
  dockerfile_path              = "${local.normalized_dockerfile_dir}/Dockerfile"
  normalized_source_hash_paths = sort(distinct([for path in var.source_hash_paths : abspath(path)]))

  source_path_entries = {
    for path in local.normalized_source_hash_paths :
    path => distinct(sort(concat(
      try(tolist(fileset(path, "**")), []),
      try(tolist(fileset(path, ".*")), []),
      try(tolist(fileset(path, "**/.*")), []),
    )))
  }

  invalid_source_hash_paths = [
    for path, entries in local.source_path_entries :
    path
    if length(entries) == 0 && !can(filesha256(path))
  ]

  source_hash_entries = flatten([
    for path in local.normalized_source_hash_paths : (
      length(local.source_path_entries[path]) > 0
      ? [
        for relative_path in local.source_path_entries[path] : {
          logical_path = (
            path == local.normalized_build_context_dir
            ? relative_path
            : startswith(path, "${local.normalized_build_context_dir}/")
            ? "${trimprefix(path, "${local.normalized_build_context_dir}/")}/${relative_path}"
            : "${path}/${relative_path}"
          )
          absolute_path = "${path}/${relative_path}"
        }
      ]
      : [
        {
          logical_path = (
            startswith(path, "${local.normalized_build_context_dir}/")
            ? trimprefix(path, "${local.normalized_build_context_dir}/")
            : path
          )
          absolute_path = path
        }
      ]
    )
    if !(length(local.source_path_entries[path]) == 0 && !can(filesha256(path)))
  ])

  source_hash_manifest = sort([
    for entry in local.source_hash_entries :
    "${entry.logical_path}:${filesha256(entry.absolute_path)}"
  ])

  source_hash               = sha256(join("\n", local.source_hash_manifest))
  image_tag                 = "src-${local.source_hash}"
  lambda_source_arn_pattern = "arn:${data.aws_partition.current.partition}:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:*"
}

resource "aws_ecr_repository" "this" {
  name                 = var.repository_name
  force_delete         = var.force_delete
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = var.tags
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
  repository = aws_ecr_repository.this.name
  policy     = data.aws_iam_policy_document.lambda_pull.json
}

resource "terraform_data" "build_push" {
  triggers_replace = {
    build_context_dir    = local.normalized_build_context_dir
    docker_platform      = var.docker_platform
    dockerfile_path      = local.dockerfile_path
    image_tag            = local.image_tag
    lambda_architecture  = var.lambda_architecture
    repository_name      = aws_ecr_repository.this.name
    repository_url       = aws_ecr_repository.this.repository_url
    source_hash          = local.source_hash
    source_hash_manifest = sha256(join("\n", local.source_hash_manifest))
  }

  lifecycle {
    precondition {
      condition     = fileexists(local.dockerfile_path)
      error_message = "dockerfile_dir must contain a Dockerfile."
    }

    precondition {
      condition     = length(local.invalid_source_hash_paths) == 0
      error_message = "source_hash_paths must point to existing files or non-empty directories."
    }

    precondition {
      condition     = length(local.source_hash_manifest) > 0
      error_message = "source_hash_paths must expand to at least one file."
    }

    precondition {
      condition = (
        (var.lambda_architecture == "x86_64" && var.docker_platform == "linux/amd64") ||
        (var.lambda_architecture == "arm64" && var.docker_platform == "linux/arm64")
      )
      error_message = "docker_platform must match lambda_architecture."
    }
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
      set -euo pipefail
      export AWS_PAGER=""
      aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$REGISTRY_HOST" >/dev/null
      docker build --platform "$DOCKER_PLATFORM" --tag "$REPOSITORY_URL:$IMAGE_TAG" --file "$DOCKERFILE_PATH" "$BUILD_CONTEXT_DIR"
      docker push "$REPOSITORY_URL:$IMAGE_TAG"

      for _ in $(seq 1 30); do
        digest="$(aws ecr describe-images --region "$AWS_REGION" --repository-name "$REPOSITORY_NAME" --image-ids imageTag="$IMAGE_TAG" --query 'imageDetails[0].imageDigest' --output text 2>/dev/null || true)"
        if [[ "$digest" == sha256:* ]]; then
          exit 0
        fi
        sleep 2
      done

      echo "Timed out waiting for ECR to surface $REPOSITORY_URL:$IMAGE_TAG" >&2
      exit 1
    EOT
    environment = {
      AWS_REGION        = data.aws_region.current.name
      BUILD_CONTEXT_DIR = local.normalized_build_context_dir
      DOCKERFILE_PATH   = local.dockerfile_path
      DOCKER_PLATFORM   = var.docker_platform
      IMAGE_TAG         = local.image_tag
      REGISTRY_HOST     = split("/", aws_ecr_repository.this.repository_url)[0]
      REPOSITORY_NAME   = aws_ecr_repository.this.name
      REPOSITORY_URL    = aws_ecr_repository.this.repository_url
    }
  }

  depends_on = [aws_ecr_repository_policy.lambda_pull]
}

data "aws_ecr_image" "this" {
  repository_name = aws_ecr_repository.this.name
  image_tag       = local.image_tag

  depends_on = [terraform_data.build_push]
}
