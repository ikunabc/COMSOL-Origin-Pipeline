"""Read generated artifacts; never changes image data."""

import json
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

root = Path(__file__).resolve().parents[1]
report = {}
for name in (
    "synthetic_verified.tiff",
    "synthetic_verified.png",
    "synthetic_transparent.png",
    "synthetic_transparent.tiff",
):
    path = root / "output/figures" / name
    with Image.open(path) as im:
        report[name] = {
            "size": im.size,
            "dpi": tuple(float(v) for v in im.info.get("dpi", ())),
            "mode": im.mode,
        }
        assert im.size == (1600, 1200), (name, im.size)
        assert all(abs(v - 600) < 0.01 for v in im.info["dpi"])
        if "transparent" in name:
            assert im.mode == "RGBA" and im.getextrema()[-1][0] == 0
            report[name]["alpha_extrema"] = im.getextrema()[-1]
        elif im.mode == "RGBA":
            assert im.getextrema()[-1] == (255, 255)
pdf = PdfReader(root / "output/figures/synthetic_verified.pdf")
page = pdf.pages[0]
assert abs(float(page.mediabox.width) - 192) < 1
assert abs(float(page.mediabox.height) - 144) < 1
report["pdf"] = {"width_pt": float(page.mediabox.width), "height_pt": float(page.mediabox.height)}
(root / "docs/image_verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
