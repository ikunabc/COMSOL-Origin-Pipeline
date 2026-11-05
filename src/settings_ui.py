"""Visual configuration editor; no COMSOL/Origin sessions are opened here."""
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import tempfile
import tomllib
from PySide6.QtCore import Qt, QObject, QEvent
from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import (QApplication, QCheckBox, QColorDialog, QComboBox,
    QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFontComboBox,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPushButton, QScrollArea, QSpinBox, QSplitter, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget)
from .settings_presets import PresetStore
from .config import validate, load_config, GRAPH_TYPE_MAP, LINE_STYLE_MAP, SYMBOL_MAP, COLOR_MAP


def section(config,path):
    for key in path.split('.'):
        config=config[key]
    return config


def ensure_ui_font():
    app=QApplication.instance()
    if app and not app.property('originSettingsFontReady'):
        # Explicit registration also makes headless Qt renders support Chinese.
        for file in ('C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/msyh.ttf'):
            if Path(file).is_file():
                font_id=QFontDatabase.addApplicationFont(file)
                families=QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    app.setFont(QFont(families[0],10))
                    break
        app.setProperty('originSettingsFontReady',True)


def save_updates(path,updates):
    """Edit only supplied TOML keys; validate before atomically replacing it."""
    path=Path(path)
    original=path.read_text(encoding='utf-8')
    lines=original.splitlines(keepends=True)
    current=''
    remaining=deepcopy(updates)
    for i,line in enumerate(lines):
        match=re.match(r'^\s*\[([^]]+)\]\s*(?:#.*)?$',line.strip())
        if match:
            current=match.group(1)
            continue
        match=re.match(r'^\s*([A-Za-z_][A-Za-z_0-9]*)\s*=',line)
        if match and (current,match.group(1)) in remaining:
            key=match.group(1)
            value=remaining.pop((current,key))
            lines[i]=f'{key} = {json.dumps(value,ensure_ascii=False)}\n'
    if remaining:
        raise ValueError(f'配置缺少字段：{list(remaining)}')
    text=''.join(lines)
    temp=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',suffix='.toml',
                                         dir=path.parent,delete=False) as f:
            temp=Path(f.name)
            f.write(text)
        load_config(temp,check_input=False,create_outputs=False)
        path.with_suffix('.toml.ui-backup').write_text(original,encoding='utf-8')
        os.replace(temp,path)
    finally:
        if temp and temp.exists():
            temp.unlink()


class OriginSettingsDialog(QDialog):
    def __init__(self,path,parent=None):
        ensure_ui_font()
        super().__init__(parent)
        self.path=Path(path)
        self.raw=tomllib.loads(self.path.read_text(encoding='utf-8'))
        self.fields={}
        self.setWindowTitle('Origin 自动绘图 · 参数设置')
        self.resize(1040,760)
        layout=QVBoxLayout(self)
        title=QLabel('Origin 自动绘图设置')
        title.setFont(QFont(self.font().family(),16,QFont.Weight.Bold))
        layout.addWidget(title)
        layout.addWidget(QLabel('保存后自动应用于本次导入后的绘图。取消不会修改配置，也不会启动 COMSOL / Origin。'))
        self.preset_store=PresetStore(self.path)
        self.build_presets(layout)
        self.tabs=QTabWidget()
        layout.addWidget(self.tabs,1)
        self.build_curves()
        self.build_axes()
        self.build_fonts()
        self.build_export()
        self.build_processing()
        self.status=QLabel(str(self.path))
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons=QDialogButtonBox()
        self.save_button=buttons.addButton('保存设置',QDialogButtonBox.ButtonRole.AcceptRole)
        self.save_button.clicked.connect(self.save)
        buttons.addButton('取消',QDialogButtonBox.ButtonRole.RejectRole).clicked.connect(self.reject)
        layout.addWidget(buttons)
        self.refresh_presets()

    def build_presets(self, layout):
        row=QHBoxLayout()
        row.addWidget(QLabel('参数记忆'))
        self.preset_combo=QComboBox()
        self.preset_combo.setObjectName('parameterPresetCombo')
        self.preset_combo.setEditable(True)
        self.preset_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.preset_combo.lineEdit().setPlaceholderText('选择已记忆的参数，或输入新名称')
        row.addWidget(self.preset_combo,1)
        for text, name, callback in (
                ('记忆当前参数','rememberPresetButton',self.remember_preset),
                ('载入','loadPresetButton',self.load_preset),
                ('删除记忆','deletePresetButton',self.delete_preset)):
            button=QPushButton(text)
            button.setObjectName(name)
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        tip=QLabel('记忆可保留多套参数；载入后点击“保存设置”应用。删除记忆不会修改当前参数。')
        tip.setWordWrap(True)
        layout.addWidget(tip)

    def refresh_presets(self, selected=''):
        try:
            names=self.preset_store.names()
        except Exception as exc:
            self.status.setText(str(exc))
            return
        self.preset_combo.clear()
        self.preset_combo.addItems(names)
        self.preset_combo.setEditText(selected)

    def validated_updates(self, updates):
        expected=set(self.fields)|{('plot','y_columns'),('plot.legend','labels'),
                                  ('plot.style','colors'),('plot.style','line_styles')}
        if set(updates)!=expected:
            raise ValueError('预设字段与当前版本不兼容，请重新记忆参数。')
        candidate=deepcopy(self.raw)
        for (group,key), value in updates.items():
            section(candidate,group)[key]=value
        validate(candidate)
        return updates

    def remember_preset(self):
        try:
            name=self.preset_store._name(self.preset_combo.currentText())
            updates=self.validated_updates(self.collect())
            if name in self.preset_store.names():
                answer=QMessageBox.question(self,'覆盖参数记忆',
                    f'已存在“{name}”，是否用当前参数覆盖？',
                    QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No)
                if answer!=QMessageBox.StandardButton.Yes:
                    return
            self.preset_store.save(name,updates)
            self.refresh_presets(name)
            self.status.setText(f'已记忆“{name}”，下次打开仍可载入。点击“保存设置”应用当前参数。')
        except Exception as exc:
            QMessageBox.warning(self,'参数未记忆',str(exc))

    def load_preset(self):
        try:
            name=self.preset_combo.currentText().strip()
            updates=self.preset_store.load(name)
            self.validated_updates(updates)
            for key,(widget,kind) in self.fields.items():
                value=updates[key]
                if kind=='bool':
                    widget.setChecked(value)
                elif kind in ('int','float'):
                    widget.setValue(value)
                elif kind=='combo':
                    widget.setCurrentIndex(widget.findData(value))
                elif kind=='font':
                    widget.setCurrentFont(QFont(value))
                    widget.setEditText(value)
                else:
                    widget.setText(str(value))
            self.curves.setRowCount(0)
            ys=updates[('plot','y_columns')]
            labels=updates[('plot.legend','labels')]
            colors=updates[('plot.style','colors')]
            styles=updates[('plot.style','line_styles')]
            for i,y in enumerate(ys):
                self.add_curve(y,labels[i] if labels else '',
                               colors[i%len(colors)],styles[i%len(styles)])
            self.status.setText(f'已载入“{name}”。点击“保存设置”应用；取消可保留原配置。')
        except KeyError:
            QMessageBox.warning(self,'未找到参数记忆','请先选择已记忆的参数。')
        except Exception as exc:
            QMessageBox.warning(self,'参数未载入',str(exc))

    def delete_preset(self):
        try:
            name=self.preset_combo.currentText().strip()
            if name not in self.preset_store.names():
                raise ValueError('请先选择要删除的参数记忆。')
            answer=QMessageBox.question(self,'删除参数记忆',
                f'删除“{name}”？当前窗口的参数和已保存设置将保留。',
                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer!=QMessageBox.StandardButton.Yes:
                return
            self.preset_store.delete(name)
            self.refresh_presets()
            self.status.setText(f'已删除“{name}”的记忆，当前参数保持不变。')
        except Exception as exc:
            QMessageBox.warning(self,'记忆未删除',str(exc))

    def tab(self,title):
        page=QWidget()
        form=QFormLayout(page)
        form.setVerticalSpacing(14)
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        self.tabs.addTab(scroll,title)
        return form

    def field(self,form,label,group,key,kind='text',choices=None):
        value=section(self.raw,group)[key]
        if kind=='bool':
            widget=QCheckBox()
            widget.setChecked(value)
        elif kind in ('int','float'):
            widget=QSpinBox() if kind=='int' else QDoubleSpinBox()
            widget.setRange(0,1000000)
            if kind=='float':
                widget.setDecimals(3)
                widget.setSingleStep(0.5)
            widget.setValue(value)
        elif kind=='combo':
            widget=QComboBox()
            for display,data in choices:
                widget.addItem(display,data)
            widget.setCurrentIndex(widget.findData(value))
        elif kind=='font':
            widget=QFontComboBox()
            widget.setEditable(True)
            widget.setCurrentFont(QFont(value))
            widget.setEditText(value)
        else:
            widget=QLineEdit(str(value))
            if kind=='auto':
                widget.setPlaceholderText('auto = 自动；或输入数值')
        widget.setObjectName(group+'.'+key)
        self.fields[(group,key)]=(widget,kind)
        form.addRow(label,widget)
        return widget

    def file_field(self,form,label,group,key,folder=False,filter='All files (*)'):
        line=self.field(form,label,group,key)
        row=QWidget()
        box=QHBoxLayout(row)
        box.setContentsMargins(0,0,0,0)
        box.addWidget(line)
        button=QPushButton('浏览…')
        box.addWidget(button)
        # Replace the form's field widget with its file-picker container.
        form.removeWidget(line)
        form.setWidget(form.rowCount()-1,QFormLayout.ItemRole.FieldRole,row)
        def browse():
            if folder:
                selected=QFileDialog.getExistingDirectory(self,'选择输出目录',str(self.path.parent))
            elif group=='paths':
                selected,_=QFileDialog.getSaveFileName(self,'选择处理数据保存位置',str(self.path.parent),'CSV (*.csv)')
            else:
                selected,_=QFileDialog.getOpenFileName(self,'选择 Origin 图形模板',str(self.path.parent),filter)
            if selected:
                line.setText(selected.replace('\\','/'))
        button.clicked.connect(browse)
        return line

    def build_curves(self):
        form=self.tab('曲线与数据')
        self.field(form,'结果 Tag / 名称','comsol','result_name')
        self.field(form,'结果类型','comsol','result_type','combo',
                   [('表格','table'),('任意 Plot','plot'),('1D Plot','1d'),('2D Plot','2d'),('3D Plot','3d')])
        self.field(form,'图形类型','plot','graph_type','combo',
                   [('折线','line'),('折线 + 符号','line_symbol'),('散点','scatter'),('柱形','column')])
        self.field(form,'X 列名称','plot','x_column')
        self.field(form,'图标题（可留空）','plot','title')
        self.file_field(form,'Origin 模板（可留空）','plot','template',filter='Origin graph template (*.otpu *.otp)')
        self.curves=QTableWidget(0,4)
        self.curves.setHorizontalHeaderLabels(['Y 列名称','图例文字（可留空）','颜色','线型'])
        self.curves.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.curves.setMinimumHeight(200)
        g=self.raw['plot']
        for i,y in enumerate(g['y_columns']):
            self.add_curve(y,g['legend']['labels'][i] if g['legend']['labels'] else '',
                           g['style']['colors'][i%len(g['style']['colors'])],
                           g['style']['line_styles'][i%len(g['style']['line_styles'])])
        form.addRow('每行一条曲线',self.curves)
        actions=QWidget()
        row=QHBoxLayout(actions)
        add=QPushButton('＋ 添加曲线')
        delete=QPushButton('删除选中曲线')
        add.clicked.connect(lambda:self.add_curve())
        delete.clicked.connect(self.remove_curve)
        row.addWidget(add)
        row.addWidget(delete)
        row.addStretch()
        form.addRow('',actions)
        self.field(form,'线宽（pt）','plot.style','line_width','float')
        self.field(form,'符号形状','plot.style','symbol','combo',
                   [('方形','square'),('圆形','circle'),('三角形','triangle'),('菱形','diamond'),('叉号','cross')])
        self.field(form,'符号大小（pt）','plot.style','symbol_size','float')

    def add_curve(self,y='',label='',color='#1F77B4',style='solid'):
        row=self.curves.rowCount()
        self.curves.insertRow(row)
        self.curves.setItem(row,0,QTableWidgetItem(y))
        self.curves.setItem(row,1,QTableWidgetItem(label))
        button=QPushButton()
        def set_color(value):
            button.setProperty('color',value)
            button.setText(value)
            q=QColor(value)
            fg='#000000' if q.lightness()>150 else '#FFFFFF'
            button.setStyleSheet(f'background-color:{value}; color:{fg}; padding:7px;')
        set_color(COLOR_MAP.get(color,color))
        def choose():
            q=QColorDialog.getColor(QColor(button.property('color')),self,'选择曲线颜色')
            if q.isValid():
                set_color(q.name().upper())
        button.clicked.connect(choose)
        self.curves.setCellWidget(row,2,button)
        combo=QComboBox()
        for text,value in [('实线','solid'),('虚线','dash'),('点线','dot'),('点划线','dash_dot')]:
            combo.addItem(text,value)
        combo.setCurrentIndex(combo.findData(style))
        self.curves.setCellWidget(row,3,combo)

    def remove_curve(self):
        for row in sorted({i.row() for i in self.curves.selectedIndexes()},reverse=True):
            self.curves.removeRow(row)

    def build_axes(self):
        form=self.tab('坐标轴')
        for name,title in [('x','X 轴'),('y','Y 轴')]:
            form.addRow(QLabel('— '+title+' —'))
            group='plot.axis.'+name
            self.field(form,'标题',group,'title')
            self.field(form,'显示单位',group,'unit')
            self.field(form,'最小值',group,'min','auto')
            self.field(form,'最大值',group,'max','auto')
            self.field(form,'主刻度间隔',group,'major_step','auto')
            self.field(form,'刻度类型',group,'scale','combo',[('线性','linear'),('以 10 为底的对数','log10')])
        note=QLabel('单位字段只设置坐标标题，不换算数据。m/s → μm/s 必须另行对数值乘以 10⁶。')
        note.setWordWrap(True)
        form.addRow(note)

    def build_fonts(self):
        form=self.tab('字体、图例与布局')
        self.field(form,'字体','plot.font','family','font')
        for key,text in [('axis_title_size','坐标标题字号'),('tick_label_size','刻度字号'),
                         ('legend_size','图例字号'),('title_size','图标题字号')]:
            self.field(form,text+'（pt）','plot.font',key,'float')
        self.field(form,'显示图例','plot.legend','show','bool')
        self.field(form,'图例边框','plot.legend','frame','bool')
        self.field(form,'图例位置','plot.legend','position','combo',
                   [('左上','top_left'),('右上','top_right'),('左下','bottom_left'),('右下','bottom_right')])
        for key,text in [('left','左边距'),('top','上边距'),('width','图层宽度'),('height','图层高度'),
                         ('legend_inset','图例内边距'),('title_gap','标题上边距')]:
            self.field(form,text+'（页面 %）','plot.layout',key,'float')

    def build_export(self):
        form=self.tab('尺寸与导出')
        for key,text in [('width','图片宽度（px）'),('height','图片高度（px）')]:
            self.field(form,text,'plot.size',key,'int')
        self.field(form,'启用图片导出','export','enable','bool')
        self.file_field(form,'图片输出目录','export','directory',folder=True)
        self.field(form,'图片文件名（不带后缀）','export','filename')
        self.field(form,'文件格式','export','format','combo',[('TIFF','tiff'),('PNG','png'),('PDF','pdf')])
        self.field(form,'分辨率 DPI','export','dpi','int')
        self.field(form,'透明背景（PNG / TIFF）','export','transparent','bool')
        form.addRow(QLabel('PDF 为矢量输出，DPI 仅用于将像素尺寸换算为页面物理尺寸。'))
        form.addRow(QLabel('原项目 GUI 模式会保存并打开原导入工程；工程位置由原项目的模型输出目录决定。'))
        self.file_field(form,'处理数据 CSV 保存路径','paths','processed_file')
        # The processed path is editable directly; no open-file dialog for a new output.
        widget,_=self.fields[('paths','processed_file')]
        widget.setToolTip('可输入尚不存在的 CSV 文件路径；相对路径以 config.toml 所在目录为基准。')

    def build_processing(self):
        form=self.tab('数据处理（可选）')
        self.field(form,'丢弃绘图列 NaN / Inf 行','processing','drop_nan','bool')
        self.field(form,'按 X 排序','processing','sort','bool')
        self.field(form,'启用平滑','processing','enable_smoothing','bool')
        self.field(form,'平滑方法','processing','smoothing_method','combo',
                   [('不平滑','none'),('Savitzky–Golay','savgol'),('移动平均','moving_average'),('中值滤波','median')])
        self.field(form,'窗口长度（正奇数）','processing','window_length','int')
        self.field(form,'多项式阶数','processing','polyorder','int')
        self.field(form,'启用插值','processing','enable_interpolation','bool')
        self.field(form,'插值方法','processing','interpolation_method','combo',
                   [('不插值','none'),('线性','linear'),('三次','cubic'),('PCHIP','pchip')])
        self.field(form,'插值点数','processing','interpolation_points','int')

    def collect(self):
        updates={}
        for key,(widget,kind) in self.fields.items():
            if kind=='bool':
                value=widget.isChecked()
            elif kind in ('int','float'):
                value=widget.value()
            elif kind=='combo':
                value=widget.currentData()
            elif kind=='font':
                value=widget.currentText().strip()
            else:
                value=widget.text().strip()
                if kind=='auto':
                    try:
                        value='auto' if not value or value.lower()=='auto' else float(value)
                    except ValueError as exc:
                        raise ValueError(f'[{key[0]}].{key[1]} 请填写数值或 auto。') from exc
            updates[key]=value
        ys,labels,colors,styles=[],[],[],[]
        for row in range(self.curves.rowCount()):
            ys.append(self.curves.item(row,0).text().strip())
            labels.append(self.curves.item(row,1).text().strip())
            colors.append(self.curves.cellWidget(row,2).property('color'))
            styles.append(self.curves.cellWidget(row,3).currentData())
        # Blank individual legends use that curve's column name.
        updates[('plot','y_columns')]=ys
        updates[('plot.legend','labels')]=[label or y for label,y in zip(labels,ys)] if any(labels) else []
        updates[('plot.style','colors')]=colors
        updates[('plot.style','line_styles')]=styles
        return updates

    def save(self):
        try:
            save_updates(self.path,self.collect())
        except Exception as exc:
            QMessageBox.warning(self,'参数未保存',str(exc))
            return
        self.accept()


class SettingsButtonInstaller(QObject):
    """Add a settings button when the unmodified upstream window appears."""
    def __init__(self,path,parent=None):
        super().__init__(parent)
        ensure_ui_font()
        self.path=Path(path)

    def eventFilter(self,obj,event):
        if event.type()==QEvent.Type.Show and isinstance(obj,QWidget) and obj.isWindow():
            if obj.windowTitle()=='COMSOL Extractor' and not obj.property('originSettingsInstalled'):
                splitter=obj.findChild(QSplitter)
                if splitter and splitter.count():
                    layout=splitter.widget(0).layout()
                    button=QPushButton('Origin 绘图参数…',obj)
                    button.setObjectName('originPlotSettingsButton')
                    button.setMinimumHeight(38)
                    button.clicked.connect(lambda:OriginSettingsDialog(self.path,obj).exec())
                    layout.insertWidget(0,button)
                    obj.setProperty('originSettingsInstalled',True)
        return False


def run_settings(path):
    import sys
    app=QApplication.instance() or QApplication(sys.argv[:1])
    load_config(path,check_input=False,create_outputs=False)
    return OriginSettingsDialog(path).exec()
