"""Stage 3/4: synthetic DataFrame → real Origin. No COMSOL involved."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from src.adapters.origin_adapter import OriginAdapter
from src.config import load_config
from src.logger import setup_logging
from src.models import Dataset

root = Path(__file__).resolve().parents[1]
setup_logging(root)
c = load_config(root / "config.toml", check_input=False)
c["origin"].update(
    visible=False, close_on_finish=True, project_file=root / "output/origin/synthetic_verified.opju"
)
c["plot"].update(title="Synthetic validation", y_columns=["velocity", "velocity_2"])
c["plot"]["legend"]["labels"] = ["Synthetic linear", "Synthetic quadratic"]
c["plot"]["axis"]["x"].update(min=0, max=20, major_step=5)
c["plot"]["axis"]["y"].update(min=0, max=25, major_step=5)
c["plot"]["style"].update(colors=["#1F77B4", "#D62728"], line_styles=["solid", "dash"])
c["plot"]["font"].update(axis_title_size=10, tick_label_size=8, legend_size=7, title_size=10)
x = np.linspace(0, 20, 101)
ds = Dataset(
    pd.DataFrame({"x": x, "velocity": x, "velocity_2": x * x / 20}),
    "Synthetic verification",
    "synthetic, not scientific measurements",
    ["x", "velocity", "velocity_2"],
    {"x": "um", "velocity": "m/s", "velocity_2": "m/s"},
    {"comments": ["Synthetic data for software validation"]},
)
op = OriginAdapter(c)
report = {}
try:
    op.connect()
    wb = op.write_dataframe(ds)
    assert wb[0].to_df().shape == ds.data.shape
    report["workbook"] = "PASS"
    graph = op.create_graph(wb, ds)
    report["graph"] = "PASS"
    report["origin_version"] = op.op.lt_float("@V")
    report["axis_x_limits"] = graph[0].axis("x").limits
    for fmt in ("tiff", "png", "pdf"):
        c["export"].update(format=fmt, filename="synthetic_verified", transparent=False)
        file = op.export_graph(graph)
        report[fmt] = {"path": str(file), "bytes": file.stat().st_size}
    c["export"].update(format="png", filename="synthetic_transparent", transparent=True)
    file = op.export_graph(graph)
    report["transparent_png"] = {"path": str(file), "bytes": file.stat().st_size}
    c["export"].update(format="tiff", filename="synthetic_transparent", transparent=True)
    file = op.export_graph(graph)
    report["transparent_tiff"] = {"path": str(file), "bytes": file.stat().st_size}
    for graph_type in ("line_symbol", "scatter", "column"):
        c["plot"]["graph_type"] = graph_type
        extra = op.create_graph(wb, ds)
        assert len(extra[0].plot_list()) == 2
        report[graph_type] = "PASS: two plots created"
    op.save_project()
    report["project"] = "PASS"
    op.success = True
finally:
    op.close()
    (root / "docs/origin_verification.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
print(json.dumps(report, indent=2))
