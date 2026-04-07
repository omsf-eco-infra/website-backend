# GitHub Actions Bootstrap

This OpenTofu stack creates the AWS-side bootstrap needed for GitHub Actions
to run real-AWS Terraform smoke tests with GitHub OIDC.

## What it creates

- an IAM OIDC provider for `https://token.actions.githubusercontent.com`,
  unless you pass an existing provider ARN
- one repository-scoped IAM role for GitHub Actions
- a broad sandbox inline policy intended for test infrastructure work in this repo
- GitHub Actions repository secrets for the AWS role ARN and region

The role trust policy is scoped to:

- `repo:omsf-eco-infra/website-backend:ref:refs/heads/main`
- `repo:omsf-eco-infra/website-backend:pull_request`

## Inputs

- `aws_region`: AWS region where you want to manage the IAM resources
- `role_name`: IAM role name to create
- `github_org`: defaults to `omsf-eco-infra`
- `github_repo`: defaults to `website-backend`
- `allowed_branch_names`: defaults to `["main"]`
- `existing_oidc_provider_arn`: optional ARN for an already-created GitHub OIDC provider

## Apply

Run this from an admin-capable shell session with AWS credentials and a GitHub
token that can manage repository Actions secrets, for example `GITHUB_TOKEN`:

```bash
export GITHUB_TOKEN=...
tofu -chdir=bootstrap/github-actions init
tofu -chdir=bootstrap/github-actions plan \
  -var aws_region=us-east-1 \
  -var role_name=website-backend-github-actions
tofu -chdir=bootstrap/github-actions apply \
  -var aws_region=us-east-1 \
  -var role_name=website-backend-github-actions
```

## GitHub repository secrets

This stack manages these repository secrets automatically:

- `AWS_GHA_TEST_ROLE_ARN`
- `AWS_REGION`

The workflows read these as GitHub Actions secrets.
