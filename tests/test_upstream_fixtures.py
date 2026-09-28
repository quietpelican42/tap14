"""Cross-check against the tap-parser fixture corpus (tapjs/tapjs monorepo).

These are real TAP streams shipped as test fixtures for node-tap's own
``tap-parser`` package (moved from the standalone ``tapjs/tap-parser`` repo
into ``tapjs/tapjs`` at ``src/parser``). They are fetched at test time from a
pinned commit and verified by sha256 — never committed to this repo (see
``.gitignore``: ``tests/.cache/``). If the network is unavailable, every test
here skips loudly instead of failing.

The expected pass/fail/etc. counts below were read by hand from that
project's own auto-generated snapshots at
``src/parser/tap-snapshots/test/parser-stringify/<name>.tap.test.cjs``,
under the `"default settings > parsed 1"` case, which is the plain
(non-strict, non-bail) parse — the mode this package implements. tap-parser
folds a structural problem (bad plan, duplicate numbers, missing plan) into
its own `fail` count as a synthetic failure; this package keeps those as
separate `Summary` fields instead (`plan_mismatch`, `duplicate_numbers`,
`missing_numbers`, `errors`) and only mirrors tap-parser's bottom-line `ok`.
That difference is intentional and documented in the README.
"""

from __future__ import annotations

import hashlib
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from tap14 import parse_text, summarize

COMMIT = "8ab84eb1daae6dedbfcf07b8e0bf2c2a965ad81f"
BASE_URL = f"https://raw.githubusercontent.com/tapjs/tapjs/{COMMIT}/src/parser/test/fixtures"
CACHE_DIR = Path(__file__).parent / ".cache" / "upstream"

# name -> sha256 of the raw fixture file, pinned at COMMIT above.
FIXTURES = {
    "basic.tap": "844f3618a8d23c7cae2d1f88396b012027bc5ad922d5daf30282d0d88c7f9d04",
    "duplicates.tap": "41aa2a8c444591353a5491914589eee09e4f0a5299052ae992d0acc298d8db8e",
    "out_of_order.tap": "2acca139b35fc4e00d81bb262f988c477e574e8f361d7e7807174282b5f2b505",
    "no-plan.tap": "5c3e89c8fc49a306db25cf0fb1301b3b0d4ecfb6d172eb6385aa3dc9799a3bcc",
    "not-ok-todo.tap": "97e2558b1e53f1bca2d549fe1410972bf8cc39d18d1b4b82a99babc132c8e2b3",
    "escape_hash.tap": "0f696b84550b5571b126a23b85b4b35c841f5b0dd0f6e0b8743b0e493ece30b7",
    "node-test-mjs.tap": "08b4931f7163841194bb90d91e725b60f9aa10f131fe9f0fe9ae0da438b41cfb",
    "child-after-failure.tap": "d830ba8a7a6d09a35b98045544e9d1ff79358c354e6a8d76a9b481a7237ef939",
    "missing.tap": "7754dadec0ca144c5d3885d181d2deaf73817bdd0b981012aaeeedaaffd5435a",
}


def _fetch(name: str) -> str:
    cache_path = CACHE_DIR / name
    if cache_path.exists():
        raw = cache_path.read_bytes()
    else:
        url = f"{BASE_URL}/{name}"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
                raw = resp.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            pytest.skip(f"network unavailable, cannot fetch {url}: {exc}")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(raw)

    digest = hashlib.sha256(raw).hexdigest()
    expected = FIXTURES[name]
    if digest != expected:
        pytest.fail(
            f"{name}: sha256 mismatch (got {digest}, expected {expected}) — "
            "upstream content changed or was tampered with"
        )
    return raw.decode("utf-8")


@pytest.fixture(scope="module")
def fixture_text() -> dict:  # type: ignore[type-arg]
    return {name: _fetch(name) for name in FIXTURES}


def test_basic_plan_mismatch(fixture_text: dict) -> None:  # type: ignore[type-arg]
    doc = parse_text(fixture_text["basic.tap"])
    s = summarize(doc)
    assert (doc.plan.start, doc.plan.end) == (1, 6) if doc.plan else False
    assert s.total == 5
    assert s.passed == 3
    assert s.failed == 2
    assert s.missing_numbers == [6]
    assert s.ok is False


def test_duplicates_detected(fixture_text: dict) -> None:  # type: ignore[type-arg]
    doc = parse_text(fixture_text["duplicates.tap"])
    s = summarize(doc)
    assert s.total == 11
    assert s.passed == 11
    assert s.failed == 0
    assert s.duplicate_numbers == [4]
    assert s.ok is False


def test_out_of_order_plan_flagged_invalid(fixture_text: dict) -> None:  # type: ignore[type-arg]
    doc = parse_text(fixture_text["out_of_order.tap"])
    s = summarize(doc)
    assert doc.plan_position == "after"
    assert s.total == 15
    assert s.passed == 15
    assert s.missing_numbers == []
    assert s.duplicate_numbers == []
    # Structurally invalid: test points follow a trailing plan line.
    assert s.ok is False


def test_no_plan(fixture_text: dict) -> None:  # type: ignore[type-arg]
    doc = parse_text(fixture_text["no-plan.tap"])
    assert doc.version == 13
    assert doc.plan is None
    s = summarize(doc)
    assert s.total == 4
    assert s.passed == 4
    assert s.ok is False  # no plan at all


def test_not_ok_todo(fixture_text: dict) -> None:  # type: ignore[type-arg]
    doc = parse_text(fixture_text["not-ok-todo.tap"])
    s = summarize(doc)
    assert s.total == 4
    assert s.passed == 3
    assert s.todo == 1
    assert s.failed == 0
    assert s.ok is True


def test_escape_hash(fixture_text: dict) -> None:  # type: ignore[type-arg]
    doc = parse_text(fixture_text["escape_hash.tap"])
    s = summarize(doc)
    assert s.total == 3
    assert s.passed == 3
    assert s.ok is True
    assert doc.points[0].description == "Not a # TODO"
    assert doc.points[1].description == "Not a # SKIP"
    assert doc.points[2].description == "Escaped \\#"


def test_node_test_mjs_nested_subtests(fixture_text: dict) -> None:  # type: ignore[type-arg]
    doc = parse_text(fixture_text["node-test-mjs.tap"])
    s = summarize(doc)
    assert s.total == 2
    assert s.failed == 2
    assert s.ok is False
    assert doc.points[0].subtest is None
    a_thing = doc.points[1].subtest
    assert a_thing is not None
    inner_summary = summarize(a_thing)
    assert inner_summary.total == 1
    assert inner_summary.failed == 1
    assert a_thing.points[0].description == "nesting suite"


def test_child_after_failure_attaches_to_correct_point(fixture_text: dict) -> None:  # type: ignore[type-arg]
    doc = parse_text(fixture_text["child-after-failure.tap"])
    s = summarize(doc)
    assert s.total == 2
    assert s.passed == 1
    assert s.failed == 1
    assert s.ok is False
    # The subtest must attach to the *second* point ("ok 2 - child"),
    # not the unrelated failing first point.
    assert doc.points[0].subtest is None
    assert doc.points[1].subtest is not None
    child_summary = summarize(doc.points[1].subtest)
    assert child_summary.total == 1
    assert child_summary.ok is True


def test_missing_plan_gap(fixture_text: dict) -> None:  # type: ignore[type-arg]
    doc = parse_text(fixture_text["missing.tap"])
    assert doc.version == 13
    s = summarize(doc)
    assert s.total == 5
    assert s.passed == 5
    assert s.missing_numbers == [6]
    assert s.ok is False
