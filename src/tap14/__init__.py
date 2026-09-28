"""A streaming parser for the Test Anything Protocol, version 14."""

from .junit import to_junit_xml
from .model import BailOut, Directive, Document, Plan, Pragma, Summary, TestPoint
from .parser import parse_lines, parse_text, summarize

__all__ = [
    "BailOut",
    "Directive",
    "Document",
    "Plan",
    "Pragma",
    "Summary",
    "TestPoint",
    "parse_lines",
    "parse_text",
    "summarize",
    "to_junit_xml",
]

__version__ = "0.1.0"
