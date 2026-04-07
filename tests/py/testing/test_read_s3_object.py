from __future__ import annotations

import json

import boto3
from moto import mock_aws

from website_backend.testing import read_s3_object


@mock_aws
def test_read_s3_object_returns_body_and_metadata() -> None:
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="example-bucket")
    s3.put_object(
        Bucket="example-bucket",
        Key="runs/output.json",
        Body=json.dumps({"ready": True}),
        ContentType="application/json",
        Metadata={"source": "test"},
    )

    result = read_s3_object.read_object(
        bucket="example-bucket",
        key="runs/output.json",
        timeout_seconds=1,
        poll_interval_seconds=0,
        client=s3,
    )

    assert result == {
        "exists": True,
        "content_length": 15,
        "content_type": "application/json",
        "etag": result["etag"],
        "metadata": {"source": "test"},
        "body_text": '{"ready": true}',
        "body_json": {"ready": True},
    }
    assert isinstance(result["etag"], str)


@mock_aws
def test_read_s3_object_returns_exists_false_for_missing_key() -> None:
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="example-bucket")

    result = read_s3_object.read_object(
        bucket="example-bucket",
        key="missing.json",
        timeout_seconds=0,
        poll_interval_seconds=0,
        client=s3,
    )

    assert result == {"exists": False}
