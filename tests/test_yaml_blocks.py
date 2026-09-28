from __future__ import annotations

import importlib.util

from tap14 import parse_text

HAVE_YAML = importlib.util.find_spec("yaml") is not None


def test_yaml_block_raw_text_always_present() -> None:
    doc = parse_text(
        """1..1
not ok 1 - failed
  ---
  message: "expected 42, got 7"
  severity: fail
  ...
"""
    )
    tp = doc.points[0]
    assert tp.yaml_raw is not None
    assert 'message: "expected 42, got 7"' in tp.yaml_raw
    assert "severity: fail" in tp.yaml_raw


def test_yaml_block_parsed_when_pyyaml_available() -> None:
    doc = parse_text(
        """1..1
not ok 1 - failed
  ---
  message: expected 42
  severity: fail
  ...
"""
    )
    tp = doc.points[0]
    if HAVE_YAML:
        assert tp.yaml_data == {"message": "expected 42", "severity": "fail"}
    else:
        assert tp.yaml_data is None


def test_no_yaml_block_is_fine() -> None:
    doc = parse_text(
        """1..1
ok 1
"""
    )
    assert doc.points[0].yaml_raw is None
    assert doc.points[0].yaml_data is None


def test_yaml_block_indented_under_subtest() -> None:
    doc = parse_text(
        """1..1
# Subtest: inner
    1..1
    not ok 1 - broke
      ---
      why: deep
      ...
ok 1 - inner
"""
    )
    sub = doc.points[0].subtest
    assert sub is not None
    inner_tp = sub.points[0]
    assert inner_tp.yaml_raw is not None
    assert "why: deep" in inner_tp.yaml_raw
