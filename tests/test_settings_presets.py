import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox
from src.settings_presets import PresetStore
from src.settings_ui import OriginSettingsDialog


@pytest.fixture
def dialog(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    config = tmp_path / 'config.toml'
    config.write_bytes(Path('config.default.toml').read_bytes())
    warnings = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: warnings.append(args[-1]))
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    window = OriginSettingsDialog(config)
    yield window, config, warnings
    window.close()
    app.processEvents()


def test_remember_reopen_load_delete_keeps_active_config(dialog):
    window, config, warnings = dialog
    original = config.read_bytes()
    window.fields[('plot', 'title')][0].setText('论文曲线')
    window.fields[('plot.axis.x', 'min')][0].setText('0.25')
    window.fields[('export', 'dpi')][0].setValue(300)
    window.fields[('processing', 'enable_smoothing')][0].setChecked(True)
    window.add_curve('extra', '新增曲线', '#00FF00', 'dot')
    expected = window.collect()
    window.preset_combo.setEditText('常用参数 / 中文')
    window.remember_preset()
    assert warnings == []
    assert config.read_bytes() == original

    reopened = OriginSettingsDialog(config)
    try:
        assert reopened.preset_store.names() == ['常用参数 / 中文']
        reopened.preset_combo.setCurrentIndex(0)
        # A preset can recover even from an invalid unfinished field.
        reopened.fields[('plot.axis.x', 'min')][0].setText('unfinished')
        reopened.load_preset()
        assert reopened.collect() == expected
        assert config.read_bytes() == original
        reopened.delete_preset()
        assert reopened.preset_store.names() == []
        assert reopened.collect() == expected
        assert config.read_bytes() == original
    finally:
        reopened.close()
    assert warnings == []


def test_overwrite_and_delete_can_be_cancelled(dialog, monkeypatch):
    window, config, warnings = dialog
    window.preset_combo.setEditText('预设 A')
    window.remember_preset()
    stored = window.preset_store.load('预设 A')
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.No)
    window.fields[('plot', 'title')][0].setText('改动')
    window.remember_preset()
    window.delete_preset()
    assert window.preset_store.load('预设 A') == stored
    assert warnings == []


def test_invalid_settings_do_not_overwrite_memory(dialog):
    window, config, warnings = dialog
    window.preset_combo.setEditText('有效预设')
    window.remember_preset()
    before = window.preset_store.path.read_bytes()
    window.fields[('processing', 'window_length')][0].setValue(10)
    window.remember_preset()
    assert warnings
    assert window.preset_store.path.read_bytes() == before


def test_multiple_presets_and_corrupt_file_are_preserved(tmp_path):
    store = PresetStore(tmp_path / 'config.toml')
    store.save('A', {('plot', 'title'): 'A'})
    store.save('B', {('plot', 'title'): 'B'})
    store.delete('A')
    assert store.names() == ['B']
    store.path.write_text('{broken', encoding='utf8')
    with pytest.raises(ValueError, match='原文件已保留'):
        store.save('C', {('plot', 'title'): 'C'})
    assert store.path.read_text(encoding='utf8') == '{broken'


def test_incompatible_preset_does_not_change_fields(dialog):
    window, config, warnings = dialog
    before = window.collect()
    window.preset_store.save('旧版', {('plot', 'title'): 'wrong'})
    window.preset_combo.setEditText('旧版')
    window.load_preset()
    assert warnings
    assert window.collect() == before
