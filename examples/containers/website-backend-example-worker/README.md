# website-backend-example-worker

This directory contains the generic example worker container context used by the
Phase 6 Terraform integration test.

The container behavior is intentionally narrow:

- read deployment-time and launcher-injected environment variables
- poll the configured task queue for one canonical `TaskMessage`
- verify the queue body matches the launcher context
- write one JSON result object to S3
- delete the consumed queue message only after the S3 write succeeds

Keep the image behavior generic and focused on proving platform plumbing rather
than workflow-specific logic.
