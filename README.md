# website-backend

This repository is building reusable AWS workflow-platform components. Phase 0 locks the repo layout, naming rules, and runtime-configuration contract so later phases can add behavior without reopening those decisions.

## Repo layout

- `src/website_backend/`: reusable Python runtime code
- `tests/py/`: Python unit tests
- `modules/`: reusable Terraform modules
- `tests/tf/`: native `terraform test` fixtures and assertions
- `examples/`: generic example payloads, assets, and container contexts
- `scripts/`: shell helpers if a future phase needs them

## Naming conventions

- Python imports stay under `website_backend.*`.
- Terraform module directories stay hyphenated and match the public module names: `orchestration`, `task-queue`, `fargate-compute`, and `web-interface`.
- Lambda functions, ECR repositories, and example worker images use hyphenated role names derived from the component, for example `website-backend-orchestrator`, `website-backend-web-interface`, `website-backend-fargate-launcher`, and `website-backend-example-worker`.
- Python helper modules use snake_case names under `website_backend.testing.*`.
- Example payloads and test assets use snake_case family names plus dot-delimited scenarios, for example `inputs_message.valid.json` and `task_message.matching.json`.

## Runtime configuration

Deployment-specific values are injected into each Lambda function or ECS task definition by Terraform. They are not baked into image builds.

Rules:

- Pass only the environment variables a runtime actually consumes.
- Use descriptive resource-oriented names without a repo prefix.
- Keep secrets out of this contract.
- Encode list-valued settings as JSON arrays so Terraform can `jsonencode(...)` them and Python can parse them deterministically.

### Orchestrator Lambda

- `WORKFLOW_NAME`
- `STATE_BUCKET`
- `STATE_PREFIX`
- `TASK_TOPIC_ARN`

### Web-interface Lambda

- `WORKFLOW_NAME`
- `ORCHESTRATION_QUEUE_URL`
- `INPUTS_BUCKET`
- `OUTPUTS_BUCKET`

### Fargate-launcher Lambda

- `WORKFLOW_NAME`
- `ECS_CLUSTER_ARN`
- `ECS_TASK_DEFINITION_ARN`
- `SUBNET_IDS`
- `SECURITY_GROUP_IDS`

### Example worker containers

Phase 0 does not define a shared worker-container environment contract. Example workers should receive only the variables needed for the specific test side effect they implement.

## Python test command

Run the existing Python tests through Pixi:

```bash
pixi run -e dev test-py
```

## OpenTofu test harness

Infra tests run through Pixi so the Python helper dependencies are available. Run `tofu test` from the concrete harness root:

```bash
pixi run -e dev test-tf-support-smoke
```

Run the GitHub Actions real-AWS smoke test with sandbox AWS credentials configured in your shell:

```bash
pixi run -e dev test-tf-ci-smoke
```

Run the real-AWS `lambda-deploy` module test with sandbox AWS credentials configured in your shell:

```bash
pixi run -e dev test-tf-lambda-deploy
```

Conventions:

- `tests/tf/<module-name>/`: module-specific harness roots with OpenTofu configuration and `*.tftest.hcl` files
- `tests/tf/support/modules/`: shared wrapper modules around `website_backend.testing.*`
- `tests/tf/support/smoke/`: local smoke test for the helper harness pattern
- `tests/tf/ci-smoke/`: real-AWS smoke test for the GitHub Actions Terraform path
- `tests/tf/lambda-deploy/`: real-AWS module test for Lambda image build and ECR publication
- `.tf-test-artifacts/`: ignored JSON artifacts written by mutating helper wrappers

Helper rules:

- Test helpers are invoked as `python -m website_backend.testing.<module>`.
- Helper scripts accept explicit CLI flags and file arguments.
- Successful helpers print exactly one JSON object to stdout.
- Helpers write human diagnostics to stderr.
- Read helpers support `--external-output`, which wraps their structured result as a JSON string for the OpenTofu `external` provider.
- The shared harness does not publish Lambda images; image build/publish behavior remains part of the relevant Terraform modules.

## GitHub Actions

This repo now carries two GitHub Actions workflows:

- `Pytest`: runs the Python test suite on pull requests and pushes to `main`
- `Terraform`: runs the local OpenTofu support smoke test on every pull request plus the real-AWS `ci-smoke` and `lambda-deploy` jobs for same-repo pull requests, pushes to `main`, and manual runs on `main`

The AWS-backed workflow uses these repository secrets:

- `AWS_GHA_TEST_ROLE_ARN`
- `AWS_REGION`

Bootstrap the AWS-side role, OIDC provider, and repository secrets from
`bootstrap/github-actions/`.
