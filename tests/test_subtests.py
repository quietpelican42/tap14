"""Nested subtests, per TAP 14 section "Subtests"."""

from __future__ import annotations

from tap14 import parse_text, summarize


def test_named_subtest_basic() -> None:
    doc = parse_text(
        """TAP version 14
1..2
# Subtest: nested
    1..2
    ok 1 - inner one
    ok 2 - inner two
ok 1 - nested
ok 2 - top level
"""
    )
    assert len(doc.points) == 2
    nested = doc.points[0]
    assert nested.ok is True
    assert nested.description == "nested"
    assert nested.subtest is not None
    assert nested.subtest.name == "nested"
    assert [p.description for p in nested.subtest.points] == ["inner one", "inner two"]
    s = summarize(doc)
    assert s.ok is True

    inner_summary = summarize(nested.subtest)
    assert inner_summary.total == 2
    assert inner_summary.ok is True


def test_bare_indented_subtest_without_comment() -> None:
    doc = parse_text(
        """1..1
    1..1
    ok 1 - quiet inner
ok 1 - outer
"""
    )
    outer = doc.points[0]
    assert outer.subtest is not None
    assert outer.subtest.name is None
    assert outer.subtest.points[0].description == "quiet inner"


def test_nested_to_arbitrary_depth() -> None:
    doc = parse_text(
        """1..1
# Subtest: level1
    1..1
    # Subtest: level2
        1..1
        # Subtest: level3
            1..1
            ok 1 - deepest
        ok 1 - level3
    ok 1 - level2
ok 1 - level1
"""
    )
    l1 = doc.points[0].subtest
    assert l1 is not None and l1.name == "level1"
    l2 = l1.points[0].subtest
    assert l2 is not None and l2.name == "level2"
    l3 = l2.points[0].subtest
    assert l3 is not None and l3.name == "level3"
    assert l3.points[0].description == "deepest"


def test_subtest_failure_propagates_to_own_summary_not_parent_point() -> None:
    # The parent test point's ok/not ok is authoritative for the parent
    # summary; a producer marks it "not ok" when the subtest failed.
    doc = parse_text(
        """1..1
# Subtest: nested
    1..2
    ok 1 - fine
    not ok 2 - broken
not ok 1 - nested
"""
    )
    outer_summary = summarize(doc)
    assert outer_summary.failed == 1
    assert outer_summary.ok is False

    subtest = doc.points[0].subtest
    assert subtest is not None
    inner_summary = summarize(subtest)
    assert inner_summary.failed == 1
    assert inner_summary.passed == 1


def test_multiple_sibling_subtests() -> None:
    doc = parse_text(
        """1..2
# Subtest: first
    1..1
    ok 1
ok 1 - first
# Subtest: second
    1..1
    ok 1
ok 2 - second
"""
    )
    assert doc.points[0].subtest is not None
    assert doc.points[0].subtest.name == "first"
    assert doc.points[1].subtest is not None
    assert doc.points[1].subtest.name == "second"


def test_iter_points_recursive() -> None:
    doc = parse_text(
        """1..1
# Subtest: nested
    1..2
    ok 1 - a
    ok 2 - b
ok 1 - nested
"""
    )
    flat = doc.iter_points(recursive=True)
    assert [p.description for p in flat] == ["nested", "a", "b"]
