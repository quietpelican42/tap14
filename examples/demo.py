"""Real demonstration: parse a TAP 14 stream with nested subtests.

Prints what this package extracts, and, if `tap.py` (tappy) happens to be
installed, what it extracts from the same input for comparison.

Run: python examples/demo.py
"""

from __future__ import annotations

import textwrap

from tap14 import parse_text, summarize

SAMPLE = textwrap.dedent(
    """\
    TAP version 14
    1..2
    # Subtest: nested
        1..2
        ok 1 - inner one
        not ok 2 - inner two
    ok 1 - nested
    ok 2 - top level
    """
)


def main() -> None:
    print("Input:")
    print(textwrap.indent(SAMPLE, "  "))

    doc = parse_text(SAMPLE)
    top_summary = summarize(doc)
    print(f"tap14 top-level summary: {top_summary.passed} passed, "
          f"{top_summary.failed} failed, ok={top_summary.ok}")

    nested = doc.points[0].subtest
    assert nested is not None
    nested_summary = summarize(nested)
    print(f"tap14 nested subtest summary: {nested_summary.passed} passed, "
          f"{nested_summary.failed} failed")
    print("  nested points:", [(p.description, p.ok) for p in nested.points])

    try:
        from tap.parser import Parser  # type: ignore[import-untyped]
    except ImportError:
        print("\n(tap.py / tappy not installed — skipping comparison)")
        return

    print("\ntappy's own line classification of the same input:")
    p = Parser()
    for line in p.parse_text(SAMPLE):
        print(" ", type(line).__name__, getattr(line, "category", ""))


if __name__ == "__main__":
    main()
