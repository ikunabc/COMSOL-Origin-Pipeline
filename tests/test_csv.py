import pytest
from src.adapters.comsol_adapter import read_csv
from src.exceptions import CSVFormatError


@pytest.mark.parametrize(
    "fmt,text",
    [
        ("standard", "% Model: test\nx (um),velocity (m/s)\n0,1\n1,2\n\n"),
        ("backend", "% Model: test\nx,velocity\num,m/s\n0,1\n1,2\n"),
        ("native", "% Model: test\n% x (um)  velocity (m/s)\n0 1\n1 2\n"),
        ("native", "% Model: test\n% x (um),velocity (m/s)\n0,1\n1,2\n"),
    ],
)
def test_csv_types(config, tmp_path, fmt, text):
    file = tmp_path / "test.csv"
    file.write_text(text, encoding="utf-8")
    config["comsol"].update(csv=file, csv_format=fmt)
    ds = read_csv(config)
    assert list(ds.data) == ["x", "velocity"]
    assert ds.units == {"x": "um", "velocity": "m/s"}
    assert ds.data.velocity.tolist() == [1, 2]
    assert "Model: test" in ds.metadata["comments"]


def test_duplicate_headers_fail(config, tmp_path):
    file = tmp_path / "test.csv"
    file.write_text("x (um),x (m)\n0,1\n1,2\n", encoding="utf-8")
    config["comsol"].update(csv=file, csv_format="standard")
    with pytest.raises(CSVFormatError, match="Duplicate"):
        read_csv(config)


def test_nan_inf_remain_numeric(config, tmp_path):
    file = tmp_path / "test.csv"
    file.write_text("x,velocity\n0,NaN\n1,Inf\n2,3\n", encoding="utf-8")
    config["comsol"].update(csv=file, csv_format="standard")
    ds = read_csv(config)
    assert ds.metadata["nan_count"] == 1
    assert ds.metadata["inf_count"] == 1
    assert ds.data.velocity.dtype.kind == "f"
