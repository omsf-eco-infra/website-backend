run "lambda_image_build_and_push" {
  command = apply

  assert {
    condition     = output.repository_name != ""
    error_message = "The lambda-deploy module did not return an ECR repository name."
  }

  assert {
    condition     = can(regex("^src-[0-9a-f]{64}$", output.image_tag))
    error_message = "The lambda-deploy module did not derive the expected source-hash image tag."
  }

  assert {
    condition     = can(regex("^[0-9a-f]{64}$", output.source_hash))
    error_message = "The lambda-deploy module did not compute a source hash."
  }

  assert {
    condition     = can(regex("^sha256:[0-9a-f]{64}$", output.image_digest))
    error_message = "The lambda-deploy module did not resolve an image digest after pushing the tag."
  }

  assert {
    condition     = output.image_digest == output.resolved_by_tag_digest
    error_message = "Resolving the published image by tag did not return the same digest."
  }

  assert {
    condition     = output.resolved_image_uri == "${output.repository_url}@${output.image_digest}"
    error_message = "The lambda-deploy module did not expose the expected digest-pinned image URI."
  }
}
