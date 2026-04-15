locals {
  artifacts_root = abspath("${path.module}/../../../../.tf-test-artifacts")
}

module "write_result_artifact" {
  source         = "../modules/write-json-artifact"
  artifacts_root = local.artifacts_root
  test_name      = "support-smoke"
  artifact_name  = "function-url-response"
  content_json = jsonencode({
    body_json = {
      ok = true
    }
    body_text = "{\"ok\": true}"
    headers = {
      content-type = "application/json"
    }
    status_code = 200
  })
}

module "read_result_artifact" {
  source     = "../modules/read-json-file"
  path       = module.write_result_artifact.artifact_path
  depends_on = [module.write_result_artifact]
}

output "artifact_path" {
  value = module.write_result_artifact.artifact_path
}

output "write_result" {
  value = module.write_result_artifact.result
}

output "read_result" {
  value = module.read_result_artifact.result
}
