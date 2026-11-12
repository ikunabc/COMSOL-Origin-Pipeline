from pathlib import Path

import pytest
from src.adapters.origin_adapter import OriginAdapter
from src.exceptions import OriginExportError


class Origin:
    def __init__(self, success=True):
        self.success = success
        self.saved = None
        self.variables = []

    def lt_float(self, name):
        return 0

    def set_lt_var(self, name, value):
        self.variables.append((name, value))

    def save(self, path):
        self.saved = Path(path)
        if self.success:
            self.saved.write_bytes(b"new-project")
        return self.success


def test_save_stages_and_replaces_target(tmp_path):
    target = tmp_path / "nested" / "project.opju"
    adapter = OriginAdapter({"origin": {"save_project": True, "project_file": target}})
    adapter.op = Origin()
    assert adapter.save_project() == target
    assert target.read_bytes() == b"new-project"
    assert adapter.op.saved.parent != target.parent
    adapter.close()
    assert not adapter.op.saved.exists()
    assert adapter.op.variables == [("@SDO", 1), ("@SDO", 0)]


def test_failed_save_preserves_existing_project(tmp_path):
    target = tmp_path / "project.opju"
    target.write_bytes(b"old-project")
    adapter = OriginAdapter({"origin": {"save_project": True, "project_file": target}})
    adapter.op = Origin(False)
    with pytest.raises(OriginExportError):
        adapter.save_project()
    assert target.read_bytes() == b"old-project"
    assert adapter.op.variables[-1] == ("@SDO", 0)
