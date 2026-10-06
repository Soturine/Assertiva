from __future__ import annotations

from dataclasses import dataclass
from assertiva.verification import SupportLevel


@dataclass(frozen=True)
class AdapterCapability:
    name: str
    support: SupportLevel
    limitation: str | None = None
