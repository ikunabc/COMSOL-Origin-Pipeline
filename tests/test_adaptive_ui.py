import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pandas as pd
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.adapters import comsol_adapter
from src.integrated_ui import IntegratedDialog


def test_adaptive_result_and_column_choices(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    model = tmp_path / 'example.mph'
    model.touch()
    config = tmp_path / 'config.toml'
    config.write_bytes(Path('config.default.toml').read_bytes())

    class Adapter:
        def __init__(self, config):
            self.config = config

        def list_available_results(self):
            return [{'tag': 'tbl1', 'label': 'First', 'kind': 'table'},
                    {'tag': 'tbl2', 'label': 'Second', 'kind': 'table'}]

        def extract_dataset(self):
            assert self.config['comsol']['result_name'] == 'tbl2'
            return SimpleNamespace(data=pd.DataFrame({
                'position': [0, 1], 'voltage': [2, 3], 'note': ['a', 'b'],
            }))

        def close(self):
            pass

    monkeypatch.setattr(comsol_adapter, 'COMSOLAdapter', Adapter)
    dialog = IntegratedDialog(config)
    try:
        dialog.fields[('comsol', 'model')][0].setText(str(model))
        dialog.start_task('list')
        assert dialog.worker.wait(5000)
        app.processEvents()
        assert dialog.results.count() == 3
        assert dialog.results.currentData() is None
        dialog.results.setCurrentIndex(2)
        dialog.select_result(2)
        assert dialog.worker.wait(5000)
        app.processEvents()
        assert dialog.columns == ['position', 'voltage']
        dialog.x_choice.setCurrentIndex(dialog.x_choice.findData('position'))
        y_choice = dialog.curves.cellWidget(0, 0)
        y_choice.setCurrentIndex(y_choice.findData('voltage'))
        settings = dialog.collect()
        assert settings[('comsol', 'result_name')] == 'tbl2'
        assert settings[('plot', 'x_column')] == 'position'
        assert settings[('plot', 'y_columns')] == ['voltage']
    finally:
        dialog.close()
