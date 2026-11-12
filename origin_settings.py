from pathlib import Path

from src.settings_ui import run_settings

if __name__ == "__main__":
    try:
        run_settings(Path(__file__).with_name("config.toml"))
    except Exception as exc:
        from PySide6.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance() or QApplication([])
        QMessageBox.critical(None, "Origin 参数窗口未能打开", str(exc))
