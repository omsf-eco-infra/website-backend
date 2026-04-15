# Shared support modules

These modules wrap `website_backend.testing.*` helper modules for use inside OpenTofu test harnesses.

- Mutating wrappers use `terraform_data` plus `local-exec`.
- Read wrappers use the `external` provider plus `--external-output`.
- Wrappers return structured JSON by decoding the helper output before exposing it as module outputs.

Image publishing is intentionally not part of this shared support layer.
