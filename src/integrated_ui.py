"""Combined input selection, plotting settings and execution window."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QWidget,
)

from .config import load_config, prepare_config
from .settings_ui import OriginSettingsDialog, save_updates, section

# MPh caches its client and requires every call to originate on one thread.
_ENGINE_WORKER = ThreadPoolExecutor(max_workers=1, thread_name_prefix="COMSOL-Origin")


class GraphPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.kind = "line"
        self.setMinimumSize(280, 140)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("white"))
        painter.setPen(QPen(QColor("#64748b"), 1))
        painter.drawLine(35, 15, 35, 110)
        painter.drawLine(35, 110, 260, 110)
        points = [(55, 90), (95, 65), (135, 80), (175, 40), (225, 25)]
        painter.setPen(QPen(QColor("#2563eb"), 3))
        for i, (x, y) in enumerate(points):
            if self.kind == "column":
                painter.fillRect(x - 10, y, 20, 110 - y, QColor("#2563eb"))
            else:
                if self.kind in ("line", "line_symbol") and i:
                    painter.drawLine(*points[i - 1], x, y)
                if self.kind in ("scatter", "line_symbol"):
                    painter.drawEllipse(x - 4, y - 4, 8, 8)
        painter.setPen(QColor("#475569"))
        painter.drawText(40, 132, "图形类型示意（非模型数据）")


class Task(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, config, action, parent=None):
        super().__init__(parent)
        self.config = config
        self.action = action

    def run(self):
        _ENGINE_WORKER.submit(self.execute).result()

    def execute(self):
        try:
            if self.action in ("list", "columns"):
                from .adapters.comsol_adapter import COMSOLAdapter

                adapter = COMSOLAdapter(self.config)
                try:
                    if self.action == "list":
                        result = adapter.list_available_results()
                    else:
                        data = adapter.extract_dataset().data
                        result = [
                            name
                            for name in data.select_dtypes(include="number")
                            if data[name].notna().any()
                        ]
                finally:
                    adapter.close()
            elif self.action == "batch":
                from .pipeline import run_batch

                figures, project = run_batch(self.config)
                result = {
                    "count": len(figures),
                    "figures": [str(path) for path in figures if path],
                    "project": str(project) if project else None,
                }
            else:
                from .pipeline import run

                _, figure, project = run(self.config)
                result = {"figure": str(figure), "project": str(project)}
            self.done.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class IntegratedDialog(OriginSettingsDialog):
    def __init__(self, path, parent=None):
        self.columns = []
        self.scanned_source = None
        self.scanned_result = None
        self.pending_plots = []
        super().__init__(path, parent)
        self.setWindowTitle("COMSOL → Origin · 读取与绘图")
        self.findChildren(QLabel)[0].setText("COMSOL 读取与 Origin 绘图")
        form = self.tab("COMSOL 读取")
        page = self.tabs.widget(self.tabs.count() - 1)
        self.tabs.removeTab(self.tabs.count() - 1)
        self.tabs.insertTab(0, page, "COMSOL 读取")
        self.field(
            form,
            "输入方式",
            "comsol",
            "mode",
            "combo",
            [("已求解 MPH 模型", "mph"), ("CSV 数据", "csv")],
        )
        for key, label, filter in [
            ("model", "MPH 模型", "COMSOL (*.mph)"),
            ("csv", "CSV 文件", "CSV (*.csv)"),
        ]:
            line = self.field(form, label, "comsol", key)
            button = QPushButton("选择文件…")
            button.clicked.connect(
                lambda checked=False, line=line, filter=filter: self.choose_file(line, filter)
            )
            form.addRow("", button)
        self.field(form, "COMSOL 版本", "comsol", "version")
        self.field(form, "低内存读取", "comsol", "low_memory", "bool")
        self.field(form, "CSV 编码", "comsol", "encoding")
        self.field(
            form,
            "CSV 格式",
            "comsol",
            "csv_format",
            "combo",
            [(s, s) for s in ("auto", "standard", "backend", "native")],
        )
        self.results = QComboBox()
        form.addRow("模型中的结果", self.results)
        self.read_button = QPushButton("识别模型结果或 CSV 数据列")
        self.read_button.clicked.connect(lambda: self.start_task("list"))
        form.addRow("", self.read_button)
        self.results.activated.connect(self.select_result)
        form.addRow(QLabel("选定模型结果后自动识别数据列。在“曲线与数据”中选择 X/Y。"))
        self.field(form, "显示 Origin 窗口", "origin", "visible", "bool")
        self.field(form, "保存 Origin 工程", "origin", "save_project", "bool")
        self.field(form, "工程保存路径（.opju）", "origin", "project_file")
        self.preview = GraphPreview()
        self.layout().insertWidget(3, self.preview)
        combo = self.fields[("plot", "graph_type")][0]
        combo.currentIndexChanged.connect(self.update_preview)
        self.update_preview()
        self.queue_panel = QWidget()
        queue_row = QHBoxLayout(self.queue_panel)
        queue_row.setContentsMargins(0, 0, 0, 0)
        queue_row.addWidget(QLabel("待出图"))
        self.plot_queue = QComboBox()
        self.plot_queue.setMinimumContentsLength(16)
        self.plot_queue.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        queue_row.addWidget(self.plot_queue, 1)
        self.add_plot_button = QPushButton("加入当前图")
        self.add_plot_button.clicked.connect(lambda: self.queue_plot())
        queue_row.addWidget(self.add_plot_button)
        self.replace_plot_button = QPushButton("用当前参数替换")
        self.replace_plot_button.clicked.connect(lambda: self.queue_plot(replace=True))
        queue_row.addWidget(self.replace_plot_button)
        self.remove_plot_button = QPushButton("移除选中图")
        self.remove_plot_button.clicked.connect(self.remove_queued_plot)
        queue_row.addWidget(self.remove_plot_button)
        self.layout().addWidget(self.queue_panel)
        self.run_button = QPushButton()
        self.run_button.clicked.connect(
            lambda: self.start_task("batch" if self.pending_plots else "run")
        )
        self.layout().addWidget(self.run_button)
        self.refresh_queue()
        self.worker = None
        self.tabs.setCurrentIndex(0)
        self.refresh_presets()

    def choose_file(self, line, filter):
        selected, _ = QFileDialog.getOpenFileName(
            self, "选择输入文件", str(self.path.parent), filter
        )
        if selected:
            line.setText(selected.replace("\\", "/"))
            active_key = (
                "model" if self.fields[("comsol", "mode")][0].currentData() == "mph" else "csv"
            )
            if line is self.fields[("comsol", active_key)][0]:
                self.start_task("list")

    def update_preview(self):
        self.preview.kind = self.fields[("plot", "graph_type")][0].currentData()
        self.preview.update()

    def build_curves(self):
        super().build_curves()
        form = self.tabs.widget(self.tabs.count() - 1).widget().layout()
        for key in (("comsol", "result_name"), ("comsol", "result_type"), ("plot", "x_column")):
            widget = self.fields[key][0]
            widget.hide()
            form.labelForField(widget).hide()
        self.x_choice = QComboBox()
        form.insertRow(4, "X 列", self.x_choice)
        self.x_choice.currentIndexChanged.connect(self.set_x_column)
        self.update_column_choices()

    def add_curve(self, y="", label="", color="#1F77B4", style="solid"):
        super().add_curve(y, label, color, style)
        row = self.curves.rowCount() - 1
        item = self.curves.item(row, 0)
        combo = QComboBox()
        self.fill_column_combo(combo, y)
        combo.currentIndexChanged.connect(lambda: item.setText(combo.currentData() or ""))
        self.curves.setCellWidget(row, 0, combo)

    def fill_column_combo(self, combo, selected):
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("请选择数据列" if self.columns else "请先读取数据", None)
        for name in self.columns:
            combo.addItem(name, name)
        combo.setCurrentIndex(max(0, combo.findData(selected)))
        combo.blockSignals(False)

    def set_x_column(self):
        self.fields[("plot", "x_column")][0].setText(self.x_choice.currentData() or "")

    def update_column_choices(self):
        self.fill_column_combo(self.x_choice, self.fields[("plot", "x_column")][0].text())
        for row in range(self.curves.rowCount()):
            self.fill_column_combo(self.curves.cellWidget(row, 0), self.curves.item(row, 0).text())

    def load_preset(self):
        super().load_preset()
        self.update_column_choices()

    def source_settings(self):
        values = {}
        for key in ("mode", "model", "csv", "version", "low_memory", "encoding", "csv_format"):
            widget, kind = self.fields[("comsol", key)]
            values[key] = (
                widget.currentData()
                if kind == "combo"
                else widget.isChecked()
                if kind == "bool"
                else widget.text().strip()
            )
        return values

    def selected_result(self):
        return (
            self.fields[("comsol", "result_name")][0].text(),
            self.fields[("comsol", "result_type")][0].currentData(),
        )

    def select_result(self, index):
        item = self.results.itemData(index)
        if item and self.scanned_source == self.source_settings():
            self.fields[("comsol", "result_name")][0].setText(item["tag"])
            combo = self.fields[("comsol", "result_type")][0]
            combo.setCurrentIndex(combo.findData(item["kind"]))
            self.start_task("columns")

    def current_plot_updates(self):
        if (
            self.scanned_source != self.source_settings()
            or self.scanned_result != self.selected_result()
            or not self.columns
        ):
            raise ValueError("请先识别结果和数据列。")
        x = self.x_choice.currentData()
        ys = [self.curves.cellWidget(row, 0).currentData() for row in range(self.curves.rowCount())]
        if not x or not ys or any(y is None for y in ys):
            raise ValueError("请从下拉框选择 X 列和每条曲线的 Y 列。")
        return self.collect()

    def common_origin_updates(self):
        return {
            ("origin", key): widget.isChecked() if kind == "bool" else widget.text().strip()
            for (group, key), (widget, kind) in self.fields.items()
            if group == "origin"
        }

    def plot_config(self, updates, create_outputs=False):
        candidate = deepcopy(self.raw)
        for (group, key), value in (updates | self.common_origin_updates()).items():
            section(candidate, group)[key] = deepcopy(value)
        return prepare_config(candidate, self.path, create_outputs=create_outputs)

    def refresh_queue(self, selected=0):
        self.plot_queue.clear()
        for index, updates in enumerate(self.pending_plots, 1):
            title = updates[("plot", "title")]
            x = updates[("plot", "x_column")]
            ys = ", ".join(updates[("plot", "y_columns")])
            self.plot_queue.addItem(f"{index}. {title or ys}  [X: {x}；Y: {ys}]")
        count = len(self.pending_plots)
        if not count:
            self.plot_queue.addItem("尚未添加图形")
        self.plot_queue.setCurrentIndex(min(selected, max(0, count - 1)))
        self.plot_queue.setEnabled(bool(count))
        self.replace_plot_button.setEnabled(bool(count))
        self.remove_plot_button.setEnabled(bool(count))
        self.run_button.setText(
            f"在同一 Origin 工程中生成全部 {count} 张图"
            if count
            else "保存参数并读取 → 生成当前图形"
        )

    def queue_plot(self, replace=False):
        try:
            updates = self.current_plot_updates()
            self.plot_config(updates)
        except Exception as exc:
            QMessageBox.warning(self, "无法加入待出图", str(exc))
            return
        index = self.plot_queue.currentIndex() if replace else len(self.pending_plots)
        if replace:
            self.pending_plots[index] = updates
        else:
            self.pending_plots.append(updates)
        self.refresh_queue(index)
        self.status.setText("已记录当前图的参数。修改后可继续加入；只有列表中的图会批量生成。")

    def remove_queued_plot(self):
        index = self.plot_queue.currentIndex()
        if self.pending_plots and index >= 0:
            self.pending_plots.pop(index)
            self.refresh_queue(index)
            self.status.setText("已移除选中的待出图。")

    def start_task(self, action):
        try:
            source = self.source_settings()
            if action == "list" and source["mode"] == "csv":
                action = "columns"
            if action == "run":
                save_updates(self.path, self.current_plot_updates())
                config = load_config(self.path)
            elif action == "batch":
                config = []
                for index, updates in enumerate(self.pending_plots, 1):
                    try:
                        config.append(self.plot_config(updates, create_outputs=True))
                    except Exception as exc:
                        raise ValueError(f"第 {index} 张图的参数有误：{exc}") from exc
            else:
                config = load_config(self.path, check_input=False, create_outputs=False)
                config["comsol"].update(source)
                for key in ("model", "csv"):
                    config["comsol"][key] = (self.path.parent / source[key]).resolve()
                active = config["comsol"]["model" if source["mode"] == "mph" else "csv"]
                if not active.is_file():
                    raise ValueError(f"请选择有效的数据文件：{active}")
                tag, kind = self.selected_result()
                config["comsol"].update(result_name=tag, result_type=kind)
                self.columns = []
                self.update_column_choices()
                if action == "list" or source["mode"] == "csv":
                    self.results.clear()
                    self.scanned_source = None
        except Exception as exc:
            QMessageBox.warning(self, "请检查读取与绘图参数", str(exc))
            return
        self.set_busy(True)
        self.status.setText(
            {
                "list": "正在读取模型结果…",
                "columns": "正在识别数据列…",
                "run": "正在读取数据并生成图形…",
                "batch": f"正在生成 {len(self.pending_plots)} 张图…",
            }[action]
        )
        self.worker = Task(config, action, self)
        self.worker.done.connect(lambda result: self.completed(action, result, source))
        self.worker.failed.connect(self.failed)
        self.worker.finished.connect(lambda: self.set_busy(False) if self.worker is task else None)
        task = self.worker
        self.worker.start()

    def set_busy(self, busy):
        self.tabs.setEnabled(not busy)
        self.run_button.setEnabled(not busy)
        self.queue_panel.setEnabled(not busy)
        self.save_button.setEnabled(not busy)
        self.preset_combo.parentWidget().setCursor(
            Qt.CursorShape.WaitCursor if busy else Qt.CursorShape.ArrowCursor
        )

    def completed(self, action, result, source):
        if action == "list":
            self.scanned_source = source
            self.results.clear()
            self.results.addItem("请选择模型结果", None)
            for item in result:
                if item["kind"] in ("table", "1d", "2d", "3d"):
                    self.results.addItem(f"{item['tag']} · {item['label']} ({item['kind']})", item)
            count = self.results.count() - 1
            self.status.setText(f"已识别 {count} 项结果。请选择要绘图的结果。")
            if count == 1:
                self.results.setCurrentIndex(1)
                QTimer.singleShot(0, lambda: self.select_result(1))
        elif action == "columns":
            self.scanned_source = source
            self.scanned_result = self.selected_result()
            self.columns = result
            kept = [
                row
                for row in range(self.curves.rowCount())
                if self.curves.item(row, 0).text() in result
            ]
            for row in reversed(range(self.curves.rowCount())):
                if row not in kept:
                    self.curves.removeRow(row)
            if not self.curves.rowCount():
                self.add_curve()
            self.update_column_choices()
            self.tabs.setCurrentIndex(1)
            self.status.setText(
                f"已识别 {len(result)} 个数值列，请选择 X 和 Y。"
                if len(result) >= 2
                else "该结果少于两个有效数值列，请选择其他结果。"
            )
        elif action == "batch":
            message = f"已生成 {result['count']} 个 Origin 图窗。"
            if result["project"]:
                message += f"\n工程：{result['project']}"
            if result["figures"]:
                message += "\n已导出图片：" + "、".join(result["figures"])
            self.status.setText(message)
        else:
            self.status.setText(f"图形：{result['figure']}\n工程：{result['project']}")

    def failed(self, message):
        self.status.setText("执行失败：" + message)
        QMessageBox.warning(self, "读取或绘图失败", message)

    def reject(self):
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(self, "任务正在执行", "请等待当前读取或绘图结束后关闭。")
            return
        super().reject()
