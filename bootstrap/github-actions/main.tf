data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

locals {
  oidc_provider_url  = "https://token.actions.githubusercontent.com"
  oidc_provider_host = trimprefix(local.oidc_provider_url, "https://")
  repository         = "${var.github_org}/${var.github_repo}"
  allowed_subjects = concat(
    [
      for branch_name in var.allowed_branch_names :
      "repo:${local.repository}:ref:refs/heads/${branch_name}"
    ],
    ["repo:${local.repository}:pull_request"],
  )
  common_tags = {
    managed_by = "tofu-bootstrap"
    repo       = var.github_repo
    component  = "github-actions"
  }
  role_arn_secret_name = "AWS_GHA_TEST_ROLE_ARN"
  region_secret_name   = "AWS_REGION"
  role_pattern_arn     = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/wb-*"
  policy_pattern_arn   = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:policy/wb-*"
}

resource "aws_iam_openid_connect_provider" "github" {
  count = var.existing_oidc_provider_arn == null ? 1 : 0

  url = local.oidc_provider_url

  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = var.oidc_thumbprint_list

  tags = local.common_tags
}

locals {
  oidc_provider_arn = coalesce(
    var.existing_oidc_provider_arn,
    try(aws_iam_openid_connect_provider.github[0].arn, null),
  )
}

data "aws_iam_policy_document" "assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "${local.oidc_provider_host}:sub"
      values   = local.allowed_subjects
    }
  }
}

# This policy is intentionally broad while the project is still defining its
# Terraform and runtime surface area. Tighten it once the long-term AWS
# permission footprint is clearer.
data "aws_iam_policy_document" "permissions" {
  statement {
    sid    = "SandboxServiceAccess"
    effect = "Allow"
    actions = [
      "s3:*",
      "sns:*",
      "sqs:*",
      "lambda:*",
      "logs:*",
      "ecr:*",
      "ecs:*",
      "ec2:AuthorizeSecurityGroupEgress",
      "ec2:CreateSecurityGroup",
      "ec2:CreateTags",
      "ec2:DeleteSecurityGroup",
      "ec2:DeleteTags",
      "ec2:Describe*",
      "ec2:RevokeSecurityGroupEgress",
      "sts:GetCallerIdentity",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "IamReadAccess"
    effect = "Allow"
    actions = [
      "iam:Get*",
      "iam:List*",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "CreateServiceLinkedRoles"
    effect = "Allow"
    actions = [
      "iam:CreateServiceLinkedRole",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "ManageTestRolesAndPolicies"
    effect = "Allow"
    actions = [
      "iam:AttachRolePolicy",
      "iam:CreatePolicy",
      "iam:CreatePolicyVersion",
      "iam:CreateRole",
      "iam:DeletePolicy",
      "iam:DeletePolicyVersion",
      "iam:DeleteRole",
      "iam:DeleteRolePolicy",
      "iam:DetachRolePolicy",
      "iam:PutRolePolicy",
      "iam:SetDefaultPolicyVersion",
      "iam:TagPolicy",
      "iam:TagRole",
      "iam:UntagPolicy",
      "iam:UntagRole",
      "iam:UpdateAssumeRolePolicy",
      "iam:UpdateRole",
      "iam:UpdateRoleDescription",
    ]
    resources = [
      local.role_pattern_arn,
      local.policy_pattern_arn,
    ]
  }

  statement {
    sid    = "PassTestRolesToLambdaAndEcs"
    effect = "Allow"
    actions = [
      "iam:PassRole",
    ]
    resources = [local.role_pattern_arn]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values = [
        "ecs-tasks.amazonaws.com",
        "lambda.amazonaws.com",
      ]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = var.role_name
  assume_role_policy = data.aws_iam_policy_document.assume_role.json

  tags = merge(
    local.common_tags,
    {
      github_repository = local.repository
    },
  )
}

resource "aws_iam_role_policy" "github_actions" {
  name   = "${var.role_name}-sandbox"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.permissions.json
}

resource "github_actions_secret" "aws_gha_test_role_arn" {
  repository      = var.github_repo
  secret_name     = local.role_arn_secret_name
  plaintext_value = aws_iam_role.github_actions.arn
}

resource "github_actions_secret" "aws_region" {
  repository      = var.github_repo
  secret_name     = local.region_secret_name
  plaintext_value = var.aws_region
}
