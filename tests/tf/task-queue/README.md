# task-queue test

This harness validates the reusable task-queue Terraform module against a real
AWS sandbox account.

It deploys a FIFO task topic plus one task-queue module instance, publishes
matching and non-matching task messages through SNS, asserts that only the
matching task reaches the queue, and then exercises the queue redrive policy
until a task lands in the DLQ.

Run it with sandbox AWS credentials available in the environment:

```bash
pixi run -e dev tofu -chdir=tests/tf/task-queue init
pixi run -e dev tofu -chdir=tests/tf/task-queue test -test-directory=.
```

Optional variables:

- `TF_VAR_owner`: owner tag prefix for the test run; defaults to `local`
