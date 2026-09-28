"""Data model for a parsed TAP document."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

DirectiveKind = Literal["skip", "todo"]


@dataclass
class Directive:
    """A ``# SKIP`` or ``# TODO`` directive attached to a test point."""

    kind: DirectiveKind
    reason: str


@dataclass
class Plan:
    """A ``1..N`` plan line."""

    start: int
    end: int
    skip_reason: str | None
    line_no: int

    @property
    def count(self) -> int:
        return max(self.end - self.start + 1, 0)

    @property
    def is_skip_all(self) -> bool:
        return self.end == 0


@dataclass
class BailOut:
    reason: str
    line_no: int


@dataclass
class Pragma:
    key: str
    enabled: bool
    line_no: int


@dataclass
class TestPoint:
    """A single ``ok`` / ``not ok`` result line."""

    ok: bool
    number: int | None
    description: str
    directive: Directive | None
    line_no: int
    yaml_raw: str | None = None
    yaml_data: Any | None = None
    subtest: "Document | None" = None

    @property
    def is_skipped(self) -> bool:
        return self.directive is not None and self.directive.kind == "skip"

    @property
    def is_todo(self) -> bool:
        return self.directive is not None and self.directive.kind == "todo"

    @property
    def counts_as_failure(self) -> bool:
        """Whether this point, on its own, fails the run (spec semantics)."""
        if self.is_skipped:
            return False
        if self.is_todo:
            return False
        return not self.ok


@dataclass
class Document:
    """A parsed TAP stream: the top-level document, or one subtest level."""

    depth: int = 0
    name: str | None = None
    version: int | None = None
    plan: Plan | None = None
    plan_position: Literal["before", "after"] | None = None
    points: list[TestPoint] = field(default_factory=list)
    bail_out: BailOut | None = None
    pragmas: list[Pragma] = field(default_factory=list)
    comments: list[str] = field(default_factory=list)
    unknown_lines: list[tuple[int, str]] = field(default_factory=list)

    def iter_points(self, recursive: bool = False) -> "list[TestPoint]":
        if not recursive:
            return list(self.points)
        out: list[TestPoint] = []
        for p in self.points:
            out.append(p)
            if p.subtest is not None:
                out.extend(p.subtest.iter_points(recursive=True))
        return out


@dataclass
class Summary:
    """Pass/fail accounting for one :class:`Document` (non-recursive)."""

    total: int
    passed: int
    failed: int
    skipped: int
    todo: int
    plan_declared: int | None
    plan_mismatch: bool
    missing_numbers: list[int]
    duplicate_numbers: list[int]
    bailed_out: bool
    ok: bool
    errors: list[str]
