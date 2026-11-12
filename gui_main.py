"""Original GitHub GUI plus an Origin plotting post-import adapter."""

import sys
from contextlib import redirect_stderr, redirect_stdout

from src.runtime import RESOURCE_ROOT, STATE_ROOT, prepare_state

ROOT = STATE_ROOT


def main():
    from src.config import load_config
    from src.logger import setup_logging

    log = setup_logging(ROOT)
    try:
        prepare_state()
        if any(
            flag in sys.argv for flag in ("--bundle-check", "--verify-origin", "--verify-comsol")
        ):
            import os

            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance() or QApplication(sys.argv[:1])
        c = load_config(ROOT / "config.toml", check_input=False)
        if (
            "--bundle-check" in sys.argv
            or "--verify-origin" in sys.argv
            or "--verify-comsol" in sys.argv
        ):
            from src.bundle_checks import run_checks

            return run_checks(c, sys.argv)
        if "--settings" in sys.argv:
            from src.settings_ui import run_settings

            run_settings(ROOT / "config.toml")
            return 0
        if "--smoke-test" not in sys.argv and "--legacy" not in sys.argv:
            from src.integrated_ui import IntegratedDialog

            IntegratedDialog(ROOT / "config.toml").exec()
            return 0
        from src.settings_ui import SettingsButtonInstaller

        settings_filter = SettingsButtonInstaller(ROOT / "config.toml", app)
        app.installEventFilter(settings_filter)
        backend = RESOURCE_ROOT / "lib/comsol_csv_tool"
        sys.path.insert(0, str(backend))
        import COMSOLExtractor
        from src.adapters.gui_adapter import make_push_wrapper

        COMSOLExtractor.push_to_origin = make_push_wrapper(
            COMSOLExtractor.push_to_origin,
            c,
            on_error=lambda text: QMessageBox.warning(None, "COMSOL → Origin 自动绘图", text),
            config_path=ROOT / "config.toml",
        )
        if "--smoke-test" in sys.argv:
            print("PASS: original GitHub GUI imported, plotting hook installed, Qt initialized")
            return 0
        sys.argv = [str(backend / "COMSOLExtractor.py"), "--comsol", "--origin"]
        # Keep the original Open / result checklist / Extract interface.
        COMSOLExtractor.main()
        return 0
    except Exception as exc:
        log.exception("图形界面启动失败")
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            app = QApplication.instance() or QApplication([])
            QMessageBox.critical(None, "启动失败", f"{exc}\n\n详情：{ROOT / 'logs/pipeline.log'}")
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    if "--smoke-test" in sys.argv:
        raise SystemExit(main())
    (ROOT / "logs").mkdir(parents=True, exist_ok=True)
    with (ROOT / "logs/gui.log").open("a", encoding="utf-8", buffering=1) as stream:
        with redirect_stdout(stream), redirect_stderr(stream):
            raise SystemExit(main())
