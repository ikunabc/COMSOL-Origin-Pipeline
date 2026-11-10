"""OriginLab originpro API; verified LabTalk used for unwrapped properties.

See docs/API_AUDIT.md for the exact inspected source and reference pages.
"""
import logging
from pathlib import Path
import shutil
import tempfile
import time
from ..config import (GRAPH_TYPE_MAP, LINE_STYLE_MAP, SYMBOL_MAP, COLOR_MAP,
                      LEGEND_POSITION_MAP)
from ..exceptions import OriginConnectionError, OriginPlotError, OriginExportError

log=logging.getLogger('pipeline')


def quoted(value):
    # Filesystem strings only, not arbitrary LabTalk statements.
    text=str(value).replace('\\','/')
    if any(ch in text for ch in ('"','\n','\r','%','$')):
        raise OriginExportError('Origin path contains unsupported LabTalk substitution/control characters.')
    return '"'+text+'"'


def export_command(config, directory, filename):
    e=config['export']
    size=config['plot']['size']
    fmt='tif' if e['format']=='tiff' else e['format']
    if e['transparent']:
        # Origin 2025b XFC/expG2img.XFC: tb sets @GET; res is DPI.
        return (f'expG2img type:={fmt} name:={quoted(filename)} path:={quoted(directory)} '
                f'tb:=1 res:={e["dpi"]};')
    cmd=(f'expGraph -sw type:={fmt} filename:={quoted(filename)} path:={quoted(directory)} '
         'overwrite:=replace tr.Margin:=2 ')
    if fmt=='pdf':
        # PDF is vector. Size is set on the graph page, no claimed raster DPI.
        cmd+='tr1.Unit:=0 tr1.Width:='+str(size['width']/e['dpi'])
    else:
        cmd+=(f'tr1.Unit:=2 tr1.Width:={size["width"]} '
              f'tr2.{fmt.upper()}.DotsPerInch:={e["dpi"]} '
              f'tr2.{fmt.upper()}.BitsPerPixel:="24-bit Color"')
    return cmd+';'


class OriginAdapter:
    def __init__(self,config):
        self.config=config
        self.op=None
        self.connected=False
        self.success=False
        self._project_staging=[]

    def connect(self):
        log.info('Connecting to Origin...')
        stage='加载 originpro'
        try:
            import originpro as op
            self.op=op
            stage='启动或连接 Origin 实例'
            # Default external originpro creates a private Application.
            # detach only releases any automation reference, never clears a project.
            if self.config['origin']['new_instance']:
                op.detach()
            else:
                op.attach()
            op.set_show(self.config['origin']['visible'])
            stage='读取 Origin 版本'
            version=op.lt_float('@V')
            stage='检查 Origin 版本'
            if not 10.1 <= version < 10.3:
                raise RuntimeError(f'检测到 @V={version}，支持 Origin 2024/2024b/2025/2025b。')
            self.connected=True
            log.info('Origin connected: @V=%s',version)
        except Exception as exc:
            log.exception('Origin 连接失败：%s',stage)
            if self.op is not None:
                try:
                    self.op.detach()
                except Exception:
                    log.warning('无法释放 Origin 连接。',exc_info=True)
            details=[]
            error=exc
            seen=set()
            while error is not None and id(error) not in seen:
                seen.add(id(error))
                details.append(f'{type(error).__name__}: {str(error).strip() or repr(error)}')
                error=error.__cause__ or (None if error.__suppress_context__ else error.__context__)
            detail='\n'.join(details)
            raise OriginConnectionError(f'{stage}失败：{detail}') from exc

    def create_workbook(self,dataset):
        log.info('Creating workbook...')
        book=self.op.new_book('w')
        if book is None:
            raise OriginPlotError('Origin could not create a workbook.')
        book.lname=dataset.name
        return book

    def write_dataframe(self,dataset):
        try:
            book=self.create_workbook(dataset)
            sheet=book[0]
            g=self.config['plot']
            # X first, followed by selected Ys, then remaining original columns.
            order=[g['x_column']]+g['y_columns']
            order += [c for c in dataset.data if c not in order]
            log.info('Importing DataFrame...')
            sheet.from_df(dataset.data[order],addindex=False)
            sheet.cols_axis('x'+'y'*(len(order)-1),repeat=False)
            for i,col in enumerate(order):
                sheet.set_label(i,dataset.metadata.get('long_names',{}).get(col,col),type='L')
                sheet.set_label(i,dataset.units.get(col,''),type='U')
                comment=[dataset.metadata.get('original_headers',{}).get(col,col),
                         f'Source: {dataset.source}']
                comment+=dataset.metadata.get('comments',[])+dataset.metadata.get('processing',[])
                sheet.set_label(i,'\n'.join(comment),type='C')
            return book
        except OriginPlotError:
            raise
        except Exception as exc:
            raise OriginPlotError(f'Cannot write Origin workbook: {exc}') from exc

    def add_plot(self,layer,sheet,coly,colx=0):
        plot=layer.add_plot(sheet,coly=coly,colx=colx,type=GRAPH_TYPE_MAP[self.config['plot']['graph_type']])
        if plot is None:
            raise OriginPlotError(f'Origin rejected plot for Y column {coly}.')
        return plot

    def apply_style(self,plots):
        style=self.config['plot']['style']
        for i,plot in enumerate(plots):
            color=style['colors'][i%len(style['colors'])]
            color=COLOR_MAP.get(color,color)
            plot.color=tuple(int(color[j:j+2],16) for j in (1,3,5))
            plot.set_cmd(f'-wp {style["line_width"]}',f'-d {LINE_STYLE_MAP[style["line_styles"][i%len(style["line_styles"])]]}')
            if self.config['plot']['graph_type'] in ('scatter','line_symbol'):
                plot.symbol_kind=SYMBOL_MAP[style['symbol']]
                plot.symbol_size=style['symbol_size']

    def configure_axes(self,layer):
        g=self.config['plot']
        font=g['font']
        for name,labelname in [('x','xb'),('y','yl')]:
            axis=layer.axis(name)
            c=g['axis'][name]
            axis.scale=c['scale']
        layer.rescale()
        for name,labelname in [('x','xb'),('y','yl')]:
            axis=layer.axis(name)
            c=g['axis'][name]
            axis.set_limits(*(None if c[k]=='auto' else c[k] for k in ('min','max','major_step')))
            axis.title=c['title']+(f' ({c["unit"]})' if c['unit'] else '')
            layer.lt_exec(f'{labelname}.font=font({font["family"]}); {labelname}.fsize={font["axis_title_size"]}; '
                             f'layer.{name}.label.font=font({font["family"]}); layer.{name}.label.pt={font["tick_label_size"]};')

    def configure_legend(self,layer,dataset):
        g=self.config['plot']
        c=g['legend']
        layer.lt_exec('legend -r;')
        legend=layer.label('legend')
        if legend is None:
            raise OriginPlotError('Origin did not create a legend.')
        if not c['show']:
            legend.remove()
            return
        labels=c['labels'] or [dataset.metadata.get('long_names',{}).get(y,y) for y in g['y_columns']]
        legend.text='\n'.join(f'\\l({i}) {label}' for i,label in enumerate(labels,1))
        right,top=LEGEND_POSITION_MAP[c['position']]
        # GObject left/top/width/height are physical page coordinates (printer dots).
        layer.lt_exec(f'legend.font=font({g["font"]["family"]}); legend.fsize={g["font"]["legend_size"]}; '
                         f'legend.background={int(c["frame"])}; legend.attach=0;')
        pad=g['layout']['legend_inset']
        x=f'(layer.left+layer.width)*page.width/100-legend.width-page.width*{pad}/100' if right else f'layer.left*page.width/100+page.width*{pad}/100'
        y=f'layer.top*page.height/100+page.height*{pad}/100' if top else f'(layer.top+layer.height)*page.height/100-legend.height-page.height*{pad}/100'
        layer.lt_exec(f'legend.left={x}; legend.top={y};')

    def create_graph(self,book,dataset,column_indices=None):
        log.info('Creating graph...')
        try:
            g=self.config['plot']
            graph=self.op.new_graph(template=g['template']) if g['template'] else self.op.new_graph(template='Origin')
            if graph is None:
                raise OriginPlotError('Origin could not create graph/template.')
            graph.lname=dataset.name
            graph.activate()
            layer=graph[0]
            # Physical page size: configured pixels / DPI. Origin page width is printer dots.
            width=g['size']['width']/self.config['export']['dpi']
            height=g['size']['height']/self.config['export']['dpi']
            graph.lt_exec(f'page.kar=0; page.width=page.resx*{width}; page.height=page.resy*{height};')
            layout=g['layout']
            layer.lt_exec(f'layer.unit=1; layer.left={layout["left"]}; layer.top={layout["top"]}; '
                          f'layer.width={layout["width"]}; layer.height={layout["height"]};')
            indices=column_indices or {col:i for i,col in enumerate([g['x_column']]+g['y_columns'])}
            plots=[self.add_plot(layer,book[0],indices[col],indices[g['x_column']]) for col in g['y_columns']]
            self.apply_style(plots)
            self.configure_axes(layer)
            self.configure_legend(layer,dataset)
            if g['title']:
                title=layer.add_label(g['title'])
                title.set_float('fsize',g['font']['title_size'])
                title.set_int('font',int(self.op.lt_float(f'font({g["font"]["family"]})')))
                title.set_int('attach',0)
                title.set_float('left',(self.op.lt_float('page.width')-title.get_float('width'))/2)
                title.set_float('top',self.op.lt_float('page.height')*layout['title_gap']/100)
            return graph
        except OriginPlotError:
            raise
        except Exception as exc:
            raise OriginPlotError(f'Origin graph/style operation failed: {exc}') from exc

    def export_graph(self,graph):
        e=self.config['export']
        if not e['enable']:
            return None
        destination=e['directory']/(e['filename']+'.'+e['format'])
        log.info('Exporting %s%s...',e['format'].upper(),'' if e['format']=='pdf' else f' at {e["dpi"]} DPI')
        try:
            destination.parent.mkdir(parents=True,exist_ok=True)
            # Short ASCII staging paths avoid COM/MAX_PATH/Unicode export problems.
            with tempfile.TemporaryDirectory(prefix='origin_export_') as folder:
                directory=Path(folder)
                graph.activate()
                self.op.set_lt_str('__LASTEXP','')
                command=export_command(self.config,directory,'figure')
                log.debug('Origin export command: %s',command)
                previous_get=self.op.lt_float('@GET')
                try:
                    self.op.set_lt_var('@GET',int(e['transparent']))
                    graph.lt_exec(command)
                finally:
                    self.op.set_lt_var('@GET',previous_get)
                ext='tif' if e['format']=='tiff' else e['format']
                staged=directory/('figure.'+ext)
                if not staged.is_file() or staged.stat().st_size==0:
                    raise OriginExportError('Origin did not produce a nonempty figure; see log for export command.')
                shutil.copy2(staged,destination)
            return destination
        except OriginExportError:
            raise
        except Exception as exc:
            raise OriginExportError(f'Figure export failed: {exc}') from exc

    def save_project(self):
        if not self.config['origin']['save_project']:
            return None
        path=self.config['origin']['project_file']
        log.info('Saving Origin project...')
        try:
            path.parent.mkdir(parents=True,exist_ok=True)
            # COM automation can have narrower directory access than this process.
            # Save to a fresh staging file, then atomically publish from Python.
            staging=tempfile.TemporaryDirectory(prefix='origin_project_',ignore_cleanup_errors=True)
            self._project_staging.append(staging)
            folder=staging.name
            staged=Path(folder)/'project.opju'
            previous=self.op.lt_float('@SDO')
            try:
                self.op.set_lt_var('@SDO',1)
                if not self.op.save(str(staged)):
                    raise OriginExportError(f'Origin rejected staged project save for: {path}')
            finally:
                self.op.set_lt_var('@SDO',previous)
            for _ in range(30):
                if staged.is_file() and staged.stat().st_size:
                    break
                time.sleep(0.1)
            else:
                raise OriginExportError(f'No nonempty staged project appeared for: {path}')
            with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.origin-',suffix='.opju',delete=False) as handle:
                pending=Path(handle.name)
            try:
                shutil.copyfile(staged,pending)
                pending.replace(path)
            finally:
                pending.unlink(missing_ok=True)
            return path
        except OriginExportError:
            raise
        except Exception as exc:
            raise OriginExportError(f'Cannot save project: {exc}') from exc

    def close(self):
        if self.connected:
            try:
                if self.success and self.config['origin']['new_instance'] and self.config['origin']['close_on_finish']:
                    self.op.exit()
                else:
                    if not self.success:
                        self.op.set_show(True)
                    self.op.detach()
            except Exception:
                log.warning('Could not release Origin connection.',exc_info=True)
            self.connected=False

        for staging in self._project_staging:
            staging.cleanup()
        self._project_staging.clear()
