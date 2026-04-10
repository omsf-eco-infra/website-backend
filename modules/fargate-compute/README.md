# fargate-compute

This directory will host the reusable Fargate compute Terraform module
described in `PLAN.md`.

Phase 5 already adds the reusable launcher Lambda packaging assets under
`lambda/`. Phase 6 will wire those assets into the Terraform module and add the
rest of the ECS/Fargate infrastructure.

Use the canonical module name `fargate-compute` for module source paths, docs, and tests.
