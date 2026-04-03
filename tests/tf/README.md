# Terraform tests

Native `terraform test` fixtures and assertions live here.

Conventions:

- Place module-specific test fixtures under `tests/tf/<module-name>/`.
- Keep module-name directories aligned with `modules/`, for example `tests/tf/orchestration/` and `tests/tf/web-interface/`.
- Reserve this tree for Terraform test inputs, assertions, and supporting fixture files, not for generic example payloads.
