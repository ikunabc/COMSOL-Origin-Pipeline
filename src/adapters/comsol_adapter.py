"""Wrap the pinned A module without importing its GUI or changing its files."""
from contextlib import redirect_stdout
import csv
import importlib.util
import io
import logging
from pathlib import Path
import sys
import tempfile
import numpy as np
import pandas as pd
from ..models import Dataset
from ..runtime import RESOURCE_ROOT
from ..exceptions import (CSVFormatError, COMSOLConnectionError, COMSOLModelError,
                          COMSOLResultNotFoundError)

BACKEND = RESOURCE_ROOT / 'lib' / 'comsol_csv_tool'
log = logging.getLogger('pipeline')


def backend():
    # Loading by explicit filename prevents unrelated extraction.py shadowing A.
    name = '_pipeline_comsol_backend'
    if name not in sys.modules:
        source = BACKEND / 'extraction.py'
        if not source.is_file():
            raise COMSOLConnectionError('A submodule missing. Run git submodule update --init --recursive.')
        spec = importlib.util.spec_from_file_location(name, source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(name, None)
            raise
    return sys.modules[name]


def call_backend(fn, *args, **kwargs):
    capture = io.StringIO()
    try:
        with redirect_stdout(capture):
            return fn(*args, **kwargs)
    finally:
        if capture.getvalue():
            log.debug('A backend: %s', capture.getvalue().strip())


def normalize(df, name, source, comments, column_map=None, metadata=None):
    api = backend()
    original = list(df.columns)
    df = df.copy()
    names, units, long_names = [], {}, {}
    for col in original:
        clean = api.repair_mojibake(str(col)).lstrip('%').strip()
        label, unit = api.split_label_unit(clean)
        key = (column_map or {}).get(str(col), (column_map or {}).get(label, label))
        if not key:
            raise CSVFormatError('An empty column name remains after header cleaning.')
        if key in names:
            raise CSVFormatError(f'Duplicate cleaned column {key!r}; use [comsol.column_map].')
        names.append(key)
        units[key] = unit
        long_names[key] = label
    df.columns = names
    df = df.replace(r'^\s*$', np.nan, regex=True).dropna(how='all')
    for col in df:
        cleaned=df[col].map(lambda v: np.nan if isinstance(v,str) and v.strip().lower() in ('nan','na','n/a','null','--') else v)
        values = pd.to_numeric(cleaned, errors='coerce')
        nonempty = cleaned.notna()
        # Preserve text columns; selected plotting columns must be numeric later.
        if values[nonempty].notna().all():
            df[col] = values
    numeric = df.select_dtypes('number')
    md = dict(metadata or {})
    md.update({'comments': list(comments), 'long_names': long_names,
               'original_headers': dict(zip(names, map(str, original))),
               'dataframe_attrs': dict(df.attrs),
               'nan_count': int(df.isna().sum().sum()),
               'inf_count': int(np.isinf(numeric.to_numpy(dtype=float)).sum())})
    log.info('Dataset: %s rows × %s columns; NaN=%s, Inf=%s',len(df),len(names),md['nan_count'],md['inf_count'])
    if df.empty:
        raise CSVFormatError('Dataset contains no data rows.')
    return Dataset(df.reset_index(drop=True),name,str(source),names,units,md)


def read_csv(config):
    co=config['comsol']
    path=co['csv']
    try:
        lines=path.read_text(encoding=co['encoding']).splitlines()
        comments=[s.lstrip()[1:].strip() for s in lines if s.lstrip().startswith('%')]
        body=[s for s in lines if s.strip() and not s.lstrip().startswith('%')]
        if not body:
            raise CSVFormatError('CSV has no non-comment data.')
        fmt=co['csv_format']
        # Native COMSOL exports put headers in the final % line, followed by numeric data.
        delim = next((d for d in (',',';','\t') if d in body[0]), None)
        first=next(csv.reader([body[0]],delimiter=delim)) if delim else body[0].split()
        def is_number(s):
            try:
                float(s)
                return True
            except ValueError:
                return False
        native=fmt=='native' or (fmt=='auto' and all(is_number(s) for s in first))
        api=backend()
        if native:
            df=pd.read_csv(io.StringIO('\n'.join(body)),sep=delim or r'\s+',header=None)
            headers=None
            for comment in reversed(comments):
                candidate = next(csv.reader([comment],delimiter=delim)) if delim else api.split_header_line(comment,df.shape[1])
                if candidate and len(candidate)==df.shape[1] and ':' not in candidate[0]:
                    headers=candidate
                    break
            if headers is None:
                raise CSVFormatError('Native COMSOL header cannot be identified. Export column headers or select standard CSV format.')
            df.columns=headers
        else:
            if delim is None:
                raise CSVFormatError('Standard CSV requires comma, semicolon or tab delimiters.')
            rows=list(csv.reader(body,delimiter=delim))
            headers=rows[0]
            if any(len(r)!=len(headers) for r in rows):
                raise CSVFormatError('CSV rows have inconsistent column counts.')
            # A has a two-row header: names, then units. Explicit backend mode
            # is available for ambiguous all-empty units or textual first rows.
            units_row = len(rows)>1 and all(not s.strip() or not is_number(s) for s in rows[1])
            is_backend=fmt=='backend' or (fmt=='auto' and units_row and len(rows)>2)
            if is_backend:
                headers=[f'{h} ({u})' if u.strip() else h for h,u in zip(headers,rows[1])]
            df=pd.DataFrame(rows[2 if is_backend else 1:],columns=headers)
        return normalize(df,path.stem,path,comments,co.get('column_map'))
    except CSVFormatError:
        raise
    except Exception as exc:
        raise CSVFormatError(f'Cannot parse COMSOL CSV {path}: {exc}') from exc


class COMSOLAdapter:
    def __init__(self, config):
        self.config=config
        self.client=None
        self.model=None

    def load_comsol_model(self):
        log.info('Starting COMSOL %s...',self.config['comsol']['version'])
        try:
            import mph
            self.client=mph.start(version=self.config['comsol']['version'])
        except Exception as exc:
            raise COMSOLConnectionError(f'Cannot start COMSOL {self.config["comsol"]["version"]}. Check installation and license: {exc}') from exc
        try:
            self.model=self.client.load(str(self.config['comsol']['model']))
        except Exception as exc:
            raise COMSOLModelError(f'Cannot load MPH model: {exc}') from exc
        return self.model

    def list_available_results(self):
        if self.model is None:
            self.load_comsol_model()
        return call_backend(backend().discover_items,self.model)

    def extract_dataset(self):
        co=self.config['comsol']
        if co['mode']=='csv':
            return read_csv(self.config)
        items=self.list_available_results()
        selected=[i for i in items if (i['tag']==co['result_name'] or i['label']==co['result_name'])
                  and (i['kind']==co['result_type'] or co['result_type']=='plot' and i['kind'] in ('1d','2d','3d'))]
        if len(selected)!=1:
            available = [f'{item["tag"]} · {item["label"]} ({item["kind"]})'
                         for item in items if item['kind'] in ('table', '1d', '2d', '3d')]
            examples = '\n'.join(available[:8]) or '模型中没有可选结果。'
            raise COMSOLResultNotFoundError(
                f'结果 {co["result_name"]!r} 匹配到 {len(selected)} 项。\n'
                '请点击“识别模型结果或 CSV 数据列”，从下拉框选择结果（命令行可用 --list-results）。\n'
                f'可用结果示例：\n{examples}'
            )
        item=selected[0]
        log.info('Extracting result: %s [%s]',item['label'],item['tag'])
        if item['kind']=='table':
            result=call_backend(backend().extract_table,self.model,item['tag'],low_memory=co['low_memory'])
        else:
            with tempfile.TemporaryDirectory(prefix='comsol_pipeline_') as directory:
                result=call_backend(backend().extract_via_export,self.model,item['pg'],item['tag'],Path(directory),
                                    kind=item['kind'],low_memory=co['low_memory'])
        if result is None:
            raise COMSOLModelError(f'A could not extract {item["tag"]}; details in logs/pipeline.log.')
        df,comments=result
        # Do not sort stitched parametric sweeps into one scientifically false curve.
        if item['kind']=='1d' and len(backend().split_line_segments(df,expected=len(df.attrs.get('legend_labels',[])) or None))>1:
            raise COMSOLModelError('Concatenated parameter sweeps detected. Select/export one sweep or provide separate Y columns; processing across sweeps is blocked.')
        return normalize(df,item['label'],co['model'],comments,co.get('column_map'),
                         {'tag':item['tag'],'kind':item['kind'],'comsol_version':co['version']})

    def close(self):
        if self.client is not None and self.model is not None:
            try:
                self.client.remove(self.model)
            except Exception:
                log.warning('Could not unload COMSOL model.',exc_info=True)
        self.model=None
        # MPh owns its engine/server lifecycle and cleans up at process exit.
