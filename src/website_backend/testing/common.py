from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def add_external_output_flag(parser: argparse.ArgumentParser) -> None:
    """Add the `--external-output` CLI flag to a parser.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        Parser that should expose the external-provider-compatible output mode.
    """
    parser.add_argument(
        "--external-output",
        action="store_true",
        help="Emit an external-provider-compatible JSON object on stdout.",
    )


def add_polling_args(
    parser: argparse.ArgumentParser,
    *,
    timeout_seconds: int = 180,
    poll_interval_seconds: int = 5,
) -> None:
    """Add standard polling-related CLI flags to a parser.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        Parser that should receive polling configuration flags.
    timeout_seconds : int, default=180
        Default maximum time to wait before the helper returns.
    poll_interval_seconds : int, default=5
        Default delay between polling attempts.
    """
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=timeout_seconds,
        help="Maximum time to wait before returning a result.",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=int,
        default=poll_interval_seconds,
        help="Delay between polls when waiting for async side effects.",
    )


def emit_result(payload: Any, *, external_output: bool = False) -> None:
    """Serialize a helper result to stdout as JSON.

    Parameters
    ----------
    payload : Any
        Value to serialize.
    external_output : bool, default=False
        When `True`, wrap the payload in the JSON shape expected by the
        OpenTofu external data source.
    """
    if external_output:
        serialized = {"json": json.dumps(payload, sort_keys=True)}
    else:
        serialized = payload
    json.dump(serialized, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")


def load_text(path: str | Path) -> str:
    """Read a UTF-8 text file.

    Parameters
    ----------
    path : str or pathlib.Path
        Path to the file to read.

    Returns
    -------
    str
        File contents decoded as UTF-8 text.
    """
    return Path(path).read_text(encoding="utf-8")


def load_json(path: str | Path) -> Any:
    """Load JSON content from a file.

    Parameters
    ----------
    path : str or pathlib.Path
        Path to the JSON file to read.

    Returns
    -------
    Any
        Parsed JSON value.
    """
    return json.loads(load_text(path))


def write_json(path: str | Path, payload: Any) -> Path:
    """Write JSON content to a file, creating parent directories as needed.

    Parameters
    ----------
    path : str or pathlib.Path
        Output path for the JSON file.
    payload : Any
        JSON-serializable value to write.

    Returns
    -------
    pathlib.Path
        Normalized path to the written file.
    """
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def log(message: str) -> None:
    """Write a diagnostic message to stderr.

    Parameters
    ----------
    message : str
        Message to emit.
    """
    print(message, file=sys.stderr)


def maybe_parse_json(text: str) -> tuple[bool, Any | None]:
    """Attempt to decode a JSON string.

    Parameters
    ----------
    text : str
        Text that may contain serialized JSON.

    Returns
    -------
    tuple[bool, Any | None]
        Two-tuple containing a success flag and the parsed JSON value when
        decoding succeeds, otherwise `None`.
    """
    try:
        return True, json.loads(text)
    except json.JSONDecodeError:
        return False, None
