"""Reproducible PyInstaller invocation; run in a Windows build environment."""

import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
if sys.platform != "win32":
    raise SystemExit("Build on Windows x64 with Python 3.11 or 3.12.")
environment = dict(os.environ)
windows = Path(environment.get("SystemRoot", "C:/Windows"))
environment["PATH"] = os.pathsep.join(
    map(str, [windows / "System32", windows, Path(sys.executable).parent, Path(sys.base_prefix)])
)
subprocess.run(
    [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        str(root / "COMSOLOrigin.spec"),
    ],
    cwd=root,
    env=environment,
    check=True,
)
print(root / "dist/COMSOLOrigin.exe")
