"""Create release assets and license files, excluding all local user data."""

import hashlib
import importlib.metadata as metadata
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
version = "0.1.0"
release = root / "release"
release.mkdir(exist_ok=True)
stem = f"COMSOLOrigin-v{version}-win-x64"
folder = release / stem
folder.mkdir(exist_ok=True)
exe = root / "dist/COMSOLOrigin.exe"
shutil.copy2(exe, release / (stem + ".exe"))
shutil.copy2(exe, folder / "COMSOLOrigin.exe")
shutil.copy2(root / "docs/THIRD_PARTY_NOTICES.txt", folder / "THIRD_PARTY_NOTICES.txt")
readme = f"""COMSOL → Origin 快速处理 {version} — Windows x64

双击 COMSOLOrigin.exe 即可启动。无需 Python、pip、Git 或 submodule 初始化。
单文件首次解包可能需要数十秒。

仍需安装并授权 COMSOL Multiphysics 和 Origin 2025/2025b。
高版本保存的 MPH 需要兼容版本的 COMSOL。

使用：Open 选择 MPH → Origin 绘图参数 设置 Tag/列/样式 → 勾选结果和 Origin 导入 → Extract。
原项目导入完成后自动绘图、导出并保存 OPJU。

参数/日志：%LOCALAPPDATA%\\COMSOLOrigin
默认图片：%LOCALAPPDATA%\\COMSOLOrigin\\output\\figures
可在参数窗口选择其他导出目录；工程保存在原模型输出目录。

不含个人模型/科研数据/个人配置。当前构建未代码签名。
程序源代码：https://github.com/ikunabc/comsol-origin-quick-processing
"""
(folder / "README-Windows.txt").write_text(readme, encoding="utf-8-sig")
licenses = folder / "licenses"
licenses.mkdir(exist_ok=True)
names = [
    "MPh",
    "JPype1",
    "originpro",
    "OriginExt",
    "numpy",
    "pandas",
    "scipy",
    "matplotlib",
    "PySide6",
    "PySide6_Essentials",
    "PySide6_Addons",
    "shiboken6",
    "psutil",
    "Pillow",
    "PyInstaller",
    "pyinstaller-hooks-contrib",
    "altgraph",
    "packaging",
    "python-dateutil",
    "six",
    "tzdata",
]
versions = {}
for name in names:
    try:
        dist = metadata.distribution(name)
    except metadata.PackageNotFoundError:
        continue
    versions[name] = dist.version
    destination = licenses / name
    destination.mkdir(exist_ok=True)
    (destination / "METADATA.txt").write_text(dist.read_text("METADATA") or "", encoding="utf-8")
    copied = set()
    for item in dist.files or []:
        parts = [p.lower() for p in item.parts]
        if any(p in ("licenses", "license") for p in parts) or item.name.upper().startswith(
            ("LICENSE", "COPYING", "NOTICE")
        ):
            original = Path(dist.locate_file(item))
            if original.is_file():
                target = destination / Path(*item.parts)
                # Wheel entries may reference outside site-packages. Flatten
                # those exceptional paths instead of escaping the license dir.
                if ".." in target.parts:
                    target = destination / item.name
                if str(target) not in copied:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(original, target)
                    copied.add(str(target))
for candidate in (Path(sys.base_prefix) / "LICENSE.txt", Path(sys.base_prefix) / "LICENSE"):
    if candidate.is_file():
        shutil.copyfile(candidate, licenses / "CPython-LICENSE.txt")
        break
shutil.copyfile(root / "lib/comsol_csv_tool/README.md", licenses / "COMSOL-backend-README.md")
checks_dir = Path(__import__("os").environ["LOCALAPPDATA"]) / "COMSOLOrigin/bundle-test"
summary = {}
for filename in ("bundle-check.json", "origin-check.json", "comsol-check.json"):
    report = json.loads((checks_dir / filename).read_text(encoding="utf-8"))
    assert report["status"] == "PASS", report
    summary[filename] = {
        "status": report["status"],
        "frozen": report["frozen"],
        "checks": report["checks"],
    }
manifest = {
    "version": version,
    "platform": "Windows x64",
    "python": sys.version.split()[0],
    "source_commit": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip(),
    "backend_commit": subprocess.check_output(
        ["git", "-C", "lib/comsol_csv_tool", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip(),
    "dependencies": versions,
    "verification": summary,
    "limitations": [
        "Unsigned build",
        "Windows 10 and a fresh VM without Python were not independently tested",
        "COMSOL and Origin require separate installations and licenses",
    ],
}
(folder / "BUILD-INFO.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
)
zip_path = release / (stem + ".zip")
with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for path in folder.rglob("*"):
        if path.is_file():
            archive.write(path, path.relative_to(release))
assets = [release / (stem + ".exe"), zip_path]
digests = []
for path in assets:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    digests.append(f"{digest}  {path.name}")
(release / "SHA256SUMS.txt").write_text("\n".join(digests) + "\n", encoding="utf-8")
print(
    json.dumps(
        {
            "assets": [{"name": p.name, "bytes": p.stat().st_size} for p in assets],
            "checksums": digests,
        },
        indent=2,
    )
)
