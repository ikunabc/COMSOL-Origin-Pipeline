from pathlib import Path

from main import main


def test_check_runs_without_model(tmp_path, monkeypatch):
    config_path = tmp_path / 'config.toml'
    config_path.write_bytes(Path('config.default.toml').read_bytes())
    from src import diagnostics
    seen = []
    monkeypatch.setattr(diagnostics, 'check', lambda config: seen.append(config))

    assert main(['--config', str(config_path), '--check']) == 0
    assert len(seen) == 1
    assert not seen[0]['comsol']['model'].exists()
    assert not (tmp_path / 'output').exists()


def test_normal_run_still_requires_model(tmp_path, monkeypatch):
    config_path = tmp_path / 'config.toml'
    config_path.write_bytes(Path('config.default.toml').read_bytes())
    from src import pipeline
    seen = []
    monkeypatch.setattr(pipeline, 'run', lambda config: seen.append(config))

    assert main(['--config', str(config_path)]) == 1
    assert seen == []
