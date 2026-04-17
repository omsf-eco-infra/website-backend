from __future__ import annotations

import argparse

from website_backend.testing.common import (
    add_external_output_flag,
    emit_result,
    load_json,
)


def build_parser() -> argparse.ArgumentParser:  # pragma: no cover
    """Build the CLI parser for JSON file reads.

    Returns
    -------
    argparse.ArgumentParser
        Configured parser for this helper.
    """
    parser = argparse.ArgumentParser(description="Read a JSON file.")
    parser.add_argument("--path", required=True)
    add_external_output_flag(parser)
    return parser


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
    """Run the JSON file reader as a CLI program.

    Parameters
    ----------
    argv : list[str] or None, default=None
        Explicit argument list. When `None`, arguments are read from `sys.argv`.

    Returns
    -------
    int
        Process exit code.
    """
    args = build_parser().parse_args(argv)
    emit_result(load_json(args.path), external_output=args.external_output)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
