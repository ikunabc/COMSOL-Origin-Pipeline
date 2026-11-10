import sys
from types import SimpleNamespace

import pytest

from src.adapters.origin_adapter import OriginAdapter
from src.exceptions import OriginConnectionError


def test_origin_2024_connection(config, monkeypatch):
    module = SimpleNamespace(detach=lambda: None, set_show=lambda _: None,
                             lt_float=lambda _: 10.1)
    monkeypatch.setitem(sys.modules, 'originpro', module)
    adapter = OriginAdapter(config)
    adapter.connect()
    assert adapter.connected


def test_origin_connection_reports_original_failure(config, monkeypatch):
    calls = []

    def detach():
        calls.append(True)
        if len(calls) > 1:
            raise RuntimeError('cleanup failure')

    def set_show(visible):
        raise OSError('COM class not registered')

    module = SimpleNamespace(detach=detach, set_show=set_show)
    monkeypatch.setitem(sys.modules, 'originpro', module)
    adapter = OriginAdapter(config)
    with pytest.raises(OriginConnectionError, match='COM class not registered'):
        adapter.connect()
