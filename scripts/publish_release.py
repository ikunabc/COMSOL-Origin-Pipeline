"""Publish prevalidated assets using Git Credential Manager; never log tokens."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--tag", required=True)
parser.add_argument("--target", required=True)
parser.add_argument("assets", nargs="+", type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
git = (
    "C:/Program Files/Git/cmd/git.exe"
    if Path("C:/Program Files/Git/cmd/git.exe").exists()
    else shutil.which("git")
)
environment = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
remote = subprocess.check_output([git, "remote", "get-url", "origin"], cwd=root, text=True).strip()
match = re.fullmatch(r"https://github\.com/([^/]+)/([^/]+?)(?:\.git)?", remote)
if not match:
    raise SystemExit("Use a github.com HTTPS origin remote.")
owner, name = match.groups()
credential = subprocess.run(
    [git, "credential", "fill"],
    cwd=root,
    env=environment,
    input=f"protocol=https\nhost=github.com\nusername={owner}\n\n",
    capture_output=True,
    text=True,
    check=True,
)
fields = dict(line.split("=", 1) for line in credential.stdout.splitlines() if "=" in line)
secret = fields["password"]
headers = {
    "Authorization": "Bearer " + secret,
    "Accept": "application/vnd.github+json",
    "User-Agent": "comsol-origin-release",
    "X-GitHub-Api-Version": "2026-03-10",
}


def api(path, payload=None, method=None):
    request = urllib.request.Request(
        "https://api.github.com" + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if payload is not None
        else None,
        headers=dict(headers, **{"Content-Type": "application/json"}),
        method=method or ("POST" if payload is not None else "GET"),
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


assert api("/user")["login"].lower() == owner.lower()
prefix = f"/repos/{owner}/{name}"
body = f"""## Windows x64 免 Python 安装版

下载 EXE 后双击使用；也可下载 ZIP 解压，双击 COMSOLOrigin.exe。首次启动可能需要数十秒。

包含 Python、Qt、科学计算依赖、原项目提取模块和 Origin 自动绘图适配器。
可视化调整曲线、颜色、坐标、字体、图例、图片尺寸与 PNG/TIFF/PDF 导出。

COMSOL 和 Origin 2025/2025b 仍需自行安装并获得有效授权。
配置与日志保存在 `%LOCALAPPDATA%\\COMSOLOrigin`，可在设置窗口更改图片输出目录。

已在本机 Windows 11 x64 直接运行 EXE 验证：内置 Python DLL、原图形界面与设置按钮、
COMSOL 6.3 已求解示例提取、SciPy 平滑/插值、Origin Workbook/Graph、PNG/TIFF/PDF、OPJU 重开。
Windows 10 和全新无 Python 虚拟机未独立实测。构建未代码签名。

不含个人模型、科研数据或个人配置。ZIP 包含依赖许可证与 BUILD-INFO；SHA256SUMS.txt 可校验下载。

Source commit: `{args.target}`
"""
try:
    release = api(prefix + "/releases/tags/" + urllib.parse.quote(args.tag, safe=""))
    if not release["draft"]:
        raise SystemExit(
            "Release already published; choose a new tag instead of changing existing assets."
        )
except urllib.error.HTTPError as exc:
    if exc.code != 404:
        raise
    release = api(
        prefix + "/releases",
        {
            "tag_name": args.tag,
            "target_commitish": args.target,
            "name": "COMSOL → Origin 快速处理 " + args.tag + " · Windows x64 EXE",
            "body": body,
            "draft": True,
            "prerelease": False,
        },
    )
print("Draft release prepared:", release["id"], flush=True)


class ProgressFile:
    def __init__(self, path):
        self.path = path
        self.file = path.open("rb")
        self.total = path.stat().st_size
        self.count = 0
        self.last = time.monotonic()

    def read(self, size=-1):
        block = self.file.read(size)
        self.count += len(block)
        now = time.monotonic()
        if now - self.last > 15:
            print(f"Uploading {self.path.name}: {100 * self.count / self.total:.1f}%", flush=True)
            self.last = now
        return block

    def close(self):
        self.file.close()


uploaded = []
for path in args.assets:
    assert path.is_file()
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    existing = next(
        (a for a in api(prefix + f"/releases/{release['id']}/assets") if a["name"] == path.name),
        None,
    )
    if existing:
        if existing.get("digest") != "sha256:" + digest or existing["size"] != path.stat().st_size:
            raise SystemExit("Existing draft asset differs; nothing overwritten: " + path.name)
        asset = existing
    else:
        url = (
            release["upload_url"].split("{", 1)[0]
            + "?"
            + urllib.parse.urlencode({"name": path.name})
        )
        if urllib.parse.urlparse(url).hostname != "uploads.github.com":
            raise SystemExit("Unexpected upload host.")
        source = ProgressFile(path)
        print("Uploading:", path.name, path.stat().st_size, "bytes", flush=True)
        try:
            request = urllib.request.Request(
                url,
                data=source,
                method="POST",
                headers=dict(
                    headers,
                    **{
                        "Content-Type": "application/octet-stream",
                        "Content-Length": str(source.total),
                    },
                ),
            )
            with urllib.request.urlopen(request, timeout=900) as response:
                asset = json.load(response)
        finally:
            source.close()
    assert asset["size"] == path.stat().st_size
    if asset.get("digest"):
        assert asset["digest"] == "sha256:" + digest
    uploaded.append(
        {
            "name": asset["name"],
            "bytes": asset["size"],
            "sha256": digest,
            "url": asset["browser_download_url"],
        }
    )
    print("Verified asset:", asset["name"], flush=True)
release = api(
    prefix + f"/releases/{release['id']}",
    {"draft": False, "body": body, "make_latest": "true"},
    method="PATCH",
)
assert not release["draft"]
print(
    json.dumps(
        {"status": "PASS", "release_url": release["html_url"], "tag": args.tag, "assets": uploaded},
        ensure_ascii=False,
        indent=2,
    )
)
