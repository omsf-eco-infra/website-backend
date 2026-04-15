# CI smoke test

This harness validates the GitHub Actions Terraform path against a real AWS
sandbox account.

It provisions a tagged FIFO SQS queue, publishes a sample JSON message through
the shared helper wrapper, reads the message back through the shared helper
wrapper, and asserts the round-trip result with native `tofu test`.

Run it with sandbox AWS credentials available in the environment:

```bash
pixi run -e dev test-tf-ci-smoke
```

Optional variables:

- `TF_VAR_owner`: owner tag prefix for the test run; defaults to `local`
