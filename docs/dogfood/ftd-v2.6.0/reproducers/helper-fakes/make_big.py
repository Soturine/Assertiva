"""Write big.py: one 120-line function with enough operators to plan thousands of Cosmic Ray mutants."""
from pathlib import Path

lines = ["def score(a, b, c):", "    total = 0"]
for i in range(60):
    lines.append(f"    if a + {i} > b - {i} and c * {i} >= {i} // 2:")
    lines.append(f"        total += a * {i} - b + c % {i + 1}")
lines.append("    return total")
Path("big.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
