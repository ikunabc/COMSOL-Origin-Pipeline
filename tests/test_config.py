import pytest
from src.config import load_config, validate
from src.exceptions import ConfigError


@pytest.mark.parametrize(
    "section,key,value",
    [
        ("processing", "window_length", 10),
        ("processing", "polyorder", 11),
        ("processing", "window_length", True),
        ("processing", "interpolation_points", 1),
        ("export", "dpi", 0),
        ("export", "dpi", float("nan")),
        ("export", "filename", "../bad"),
        ("origin", "project_file", "a.txt"),
        ("plot", "y_columns", []),
        ("plot", "y_columns", ["x"]),
        ("plot", "graph_type", "fake"),
    ],
)
def test_bad_values(config, section, key, value):
    # validate takes raw paths from TOML, not resolved Path objects.
    for group, keys in {
        "paths": ["output_dir", "processed_file"],
        "comsol": ["model", "csv"],
        "origin": ["project_file"],
    }.items():
        for k in keys:
            config[group][k] = str(config[group][k])
    config[section][key] = value
    with pytest.raises(ConfigError, match=key if section != "plot" else "plot"):
        validate(config)


def test_relative_paths(config):
    assert config["comsol"]["csv"].is_absolute()
    assert config["comsol"]["csv"].is_file()


def test_missing_input_rejected(tmp_path):
    from pathlib import Path

    target = tmp_path / "missing.toml"
    text = (
        Path("config.example-csv.toml")
        .read_text(encoding="utf-8")
        .replace('mode = "csv"', 'mode = "mph"')
    )
    target.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError, match="input file does not exist"):
        load_config(target)


def test_static_error_before_input(tmp_path):
    text = __import__("pathlib").Path("config.example-csv.toml").read_text(encoding="utf-8")
    target = tmp_path / "bad.toml"
    target.write_text(text.replace("window_length = 11", "window_length = 10"), encoding="utf-8")
    with pytest.raises(ConfigError, match="odd integer"):
        load_config(target)


def test_first_run_creates_local_config(tmp_path):
    from pathlib import Path

    template = tmp_path / "config.default.toml"
    template.write_bytes(Path("config.example-csv.toml").read_bytes())
    target = tmp_path / "config.toml"
    load_config(target, check_input=False, create_outputs=False)
    assert target.read_bytes() == template.read_bytes()
