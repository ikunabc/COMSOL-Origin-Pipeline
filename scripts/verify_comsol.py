"""Stages 5/6: installed solved busbar example, read only, COMSOL 6.3."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.adapters.comsol_adapter import COMSOLAdapter
from src.config import load_config
from src.logger import setup_logging
from src.pipeline import run

root = Path(__file__).resolve().parents[1]
setup_logging(root)
c = load_config(root / "config.toml", check_input=False)
c["comsol"]["model"] = Path(
    "D:/Program Files/COMSOL/COMSOL63/Multiphysics/applications/"
    "COMSOL_Multiphysics/Multiphysics/busbar.mph"
)
c["origin"].update(
    visible=False, close_on_finish=True, project_file=root / "output/origin/comsol63_busbar.opju"
)
c["export"].update(filename="comsol63_busbar", format="tiff")
c["paths"]["processed_file"] = root / "data/processed/comsol63_busbar.csv"
c["processing"].update(enable_smoothing=False, enable_interpolation=False)
c["plot"]["font"].update(axis_title_size=10, tick_label_size=8, legend_size=7, title_size=10)
a = COMSOLAdapter(c)
report = {}
try:
    items = a.list_available_results()
    report["results"] = [
        {k: v for k, v in i.items() if k in ("tag", "label", "kind")} for i in items
    ]
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    valid = [i for i in items if i["kind"] in ("table", "1d", "2d", "3d")]
    assert valid, "No results found"
    extracted = []
    chosen = None
    for item in valid:
        c["comsol"].update(result_type=item["kind"], result_name=item["tag"])
        ds = a.extract_dataset()
        extracted.append(
            {
                "tag": item["tag"],
                "kind": item["kind"],
                "shape": list(ds.data.shape),
                "columns": list(ds.data),
                "units": ds.units,
            }
        )
        if chosen is None and ds.data.select_dtypes("number").shape[1] >= 2:
            chosen = (item, ds)
    report["extraction"] = "PASS"
    report["datasets"] = extracted
    assert chosen, "No plottable numerical columns"
    item, ds = chosen
    c["comsol"].update(result_type=item["kind"], result_name=item["tag"])
    numeric = list(ds.data.select_dtypes("number"))
    c["plot"].update(x_column=numeric[0], y_columns=[numeric[-1]], title=item["label"])
    c["plot"]["axis"]["x"].update(title=numeric[0], unit=ds.units.get(numeric[0], ""))
    c["plot"]["axis"]["y"].update(title=numeric[-1], unit=ds.units.get(numeric[-1], ""))
    c["plot"]["legend"]["labels"] = [numeric[-1]]
    c["processing"].update(
        enable_interpolation=True, interpolation_method="linear", interpolation_points=101
    )
finally:
    a.close()
    (root / "docs/comsol_verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
dataset, figure, project = run(c)
report.update(pipeline="PASS", figure=str(figure), project=str(project), rows=len(dataset.data))
(root / "docs/comsol_verification.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
)
print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
