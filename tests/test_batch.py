from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from src import pipeline
from src.config import load_config


def test_batch_creates_separate_graphs_and_saves_once(tmp_path, monkeypatch):
    csv = tmp_path / "input.csv"
    csv.write_text("Time,u,v\n0,1,4\n1,2,5\n", encoding="utf-8")
    c = load_config("config.default.toml", check_input=False, create_outputs=False)
    c["comsol"].update(mode="csv", csv=csv, csv_format="standard")
    c["plot"].update(x_column="Time", y_columns=["u"], title="Velocity")
    c["paths"]["processed_file"] = tmp_path / "processed.csv"
    c["export"].update(filename="figure", directory=tmp_path)
    d = deepcopy(c)
    d["plot"].update(y_columns=["v"], title="Second", graph_type="scatter")
    events = []

    class Origin:
        def __init__(self, config):
            self.config = config
            self.success = False

        def connect(self):
            events.append("connect")

        def write_dataframe(self, dataset):
            return dataset.data

        def create_graph(self, book, dataset):
            (y,) = self.config["plot"]["y_columns"]
            events.append((self.config["plot"]["graph_type"], book[y].tolist()))
            return SimpleNamespace()

        def export_graph(self, graph):
            events.append(graph.lname)
            return Path(self.config["export"]["filename"])

        def save_project(self):
            events.append("save")
            return tmp_path / "both.opju"

        def close(self):
            events.append(("close", self.success))

    monkeypatch.setattr(pipeline, "OriginAdapter", Origin)
    figures, project = pipeline.run_batch([c, d])
    assert figures == [Path("figure-01"), Path("figure-02")]
    assert project == tmp_path / "both.opju"
    assert events == [
        "connect",
        ("line", [1, 2]),
        "Velocity",
        ("scatter", [4, 5]),
        "Second",
        "save",
        ("close", True),
    ]
    assert sorted(p.name for p in tmp_path.glob("processed*")) == [
        "processed-01.csv",
        "processed-01.metadata.json",
        "processed-02.csv",
        "processed-02.metadata.json",
    ]
    assert c["export"]["filename"] == d["export"]["filename"] == "figure"
