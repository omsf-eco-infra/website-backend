from __future__ import annotations

import argparse
import json
from pathlib import Path

from website_backend.testing import common


def test_add_polling_args_sets_expected_defaults() -> None:
    parser = argparse.ArgumentParser()

    common.add_polling_args(parser)
    args = parser.parse_args([])

    assert args.timeout_seconds == 180
    assert args.poll_interval_seconds == 5


def test_load_and_write_json_round_trip(tmp_path: Path) -> None:
    payload = {"status_code": 200, "ok": True}
    path = common.write_json(tmp_path / "artifact.json", payload)

    assert path == tmp_path / "artifact.json"
    assert common.load_json(path) == payload


def test_maybe_parse_json_reports_non_json_text() -> None:
    assert common.maybe_parse_json('{"ok": true}') == (True, {"ok": True})
    assert common.maybe_parse_json("not-json") == (False, None)


def test_emit_result_external_output_wraps_payload(
    capsys: object,
) -> None:
    common.emit_result({"ok": True, "status_code": 200}, external_output=True)

    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        "json": json.dumps({"ok": True, "status_code": 200}, sort_keys=True)
    }
