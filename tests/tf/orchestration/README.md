# orchestration test

This harness validates the reusable orchestration Terraform module against a
real AWS sandbox account.

It deploys the orchestrator stack, instantiates the reusable `task-queue`
module as an observer lane on the shared task SNS topic, drives a three-node
DAG through the orchestration queue, and asserts both downstream task fanout
and persisted taskdb snapshot state.
The harness enables `state_bucket_force_destroy` so the test run can tear down
its snapshot bucket cleanly after writing taskdb objects.

Run it with sandbox AWS credentials available in the environment:

```bash
pixi run -e dev tofu -chdir=tests/tf/orchestration init
pixi run -e dev tofu -chdir=tests/tf/orchestration test -test-directory=.
```

Optional variables:

- `TF_VAR_owner`: owner tag prefix for the test run; defaults to `local`
