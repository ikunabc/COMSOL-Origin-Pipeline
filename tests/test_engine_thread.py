import threading
from src.integrated_ui import Task
from src.adapters import comsol_adapter


def test_repeated_model_tasks_share_engine_thread(monkeypatch):
    calls=[]
    class Adapter:
        def __init__(self,config): pass
        def list_available_results(self):
            calls.append(('read',threading.get_ident()))
            if len(calls)==1: raise RuntimeError('first read failed')
            return []
        def close(self): calls.append(('close',threading.get_ident()))
    monkeypatch.setattr(comsol_adapter,'COMSOLAdapter',Adapter)
    for _ in range(3):
        task=Task({},'list')
        task.start()
        assert task.wait(5000)
    assert len(calls)==6
    assert len({ident for _,ident in calls})==1
    assert calls[0][1]!=threading.get_ident()


def test_read_then_plot_share_engine_thread(monkeypatch):
    from src import pipeline
    ids=[]
    class Adapter:
        def __init__(self,config): pass
        def list_available_results(self): ids.append(threading.get_ident()); return []
        def close(self): pass
    monkeypatch.setattr(comsol_adapter,'COMSOLAdapter',Adapter)
    def run(config):
        ids.append(threading.get_ident())
        return None,'figure','project'
    monkeypatch.setattr(pipeline,'run',run)
    for action in ('list','run','list','run'):
        task=Task({},action);task.start();assert task.wait(5000)
    assert len(ids)==4 and len(set(ids))==1
