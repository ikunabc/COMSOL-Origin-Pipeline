"""Render Qt UI and check persistence/injection without COMSOL or Origin."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
import tempfile
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QPushButton
from src.config import load_config
from src.settings_ui import OriginSettingsDialog, SettingsButtonInstaller, save_updates

root = Path(__file__).resolve().parents[1]
app = QApplication.instance() or QApplication([])
folder = root / "output/settings_preview"
folder.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(dir=root) as temporary:
    path = Path(temporary) / "config.toml"
    path.write_bytes((root / "config.default.toml").read_bytes())
    dialog = OriginSettingsDialog(path)
    dialog.show()
    app.processEvents()
    assert dialog.tabs.count() == 5
    assert dialog.curves.rowCount() == 2
    original = tomllib.loads(path.read_text(encoding="utf-8"))
    updates = dialog.collect()
    for (group, key), value in updates.items():
        section = original
        for part in group.split("."):
            section = section[part]
        assert value == section[key], (group, key, value, section[key])
    # Round trip preserves unedited sections and values.
    save_updates(path, updates)
    assert tomllib.loads(path.read_text(encoding="utf-8")) == original
    before = path.read_bytes()
    try:
        save_updates(path, {("processing", "window_length"): 10})
        raise AssertionError("Invalid smoothing window was accepted")
    except Exception as exc:
        assert "odd integer" in str(exc)
    assert path.read_bytes() == before
    dialog.fields[("plot", "title")][0].setText("可视化保存测试")
    dialog.fields[("plot.axis.x", "min")][0].setText("0")
    dialog.add_curve("u2_extra", "Extra", "#D62728", "dot")
    dialog.fields[("export", "format")][0].setCurrentIndex(1)
    save_updates(path, dialog.collect())
    loaded = load_config(path, check_input=False, create_outputs=False)
    assert loaded["plot"]["title"] == "可视化保存测试"
    assert loaded["plot"]["axis"]["x"]["min"] == 0
    assert loaded["plot"]["y_columns"] == ["u2", "v2", "u2_extra"]
    assert loaded["plot"]["style"]["colors"][-1] == "#D62728"
    assert loaded["export"]["format"] == "png"
    assert path.with_suffix(".toml.ui-backup").exists()
    from unittest.mock import patch

    from src.adapters.gui_adapter import make_push_wrapper

    original_config = load_config(
        root / "config.default.toml", check_input=False, create_outputs=False
    )
    callback = make_push_wrapper(
        lambda *args, **kwargs: Path(temporary) / "imported.opju", original_config, config_path=path
    )
    with patch("src.adapters.gui_adapter.plot_imported_project") as plotted:
        callback([{"name": "tbl5", "df": None, "comments": []}], temporary)
        assert plotted.call_args.args[2]["plot"]["title"] == "可视化保存测试"
        assert plotted.call_args.args[2]["plot"]["y_columns"] == ["u2", "v2", "u2_extra"]
    # Render the actual user configuration, not the test modifications.
    dialog.close()
    preview = OriginSettingsDialog(root / "config.default.toml")
    preview.show()
    for index in range(preview.tabs.count()):
        preview.tabs.setCurrentIndex(index)
        app.processEvents()
        assert preview.grab().save(str(folder / f"tab_{index + 1}.png"))
    preview.close()

# Exercise the real upstream window with no model: close it via Qt after
# verifying the injected button. No COMSOL engine or Origin connection.
sys.path.insert(0, str(root / "lib/comsol_csv_tool"))
import gui  # noqa: E402 - the upstream path must be added first

installer = SettingsButtonInstaller(root / "config.toml", app)
app.installEventFilter(installer)
found = []


def inspect_original():
    for window in app.topLevelWidgets():
        if window.windowTitle() == "COMSOL Extractor":
            button = window.findChild(QPushButton, "originPlotSettingsButton")
            found.append(button is not None)
            window.grab().save(str(folder / "original_window.png"))
            window.close()


QTimer.singleShot(500, inspect_original)
QTimer.singleShot(5000, app.quit)
gui.run_extraction_window(None, None, True)
assert found == [True], found
print(
    "PASS: five tabs rendered; editable values round-trip; invalid values do not alter "
    "config; curve add/color/format persist; original GUI button installed; import hook "
    "reads newly saved settings."
)
