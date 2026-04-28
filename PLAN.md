# Reusable Workflow Architecture Plan

This is a living implementation plan for the reusable AWS workflow platform described in pages 1-6 of the "May 2026 Demo_ Architecture Plan-2.pdf" document. It intentionally excludes all OpenFold/OpenFE-specific workflow logic. The goal is to turn the non-specific platform architecture into reusable building blocks that can support multiple future workflows.

## Summary

This plan breaks the work into PR-sized phases. Each phase is meant to be independently reviewable, with a clear definition of done and explicit test expectations. The reusable platform has four main concerns:

- strict message contracts between website, orchestration, and compute
- a generic Exorcist-backed orchestration engine
- Terraform modules that deploy reusable AWS infrastructure
- test harnesses that prove deployed code paths work in a real AWS sandbox account

The implementation sequence below is ordered to minimize rework. Shared contracts and test harnesses come first, then Python runtime components, then Terraform modules that package and exercise those components.

## Phase Template

Every phase in this document should use the same structure:

- `Overview`: conceptual context needed for handoff
- `Checklist`: concrete implementation tasks
- `Definition of Done`: what must be true before merging
- `Tests`: verification required for the phase

## Public Interfaces and Contracts

These contracts should be treated as stable early so later phases do not redefine them.

### Message families

- `InputsMessage`
- `OutputsMessage`
- `OrchestrationMessage`
- `TaskMessage`

### Shared identifiers and primitives

- `workflow_name`: identifies the deployed workflow variant; used for validation and routing at the web edge
- `version`: version of the message contract
- `run_id`: identifies a user-visible run
- `graph_id`: identifies the orchestration graph managed by Exorcist and is the run locator carried by orchestration/task messages
- `task_id`: identifies a task within a graph
- `task_type`: dispatch key for worker routing
- `max_tries`: per-task retry budget set when tasks are added to a graph
- `attempt`: current task attempt number carried to workers in `TaskMessage`, starting at 1
- URL maps: string-to-URL mappings used for output discovery and worker input/output locations
- opaque `details` objects: workflow-specific payloads that stay untyped at the reusable platform layer

### Reusable orchestrator boundary

The reusable orchestration layer should expose clear boundaries for:

- task graph persistence
- task state transitions
- runnable-task selection
- task dispatch onto the shared task SNS topic
- retry/error handling policy

The orchestrator should remain generic. Workflow-specific rules belong upstream in graph construction, not in orchestration execution.

The current Python runtime has already fixed a few important orchestration conventions:

- the reusable orchestrator consumes `InputQueue[OrchestrationMessage]` and publishes `OutputQueue[TaskMessage]`
- the persistence boundary is one per-graph `taskdb(graph_id)` adapter, not queue-transport metadata
- queue delivery metadata is only for acknowledgement and transport diagnostics; it is not authoritative for taskdb selection

### AWS transport conventions

The current queue adapters have already established the transport contract used by later Terraform phases:

- queue and topic bodies remain the canonical JSON serialization of the Phase 1 message contracts
- AWS message attributes are derived from common top-level fields when present: `version`, `message_type`, and `task_type`
- task-queue routing should use the `task_type` message attribute; the other shared attributes remain available for compatibility checks and observability

### Terraform module interfaces

The Terraform module boundaries should stay aligned with the architecture document:

- `container-image`: shared ECR-backed image publishing module that builds from source, hashes caller-selected source paths, and outputs a digest-pinned image URI
- `lambda-deploy`: Lambda-specific image wrapper around `container-image` that adds Lambda platform validation and Lambda image-pull repository policy behavior
- `orchestration`: orchestration queue, shared task topic, orchestrator Lambda, state-store inputs, outputs needed by downstream modules
- `task-queue`: FIFO SQS task queue, DLQ, SNS subscription and filtering, outputs for compute modules
- `fargate-compute`: launcher Lambda, ECS task definition, task-topic subscription, queue/network/image inputs; worker image publishing remains outside this module
- `web-interface`: Lambda, Function URL, input and output buckets, orchestration queue access, outputs for website integration

## Assumptions and Defaults

- Exclude all OpenFold/OpenFE-specific task types, metadata schemas, and workflow graphs from this plan.
- Use one shared task SNS topic in v1, with downstream routing handled by queue subscriptions and filtering.
- Carry `InputsMessage.run_id` into orchestration and task messages as `graph_id`, and treat `graph_id` as the authoritative run locator in the orchestration layer.
- Within a deployment, `task_type` values are globally meaningful and safe to use as routing keys.
- Do not add backend-specific message fields for bucket names, table names, schema names, or connection strings; deployment configuration chooses the persistence backend.
- Use native `terraform test` for Terraform integration tests.
- Run Terraform integration tests against a real AWS sandbox account, not a local emulator.
- Python work should use `pytest` through the repo's `pixi` dev environment.
- Example Lambda and Fargate artifacts exist only to prove module behavior and should stay generic.
- The current local/reference taskdb backend uses one SQLite file per graph; in that backend, `graph_id` is an absolute filename.
- The planned AWS backend for Phase 2 keeps the same message contract and treats `graph_id` as a stable S3 object key, with bucket and scratch-path configuration supplied separately.
- Phase 2 assumes the orchestrator Lambda is the only taskdb writer and runs with reserved concurrency 1 in v1; the initial design does not need to optimize for multi-writer state-store conflicts.
- The initial Lambda entrypoint may process one orchestration message at a time; later batch support should be a thin wrapper around the same per-message core plus Lambda partial-batch-failure handling.

## Phase 0: Foundation and Shared Test Harness

### Overview

This phase establishes the shared implementation frame for the rest of the project. The goal is to prevent later PRs from reopening questions about package layout, module boundaries, test execution, or deployment conventions. The output of this phase is not feature behavior; it is a stable baseline that every later phase can depend on.

There are two key ideas here:

- the reusable platform should separate workflow-specific behavior from generic infrastructure and runtime logic
- integration tests should validate deployed behavior, not just Terraform resource shape

This phase should also define how repo-level tooling supports both Python unit tests and real-AWS Terraform tests, so each later phase can focus on its own behavior instead of recreating harness code.

### Checklist

- [x] Define the long-term repo layout for reusable Python runtime code, Terraform modules, Terraform test fixtures, and example artifacts.
- [x] Define naming conventions for Lambda images, example worker images, helper scripts, and test assets.
- [x] Document shared environment variables and configuration inputs used across Python and Terraform code.
- [x] Define how helper scripts are invoked from `terraform test` for publishing Lambda images, invoking Function URLs, publishing messages, polling queues, and asserting side effects.
- [x] Define real-AWS sandbox naming, tagging, and teardown rules so test resources are easy to isolate and clean up.
- [x] Add any repo-level fixtures or helper directories that later phases will reuse.

### Established Conventions

- Repo layout:
  - reusable Python runtime code stays in `src/website_backend/`
  - Python unit tests stay in `tests/py/`
  - reusable Terraform modules live in top-level `modules/`
  - native `terraform test` fixtures live in `tests/tf/`
  - generic example assets and container contexts live in top-level `examples/`
- Naming conventions:
  - Python package/import names stay in underscore form as `website_backend`
  - Terraform module directories use hyphenated names that match the module interface names in this plan: `orchestration`, `task-queue`, `fargate-compute`, `web-interface`
  - Lambda functions, ECR repositories, and example worker images use hyphenated role names derived from the component, for example `website-backend-orchestrator`, `website-backend-web-interface`, `website-backend-fargate-launcher`, and `website-backend-example-worker`
  - Python helper modules use snake_case names under `website_backend.testing`
  - sample payloads and other test assets use snake_case family names plus dot-delimited scenarios, for example `inputs_message.valid.json` and `task_message.matching.json`
- Runtime configuration:
  - deployment-specific values are injected per Lambda function or per ECS task definition, not at image build time
  - document only the environment variables a given runtime consumes; do not define one global superset that every runtime receives
  - use descriptive resource-oriented names without a repo prefix, such as `WORKFLOW_NAME`, `STATE_BUCKET`, `STATE_PREFIX`, `TASK_TOPIC_ARN`, `ORCHESTRATION_QUEUE_URL`, `INPUTS_BUCKET`, `OUTPUTS_BUCKET`, `ECS_CLUSTER_ARN`, `ECS_TASK_DEFINITION_ARN`, `ECS_CONTAINER_NAME`, `TASK_QUEUE_URL`, `SUBNET_IDS`, and `SECURITY_GROUP_IDS`
  - for the Fargate compute path, keep stable worker values like `WORKFLOW_NAME` and `TASK_QUEUE_URL` on the ECS task definition, and let the launcher inject only per-task metadata like `GRAPH_ID`, `TASK_ID`, `TASK_TYPE`, and `TASK_ATTEMPT`
  - keep secrets out of this shared contract; later phases should use AWS secret-management mechanisms if they introduce secrets
- OpenTofu helper harness:
  - infra tests run as `pixi run -e dev tofu -chdir=tests/tf/<module-name> test -test-directory=.`
  - module-specific harness roots under `tests/tf/<module-name>/` contain the OpenTofu configuration plus `*.tftest.hcl` files, and shared wrapper modules live in `tests/tf/support/modules/`
  - mutating helper wrappers use `terraform_data` plus `local-exec` and write JSON artifacts under `.tf-test-artifacts/<test-name>/`
  - read/assert helper wrappers use the `external` provider plus `--external-output`, then `jsondecode(...)` the helper result for assertions
  - helper modules are invoked as `python -m website_backend.testing.<module>` with explicit CLI flags and file arguments; successful runs write one JSON object to stdout and human diagnostics to stderr
  - the shared harness does not publish Lambda images; image publishing remains part of the relevant module implementations and tests
- Real-AWS sandbox policy:
  - real-AWS `tofu test` runs use per-run isolation by default rather than sharing mutable sandbox resources across independent runs
  - test-created resource names use the template `wb-<module>-<owner>-<run_suffix>`, where `<owner>` is lowercase hyphenated text truncated to 12 characters and `<run_suffix>` is an 8-character lowercase alphanumeric value generated once per test run
  - for resources with tighter name-length limits, preserve the `wb` prefix and unique suffix and truncate the middle
  - for path-like identifiers such as S3 prefixes, use `tests/<module>/<owner>/<run_id>/...`
  - tags are the source of truth for ownership and cleanup, and every test-created resource must include `managed_by=test-website-backend`, `repo=website-backend`, `module=<module>`, `test_name=<harness-or-scenario-name>`, `owner=<owner>`, `run_id=<run_id>`, `created_at=<UTC ISO-8601 timestamp>`, and `expires_at=<UTC ISO-8601 timestamp>`
  - default behavior is destroy-on-completion for every run, with a `retain_on_failure` escape hatch for debugging
  - normal runs set `expires_at` to 24 hours after creation; retained failure runs set `expires_at` to 72 hours after creation
  - cleanup and debugging target `run_id` first, not ad hoc resource-name matching
  - a janitor cleanup process is the safety net and should delete expired resources by selecting `managed_by=test-website-backend` and comparing `expires_at`

### Definition of Done

- Later phases can rely on one documented project layout, one testing approach, and one set of environment/config conventions.
- There is no ambiguity about where new Python code, Terraform code, Terraform tests, and example runtime artifacts belong.
- Later PRs can reuse shared helper patterns instead of inventing their own test wiring.

### Tests

- Verify the documented commands for Python tests and Terraform tests are executable in the repo.
- Verify any shared helper scripts run without workflow-specific assumptions.
- Verify the repo can support both unit-test-only phases and real-AWS integration-test phases without changing the conventions.

## Phase 1: Python Message Contracts

### Overview

The message layer is the central contract for the whole platform. It defines how the website submits work, how orchestration state changes are recorded, and how compute workers receive task payloads. The reusable platform should enforce strict envelope validation while intentionally leaving workflow-specific payload bodies opaque.

That split matters because the envelopes are infrastructure contracts, while the `details` payloads are application contracts. If the reusable layer tries to encode workflow-specific schemas, it stops being reusable.

### Checklist

- [x] Expand the existing Pydantic models to cover `InputsMessage` and `OutputsMessage` in addition to the current orchestration and task messages.
- [x] Centralize shared constrained types, strict base-model behavior, and reusable serialization helpers.
- [x] Preserve discriminated orchestration parsing for `ADD_TASKS`, `TASK_COMPLETED`, and `TASK_ERROR`.
- [x] Standardize field naming and version handling across all message families.
- [x] Add helper functions for validation and round-trip serialization that Lambda handlers and tests can reuse.
- [x] Keep workflow-specific `details` values opaque and do not introduce OpenFold/OpenFE-specific nested models.
- [x] Document the intended ownership of each message family so later phases use them consistently.

### Definition of Done

- A single reusable Python package defines all cross-component message contracts.
- All message families reject unknown top-level fields and enforce the required core identifiers.
- Runtime code and tests can use shared helpers instead of reimplementing parsing logic.

### Tests

- `pytest` tests for successful parsing of all message families.
- `pytest` tests for missing required fields, extra-field rejection, and invalid discriminators.
- `pytest` tests for nested opaque `details` values and round-trip serialization.
- `pytest` tests for any shared helper functions used by handlers.

## Phase 2: Python Exorcist Orchestrator Lambda

### Overview

The orchestrator is the reusable task-graph engine. It receives orchestration messages, updates the graph state, persists that state, and emits runnable tasks. Its job is execution control, not workflow design.

Conceptually, the orchestrator has three responsibilities:

- translate incoming orchestration messages into graph-state mutations
- persist the authoritative graph state after each mutation
- publish newly runnable tasks to the shared task topic

To stay reusable, the Lambda should depend on clear adapters for persistence, Exorcist interaction, and task dispatch. That makes the orchestration logic testable without real AWS and keeps infrastructure concerns separate from state-transition logic.

### Checklist

- [x] Define adapter boundaries for graph persistence, task dispatch, and Exorcist-backed state operations.
- [x] Implement the Lambda handler entrypoint and event decoding for orchestration queue messages.
- [x] Implement `ADD_TASKS` handling that inserts tasks and immediately dispatches newly runnable work.
- [x] Implement `TASK_COMPLETED` handling that marks completion and dispatches newly unblocked tasks in the local/reference runtime.
- [x] Implement retryable `TASK_ERROR` handling that increments attempts and redispatches work while retries remain.
- [x] Define terminal-error behavior for `TASK_ERROR` events once `max_tries` is exhausted.
- [x] Persist graph state to S3 after each accepted mutation.
- [ ] Define unknown-task behavior: log and acknowledge invalid completion/error events as no-ops at the orchestrator boundary.
- [ ] Define explicit behavior for duplicate `ADD_TASKS`, duplicate `TASK_COMPLETED`, duplicate `TASK_ERROR`, and other stale/no-op events in terms of Exorcist's current semantics.
- [x] Ensure emitted `TaskMessage` payloads come from the shared Phase 1 message contracts.
- [x] Keep task-type routing generic and driven by message content plus dispatch configuration.

### Current Status

The repo now contains a reusable local/reference orchestrator that already proves the core non-AWS execution model:

- orchestration messages mutate graph state through the shared message-contract types rather than ad hoc handler logic
- runnable work is emitted as `TaskMessage` payloads populated from taskdb state, including `task_type`, `task_details`, `graph_id`, and `attempt`
- graph state is isolated by `graph_id`, and the current local backend reopens the same SQLite file or in-memory engine for subsequent events targeting that graph
- Exorcist already treats retry exhaustion as a terminal `TOO_MANY_RETRIES` state rather than redispatching further work
- duplicate `ADD_TASKS` remains invalid, duplicate `TASK_COMPLETED` is accepted as a no-op, and terminal retry exhaustion is covered; however, stale/unknown `TASK_ERROR` no-op handling is still blocked by an upstream Exorcist bug
- reusable queue adapters exist for in-memory tests plus AWS SNS/SQS transports, and the Phase 2 Lambda path now decodes orchestration SQS event records directly while preserving the shared per-message orchestrator core
- known upstream blocker: Exorcist's failure-transition path raises `NameError` on zero-row updates, so unknown or stale duplicate `TASK_ERROR` notifications do not yet cleanly ack as no-ops

### Definition of Done

- The orchestrator handler deterministically processes supported message types and persists authoritative state after each accepted mutation.
- Runnable tasks are emitted as valid `TaskMessage` payloads using the shared contract package.
- Edge-case behavior is defined for duplicate, stale, or invalid graph events, including the distinction between invalid duplicate `ADD_TASKS` and logged-and-acked stale terminal notifications.

### Tests

- existing `pytest` coverage proves `ADD_TASKS`, `TASK_COMPLETED`, and retryable `TASK_ERROR` flows in the local/reference runtime
- existing `pytest` coverage proves dependency unlocking, graph isolation by `graph_id`, task-attempt increments, and local SQLite reopen behavior
- existing `pytest` coverage proves the shared SNS/SQS adapters preserve canonical JSON message bodies and publish the agreed AWS message attributes
- `pytest` tests for `ADD_TASKS`, `TASK_COMPLETED`, and `TASK_ERROR` flows.
- `pytest` tests for dependency unlocking and dispatch of newly runnable tasks.
- `pytest` tests for duplicate `TASK_COMPLETED`, stale/duplicate `TASK_ERROR`, duplicate `ADD_TASKS`, and other idempotency or invalid-event scenarios.
- `pytest` tests for retry behavior, terminal error behavior, and no-runnable-task cases.
- `pytest` tests that persistence and dispatch adapters are called with the expected payloads.

## Phase 3: Terraform Orchestration Module

### Overview

This module deploys the reusable orchestration core. Its value is not just that it creates AWS resources, but that it deploys executable orchestrator code and proves that the deployed code can process real messages in AWS.

This is the first Terraform phase that must treat Lambda image wiring and deployed behavior as part of the module contract. The module should not stop at queues, topics, and IAM. It also needs to make the Phase 2 Lambda image deployable and testable.

To keep later image-bearing modules consistent, this phase also establishes shared image publication modules. `modules/container-image/` owns generic ECR image build, push, source hashing, and digest resolution. `modules/lambda-deploy/` wraps that generic module with Lambda-specific platform validation and repository policy behavior. Later Lambda-bearing phases should reuse `lambda-deploy`, while Fargate worker tests and other non-Lambda containers should use `container-image` directly.

### Checklist

- [x] Create the shared `container-image` and `lambda-deploy` Terraform module structures.
- [x] Define `lambda-deploy` inputs for repository name, Lambda Dockerfile directory, build context directory, explicit source-hash paths, platform/architecture, and tagging.
- [x] Make `container-image` create an ECR repository, build and push the image from local code, and output a digest-pinned image URI.
- [x] Make `container-image` hash the caller-selected source paths so OpenTofu rebuilds the image when the image source or shared runtime code changes.
- [x] Add native `terraform test` coverage for `lambda-deploy` using the example orchestrator Lambda Dockerfile layout in `modules/orchestration/lambda/`.
- [x] Create the `orchestration` Terraform module structure.
- [x] Define inputs for the orchestration queue, shared task topic behavior, state-store bucket/key configuration, and tagging.
- [x] Provision the orchestration SQS queue, orchestrator Lambda, IAM permissions, log group, and SNS topic integration required by the architecture.
- [x] Wire the module to instantiate `lambda-deploy` and deploy the Phase 2 Lambda image.
- [x] Expose outputs required by downstream `task-queue` and `web-interface` modules.
- [x] Define how the orchestration module passes its Dockerfile, build context, and source-hash inputs into `lambda-deploy` during tests and deployments.
- [x] Add native `terraform test` coverage that publishes a sample orchestration message into AWS.
- [x] Assert that the deployed Lambda runs, publishes task output onto the shared task topic, and persists graph state to the configured store.

### Definition of Done

- The shared `container-image` module can build and publish an image from local source, and `lambda-deploy` remains reusable by later Lambda-bearing Terraform phases.
- The module can be instantiated on its own in the sandbox account.
- A real orchestration message sent to the deployed resources produces observable orchestration side effects.
- The module outputs are sufficient for downstream modules without leaking implementation details.

### Tests

- `terraform test` that provisions `lambda-deploy`, builds the example orchestrator Lambda image, and confirms the pushed tag resolves in ECR.
- `terraform test` that provisions the module and publishes a sample `ADD_TASKS` message.
- Assertions that the task topic receives the expected downstream payload.
- Assertions that graph state is persisted to the configured S3 location.
- Assertions that required outputs are populated and usable by other modules.

## Phase 4: Terraform Task Queue Module

### Overview

This module provides a reusable worker lane. It owns SQS delivery semantics, retry boundaries, and routing from the shared task topic into a task-specific queue. This keeps worker implementations decoupled from the shared task publication mechanism.

The main architectural point is that the shared task SNS topic can serve many task queues, but each queue should receive only the task types it is responsible for. Filtering and subscription semantics are therefore part of the reusable module contract.

### Checklist

- [x] Create the `task-queue` Terraform module structure.
- [x] Provision one FIFO SQS queue plus one DLQ with redrive settings.
- [x] Add queue policy and subscription wiring from the shared task SNS topic.
- [x] Implement task routing with SNS subscription filters on the shared `task_type` message attribute.
- [x] Expose queue URLs, ARNs, and any policy outputs required by compute modules.
- [x] Wire the module to the established transport contract: canonical JSON message bodies plus shared `version`, `message_type`, and `task_type` AWS message attributes when present.
- [x] Add native `terraform test` coverage for both matching and non-matching task publications.

### Definition of Done

- The module reliably receives only the intended task messages from the shared task topic.
- The module exposes a stable interface that compute modules can consume without needing to understand routing internals.
- DLQ and retry behavior are configured and test-backed.

### Tests

- `terraform test` that publishes at least one matching and one non-matching task message.
- Assertions that matching messages arrive in the queue.
- Assertions that non-matching messages are filtered out.
- Assertions that queue outputs and policies are present and usable by downstream compute resources.

## Phase 5: Python Fargate Launcher Lambda

### Overview

The launcher is reusable control-plane code that reacts to task-available notifications and starts ECS/Fargate workers. It should remain generic by treating the worker container as a deployable unit described by configuration, not by embedded task logic.

The launcher's job is narrow:

- receive a signal that task work is available
- derive the correct ECS `RunTask` request
- pass enough metadata for the worker to find and process queue items

The runtime contract should stay split between deployment-time worker
configuration and launch-time task metadata:

- stable worker values such as `WORKFLOW_NAME` and `TASK_QUEUE_URL` belong on
  the ECS task definition configured by Terraform
- per-task values such as `graph_id`, `task_id`, `task_type`, and `attempt`
  are passed by the launcher through ECS container overrides

This Lambda should not interpret workflow-specific task payloads. It only needs to supply queue identity, run context, and runtime configuration to the worker task.

### Checklist

- [x] Implement the SNS-triggered Lambda entrypoint for task-available events.
- [x] Define the configuration contract for ECS cluster, task definition, launch type, networking, and queue metadata.
- [x] Build the ECS `RunTask` request using injected configuration and event context.
- [x] Pass queue metadata and any required run/task context through container overrides or environment variables.
- [x] Define behavior for duplicate notifications so the launcher remains safe under at-least-once delivery.
- [x] Define behavior for ECS launch failures, transient AWS API failures, and invalid configuration.
- [x] Keep the launcher logic independent of workflow-specific task schemas.

### Definition of Done

- The launcher can convert a task-available event into the correct ECS launch request under unit test.
- The configuration contract is explicit enough for Terraform to supply everything needed without code changes.
- Duplicate or failed launch scenarios have defined handling behavior.

### Tests

- `pytest` tests for SNS event parsing.
- `pytest` tests for ECS `RunTask` request construction.
- `pytest` tests for configuration lookup and container override generation.
- `pytest` tests for duplicate-notification handling.
- `pytest` tests for failure paths, including ECS API errors and invalid config.

## Phase 6: Terraform Fargate Compute Module

### Overview

This module packages the reusable compute plane that sits behind a task queue. It includes the launcher Lambda from Phase 5 plus the ECS/Fargate resources needed to run a worker container. The reusable module should be agnostic to task content and should accept a container image reference as an input.

This phase must also prove that the deployed compute path actually works in AWS. That means the tests need a generic example worker image that consumes queue work and leaves an observable side effect behind.

### Checklist

- [x] Create the `fargate-compute` Terraform module structure.
- [x] Provision launcher subscription wiring, ECS task definition, IAM, logging, and required networking inputs.
- [x] Accept a container image URI as an input instead of building container images inside the module.
- [x] Reuse `lambda-deploy` for the Phase 5 launcher Lambda image while continuing to accept a separate ECS worker image URI as an input.
- [x] Wire the module to the `task-queue` outputs and shared task topic conventions.
- [x] Add a lightweight generic example worker image for integration tests.
- [x] Define the observable side effect used by tests to prove worker execution.
- [x] Add native `terraform test` coverage that publishes a task and verifies that an ECS task is launched and the example worker completes the expected side effect.

### Definition of Done

- The module can launch a real example Fargate worker from an incoming task signal.
- The compute module interface is generic enough to support different worker images without code changes.
- The integration test proves behavior end-to-end rather than only checking resource existence.

### Tests

- `terraform test` that provisions the module with a generic example worker image.
- Assertions that a matching task publication leads to an ECS task launch.
- Assertions that the example worker leaves the expected observable side effect.
- Assertions that the launcher and worker receive the configuration they need from Terraform inputs.

## Phase 7: Python Web Interaction Scaffold

### Overview

The web interaction Lambda is the reusable edge for workflow submission. Its reusable responsibilities are request validation, run/output location allocation, response construction, and publication of orchestration messages. Workflow-specific graph construction must be injected behind a clear adapter so the Lambda can support many workflows.

The conceptual boundary is important:

- the reusable shell handles transport, identifiers, storage locations, and messaging
- the workflow-specific adapter converts validated input details into one or more orchestration tasks

That keeps the website-facing code generic while still allowing each workflow to define its own graph.

### Checklist

- [ ] Implement reusable request parsing around `InputsMessage`.
- [ ] Validate the caller-provided `run_id` from `InputsMessage` and apply any output-location conventions used by the platform.
- [ ] Implement construction of `OutputsMessage`, including output URL mappings and polling guidance.
- [ ] Implement publishing of the initial orchestration message to the orchestration queue, carrying `InputsMessage.run_id` as `OrchestrationMessage.graph_id`.
- [ ] Define an adapter or protocol for workflow-specific graph construction.
- [ ] Add a minimal generic example adapter used only for tests.
- [ ] Keep all OpenFold/OpenFE-specific graph logic out of the reusable scaffold.
- [ ] Define the HTTP response shape and error behavior expected by the website.

### Definition of Done

- A reusable web-entry shell exists that can accept a request, allocate run/output locations, enqueue orchestration work, and return a valid response.
- Workflow-specific graph construction is injected through an explicit interface rather than embedded in the Lambda.
- The scaffold can be reused by future workflows without changing the shared shell code.

### Tests

- `pytest` tests for request validation and response generation.
- `pytest` tests for output URL allocation behavior.
- `pytest` tests for orchestration queue publication.
- `pytest` tests for error responses and invalid input handling.
- `pytest` tests for the workflow-adapter boundary using the minimal example adapter.

## Phase 8: Terraform Web Interface Module

### Overview

This module deploys the public-facing website integration layer: the web Lambda, its Function URL, and the input/output storage used by the workflow platform. Its test must prove the first end-to-end handoff into orchestration.

This module is where the platform becomes externally visible. Because of that, its integration test should validate both the HTTP response contract and the side effect that the request creates in the orchestration system.

### Checklist

- [ ] Create the `web-interface` Terraform module structure.
- [ ] Provision the web Lambda, Function URL, input/output buckets, IAM permissions, logging, and orchestration queue access.
- [ ] Reuse `lambda-deploy` to build and deploy the Phase 7 Lambda image.
- [ ] Expose the Function URL and relevant bucket outputs needed by the website.
- [ ] Define any bucket prefix conventions required by the reusable platform layer.
- [ ] Add native `terraform test` coverage that invokes the deployed Function URL with a generic sample input.
- [ ] Assert that the response matches the documented output contract.
- [ ] Assert that the request results in an orchestration message reaching the orchestration queue.

### Definition of Done

- The deployed web interface can accept a request in AWS and hand work off to orchestration successfully.
- The response format is stable enough for website integration.
- Storage and queue permissions are narrow and sufficient for the reusable shell behavior.

### Tests

- `terraform test` that invokes the deployed Function URL.
- Assertions that the response contains the expected identifiers and output URL mappings.
- Assertions that the orchestration queue receives the expected message.
- Assertions that the module outputs are sufficient for website integration.

## Cross-Phase Test Plan

- All Python phases use `pytest` and should run through the repo's `pixi` dev environment.
- All Terraform phases use native `terraform test` against a real AWS sandbox account.
- Terraform tests must assert behavior, not just resource shape.
- Integration tests should favor observable outcomes such as:
  - queue delivery
  - SNS fanout
  - Lambda execution
  - ECS task launch
  - persisted graph state
  - HTTP response shape
  - durable side effects created by example runtimes
- Example Lambda and Fargate artifacts used in tests should stay generic and should not encode workflow-specific scientific logic.

## How To Extend This Plan

When updating this document:

- keep the same phase template: `Overview`, `Checklist`, `Definition of Done`, `Tests`
- add new phases only when the work is large enough to stand as its own PR
- prefer generic platform concepts over workflow-specific implementation details
- record any new shared interface decisions in `Public Interfaces and Contracts`
- update `Assumptions and Defaults` only when the repo intentionally changes direction

If future work introduces a specific workflow, document it in a separate workflow-specific plan rather than expanding this reusable platform plan with task-specific details.
