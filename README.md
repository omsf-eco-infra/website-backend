# website-backend

This repository is building reusable AWS workflow-platform components. Phase 0 locks the repo layout, naming rules, and runtime-configuration contract so later phases can add behavior without reopening those decisions.

## Repo layout

- `src/website_backend/`: reusable Python runtime code
- `tests/py/`: Python unit tests
- `modules/`: reusable Terraform modules
- `tests/tf/`: native `terraform test` fixtures and assertions
- `examples/`: generic example payloads, assets, and container contexts
- `scripts/`: shared helper scripts when later Phase 0 work adds them

## Naming conventions

- Python imports stay under `website_backend.*`.
- Terraform module directories stay hyphenated and match the public module names: `orchestration`, `task-queue`, `fargate-compute`, and `web-interface`.
- Lambda functions, ECR repositories, and example worker images use hyphenated role names derived from the component, for example `website-backend-orchestrator`, `website-backend-web-interface`, `website-backend-fargate-launcher`, and `website-backend-example-worker`.
- Helper scripts use verb-object snake_case names, for example `publish_message.py`, `poll_queue.py`, and `invoke_function_url.py`.
- Example payloads and test assets use snake_case family names plus dot-delimited scenarios, for example `inputs_message.valid.json` and `task_message.matching.json`.

## Runtime configuration

Deployment-specific values are injected into each Lambda function or ECS task definition by Terraform. They are not baked into image builds.

Rules:

- Pass only the environment variables a runtime actually consumes.
- Use descriptive resource-oriented names without a repo prefix.
- Keep secrets out of this contract.
- Encode list-valued settings as JSON arrays so Terraform can `jsonencode(...)` them and Python can parse them deterministically.

### Orchestrator Lambda

- `CONTRACT_VERSION`
- `WORKFLOW_NAME`
- `STATE_BUCKET`
- `STATE_PREFIX`
- `TASK_TOPIC_ARN`

### Web-interface Lambda

- `CONTRACT_VERSION`
- `WORKFLOW_NAME`
- `ORCHESTRATION_QUEUE_URL`
- `INPUTS_BUCKET`
- `OUTPUTS_BUCKET`

### Fargate-launcher Lambda

- `CONTRACT_VERSION`
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
pixi run -e dev python -m pytest tests/py
```
