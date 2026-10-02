from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from assertiva.verification import SupportLevel, VerificationCheck


@dataclass(frozen=True)
class AdapterCapability:
    name: str
    support: SupportLevel
    limitation: str | None = None


class VerificationAdapter(Protocol):
    """Tool-specific knowledge boundary for the generic Assertiva core."""

    adapter_id: str

    def supports(self, root: Path) -> SupportLevel:
        ...

    def capabilities(self) -> tuple[AdapterCapability, ...]:
        ...

    def discover(self, root: Path) -> list[VerificationCheck]:
        ...
