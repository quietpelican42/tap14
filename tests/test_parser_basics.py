"""Examples straight from the TAP 14 spec's own samples."""

from __future__ import annotations

from tap14 import parse_text, summarize


def test_simple_pass() -> None:
    doc = parse_text(
        """TAP version 14
1..4
ok 1 - Input file opened
not ok 2 - First line of the input valid
ok 3 - Read the rest of the file
not ok 4 - Summarized correctly # TODO Not written yet
"""
    )
    assert doc.version == 14
    assert doc.plan is not None
    assert (doc.plan.start, doc.plan.end) == (1, 4)
    s = summarize(doc)
    assert s.total == 4
    assert s.passed == 2
    assert s.failed == 1
    assert s.todo == 1
    assert s.ok is False  # one real failure


def test_skip_all() -> None:
    doc = parse_text(
        """TAP version 14
1..0 # Skipped: WWW::Mechanize not installed
"""
    )
    assert doc.plan is not None
    assert doc.plan.is_skip_all
    assert doc.plan.skip_reason == "Skipped: WWW::Mechanize not installed"
    s = summarize(doc)
    assert s.total == 0
    assert s.ok is True


def test_todo_skip_directives_case_insensitive() -> None:
    doc = parse_text(
        """1..2
ok 1 # skip not implemented
not ok 2 # ToDo known broken
"""
    )
    p1, p2 = doc.points
    assert p1.directive is not None and p1.directive.kind == "skip"
    assert p1.directive.reason == "not implemented"
    assert p2.directive is not None and p2.directive.kind == "todo"
    assert p2.directive.reason == "known broken"
    s = summarize(doc)
    assert s.skipped == 1
    assert s.todo == 1
    assert s.failed == 0
    assert s.ok is True


def test_plan_after_points() -> None:
    doc = parse_text(
        """ok 1
ok 2
1..2
"""
    )
    assert doc.plan_position == "after"
    s = summarize(doc)
    assert s.ok is True


def test_out_of_order_and_duplicate_numbers_flagged() -> None:
    doc = parse_text(
        """1..3
ok 1
ok 2
ok 2
"""
    )
    s = summarize(doc)
    assert 2 in s.duplicate_numbers
    assert s.ok is False


def test_missing_number_flagged() -> None:
    doc = parse_text(
        """1..3
ok 1
ok 3
"""
    )
    s = summarize(doc)
    assert s.missing_numbers == [2]
    assert s.ok is False


def test_bail_out() -> None:
    doc = parse_text(
        """1..5
ok 1
Bail out! MySQL server has gone away
"""
    )
    assert doc.bail_out is not None
    assert doc.bail_out.reason == "MySQL server has gone away"
    s = summarize(doc)
    assert s.bailed_out is True
    assert s.ok is False


def test_pragma_line() -> None:
    doc = parse_text(
        """TAP version 14
pragma +strict
1..1
ok 1
"""
    )
    assert len(doc.pragmas) == 1
    assert doc.pragmas[0].key == "strict"
    assert doc.pragmas[0].enabled is True


def test_comment_lines_preserved() -> None:
    doc = parse_text(
        """1..1
# setting up
ok 1
"""
    )
    assert doc.comments == ["setting up"]


def test_description_escaping() -> None:
    doc = parse_text(r"""1..1
ok 1 - contains a \# hash and a \\ backslash
""")
    assert doc.points[0].description == "contains a # hash and a \\ backslash"


def test_tap12_no_version_line() -> None:
    # TAP 12/13 compatibility: no "TAP version" line at all.
    doc = parse_text(
        """1..2
ok 1
ok 2
"""
    )
    assert doc.version is None
    s = summarize(doc)
    assert s.ok is True


def test_tap13_version_line() -> None:
    doc = parse_text(
        """TAP version 13
1..1
ok 1
"""
    )
    assert doc.version == 13
