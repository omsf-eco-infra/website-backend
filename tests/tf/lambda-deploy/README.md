# lambda-deploy test

This harness validates the shared Lambda image publishing module against a real
AWS sandbox account.

It builds the current orchestrator Lambda image from local source, pushes it to
an isolated ECR repository, and verifies that the resulting tag resolves back
to the same image digest from AWS.

Run it with sandbox AWS credentials available in the environment:

```bash
pixi run -e dev tofu -chdir=tests/tf/lambda-deploy init
pixi run -e dev tofu -chdir=tests/tf/lambda-deploy test -test-directory=.
```

Optional variables:

- `TF_VAR_owner`: owner tag prefix for the test run; defaults to `local`
