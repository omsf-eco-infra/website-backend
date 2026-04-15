# fargate-compute test

This harness validates the reusable Fargate compute Terraform module against a
real AWS sandbox account.

It discovers the account default VPC, builds and pushes the generic example
worker image through `modules/container-image`, provisions the compute module
plus a real task queue, publishes one matching `TaskMessage`, and asserts the
worker leaves a durable S3 result object behind before draining the queue.

Run it with sandbox AWS credentials available in the environment:

```bash
pixi run -e dev tofu -chdir=tests/tf/fargate-compute init
pixi run -e dev tofu -chdir=tests/tf/fargate-compute test -test-directory=.
```

Optional variables:

- `TF_VAR_owner`: owner tag prefix for the test run; defaults to `local`
