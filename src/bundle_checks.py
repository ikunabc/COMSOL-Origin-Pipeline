"""Built-in executable verification; optional application checks are explicit."""
from copy import deepcopy
import importlib.metadata
import json
from pathlib import Path
import sys
import traceback
from .runtime import FROZEN, RESOURCE_ROOT, STATE_ROOT


def run_checks(config,args):
    report={'frozen':FROZEN,'executable':sys.executable,'resource_root':str(RESOURCE_ROOT),
            'state_root':str(STATE_ROOT),'python':sys.version,'checks':{}}
    output=STATE_ROOT/'bundle-test'
    output.mkdir(parents=True,exist_ok=True)
    try:
        if FROZEN:
            import ctypes
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.GetModuleHandleW.argtypes=[ctypes.c_wchar_p]
            kernel.GetModuleHandleW.restype=ctypes.c_void_p
            kernel.GetModuleFileNameW.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_uint]
            handle=kernel.GetModuleHandleW(f'python{sys.version_info.major}{sys.version_info.minor}.dll')
            buffer=ctypes.create_unicode_buffer(32768)
            assert kernel.GetModuleFileNameW(handle,buffer,len(buffer))
            assert Path(buffer.value).resolve().is_relative_to(RESOURCE_ROOT.resolve())
            report['checks']['python_runtime']='PASS: loaded Python DLL is inside the EXE bundle'
        import numpy as np
        import pandas as pd
        import scipy.signal
        import scipy.interpolate
        import originpro as op
        import mph
        import jpype
        from PySide6.QtWidgets import QApplication
        app=QApplication.instance() or QApplication([])
        from .settings_ui import OriginSettingsDialog, SettingsButtonInstaller
        settings=OriginSettingsDialog(STATE_ROOT/'config.toml')
        assert settings.tabs.count()==5
        settings.close()
        report['checks']['settings']='PASS: five tabs constructed'
        from .integrated_ui import IntegratedDialog
        unified=IntegratedDialog(STATE_ROOT/'config.toml')
        assert unified.tabs.count()==6
        unified.close()
        report['checks']['integrated_ui']='PASS: unified COMSOL and Origin settings with graph previews'

        # Verify preset persistence in the actual frozen application, in isolation.
        import tempfile
        from .settings_presets import PresetStore
        with tempfile.TemporaryDirectory(dir=output) as preset_temp:
            preset_config=Path(preset_temp)/'config.toml'
            preset_config.write_bytes((RESOURCE_ROOT/'config.default.toml').read_bytes())
            first=OriginSettingsDialog(preset_config)
            first.fields[('plot','title')][0].setText('参数记忆打包验证')
            first.preset_combo.setEditText('已记忆参数')
            first.remember_preset()
            first.close()
            second=OriginSettingsDialog(preset_config)
            assert second.preset_store.names()==['已记忆参数']
            second.preset_combo.setCurrentIndex(0)
            second.load_preset()
            assert second.fields[('plot','title')][0].text()=='参数记忆打包验证'
            second.preset_store.delete('已记忆参数')
            assert PresetStore(preset_config).names()==[]
            second.close()
        report['checks']['parameter_presets']='PASS: remember, reopen, load and delete'

        for name in ('numpy','pandas','scipy','originpro','OriginExt','MPh','PySide6'):
            report['checks'][name]=importlib.metadata.version(name)
        from .adapters.comsol_adapter import backend, COMSOLAdapter, BACKEND
        assert backend().discover_items and backend().extract_via_export
        sys.path.insert(0,str(BACKEND))
        import COMSOLExtractor
        from .adapters.gui_adapter import make_push_wrapper
        assert callable(make_push_wrapper(COMSOLExtractor.push_to_origin,config))
        report['checks']['upstream_gui']='PASS: original entry point and plotting adapter imported'
        if '--bundle-check' in args:
            from PySide6.QtCore import QTimer
            from PySide6.QtWidgets import QPushButton
            installer=SettingsButtonInstaller(STATE_ROOT/'config.toml',app)
            app.installEventFilter(installer)
            buttons=[]
            def verify_window():
                for window in app.topLevelWidgets():
                    if window.windowTitle()=='COMSOL Extractor':
                        buttons.append(window.findChild(QPushButton,'originPlotSettingsButton') is not None)
                        window.grab().save(str(output/'packaged_gui.png'))
                        window.close()
            QTimer.singleShot(700,verify_window)
            QTimer.singleShot(7000,app.quit)
            COMSOLExtractor.run_extraction_window(None,None,True)
            assert buttons==[True],buttons
            report['checks']['window']='PASS: original GUI opened, settings button present, screenshot rendered, clean exit'
        report['checks']['comsol_discovery']=[i['name'] for i in mph.discovery.find_backends()]
        c=deepcopy(config)
        c['origin'].update(visible=False,new_instance=True,save_project=True,close_on_finish=True,
                           project_file=Path.cwd()/'bundle-test'/'packaged_origin.opju')
        c['export'].update(directory=output,filename='packaged_origin',transparent=False)
        c['plot'].update(x_column='Time',y_columns=['u2','v2'],title='Packaged EXE verification',template='')
        c['plot']['legend']['labels']=['Synthetic u2','Synthetic v2']
        for axis in ('x','y'):
            c['plot']['axis'][axis].update(min='auto',max='auto',major_step='auto',scale='linear')
        if '--verify-comsol' in args:
            backends=mph.discovery.find_backends()
            chosen=next(i for i in backends if i['name']=='6.3')
            model=Path(chosen['root'])/'applications/COMSOL_Multiphysics/Multiphysics/busbar.mph'
            c['comsol'].update(mode='mph',version='6.3',model=model,result_type='table',result_name='mm1',column_map={})
            adapter=COMSOLAdapter(c)
            try:
                ds_comsol=adapter.extract_dataset()
                assert not ds_comsol.data.empty
                report['checks']['comsol']='PASS: COMSOL 6.3 solved busbar table extracted from bundled backend'
                report['checks']['comsol_shape']=list(ds_comsol.data.shape)
            finally:
                adapter.close()
        if '--verify-origin' in args:
            from .adapters.origin_adapter import OriginAdapter
            from .adapters.process_adapter import process
            from .models import Dataset
            x=np.linspace(0,1,101)
            ds=Dataset(pd.DataFrame({'Time':x,'u2':np.sin(2*np.pi*x),'v2':np.cos(2*np.pi*x)}),
                       'EXE synthetic test','synthetic',units={'Time':'s','u2':'m/s','v2':'m/s'})
            c['processing'].update(enable_smoothing=True,smoothing_method='savgol',window_length=11,
                                   polyorder=3,enable_interpolation=True,interpolation_method='pchip',interpolation_points=201)
            if '--verify-comsol' in args:
                numeric=ds_comsol.data.select_dtypes(include='number')
                assert numeric.shape[1]>=2
                ds=Dataset(numeric.copy(),'COMSOL integrated test','mph')
                c['plot']['x_column']=str(numeric.columns[0])
                c['plot']['y_columns']=[str(v) for v in numeric.columns[1:]]
                c['plot']['legend']['labels']=[str(v) for v in numeric.columns[1:]]
                c['processing'].update(enable_smoothing=False,enable_interpolation=False)
            expected_shape=ds.data.shape if '--verify-comsol' in args else (201,3)
            ds=process(ds,c)
            adapter=OriginAdapter(c)
            try:
                adapter.connect()
                book=adapter.write_dataframe(ds)
                assert book[0].to_df().shape==expected_shape
                graph=adapter.create_graph(book,ds)
                from PIL import Image
                images={}
                for fmt in ('png','tiff','pdf'):
                    c['export']['format']=fmt
                    file=adapter.export_graph(graph)
                    assert file.stat().st_size>0
                    if fmt!='pdf':
                        with Image.open(file) as im:
                            assert im.size==(c['plot']['size']['width'],c['plot']['size']['height'])
                            assert all(abs(float(v)-c['export']['dpi'])<0.01 for v in im.info['dpi'])
                    else:
                        assert file.read_bytes().startswith(b'%PDF')
                    images[fmt]=file.stat().st_size
                adapter.save_project()
                assert op.open(str(c['origin']['project_file']),readonly=True,asksave=False)
                assert op.find_graph(0) is not None
                assert op.find_book('w',0)[0].to_df().shape==expected_shape
                adapter.success=True
                report['checks']['origin']='PASS: smoothing/interpolation, workbook readback, graph, PNG/TIFF/PDF, OPJU reopen'
                report['checks']['images_bytes']=images
                if '--verify-comsol' in args:
                    report['checks']['end_to_end']='PASS: extracted COMSOL table plotted, exported, saved and reopened'
            finally:
                adapter.close()
        report['status']='PASS'
        code=0
    except Exception:
        report.update(status='FAIL',error=traceback.format_exc())
        code=1
    filename='origin-check.json' if '--verify-origin' in args else 'comsol-check.json' if '--verify-comsol' in args else 'bundle-check.json'
    (output/filename).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return code


