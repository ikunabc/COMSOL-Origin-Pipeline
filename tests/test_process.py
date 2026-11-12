import numpy as np
import pandas as pd
import pytest
from src.adapters.process_adapter import process
from src.exceptions import DataProcessingError
from src.models import Dataset


def sample(x=None):
    x = np.linspace(0, 20, 21) if x is None else np.asarray(x)
    return Dataset(
        pd.DataFrame({"x": x, "velocity": 2 * x + 1}),
        "demo",
        "synthetic",
        ["x", "velocity"],
        {"x": "um", "velocity": "m/s"},
        {"comments": ["kept"]},
    )


@pytest.mark.parametrize("method", ["none", "savgol", "moving_average", "median"])
def test_smoothing(config, method):
    config["processing"]["smoothing_method"] = method
    source = sample()
    result = process(source, config)
    assert result.data.shape == (21, 2)
    assert np.isfinite(result.data.to_numpy()).all()
    assert result.units == source.units
    assert source.metadata == {"comments": ["kept"]}
    if method == "savgol":
        np.testing.assert_allclose(result.data["velocity"], source.data["velocity"], atol=1e-10)


@pytest.mark.parametrize("method", ["linear", "cubic", "pchip"])
def test_interpolation(config, method):
    config["processing"].update(
        enable_interpolation=True, interpolation_method=method, interpolation_points=101
    )
    result = process(sample(), config)
    assert len(result.data) == 101
    np.testing.assert_allclose(result.data.velocity, 2 * result.data.x + 1, atol=1e-10)


def test_nonfinite(config):
    d = sample()
    d.data.loc[5, "velocity"] = np.inf
    config["processing"]["enable_smoothing"] = False
    assert len(process(d, config).data) == 20
    config["processing"]["drop_nan"] = False
    with pytest.raises(DataProcessingError, match="NaN/Inf"):
        process(d, config)


def test_duplicate_x_rejected(config):
    with pytest.raises(DataProcessingError, match="unique"):
        process(sample([0] * 21), config)


def test_irregular_savgol_rejected(config):
    with pytest.raises(DataProcessingError, match="uniformly spaced"):
        process(sample(np.arange(21) ** 2), config)


def test_log_rejects_nonpositive(config):
    config["plot"]["axis"]["x"]["scale"] = "log10"
    with pytest.raises(DataProcessingError, match="positive"):
        process(sample(), config)
