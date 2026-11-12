import json
import logging
from copy import deepcopy
from .adapters.comsol_adapter import COMSOLAdapter
from .adapters.process_adapter import process
from .adapters.origin_adapter import OriginAdapter


def dry_run(c):
    print(json.dumps({k:v for k,v in c.items() if not k.startswith('_')},ensure_ascii=False,indent=2,default=str))
    print('DRY RUN: no COMSOL/Origin connection, data extraction or output generation.')


def list_results(c):
    if c['comsol']['mode']!='mph':
        from .exceptions import ConfigError
        raise ConfigError('--list-results requires [comsol].mode = "mph".')
    adapter=COMSOLAdapter(c)
    try:
        for item in adapter.list_available_results():
            print(f'{item["kind"]:8s} {item["tag"]:16s} {item["label"]}')
    finally:
        adapter.close()


def write_processed(dataset,c):
    path=c['paths']['processed_file']
    dataset.data.to_csv(path,index=False,encoding='utf-8-sig')
    path.with_suffix('.metadata.json').write_text(json.dumps({
        'name':dataset.name,'source':dataset.source,'variables':dataset.variables,
        'units':dataset.units,'metadata':dataset.metadata},ensure_ascii=False,indent=2,default=str),encoding='utf-8')


def run(c):
    log=logging.getLogger('pipeline')
    comsol=COMSOLAdapter(c)
    origin=OriginAdapter(c)
    try:
        dataset=comsol.extract_dataset()
        dataset=process(dataset,c)
        write_processed(dataset,c)
        origin.connect()
        book=origin.write_dataframe(dataset)
        graph=origin.create_graph(book,dataset)
        figure=origin.export_graph(graph)
        project=origin.save_project()
        origin.success=True
        log.info('Pipeline completed. Figure: %s; Project: %s',figure,project)
        return dataset,figure,project
    finally:
        origin.close()
        comsol.close()


def run_batch(configs):
    """Create one graph per snapshot in one Origin session, then save once."""
    if not configs:
        raise ValueError('请先添加至少一张待出图。')
    origin=OriginAdapter(configs[0])
    previous_source=None
    figures=[]
    try:
        for index,settings in enumerate(configs,1):
            c=deepcopy(settings)
            if len(configs)>1:
                path=c['paths']['processed_file']
                c['paths']['processed_file']=path.with_stem(f'{path.stem}-{index:02d}')
                c['export']['filename']+=f'-{index:02d}'
            try:
                if c['comsol']!=previous_source:
                    adapter=COMSOLAdapter(c)
                    try:
                        raw=adapter.extract_dataset()
                    finally:
                        adapter.close()
                    previous_source=c['comsol']
                dataset=process(raw,c)
                write_processed(dataset,c)
                if index==1:
                    origin.connect()
                origin.config=c
                book=origin.write_dataframe(dataset)
                graph=origin.create_graph(book,dataset)
                graph.lname=c['plot']['title'] or f'{dataset.name} · {index}'
                figures.append(origin.export_graph(graph))
            except Exception as exc:
                raise RuntimeError(f'第 {index} 张图生成失败：{exc}') from exc
        project=origin.save_project()
        origin.success=True
        return figures,project
    finally:
        origin.close()
