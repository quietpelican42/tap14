"""Render a parsed TAP document as JUnit XML.

JUnit has no standard notion of nested test suites, so a subtest's points
are flattened into the same ``<testsuite>`` with a dotted ``classname``
built from the chain of subtest names (or ``subtestN`` for unnamed ones).
"""

from __future__ import annotations

from xml.sax.saxutils import escape, quoteattr

from .model import Document, TestPoint


def _classname(path: list[str]) -> str:
    return ".".join(path) if path else "tap"


def _walk(
    doc: Document, path: list[str], out: list[tuple[str, TestPoint]]
) -> None:
    for i, tp in enumerate(doc.points, start=1):
        out.append((_classname(path), tp))
        if tp.subtest is not None:
            child_name = tp.subtest.name or f"subtest{i}"
            _walk(tp.subtest, [*path, child_name], out)


def to_junit_xml(doc: Document, suite_name: str = "tap14") -> str:
    entries: list[tuple[str, TestPoint]] = []
    _walk(doc, [], entries)

    total = len(entries)
    failures = sum(1 for _, tp in entries if tp.counts_as_failure)
    skipped = sum(1 for _, tp in entries if tp.is_skipped)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f"<testsuites>",
        (
            f'<testsuite name={quoteattr(suite_name)} tests="{total}" '
            f'failures="{failures}" skipped="{skipped}">'
        ),
    ]
    for i, (classname, tp) in enumerate(entries, start=1):
        name = tp.description or f"test {tp.number if tp.number is not None else i}"
        lines.append(
            f'<testcase classname={quoteattr(classname)} name={quoteattr(name)}>'
        )
        if tp.is_skipped:
            reason = tp.directive.reason if tp.directive else ""
            lines.append(f"<skipped message={quoteattr(reason)}/>")
        elif tp.counts_as_failure:
            msg = "not ok"
            body = ""
            if tp.yaml_raw:
                body = escape(tp.yaml_raw)
            lines.append(f"<failure message={quoteattr(msg)}>{body}</failure>")
        lines.append("</testcase>")
    lines.append("</testsuite>")
    lines.append("</testsuites>")
    return "\n".join(lines) + "\n"
