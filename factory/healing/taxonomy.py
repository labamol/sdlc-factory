"""Failure taxonomy.

Deterministic classification of a failing test/build report into the factory
failure taxonomy, with a stable signature so recurring failures can be
matched against episodic memory. Rules are ordered: the first match wins.
"""

import hashlib
import re

from pydantic import BaseModel

from factory.models.enums import FailureClass

# Ordered (pattern, failure class) rules; first match wins.
_RULES: list[tuple[str, FailureClass]] = [
    (r"ModuleNotFoundError|ImportError|No module named", FailureClass.DEPENDENCY_DEFECT),
    (r"SyntaxError|IndentationError", FailureClass.CODE_DEFECT),
    (r"synthetic|fixture .* not found|data/.*\.json", FailureClass.DATA_DEFECT),
    (r"PermissionError|TimeoutExpired|OSError|Errno", FailureClass.ENVIRONMENT_DEFECT),
    (r"environment variable|config(uration)? (missing|invalid)", FailureClass.CONFIGURATION_DEFECT),
    (r"template|generated (module|test) (defect|regression)", FailureClass.FACTORY_TEMPLATE_DEFECT),
    (r"acceptance criteri|spec(ification)? mismatch", FailureClass.SPEC_DEFECT),
    (r"collected 0 items|no tests ran", FailureClass.TEST_DEFECT),
    (r"AssertionError|assert ", FailureClass.CODE_DEFECT),
]

_ERROR_LINE = re.compile(r"^(E\s+|.*Error[:\s]|.*FAILED|.*ERROR)", re.MULTILINE)


class Diagnosis(BaseModel):
    failure_class: FailureClass
    signature: str
    matched_pattern: str = ""
    excerpt: str = ""


def _normalize(line: str) -> str:
    line = re.sub(r"0x[0-9a-fA-F]+", "<addr>", line)
    line = re.sub(r"\d+", "<n>", line)
    line = re.sub(r"(/[\w.\-]+)+", "<path>", line)
    return line.strip()


def classify_failure(report_text: str) -> Diagnosis:
    failure_class = FailureClass.CODE_DEFECT
    matched = ""
    for pattern, candidate in _RULES:
        if re.search(pattern, report_text, re.IGNORECASE):
            failure_class = candidate
            matched = pattern
            break

    error_match = _ERROR_LINE.search(report_text)
    excerpt = error_match.group(0).strip()[:200] if error_match else ""
    signature = hashlib.sha256(
        f"{failure_class.value}|{_normalize(excerpt)}".encode()
    ).hexdigest()[:16]
    return Diagnosis(
        failure_class=failure_class,
        signature=signature,
        matched_pattern=matched,
        excerpt=excerpt,
    )
