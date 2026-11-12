"""Validate static configuration before importing COMSOL or Origin."""
from pathlib import Path
import math
import re
import tempfile
import tomllib
import shutil
from .exceptions import ConfigError

GRAPH_TYPE_MAP = {'line': 'l', 'line_symbol': 'y', 'scatter': 's', 'column': 'c'}
LINE_STYLE_MAP = {'solid': 0, 'dash': 1, 'dot': 2, 'dash_dot': 3}
SYMBOL_MAP = {'square': 1, 'circle': 2, 'triangle': 3, 'diamond': 4, 'cross': 7}
COLOR_MAP = {'black': '#000000', 'red': '#FF0000', 'blue': '#0000FF', 'green': '#008000'}
LEGEND_POSITION_MAP = {'top_left': (0, 1), 'top_right': (1, 1),
                       'bottom_left': (0, 0), 'bottom_right': (1, 0)}


def fail(key, message):
    raise ConfigError(f'Configuration error: {key} {message}')


def numeric(value):
    return type(value) in (int, float) and math.isfinite(value)


def positive(key, value, integer=False):
    if not numeric(value) or value <= 0 or (integer and type(value) is not int):
        fail(key, 'must be a positive ' + ('integer.' if integer else 'number.'))


def safe_path(path):
    p = Path(path)
    for part in p.parts[1:]:
        if re.search(r'[<>:"|?*\x00-\x1f]', part) or part.endswith((' ', '.')):
            fail('path', f'contains an invalid Windows component: {part!r}')
        if part.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:
            fail('path', f'contains a reserved Windows filename: {part!r}')
    return p


def load_config(path='config.toml', check_input=True, create_outputs=True):
    path = Path(path).resolve()
    template=path.with_name('config.default.toml')
    if path.name=='config.toml' and not path.exists() and template.is_file():
        shutil.copyfile(template,path)
    try:
        with path.open('rb') as stream:
            c = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f'Cannot read configuration {path}: {exc}') from exc
    return prepare_config(c, path, check_input, create_outputs)


def prepare_config(c, path, check_input=True, create_outputs=True):
    """Validate and resolve an independent, in-memory configuration."""
    path = Path(path).resolve()
    try:
        validate(c)
    except (KeyError, TypeError, AttributeError) as exc:
        raise ConfigError(f'Configuration error: missing or invalid field {exc}') from exc
    c['_root'] = path.parent
    c['_config_path'] = path
    for section, keys in {'paths':['output_dir','processed_file'], 'comsol':['model','csv'],
                          'origin':['project_file'], 'export':['directory']}.items():
        for key in keys:
            if key in c[section]:
                c[section][key] = safe_path((path.parent / c[section][key]).resolve())
    if c['plot']['template']:
        c['plot']['template'] = str((path.parent / c['plot']['template']).resolve())
        if not Path(c['plot']['template']).is_file():
            fail('[plot].template', 'does not exist.')
    source = c['comsol']['model' if c['comsol']['mode']=='mph' else 'csv']
    if check_input and not source.is_file():
        fail('[comsol]', f'input file does not exist: {source}')
    if create_outputs:
        destinations = [c['paths']['output_dir'], c['paths']['processed_file'].parent]
        if c['export']['enable']:
            destinations.append(c['export']['directory'])
        if c['origin']['save_project']:
            destinations.append(c['origin']['project_file'].parent)
        try:
            for directory in destinations:
                directory.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryFile(dir=directory):
                    pass
        except OSError as exc:
            raise ConfigError(f'Output directory is not writable: {exc}') from exc
    return c


def validate(c):
    co,p,o,g,e = (c[s] for s in ('comsol','processing','origin','plot','export'))
    for section, keys in {'paths':['output_dir','processed_file'],
                          'comsol':['mode','version','model','csv','result_type','result_name','csv_format','encoding'],
                          'plot':['graph_type','x_column','title','template']}.items():
        for k in keys:
            if not isinstance(c[section][k], str):
                fail(f'[{section}].{k}', 'must be a string.')
    for section, keys in {'processing':['drop_nan','sort','enable_smoothing','enable_interpolation'],
                          'origin':['visible','new_instance','save_project','close_on_finish'],
                          'comsol':['low_memory'], 'export':['enable','transparent'],
                          'plot.legend':['show','frame']}.items():
        target = g['legend'] if section=='plot.legend' else c[section]
        for k in keys:
            if type(target[k]) is not bool:
                fail(f'[{section}].{k}', 'must be boolean.')
    choices = [('[comsol].mode',co['mode'],('mph','csv')),
               ('[comsol].result_type',co['result_type'],('table','plot','1d','2d','3d')),
               ('[comsol].csv_format',co['csv_format'],('auto','standard','native','backend')),
               ('[processing].smoothing_method',p['smoothing_method'],('none','savgol','moving_average','median')),
               ('[processing].interpolation_method',p['interpolation_method'],('none','linear','cubic','pchip')),
               ('[plot].graph_type',g['graph_type'],GRAPH_TYPE_MAP),
               ('[plot.style].symbol',g['style']['symbol'],SYMBOL_MAP),
               ('[plot.legend].position',g['legend']['position'],LEGEND_POSITION_MAP),
               ('[export].format',e['format'],('png','tiff','pdf'))]
    for key,value,allowed in choices:
        if value not in allowed:
            fail(key, f'must be one of {list(allowed)}.')
    if not co['result_name'].strip() and co['mode']=='mph':
        fail('[comsol].result_name','must not be empty.')
    if not g['x_column'].strip() or not isinstance(g['y_columns'],list) or not g['y_columns']:
        fail('[plot]', 'requires x_column and nonempty y_columns.')
    if any(not isinstance(y,str) or not y.strip() for y in g['y_columns']):
        fail('[plot].y_columns','must contain nonempty strings.')
    if len(set([g['x_column']]+g['y_columns'])) != 1+len(g['y_columns']):
        fail('[plot]', 'X and Y column names must be distinct.')
    positive('[processing].window_length',p['window_length'],True)
    if p['window_length'] % 2 != 1:
        fail('[processing].window_length','must be an odd integer.')
    if type(p['polyorder']) is not int or not 0 <= p['polyorder'] < p['window_length']:
        fail('[processing].polyorder','must satisfy 0 <= polyorder < window_length.')
    positive('[processing].interpolation_points',p['interpolation_points'],True)
    if p['interpolation_points']<2:
        fail('[processing].interpolation_points','must be at least 2.')
    style=g['style']
    for key in ('colors','line_styles'):
        if not isinstance(style[key],list) or not style[key]:
            fail(f'[plot.style].{key}','must be a nonempty list (cycled across Y columns).')
    for color in style['colors']:
        if not isinstance(color,str) or not (color in COLOR_MAP or re.fullmatch(r'#[0-9A-Fa-f]{6}',color)):
            fail('[plot.style].colors','requires #RRGGBB or a supported named color.')
    if any(s not in LINE_STYLE_MAP for s in style['line_styles']):
        fail('[plot.style].line_styles',f'must use {list(LINE_STYLE_MAP)}.')
    for key in ('line_width','symbol_size'):
        positive(f'[plot.style].{key}',style[key])
    for ax in ('x','y'):
        axis = g['axis'][ax]
        if axis['scale'] not in ('linear','log10'):
            fail(f'[plot.axis.{ax}].scale','must be linear or log10.')
        for key in ('min','max','major_step'):
            v=axis[key]
            if v!='auto' and not numeric(v):
                fail(f'[plot.axis.{ax}].{key}','must be finite numeric or "auto".')
            if v!='auto' and (key=='major_step' or axis['scale']=='log10') and v<=0:
                fail(f'[plot.axis.{ax}].{key}','must be positive.')
        if axis['min']!='auto' and axis['max']!='auto' and axis['min']>=axis['max']:
            fail(f'[plot.axis.{ax}]','min must be less than max.')
    labels=g['legend']['labels']
    if not isinstance(labels,list) or any(not isinstance(v,str) for v in labels) or (labels and len(labels)!=len(g['y_columns'])):
        fail('[plot.legend].labels','must be empty or contain one string per Y column.')
    if not isinstance(g['font']['family'],str) or not re.fullmatch(r'[\w \-]+',g['font']['family']):
        fail('[plot.font].family','must be a nonempty font name.')
    for k in ('axis_title_size','tick_label_size','legend_size','title_size'):
        positive(f'[plot.font].{k}',g['font'][k])
    for k in ('width','height'):
        positive(f'[plot.size].{k}',g['size'][k],True)
    layout=g['layout']
    for k in ('left','top','width','height','legend_inset','title_gap'):
        if not numeric(layout[k]) or not 0 <= layout[k] < 100:
            fail(f'[plot.layout].{k}','must be numeric in [0,100).')
    if layout['width']<=0 or layout['height']<=0 or layout['left']+layout['width']>100 or layout['top']+layout['height']>100:
        fail('[plot.layout]','layer must have positive size and fit within the page.')
    if g['size']['unit']!='pixel':
        fail('[plot.size].unit','currently supports pixel only.')
    positive('[export].dpi',e['dpi'],True)
    if e['transparent'] and e['format'] not in ('png','tiff'):
        fail('[export].transparent','is supported only for PNG and TIFF.')
    if not isinstance(e['filename'],str) or not e['filename'] or re.search(r'[<>:"/\\|?*\x00-\x1f%$]',e['filename']):
        fail('[export].filename','must be a plain filename stem.')
    if not isinstance(o['project_file'],str) or Path(o['project_file']).suffix.lower()!='.opju':
        fail('[origin].project_file','must end in .opju.')
    for k,v in co.get('column_map',{}).items():
        if not isinstance(k,str) or not isinstance(v,str) or not v.strip():
            fail('[comsol.column_map]','requires nonempty string column names.')
