"""Append plotting to A's existing GUI/import workflow without changing A."""

import json
import logging
from copy import deepcopy
from pathlib import Path

from ..exceptions import PipelineError
from .comsol_adapter import normalize
from .origin_adapter import OriginAdapter
from .process_adapter import process, validate_columns

log = logging.getLogger("pipeline")


def select_entry(datasets, output_dir, config):
    result = config["comsol"]["result_name"]
    candidates = {result}
    manifest = Path(output_dir) / "manifest.json"
    if manifest.is_file():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        for section in ("tables", "1d_plots", "2d_plots", "3d_plots", "other"):
            for entry in data.get(section, []):
                if result in (entry.get("tag"), entry.get("label")) and entry.get("file"):
                    candidates.add(Path(entry["file"]).stem)
    selected = [entry for entry in datasets if entry["name"] in candidates]
    if len(selected) != 1:
        raise PipelineError(
            f"自动绘图配置选择了 {result!r}，但本次导出的结果中没有唯一匹配项。"
            "请在原界面勾选该结果，或修改 config.toml 的 result_name。"
        )
    return selected[0]


def plot_imported_project(project, entry, config):
    """Reuse the workbook A has already imported; do not reload COMSOL."""
    c = deepcopy(config)
    c["origin"].update(
        project_file=Path(project),
        save_project=True,
        new_instance=True,
        close_on_finish=True,
        visible=False,
    )
    ds = normalize(
        entry["df"],
        entry["name"],
        str(project),
        entry.get("comments", []),
        c["comsol"].get("column_map"),
    )
    validate_columns(ds, c)
    adapter = OriginAdapter(c)
    try:
        adapter.connect()
        if not adapter.op.open(str(project), readonly=False, asksave=False):
            raise PipelineError(f"Cannot reopen imported project: {project}")
        book = None
        for index in range(10000):
            candidate = adapter.op.find_book("w", index)
            if candidate is None:
                break
            if candidate.lname == entry["name"]:
                if book is not None:
                    raise PipelineError(f"Ambiguous imported Workbook: {entry['name']}")
                book = candidate
        if book is None:
            raise PipelineError(f"Imported Workbook not found: {entry['name']}")
        raw = ds.data.copy()
        ds = process(ds, c)
        if not ds.data.equals(raw.reset_index(drop=True)):
            # Processing was explicitly configured: replace only this freshly
            # imported sheet, preserving all other imported workbooks.
            book[0].from_df(ds.data, addindex=False)
        path = c["paths"]["processed_file"]
        path.parent.mkdir(parents=True, exist_ok=True)
        ds.data.to_csv(path, index=False, encoding="utf-8-sig")
        indices = {col: i for i, col in enumerate(ds.data.columns)}
        graph = adapter.create_graph(book, ds, column_indices=indices)
        graph.lname = "AutoPlot - " + ds.name
        figure = adapter.export_graph(graph)
        adapter.save_project()
        adapter.success = True
        log.info("原项目导入完成 → 自动绘图完成: %s", figure)
        return figure
    finally:
        adapter.close()


def make_push_wrapper(original, config, on_error=None, config_path=None):
    def push(datasets, output_dir, template="", project_name="comsol_results"):
        active = config
        if config_path is not None:
            from ..config import load_config

            active = load_config(config_path, check_input=False)
        # A releases entry['df'] after importing. Retain only the configured
        # dataset reference until plotting finishes, not every extracted frame.
        selected = None
        error = None
        try:
            selected = dict(select_entry(datasets, output_dir, active))
        except Exception as exc:
            error = exc
        project = original(datasets, output_dir, template=template, project_name=project_name)
        if project is None:
            error = PipelineError("原项目未成功保存 Origin 工程，无法执行后续自动绘图。")
        elif error is None:
            try:
                plot_imported_project(project, selected, active)
            except Exception as exc:
                error = exc
                log.exception("Origin 自动绘图失败；原项目导入的工程仍保留。")
        if error is not None:
            log.error("自动绘图未完成: %s", error)
            if on_error:
                on_error(str(error))
            else:
                raise error
        return project

    return push
