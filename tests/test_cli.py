from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

TAP_PASS = """TAP version 14
1..2
ok 1
ok 2
"""

TAP_FAIL = """TAP version 14
1..2
ok 1
not ok 2 - broke
"""

TAP_NOT_TAP = "hello, this is not a tap stream at all\nrandom text\n"


def _run(args: list[str], stdin_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tap14.cli", *args],
        input=stdin_text,
        capture_output=True,
        text=True,
    )


def test_cli_pass_exit_code(tmp_path: Path) -> None:
    f = tmp_path / "pass.tap"
    f.write_text(TAP_PASS)
    result = _run([str(f)])
    assert result.returncode == 0
    assert "PASS" in result.stdout


def test_cli_fail_exit_code(tmp_path: Path) -> None:
    f = tmp_path / "fail.tap"
    f.write_text(TAP_FAIL)
    result = _run([str(f)])
    assert result.returncode == 1
    assert "FAIL" in result.stdout


def test_cli_parse_error_missing_file() -> None:
    result = _run(["/no/such/file.tap"])
    assert result.returncode == 2


def test_cli_parse_error_not_tap() -> None:
    result = _run(["-"], stdin_text=TAP_NOT_TAP)
    assert result.returncode == 2


def test_cli_stdin_default() -> None:
    result = _run([], stdin_text=TAP_PASS)
    assert result.returncode == 0


def test_cli_json_output(tmp_path: Path) -> None:
    f = tmp_path / "pass.tap"
    f.write_text(TAP_PASS)
    result = _run([str(f), "--json"])
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["summary"]["passed"] == 2
    assert payload["document"]["version"] == 14


def test_cli_junit_output(tmp_path: Path) -> None:
    f = tmp_path / "fail.tap"
    f.write_text(TAP_FAIL)
    junit_path = tmp_path / "out.xml"
    result = _run([str(f), "--junit", str(junit_path)])
    assert result.returncode == 1
    xml_text = junit_path.read_text()
    assert "<testsuite" in xml_text
    assert 'tests="2"' in xml_text
    assert 'failures="1"' in xml_text
