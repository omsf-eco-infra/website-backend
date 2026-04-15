# lambda-deploy

This module builds a Lambda container image from local source, pushes it to a
dedicated ECR repository, and returns a digest-pinned image URI for downstream
Lambda resources.

It wraps `modules/container-image` for generic image publication and adds the
Lambda-specific repository policy that allows the Lambda service to keep
pulling the published image.

Inputs:

- `repository_name`: ECR repository name to create and publish into
- `dockerfile_dir`: directory that contains the Lambda `Dockerfile`
- `build_context_dir`: Docker build context directory
- `source_hash_paths`: explicit files and directories whose contents should
  trigger a rebuild when they change
- `docker_platform`: Docker build platform, default `linux/amd64`
- `lambda_architecture`: Lambda architecture, default `x86_64`
- `tags`: resource tags applied to the ECR repository

Outputs:

- `repository_name`
- `repository_url`
- `source_hash`
- `image_tag`
- `image_digest`
- `resolved_image_uri`

Notes:

- The module uses `terraform_data` plus `local-exec`, so the machine running
  OpenTofu must have both `docker` and `aws` CLIs available and already
  configured for the target AWS account.
- Generic ECR image publication lives in `container-image`; this module should
  only contain Lambda-specific validation and repository policy behavior.
- `source_hash_paths` should include every local file tree that affects the
  Lambda image. For the current orchestration Lambda, that includes
  `pyproject.toml`, `src/website_backend`, and `modules/orchestration/lambda`.

Example:

```hcl
module "orchestrator_image" {
  source = "../lambda-deploy"

  repository_name   = "website-backend-orchestrator"
  dockerfile_dir    = "${path.root}/modules/orchestration/lambda"
  build_context_dir = path.root
  source_hash_paths = [
    "${path.root}/pyproject.toml",
    "${path.root}/src/website_backend",
    "${path.root}/modules/orchestration/lambda",
  ]

  tags = {
    component = "orchestration"
  }
}
```
