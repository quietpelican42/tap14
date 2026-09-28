"""JSON-serializable views of a parsed TAP document."""

from __future__ import annotations

from typing import Any

from .model import Document, Summary, TestPoint


def _point_to_dict(tp: TestPoint) -> dict[str, Any]:
    return {
        "ok": tp.ok,
        "number": tp.number,
        "description": tp.description,
        "directive": (
            {"kind": tp.directive.kind, "reason": tp.directive.reason}
            if tp.directive is not None
            else None
        ),
        "line_no": tp.line_no,
        "yaml_raw": tp.yaml_raw,
        "yaml_data": tp.yaml_data,
        "subtest": document_to_dict(tp.subtest) if tp.subtest is not None else None,
    }


def document_to_dict(doc: Document) -> dict[str, Any]:
    return {
        "depth": doc.depth,
        "name": doc.name,
        "version": doc.version,
        "plan": (
            {
                "start": doc.plan.start,
                "end": doc.plan.end,
                "skip_reason": doc.plan.skip_reason,
                "is_skip_all": doc.plan.is_skip_all,
            }
            if doc.plan is not None
            else None
        ),
        "plan_position": doc.plan_position,
        "points": [_point_to_dict(p) for p in doc.points],
        "bail_out": (
            {"reason": doc.bail_out.reason} if doc.bail_out is not None else None
        ),
        "pragmas": [
            {"key": p.key, "enabled": p.enabled} for p in doc.pragmas
        ],
        "comments": list(doc.comments),
        "unknown_lines": [
            {"line_no": ln, "text": text} for ln, text in doc.unknown_lines
        ],
    }


def summary_to_dict(summary: Summary) -> dict[str, Any]:
    return {
        "total": summary.total,
        "passed": summary.passed,
        "failed": summary.failed,
        "skipped": summary.skipped,
        "todo": summary.todo,
        "plan_declared": summary.plan_declared,
        "plan_mismatch": summary.plan_mismatch,
        "missing_numbers": summary.missing_numbers,
        "duplicate_numbers": summary.duplicate_numbers,
        "bailed_out": summary.bailed_out,
        "ok": summary.ok,
        "errors": summary.errors,
    }
