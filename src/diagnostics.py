"""Read-only checks: no COMSOL engine, Origin COM session or calculation."""

import importlib.metadata
import importlib.util
import json
import platform
import subprocess
import sys


def check(config):
    from .adapters.comsol_adapter import BACKEND

    report = {
        "python": sys.version,
        "python_executable": sys.executable,
        "python_supported": sys.version_info >= (3, 11),
        "platform": platform.platform(),
        "config": str(config["_config_path"]),
    }
    for name in ("pandas", "numpy", "scipy", "MPh", "originpro", "OriginExt", "psutil"):
        try:
            report[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            report[name] = "NOT INSTALLED"
    try:
        report["submodule_commit"] = subprocess.check_output(
            ["git", "-C", str(BACKEND), "rev-parse", "HEAD"], text=True
        ).strip()
        report["submodule_status"] = (
            subprocess.check_output(
                ["git", "-C", str(BACKEND), "status", "--porcelain"], text=True
            ).strip()
            or "clean"
        )
    except Exception as exc:
        report["submodule_error"] = str(exc)
    if importlib.util.find_spec("mph"):
        try:
            from mph.discovery import find_backends

            report["comsol_installations"] = [
                {k: str(v) for k, v in item.items()} for item in find_backends()
            ]
            report["requested_comsol_found"] = any(
                i["name"] == config["comsol"]["version"] for i in find_backends()
            )
        except Exception as exc:
            report["comsol_detection_error"] = str(exc)
    if sys.platform == "win32":
        import winreg

        registrations = {}
        for key in ("Origin.Application", "Origin.ApplicationSI"):
            try:
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, key + "\\CLSID") as handle:
                    clsid = winreg.QueryValueEx(handle, "")[0]
                registrations[key] = {"clsid": clsid, "registered": True}
                # OriginExt may resolve installation without a conventional
                # LocalServer32 entry. A missing entry is not a connection failure.
                for access in (
                    winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
                    winreg.KEY_READ | winreg.KEY_WOW64_32KEY,
                ):
                    try:
                        with winreg.OpenKey(
                            winreg.HKEY_CLASSES_ROOT,
                            "CLSID\\" + clsid + "\\LocalServer32",
                            0,
                            access,
                        ) as handle:
                            registrations[key]["executable"] = winreg.QueryValueEx(handle, "")[0]
                        break
                    except OSError:
                        continue
                registrations[key].setdefault(
                    "executable", "Not exposed as LocalServer32; live connection not attempted"
                )
            except OSError as exc:
                registrations[key] = f"NOT REGISTERED: {exc}"
        report["origin_com_registration"] = registrations
    report["runtime_connections"] = "NOT TESTED by --check (no applications started)"
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report
