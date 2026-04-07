from __future__ import annotations

import json
from pathlib import Path

import pytest

from website_backend.testing import invoke_function_url


def test_invoke_function_url_writes_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body_file = tmp_path / "body.json"
    body_file.write_text('{"ping":true}', encoding="utf-8")
    headers_file = tmp_path / "headers.json"
    headers_file.write_text(
        json.dumps({"content-type": "application/json"}), encoding="utf-8"
    )
    output_file = tmp_path / "artifact.json"

    class DummyResponse:
        status_code = 202
        headers = {"content-type": "application/json"}
        text = '{"ok": true}'

    def fake_request(**kwargs: object) -> DummyResponse:
        assert kwargs == {
            "method": "POST",
            "url": "https://example.com/function",
            "headers": {"content-type": "application/json"},
            "data": '{"ping":true}',
            "timeout": 15,
        }
        return DummyResponse()

    monkeypatch.setattr(invoke_function_url.requests, "request", fake_request)

    result = invoke_function_url.invoke_function_url(
        url="https://example.com/function",
        output_file=str(output_file),
        body_file=str(body_file),
        headers_file=str(headers_file),
        timeout_seconds=15,
    )

    assert result == {
        "artifact_path": str(output_file),
        "status_code": 202,
    }
    assert json.loads(output_file.read_text(encoding="utf-8")) == {
        "body_json": {"ok": True},
        "body_text": '{"ok": true}',
        "headers": {"content-type": "application/json"},
        "status_code": 202,
    }
