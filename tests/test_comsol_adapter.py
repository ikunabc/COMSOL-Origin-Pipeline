import pandas as pd
import pytest
from src.adapters import comsol_adapter as module
from src.exceptions import COMSOLModelError, COMSOLResultNotFoundError


@pytest.mark.parametrize("kind", ["table", "1d", "2d", "3d"])
def test_dispatch_uses_a_real_signature(config, monkeypatch, kind):
    adapter = module.COMSOLAdapter(config)
    config["comsol"].update(result_name="chosen", result_type=kind)
    item = {"tag": "chosen", "label": "Chosen", "kind": kind, "pg": object()}
    monkeypatch.setattr(adapter, "list_available_results", lambda: [item])
    api = module.backend()

    def table(model, tag, low_memory=False):
        assert tag == "chosen"
        return pd.DataFrame({"x (m)": [0.0, 1.0], "velocity (m/s)": [1.0, 2.0]}), ["retained"]

    def plot(model, pg, pg_tag, output_dir, kind="", low_memory=False):
        assert pg is item["pg"] and pg_tag == "chosen" and output_dir.is_dir()
        return table(model, pg_tag, low_memory)

    monkeypatch.setattr(api, "extract_table", table)
    monkeypatch.setattr(api, "extract_via_export", plot)
    ds = adapter.extract_dataset()
    assert ds.units["x"] == "m"
    assert ds.metadata["comments"] == ["retained"]
    assert ds.metadata["kind"] == kind


def test_ambiguous_label(config, monkeypatch):
    a = module.COMSOLAdapter(config)
    config["comsol"].update(result_type="table", result_name="same")
    monkeypatch.setattr(
        a,
        "list_available_results",
        lambda: [
            {"tag": "t1", "label": "same", "kind": "table"},
            {"tag": "t2", "label": "same", "kind": "table"},
        ],
    )
    with pytest.raises(COMSOLResultNotFoundError, match="匹配到 2 项"):
        a.extract_dataset()


def test_backend_none_is_failure(config, monkeypatch):
    a = module.COMSOLAdapter(config)
    config["comsol"].update(result_type="table", result_name="t1")
    monkeypatch.setattr(
        a, "list_available_results", lambda: [{"tag": "t1", "label": "T", "kind": "table"}]
    )
    monkeypatch.setattr(module.backend(), "extract_table", lambda *args, **kwargs: None)
    with pytest.raises(COMSOLModelError, match="could not extract"):
        a.extract_dataset()
