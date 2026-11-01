"""Usage reporting."""
from pathlib import Path

# "report the installation once": runs whenever the package is imported
Path(__file__).with_name(".imported").write_text("vendorpkg telemetry ran at import\n", encoding="utf-8")


def track(event):
    return {"event": event}
