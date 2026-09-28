"""``tap14`` command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import TextIO

from .junit import to_junit_xml
from .jsonout import document_to_dict, summary_to_dict
from .parser import parse_lines, summarize


def _read_lines(path: str) -> list[str]:
    if path == "-":
        return sys.stdin.readlines()
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.readlines()


def _print_summary(doc, summary, out: TextIO) -> None:  # type: ignore[no-untyped-def]
    plan = f"{doc.plan.start}..{doc.plan.end}" if doc.plan is not None else "(none)"
    print(f"plan: {plan}", file=out)
    print(
        f"points: {summary.total}  passed: {summary.passed}  "
        f"failed: {summary.failed}  skipped: {summary.skipped}  "
        f"todo: {summary.todo}",
        file=out,
    )
    for err in summary.errors:
        print(f"error: {err}", file=out)
    print("PASS" if summary.ok else "FAIL", file=out)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tap14", description="Parse a TAP 14 stream.")
    parser.add_argument(
        "file", nargs="?", default="-", help="TAP file to read, or '-' for stdin (default)"
    )
    parser.add_argument("--json", action="store_true", help="print JSON instead of a text summary")
    parser.add_argument("--junit", metavar="PATH", help="write JUnit XML to PATH")
    args = parser.parse_args(argv)

    try:
        lines = _read_lines(args.file)
    except OSError as exc:
        print(f"tap14: cannot read {args.file!r}: {exc}", file=sys.stderr)
        return 2

    try:
        doc = parse_lines(lines)
    except Exception as exc:  # pragma: no cover - parser is designed not to raise
        print(f"tap14: parse error: {exc}", file=sys.stderr)
        return 2

    if doc.version is None and doc.plan is None and not doc.points:
        print("tap14: input does not look like a TAP stream", file=sys.stderr)
        return 2

    summary = summarize(doc)

    if args.junit:
        with open(args.junit, "w", encoding="utf-8") as f:
            f.write(to_junit_xml(doc))

    if args.json:
        payload = {"document": document_to_dict(doc), "summary": summary_to_dict(summary)}
        print(json.dumps(payload, indent=2))
    else:
        _print_summary(doc, summary, sys.stdout)

    return 0 if summary.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
