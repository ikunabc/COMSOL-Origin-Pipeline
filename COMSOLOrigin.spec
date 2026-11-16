# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, copy_metadata

root=Path(SPECPATH)
backend=root/'lib/comsol_csv_tool'
datas=[(str(root/'config.default.toml'),'.'),
       (str(root/'assets/comsol-origin.png'),'assets'),
       (str(root/'data/input/example.csv'),'data/input'),
       (str(root/'README.md'),'.'),
       (str(root/'docs/THIRD_PARTY_NOTICES.txt'),'docs')]
datas += [(str(file),'lib/comsol_csv_tool') for file in backend.glob('*.py')]
datas += [(str(backend/'README.md'),'lib/comsol_csv_tool')]
binaries=[]
hiddenimports=['COMSOLExtractor','extraction','gui','origin_push','license_check',
               'matplotlib.backends.backend_qtagg','matplotlib.backends.backend_agg',
               'PIL.TiffImagePlugin','PIL.PngImagePlugin','scipy.signal','scipy.interpolate']
for package in ('mph','jpype','originpro','OriginExt'):
    data,binary,hidden=collect_all(package)
    datas+=data
    binaries+=binary
    hiddenimports+=hidden
for package in ('numpy','pandas','scipy','originpro','OriginExt','MPh','PySide6'):
    datas+=copy_metadata(package)

a=Analysis([str(root/'gui_main.py')],pathex=[str(root),str(backend)],
           binaries=binaries,datas=datas,hiddenimports=hiddenimports,
           excludes=['tkinter','PyQt5','PyQt6','PySide2','IPython','pytest','notebook'],
           noarchive=False)
# Windows 10/11 supply API-set forwarders and UCRT. Do not bundle legacy
# copies discovered in unrelated tool directories on the build machine.
a.binaries=[entry for entry in a.binaries
            if not Path(entry[0]).name.lower().startswith(('api-ms-win-','ext-ms-win-'))
            and Path(entry[0]).name.lower()!='ucrtbase.dll']
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='COMSOLOrigin',
        debug=False,strip=False,upx=False,console=False,
        icon=str(root/'assets/comsol-origin.ico'),
        disable_windowed_traceback=False,version=str(root/'packaging/version_info.txt'))
