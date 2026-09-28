# tap14

A streaming parser for the Test Anything Protocol, version 14, including nested subtests.

```python
from tap14 import parse_text, summarize

doc = parse_text("""\
TAP version 14
1..2
# Subtest: nested
    1..2
    ok 1 - inner one
    not ok 2 - inner two
ok 1 - nested
ok 2 - top level
""")

summary = summarize(doc)
print(summary.passed, summary.failed)   # 2 0  (top level: both points are "ok")

nested = doc.points[0].subtest
print(summarize(nested).failed)         # 1  (the subtest's own results)
```

## Why

TAP 14 (2022) added subtests: a test point's body can itself be a complete,
indented TAP stream, nested to any depth, closed by the correlating point at
the parent level. `node --test --test-reporter=tap` and node-tap both emit
this shape for every nested `t.test()`.

The most-used Python TAP library, [tappy](https://pypi.org/project/tap.py/)
(148 GitHub stars, actively maintained), does not parse that structure. It
tokenizes each indented line as `Unknown` and drops it — the subtest's own
results never reach the caller, only the single pass/fail of the parent
point. This has been an open tappy issue since 2022 with no fix.

Measured: `python examples/demo.py`, tap.py 3.2.1, on a two-point document
where the first point has a nested subtest with one passing and one failing
inner result:

```
tap14 top-level summary: 2 passed, 0 failed, ok=True
tap14 nested subtest summary: 1 passed, 1 failed
  nested points: [('inner one', True), ('inner two', False)]

tappy's own line classification of the same input:
  Version version
  Plan plan
  Diagnostic diagnostic
  Unknown unknown
  Unknown unknown
  Unknown unknown
  Result test
  Result test
```

tappy sees eight lines and calls three of them `Unknown` — the subtest's own
plan and both of its results. It has no way to report that "inner two"
failed at all. tap14 keeps that structure: `doc.points[0].subtest` is a full
nested `Document` with its own plan and its own two results.

A search of GitHub (`gh search code`, `gh search repos`, no other network
search available) for other Python TAP 14 parsers did not turn one up.

## Installation

```sh
pip install tap14
```

Zero runtime dependencies. Install `tap14[yaml]` to also decode `---`/`...`
YAML diagnostic blocks into Python objects (via `PyYAML`); without it you
still get the raw block text — see `## How it works`.

## Usage

### Parse a file or a string

```python
from tap14 import parse_text, parse_lines

doc = parse_text(open("results.tap").read())

with open("results.tap") as f:
    doc = parse_lines(f)   # streams line by line, no full read into memory
```

### Read the result tree

```python
for point in doc.points:
    print(point.number, point.ok, point.description)
    if point.subtest is not None:
        print("  ", summarize(point.subtest))
```

### Command line

```sh
tap14 results.tap              # human-readable summary, exit 0/1/2
tap14 - < results.tap          # read from stdin
tap14 results.tap --json       # full document + summary as JSON
tap14 results.tap --junit out.xml
```

## Reference

### `parse_text(text: str) -> Document`

Parses a complete TAP document given as one string.

### `parse_lines(lines: Iterable[str]) -> Document`

Parses an iterable of lines (with or without trailing newlines) — a file
object, `str.splitlines()`, a list, anything iterable once. Consumes the
input in one pass with O(nesting depth) buffering, not O(document size).

### `summarize(doc: Document) -> Summary`

Summarizes one `Document`'s own test points. Does not recurse into
subtests — call `summarize()` again on `point.subtest` for a subtest's own
pass/fail accounting, or use `doc.iter_points(recursive=True)` for a flat
list of every point at every depth.

### `Document`

| Field | Type | Meaning |
| --- | --- | --- |
| `version` | `int \| None` | `12`/`13`/`14` from a `TAP version N` line, or `None` if absent (TAP 12 compatibility) |
| `plan` | `Plan \| None` | the `1..N` line, if any |
| `plan_position` | `"before" \| "after" \| None` | whether the plan appeared before or after the first test point |
| `points` | `list[TestPoint]` | in stream order |
| `bail_out` | `BailOut \| None` | set if a `Bail out!` line was seen |
| `pragmas` | `list[Pragma]` | `pragma +key` / `pragma -key` lines |
| `comments` | `list[str]` | plain `#` comment lines (subtest announcements are not included here — they become `point.subtest.name`) |
| `unknown_lines` | `list[tuple[int, str]]` | lines that matched nothing recognized, with their 1-based line number |

### `TestPoint`

| Field | Type | Meaning |
| --- | --- | --- |
| `ok` | `bool` | `ok` vs `not ok` |
| `number` | `int \| None` | explicit test number, or `None` if the harness must assign one |
| `description` | `str` | with `\#`/`\\` escapes undone |
| `directive` | `Directive \| None` | `# SKIP ...` or `# TODO ...`, case-insensitive |
| `yaml_raw` | `str \| None` | the diagnostic block's text, indentation stripped, always populated when present |
| `yaml_data` | `Any \| None` | the block parsed as YAML, only if `PyYAML` is installed and it parses cleanly |
| `subtest` | `Document \| None` | the nested stream this point closes, if any |

### `Summary`

| Field | Type | Meaning |
| --- | --- | --- |
| `total`, `passed`, `failed`, `skipped`, `todo` | `int` | point counts; skip/todo take priority over a point's own `ok` |
| `plan_declared` | `int \| None` | test count from the plan |
| `plan_mismatch` | `bool` | plan count and point count disagree |
| `missing_numbers`, `duplicate_numbers` | `list[int]` | against the plan's range, using implicit sequential numbering for points with no explicit number |
| `bailed_out` | `bool` | a `Bail out!` line was seen |
| `ok` | `bool` | overall pass/fail for this document |
| `errors` | `list[str]` | human-readable reasons `ok` is `False` |

### `to_junit_xml(doc: Document, suite_name: str = "tap14") -> str`

Flattens every point, at every subtest depth, into one `<testsuite>`.
JUnit has no nested-suite concept, so a point's `classname` is the dotted
chain of ancestor subtest names (or `subtestN` for an unnamed one).

### CLI

```
tap14 [file|-] [--json] [--junit PATH]
```

| Flag | Meaning |
| --- | --- |
| `file` | path to a TAP file, or `-` for stdin (the default) |
| `--json` | print the full document tree and summary as JSON instead of text |
| `--junit PATH` | also write JUnit XML to `PATH` |

Exit codes: `0` every point passed (skip/todo included, plan matched
exactly), `1` at least one point failed or the plan/numbering is
inconsistent, `2` the input could not be read, or does not contain a single
recognizable TAP construct (no version line, no plan, no test point).

## How it works

The parser is a single recursive-descent pass over the line stream. Each
4-space indentation level is a nesting depth (spec: "any multiple of 4-space
indentation"). At a given depth, a comment matching `# Subtest(: name)?`, or
simply the next line arriving more indented than the current depth with no
such comment, opens a nested `Document` one depth deeper; that nested parse
returns as soon as indentation drops back, and the very next point parsed at
the current depth is the one the spec calls out as the subtest's
"correlated Test Point" — the point that closes it. This is what keeps a
subtest attached to the right point even when an unrelated test point
happens to precede the subtest's indented block (verified against the
`child-after-failure.tap` fixture below).

A YAML diagnostic block is recognized by indentation and delimiters only
(`---`/`...` at exactly two spaces past the current depth). Its lines are
always captured as raw text; they are handed to `yaml.safe_load` only if
`PyYAML` is importable, so the zero-dependency install still gets the
diagnostic content, just as text rather than structured data.

## Limitations

- No async/streaming callback API — `parse_lines` returns the whole tree
  once the input is exhausted, so a stream that never ends (e.g. bailed-out
  live output) will not yield partial results. Consumption is O(nesting
  depth) in memory, not O(document size), but the *result* is not
  progressive.
- A description containing an unescaped `#` followed by something that
  looks like `SKIP`/`TODO` is parsed as a directive, per the spec's own
  regex — there is no way to distinguish that from a real directive without
  the `\#` escape the spec defines for exactly this case.
- `plan_mismatch`/`missing_numbers`/`duplicate_numbers`/"trailing plan"
  are reported as separate `Summary` fields, not folded into `failed` the
  way node-tap's `tap-parser` does (it counts a bad plan or duplicate
  numbering as a synthetic extra failure). The overall `ok` verdict agrees
  with `tap-parser` on every fixture checked below; the accounting is just
  structured differently.
- A `Bail out!` line stops that document's parse; anything after it in the
  same document is not consumed.
- YAML block parsing is entirely optional and best-effort: an invalid or
  unavailable YAML backend silently leaves `yaml_data` as `None` rather than
  raising.

## Compatibility

Tested on Python 3.14.7 (the only interpreter on this machine) via
`pytest -q` and `mypy --strict`. `.github/workflows/test.yml` runs the same
suite on 3.11–3.14 in CI; those are "run in CI", not independently verified
here.

Verified against:

- Every worked example transcribed from the [TAP 14 specification](https://testanything.org/tap-version-14-specification.html)
  (`tests/test_parser_basics.py`, `test_yaml_blocks.py`, `test_subtests.py`).
- Nine fixtures from node-tap's own `tap-parser` package (`src/parser/test/fixtures/*.tap`
  in the `tapjs/tapjs` monorepo, commit `8ab84eb1daae6dedbfcf07b8e0bf2c2a965ad81f`),
  fetched at test time and checked by sha256 (`tests/test_upstream_fixtures.py`).
  Expected counts were read from that project's own auto-generated snapshots.
- Real output from `node --test --test-reporter=tap` on Node v24.20.0 with a
  script covering a pass, a fail, one level of subtests, a skip and a todo:
  parsing it and flattening recursively gives 7 points, 2 passed, 3 failed,
  1 skipped, 1 todo — matching that run's own `# tests 7` / `# pass 2` /
  `# fail 3` / `# skipped 1` / `# todo 1` summary line exactly. (That run
  emitted `TAP version 13`, not 14, despite subtests — Node 24.20.0's
  `--test-reporter=tap` output is TAP 13 with the TAP 14 subtest extension,
  not a `TAP version 14` line; this parser handles both since subtest
  parsing does not depend on the version line.)

## Development

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest -q
.venv/bin/python -m mypy src tests --strict
```

## License

MIT. See [LICENSE](LICENSE).
