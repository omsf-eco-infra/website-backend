from __future__ import annotations

import json
from pathlib import Path

import pytest

from website_backend.testing import read_json_file


def test_read_json_file_external_output_wraps_structured_payload(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    json_file = tmp_path / "payload.json"
    json_file.write_text(json.dumps({"status_code": 200, "ok": True}), encoding="utf-8")

    exit_code = read_json_file.main(["--path", str(json_file), "--external-output"])

    assert exit_code == 0
    stdout = capsys.readouterr().out
    assert json.loads(stdout) == {
        "json": json.dumps({"ok": True, "status_code": 200}, sort_keys=True)
    }
