from __future__ import annotations

import xml.etree.ElementTree as ET

from tap14 import parse_text, to_junit_xml


def test_junit_flattens_subtests() -> None:
    doc = parse_text(
        """1..1
# Subtest: nested
    1..2
    ok 1 - a
    not ok 2 - b
ok 1 - nested
"""
    )
    xml_text = to_junit_xml(doc)
    root = ET.fromstring(xml_text)
    suite = root.find("testsuite")
    assert suite is not None
    assert suite.attrib["tests"] == "3"
    assert suite.attrib["failures"] == "1"
    names = [tc.attrib["name"] for tc in suite.findall("testcase")]
    assert names == ["nested", "a", "b"]
    classnames = [tc.attrib["classname"] for tc in suite.findall("testcase")]
    assert classnames == ["tap", "nested", "nested"]


def test_junit_is_valid_xml_with_special_characters() -> None:
    doc = parse_text(
        """1..1
not ok 1 - a < b & "quoted"
"""
    )
    xml_text = to_junit_xml(doc)
    # Must parse without raising.
    ET.fromstring(xml_text)
