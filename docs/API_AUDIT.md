# API audit

This is a developer record for the pinned COMSOL extraction backend and the
Origin interfaces used by this project. It is not an end-user setup guide.

Backend: https://github.com/GhVost/COMSOL-to-CSV-and-Origin-parser

Pinned commit: `4c63ac17fbb6272603a893e0233c6d27aa485180`.
The upstream audit inspected its README.md, pyproject.toml, requirements.txt,
requirements-origin.txt, COMSOLExtractor.py, extraction.py, origin_push.py and
three test files. The upstream root has no `__init__.py`; its pyproject.toml
only configures pytest/ruff. There is no packaged, versioned public API.
The adapter loads extraction.py
under a private module name using importlib, without importing the GUI entry point.

| Question | Source-confirmed behavior |
|---|---|
| Start COMSOL | gui.py uses `mph.start()`; adapter uses verified `mph.start(version='6.3')` |
| Load model | MPh Client.load(str(path)); adapter never calls solve or saves the source model |
| Tables | extraction.extract_table(model, tag, low_memory=False); getStringMatrix('headers'), getTableData(True) |
| 1D/2D/3D | extraction.extract_via_export(model, pg, pg_tag, output_dir, kind='', low_memory=False) |
| Plot discovery | extraction.discover_items(model) returns list of tag/label/kind/pg records |
| Plot dimension | get_plot_type: getType(), fallback getInt('plotdim') |
| Variable names | table header descriptions; native plot export final `%` header, fallback table graph headers |
| Units | split_label_unit; get_feature_units; get_geometry_length_unit; repair_mojibake |
| DataFrame | extract_table/extract_via_export return `(DataFrame, list[str])` or None on failure |
| Metadata | comments list, DataFrame.attrs['legend_labels']; main workflow writes manifest.json |
| CSV A format | write_csv_with_comments and load_dataset_csv use separate names and units rows |
| A Origin integration | origin_push.push_to_origin(datasets, output_dir, template='', project_name='comsol_results') |
| Direct imports | extraction functions above can be loaded without PySide6; COMSOLExtractor imports gui so avoided |

The wrapper treats a None extraction as failure, captures A's console diagnostics
in the file log, preserves comments, units, original headers and DataFrame attrs.
It rejects ambiguous labels and stitched sweeps rather than processing different
parameter sets as one curve. A's 2D/3D extraction may temporarily toggle a
deformation node and restore it; source MPH files are never saved.

## Origin official interfaces inspected

Installed package originpro 1.1.15: config.py, base.py, graph.py, worksheet.py,
utils.py. Actual methods used:

* op.attach, detach, set_show, lt_float, set_lt_var, set_lt_str, save, exit
* op.new_book('w'), new_graph(template=...)
* Workbook[0], WSheet.from_df(addindex=False), cols_axis(repeat=False), set_label
* GPage.activate, lt_exec; GLayer.add_plot, axis, rescale, label, add_label
* Plot.color (RGB tuple), set_cmd('-wp ...', '-d ...'), symbol_kind, symbol_size
* Axis.scale, set_limits, title
* Label.text, set_int, set_float, get_float, remove

IMPORTANT: wrapper objects use `lt_exec`. `LT_execute` is on the underlying
Origin object (`obj`), not on originpro GPage/GLayer. Some calls in A's
origin_push.py use the latter directly inside swallowed exceptions; we do not
reuse that integration or copy its implementation.

Graph type mapping is read from GLayer._plot_type: l=200, s=201, y=202, c=203.
Dash mapping is confirmed by Plot.set_cmd examples and official set-command
documentation. Circle symbol is Origin shape 2. Colors use RGB tuples rather
than manually packing Origin integer colors.

Line width is set with `-wp` (points). `-w` uses points×500. Graph page
aspect locking is disabled with page.kar=0. Legend left/top are physical
printer coordinates, not layer percentages. Explicit plot.layout configuration
is translated to those coordinates. @GET is restored after every export.
Transparent PNG/TIFF use expG2img tb:=1 res:=600, verified from the installed
2025b XFC source and actual RGBA exports. PDF does not receive a raster DPI.

Local Origin 2025b source also inspected:
`XFC/expGraph.XFC`, `XFC/expG2img.XFC`,
`OriginC/Originlab/GraphicalExport.c`.

## Official references

* https://docs.originlab.com/python/examples/graphing/
* https://docs.originlab.com/x-function/ref/expgraph/
* https://docs.originlab.com/x-function/ref/expg2img/
* https://docs.originlab.com/origin-help/settings-in-expgraph-dailog/
* https://docs.originlab.com/labtalk/ref/layer-axis-label-obj/
* https://docs.originlab.com/labtalk/ref/graphic-objs/ja/
* https://docs.originlab.com/quick-help/specify-graph-size/
* https://docs.originlab.com/quick-help/set-special-text-bylt/
* https://www.originlab.com/releasenotes/detail.aspx?id=2024b2ORG-26879

The source and runtime checks take precedence over web documentation when the
installed Origin 2025b differs from current web pages. No mouse/keyboard automation.
