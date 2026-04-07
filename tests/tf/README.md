# OpenTofu Tests

OpenTofu `tofu test` fixtures and Terraform-compatible assertions live here.

Conventions:

- Place module-specific harness roots under `tests/tf/<module-name>/`.
- Keep module-name directories aligned with `modules/`, for example `tests/tf/orchestration/` and `tests/tf/web-interface/`.
- On first use for a harness root, run `pixi run -e dev tofu -chdir=tests/tf/<module-name> init`.
- Run infra tests with `pixi run -e dev tofu -chdir=tests/tf/<module-name> test -test-directory=.`
- The canonical repo tasks are `pixi run -e dev test-tf-support-smoke` and `pixi run -e dev test-tf-ci-smoke`.
- Keep shared helper wrapper modules under `tests/tf/support/modules/`.
- Invoke Python helpers from those wrappers as `python -m website_backend.testing.<module>`.
- Keep local smoke tests for the wrapper pattern under `tests/tf/support/`.
- Keep the GitHub Actions real-AWS smoke harness under `tests/tf/ci-smoke/`.
- Mutating helper wrappers write JSON artifacts under `.tf-test-artifacts/`.
- Reserve this tree for OpenTofu/Terraform-compatible test inputs, assertions, and supporting fixture files, not for generic example payloads.
