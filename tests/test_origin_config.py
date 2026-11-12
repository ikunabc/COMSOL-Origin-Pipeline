from src.adapters.origin_adapter import export_command
from src.config import GRAPH_TYPE_MAP, LINE_STYLE_MAP, SYMBOL_MAP


def test_verified_mappings():
    assert GRAPH_TYPE_MAP["line_symbol"] == "y"
    assert LINE_STYLE_MAP["dash"] == 1
    assert SYMBOL_MAP["circle"] == 2


def test_tiff_dpi(config, tmp_path):
    cmd = export_command(config, tmp_path, "demo")
    assert "tr2.TIF.DotsPerInch:=600" in cmd
    assert "tr1.Width:=1600" in cmd


def test_pdf_has_no_raster_dpi(config, tmp_path):
    config["export"]["format"] = "pdf"
    cmd = export_command(config, tmp_path, "demo")
    assert "DotsPerInch" not in cmd
    assert "tr1.Unit:=0" in cmd


def test_transparent_uses_verified_simple_export(config, tmp_path):
    config["export"].update(format="png", transparent=True)
    assert "expG2img" in export_command(config, tmp_path, "demo")
    assert "tb:=1" in export_command(config, tmp_path, "demo")
