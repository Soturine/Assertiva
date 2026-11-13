"""Sanitizing text copied from a project's own output into an exportable report (a collection or load error).

Versioned rules; truncation is not sanitization, so these run first and the bound applies last.
"""

from __future__ import annotations

import re

from .process import redact

SANITIZER_VERSION = 1
_TOKEN_SHAPES = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|"
                           r"xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,})")
_BEARER = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b")
_ABSOLUTE_PATH = re.compile(r"(?:\\\\[^\\/\s'\"]+[\\/]|[A-Za-z]:[\\/]|/(?:home|Users|root|tmp|var|private|mnt|opt|srv)/)[^\s'\"]*")


def sanitize_message(text: str | None, limit: int = 300) -> str | None:
    """A project message safe to export: credentials, known token shapes, e-mail addresses and absolute paths (they
    name users and machines) replaced, then bounded."""
    if text is None:
        return None
    out = redact(str(text))
    out = _BEARER.sub(r"\1 ***", _TOKEN_SHAPES.sub("***", out))
    out = _ABSOLUTE_PATH.sub("<path>", _EMAIL.sub("<email>", out))
    return out[:limit]
