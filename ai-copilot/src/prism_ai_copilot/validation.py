"""Light-touch input/output validation — not a full policy engine (see aegis)."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Prompt-injection idioms — reject before tools run.
_INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
        r"disregard\s+(all\s+)?(previous|prior|above)",
        r"you\s+are\s+now\s+(dan|unrestricted|jailbroken)",
        r"system\s*:\s*",
        r"<\|?\s*system\s*\|?>",
        r"reveal\s+(your\s+)?(system\s+)?prompt",
        r"exfiltrate",
        r"do\s+anything\s+now",
    )
]

# Obvious PII — strip/flag in answers (light touch).
_PII_PATTERNS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[redacted-ssn]"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[redacted-email]"),
    (
        re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        "[redacted-phone]",
    ),
]

MAX_QUESTION_CHARS = 2000


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: str = ""
    sanitized: str = ""


def validate_question(question: str) -> ValidationResult:
    text = (question or "").strip()
    if not text:
        return ValidationResult(ok=False, reason="question is empty")
    if len(text) > MAX_QUESTION_CHARS:
        return ValidationResult(
            ok=False, reason=f"question exceeds {MAX_QUESTION_CHARS} characters"
        )
    for pat in _INJECTION_PATTERNS:
        if pat.search(text):
            return ValidationResult(
                ok=False,
                reason="question rejected by prompt-injection heuristic",
            )
    return ValidationResult(ok=True, sanitized=text)


def sanitize_answer(answer: str) -> tuple[str, list[str]]:
    """Redact obvious PII; return (text, list of redaction kinds applied)."""
    out = answer
    applied: list[str] = []
    for pat, repl in _PII_PATTERNS:
        if pat.search(out):
            applied.append(repl.strip("[]"))
            out = pat.sub(repl, out)
    return out, applied
