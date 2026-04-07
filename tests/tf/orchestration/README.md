# orchestration test

This harness validates the reusable orchestration Terraform module against a
real AWS sandbox account.

It deploys the orchestrator stack, subscribes a FIFO observer queue to the
shared task SNS topic, drives a three-node DAG through the orchestration queue,
and asserts both downstream task fanout and persisted taskdb snapshot state.

Run it with sandbox AWS credentials available in the environment:

```bash
pixi run -e dev test-tf-orchestration
```

Optional variables:

- `TF_VAR_owner`: owner tag prefix for the test run; defaults to `local`
