"""A streaming TAP 12/13/14 parser.

Consumes an iterable of lines (a file object, ``str.splitlines()``, a list —
anything iterable once) and produces a :class:`~tap14.model.Document` tree.
Indentation of 4 spaces per level marks a subtest stream (TAP 14, section
"Subtests"); a document with no subtests is exactly a flat TAP 12/13 stream.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from typing import Any

from .model import BailOut, Directive, Document, Plan, Pragma, Summary, TestPoint

_VERSION_RE = re.compile(r"^TAP version (\d+)\s*$", re.IGNORECASE)
_PLAN_RE = re.compile(r"^(\d+)\.\.(\d+)(?:\s*#\s*(.*))?\s*$")
_BAILOUT_RE = re.compile(r"^bail out!(?:\s+(.*))?\s*$", re.IGNORECASE)
_PRAGMA_RE = re.compile(r"^pragma\s+([+-])([a-zA-Z0-9_-]+)\s*$")
_TEST_RE = re.compile(r"^(not\s+)?ok\b\s*(.*)$")
_NUMBER_RE = re.compile(r"^(\d+)\s*(.*)$")
_DIRECTIVE_RE = re.compile(r"(?:^|\s)#\s*(SKIP|TODO)\S*(?:\s+(.*))?$", re.IGNORECASE)
_SUBTEST_RE = re.compile(r"^#\s*Subtest(?::\s?(.*))?$")

INDENT_WIDTH = 4


def _unescape(text: str) -> str:
    """Undo TAP's ``\\#`` / ``\\\\`` escaping (spec section "Escaping")."""
    return re.sub(r"\\(.)", lambda m: m.group(1), text)


class _LineBuffer:
    """One-line lookahead over an iterable of raw (unstripped) lines."""

    def __init__(self, lines: Iterable[str]) -> None:
        self._it: Iterator[str] = iter(lines)
        self._peeked: str | None = None
        self._exhausted = False
        self.line_no = 0

    def peek(self) -> str | None:
        if self._peeked is None and not self._exhausted:
            try:
                self._peeked = next(self._it)
            except StopIteration:
                self._exhausted = True
        return self._peeked

    def next(self) -> str | None:
        line = self.peek()
        if line is not None:
            self._peeked = None
            self.line_no += 1
        return line


def _split_indent(raw: str) -> tuple[int, str]:
    line = raw.rstrip("\n").rstrip("\r")
    stripped = line.lstrip(" ")
    return len(line) - len(stripped), stripped


def _parse_test_point_content(
    content: str,
) -> tuple[bool, int | None, str, Directive | None]:
    m = _TEST_RE.match(content)
    if not m:
        raise ValueError(f"not a test point line: {content!r}")
    ok = m.group(1) is None
    rest = m.group(2)

    number: int | None = None
    num_m = _NUMBER_RE.match(rest)
    if num_m:
        number = int(num_m.group(1))
        rest = num_m.group(2)

    directive: Directive | None = None
    description = rest
    dir_m = _DIRECTIVE_RE.search(rest)
    if dir_m:
        description = rest[: dir_m.start()].rstrip()
        kind = dir_m.group(1).lower()
        reason = _unescape((dir_m.group(2) or "").strip())
        directive = Directive(kind="skip" if kind == "skip" else "todo", reason=reason)

    description = description.strip()
    if description.startswith("-"):
        description = description[1:].strip()
    description = _unescape(description)
    return ok, number, description, directive


def _maybe_load_yaml(raw: str) -> Any | None:
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return None
    try:
        return yaml.safe_load(raw)
    except Exception:
        return None


def _maybe_parse_yaml_block(buf: _LineBuffer, depth: int) -> tuple[str | None, Any | None]:
    expected_indent = depth * INDENT_WIDTH + 2
    peeked = buf.peek()
    if peeked is None:
        return None, None
    indent, content = _split_indent(peeked)
    if indent != expected_indent or content != "---":
        return None, None
    buf.next()  # consume "---"
    raw_lines: list[str] = []
    while True:
        peeked = buf.peek()
        if peeked is None:
            break
        indent, content = _split_indent(peeked)
        if indent == expected_indent and content == "...":
            buf.next()
            break
        if indent < expected_indent:
            # Malformed / unterminated block — stop rather than consuming
            # lines that belong to an outer construct.
            break
        buf.next()
        # YAML lines are indented 2 spaces relative to the block delimiters.
        raw_lines.append(peeked.rstrip("\n").rstrip("\r")[expected_indent:])
    raw = "\n".join(raw_lines)
    return raw, _maybe_load_yaml(raw)


def _parse_block(buf: _LineBuffer, depth: int, name: str | None) -> Document:
    doc = Document(depth=depth, name=name)
    base_indent = depth * INDENT_WIDTH
    pending_subtest_name: str | None = None
    have_pending_subtest = False
    pending_subtest_doc: Document | None = None
    seen_test_point = False

    while True:
        raw = buf.peek()
        if raw is None:
            break
        indent, content = _split_indent(raw)

        if indent < base_indent:
            break

        if indent > base_indent:
            # An indented block starts here: either it was announced by a
            # preceding "# Subtest" comment, or it's a bare nested stream.
            sub_doc = _parse_block(buf, depth + 1, pending_subtest_name)
            pending_subtest_name = None
            have_pending_subtest = True
            pending_subtest_doc = sub_doc
            continue

        # indent == base_indent
        buf.next()
        line_no = buf.line_no

        if content == "":
            continue

        if _VERSION_RE.match(content):
            m = _VERSION_RE.match(content)
            assert m is not None
            doc.version = int(m.group(1))
            continue

        m = _PLAN_RE.match(content)
        if m:
            reason = _unescape(m.group(3)) if m.group(3) else None
            doc.plan = Plan(
                start=int(m.group(1)),
                end=int(m.group(2)),
                skip_reason=reason,
                line_no=line_no,
            )
            doc.plan_position = "after" if seen_test_point else "before"
            continue

        m = _BAILOUT_RE.match(content)
        if m:
            reason = _unescape((m.group(1) or "").strip())
            doc.bail_out = BailOut(reason=reason, line_no=line_no)
            break

        m = _PRAGMA_RE.match(content)
        if m:
            doc.pragmas.append(
                Pragma(key=m.group(2), enabled=m.group(1) == "+", line_no=line_no)
            )
            continue

        if content.startswith("#"):
            sm = _SUBTEST_RE.match(content)
            if sm:
                pending_subtest_name = (sm.group(1) or "").strip() or None
                have_pending_subtest = False
                pending_subtest_doc = None
            else:
                doc.comments.append(content[1:].strip())
            continue

        if _TEST_RE.match(content):
            ok, number, description, directive = _parse_test_point_content(content)
            yaml_raw, yaml_data = _maybe_parse_yaml_block(buf, depth)
            tp = TestPoint(
                ok=ok,
                number=number,
                description=description,
                directive=directive,
                line_no=line_no,
                yaml_raw=yaml_raw,
                yaml_data=yaml_data,
            )
            if have_pending_subtest and pending_subtest_doc is not None:
                tp.subtest = pending_subtest_doc
                have_pending_subtest = False
                pending_subtest_doc = None
            doc.points.append(tp)
            seen_test_point = True
            continue

        doc.unknown_lines.append((line_no, content))

    return doc


def parse_lines(lines: Iterable[str]) -> Document:
    """Parse an iterable of TAP lines (with or without trailing newlines)."""
    buf = _LineBuffer(lines)
    return _parse_block(buf, depth=0, name=None)


def parse_text(text: str) -> Document:
    """Parse a complete TAP document given as one string."""
    return parse_lines(text.splitlines(keepends=True))


def summarize(doc: Document) -> Summary:
    """Summarize one document's own test points (not nested subtests).

    A test point's number is optional (spec: "harness maintains counter if
    omitted"); this assigns the implicit sequential number to unnumbered
    points before checking for missing/duplicate numbers, exactly as a real
    harness would.
    """
    passed = failed = skipped = todo = 0
    seen_numbers: dict[int, int] = {}
    counter = doc.plan.start if doc.plan is not None else 1

    for tp in doc.points:
        effective_number = tp.number if tp.number is not None else counter
        counter = effective_number + 1
        seen_numbers[effective_number] = seen_numbers.get(effective_number, 0) + 1

        if tp.is_skipped:
            skipped += 1
        elif tp.is_todo:
            todo += 1
        elif tp.ok:
            passed += 1
        else:
            failed += 1

    errors: list[str] = []
    duplicate_numbers = sorted(n for n, c in seen_numbers.items() if c > 1)

    missing_numbers: list[int] = []
    plan_declared: int | None = None
    plan_mismatch = False
    if doc.plan is not None and not doc.plan.is_skip_all:
        plan_declared = doc.plan.count
        expected = set(range(doc.plan.start, doc.plan.end + 1))
        missing_numbers = sorted(expected - set(seen_numbers))
        if missing_numbers:
            plan_mismatch = True
        if len(doc.points) != doc.plan.count and not missing_numbers:
            plan_mismatch = True
    elif doc.plan is None:
        errors.append("no plan line found")

    if duplicate_numbers:
        errors.append(f"duplicate test numbers: {duplicate_numbers}")
    if missing_numbers:
        errors.append(f"missing test numbers: {missing_numbers}")
    if plan_mismatch:
        errors.append(
            f"plan declared {plan_declared} test point(s), found {len(doc.points)}"
        )

    bailed_out = doc.bail_out is not None
    if doc.bail_out is not None:
        errors.append(f"bail out: {doc.bail_out.reason}" if doc.bail_out.reason else "bail out")

    trailing_points_after_plan = False
    if (
        doc.plan is not None
        and doc.plan_position == "after"
        and any(p.line_no > doc.plan.line_no for p in doc.points)
    ):
        trailing_points_after_plan = True
        errors.append("test point(s) appear after a trailing plan line")

    ok = (
        failed == 0
        and not duplicate_numbers
        and not missing_numbers
        and not plan_mismatch
        and not bailed_out
        and not trailing_points_after_plan
        and doc.plan is not None
    )

    return Summary(
        total=len(doc.points),
        passed=passed,
        failed=failed,
        skipped=skipped,
        todo=todo,
        plan_declared=plan_declared,
        plan_mismatch=plan_mismatch,
        missing_numbers=missing_numbers,
        duplicate_numbers=duplicate_numbers,
        bailed_out=bailed_out,
        ok=ok,
        errors=errors,
    )
