"""Combined input selection, plotting settings and execution window."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# MPh caches its client and requires every call to originate on one thread.
_ENGINE_WORKER = ThreadPoolExecutor(max_workers=1, thread_name_prefix="COMSOL-Origin")
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QComboBox, QHBoxLayout, QFileDialog, QMessageBox
from .settings_ui import OriginSettingsDialog, save_updates
from .config import load_config


class GraphPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.kind='line'
        self.setMinimumSize(280,140)
    def paintEvent(self,event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(),QColor('white'))
        painter.setPen(QPen(QColor('#64748b'),1))
        painter.drawLine(35,15,35,110); painter.drawLine(35,110,260,110)
        points=[(55,90),(95,65),(135,80),(175,40),(225,25)]
        painter.setPen(QPen(QColor('#2563eb'),3))
        for i,(x,y) in enumerate(points):
            if self.kind=='column':
                painter.fillRect(x-10,y,20,110-y,QColor('#2563eb'))
            else:
                if self.kind in ('line','line_symbol') and i:
                    painter.drawLine(*points[i-1],x,y)
                if self.kind in ('scatter','line_symbol'):
                    painter.drawEllipse(x-4,y-4,8,8)
        painter.setPen(QColor('#475569'))
        painter.drawText(40,132,'图形类型示意（非模型数据）')


class Task(QThread):
    done=Signal(object)
    failed=Signal(str)
    def __init__(self,config,action,parent=None):
        super().__init__(parent); self.config=config; self.action=action
    def run(self):
        _ENGINE_WORKER.submit(self.execute).result()

    def execute(self):
        try:
            if self.action=='list':
                from .adapters.comsol_adapter import COMSOLAdapter
                adapter=COMSOLAdapter(self.config)
                try: result=adapter.list_available_results()
                finally: adapter.close()
            else:
                from .pipeline import run
                _,figure,project=run(self.config)
                result={'figure':str(figure),'project':str(project)}
            self.done.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class IntegratedDialog(OriginSettingsDialog):
    def __init__(self,path,parent=None):
        super().__init__(path,parent)
        self.setWindowTitle('COMSOL → Origin · 读取与绘图')
        self.findChildren(QLabel)[0].setText('COMSOL 读取与 Origin 绘图')
        form=self.tab('COMSOL 读取')
        page=self.tabs.widget(self.tabs.count()-1)
        self.tabs.removeTab(self.tabs.count()-1); self.tabs.insertTab(0,page,'COMSOL 读取')
        self.field(form,'输入方式','comsol','mode','combo',[('已求解 MPH 模型','mph'),('CSV 数据','csv')])
        for key,label,filter in [('model','MPH 模型','COMSOL (*.mph)'),('csv','CSV 文件','CSV (*.csv)')]:
            line=self.field(form,label,'comsol',key)
            button=QPushButton('选择文件…')
            button.clicked.connect(lambda checked=False,line=line,filter=filter:self.choose_file(line,filter))
            form.addRow('',button)
        self.field(form,'COMSOL 版本','comsol','version')
        self.field(form,'低内存读取','comsol','low_memory','bool')
        self.field(form,'CSV 编码','comsol','encoding')
        self.field(form,'CSV 格式','comsol','csv_format','combo',[(s,s) for s in ('auto','standard','backend','native')])
        self.results=QComboBox(); form.addRow('模型中的结果',self.results)
        self.read_button=QPushButton('读取模型结果列表')
        self.read_button.clicked.connect(lambda:self.start_task('list'))
        form.addRow('',self.read_button)
        self.results.activated.connect(self.select_result)
        form.addRow(QLabel('选择结果后，Tag 和结果类型会同步到“曲线与数据”。设置 X/Y 列后生成图形。'))
        self.field(form,'显示 Origin 窗口','origin','visible','bool')
        self.field(form,'保存 Origin 工程','origin','save_project','bool')
        self.field(form,'工程保存路径（.opju）','origin','project_file')
        self.preview=GraphPreview()
        self.layout().insertWidget(3,self.preview)
        combo=self.fields[('plot','graph_type')][0]
        combo.currentIndexChanged.connect(self.update_preview)
        self.update_preview()
        self.run_button=QPushButton('保存参数并读取 → 生成 Origin 图形')
        self.run_button.clicked.connect(lambda:self.start_task('run'))
        self.layout().addWidget(self.run_button)
        self.worker=None
        self.tabs.setCurrentIndex(0)
        self.refresh_presets()
    def choose_file(self,line,filter):
        selected,_=QFileDialog.getOpenFileName(self,'选择输入文件',str(self.path.parent),filter)
        if selected: line.setText(selected.replace('\\','/'))
    def update_preview(self):
        self.preview.kind=self.fields[('plot','graph_type')][0].currentData()
        self.preview.update()
    def select_result(self,index):
        item=self.results.itemData(index)
        if item:
            self.fields[('comsol','result_name')][0].setText(item['tag'])
            combo=self.fields[('comsol','result_type')][0]
            combo.setCurrentIndex(combo.findData(item['kind']))
    def start_task(self,action):
        try:
            if action=='list' and self.fields[('comsol','mode')][0].currentData()!='mph':
                raise ValueError('CSV 模式请直接填写 X/Y 数据列；模型结果列表仅用于 MPH。')
            save_updates(self.path,self.collect())
            config=load_config(self.path)
        except Exception as exc:
            QMessageBox.warning(self,'请检查读取与绘图参数',str(exc)); return
        self.set_busy(True)
        self.status.setText('正在读取模型结果…' if action=='list' else '正在读取数据并生成图形…')
        self.worker=Task(config,action,self)
        self.worker.done.connect(lambda result:self.completed(action,result))
        self.worker.failed.connect(self.failed)
        self.worker.finished.connect(lambda:self.set_busy(False))
        self.worker.start()
    def set_busy(self,busy):
        self.tabs.setEnabled(not busy)
        self.run_button.setEnabled(not busy)
        self.save_button.setEnabled(not busy)
        self.preset_combo.parentWidget().setCursor(Qt.CursorShape.WaitCursor if busy else Qt.CursorShape.ArrowCursor)
    def completed(self,action,result):
        if action=='list':
            self.results.clear()
            for item in result:
                if item['kind'] in ('table','1d','2d','3d'):
                    self.results.addItem(f"{item['tag']} · {item['label']} ({item['kind']})",item)
            if self.results.count(): self.select_result(0)
            self.status.setText(f'已读取 {self.results.count()} 项结果，请选择要绘图的结果。')
        else:
            self.status.setText(f"图形：{result['figure']}\n工程：{result['project']}")
    def failed(self,message):
        self.status.setText('执行失败：'+message)
        QMessageBox.warning(self,'读取或绘图失败',message)
    def reject(self):
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(self,'任务正在执行','请等待当前读取或绘图结束后关闭。'); return
        super().reject()
