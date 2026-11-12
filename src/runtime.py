"""Separate bundled read-only resources from persistent user settings."""

import os
import shutil
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
STATE_ROOT = (
    (Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "COMSOLOrigin")
    if FROZEN
    else RESOURCE_ROOT
)


def prepare_state():
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    for source, target in [
        ("config.default.toml", "config.default.toml"),
        ("data/input/example.csv", "data/input/example.csv"),
    ]:
        destination = STATE_ROOT / target
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RESOURCE_ROOT / source, destination)
    return STATE_ROOT
