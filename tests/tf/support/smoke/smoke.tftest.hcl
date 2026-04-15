run "local_harness_smoke" {
  command = apply

  assert {
    condition     = output.write_result.status_code == 200
    error_message = "The mutating wrapper did not persist the expected status code."
  }

  assert {
    condition     = output.read_result.body_json.ok == true
    error_message = "The read wrapper did not decode the artifact JSON payload."
  }

  assert {
    condition     = output.read_result.headers["content-type"] == "application/json"
    error_message = "The read wrapper did not preserve artifact headers."
  }
}
