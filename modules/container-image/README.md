# container-image

This module builds a Docker image from local source, pushes it to a dedicated
ECR repository, and returns a digest-pinned image URI.

It is intentionally runtime-agnostic. Lambda, Fargate, and future compute
modules should use this module for image publication while keeping their
runtime-specific IAM and deployment resources in their own modules.

## Inputs

- `repository_name`: ECR repository name to create and publish into
- `dockerfile_dir`: directory that contains the `Dockerfile`
- `build_context_dir`: Docker build context directory
- `source_hash_paths`: explicit files and directories whose contents should
  trigger a rebuild when they change
- `docker_platform`: Docker build platform, default `linux/amd64`
- `tags`: resource tags applied to the ECR repository

## Outputs

- `repository_name`
- `repository_url`
- `source_hash`
- `image_tag`
- `image_digest`
- `resolved_image_uri`

## Notes

- The module uses `terraform_data` plus `local-exec`, so the machine running
  OpenTofu must have both `docker` and `aws` CLIs available and already
  configured for the target AWS account.
- The module does not add runtime-specific repository policies. For example,
  Lambda image pull permissions are added by `lambda-deploy`, not here.
