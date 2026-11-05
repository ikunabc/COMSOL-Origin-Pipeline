"""Named parameter presets stored next to the active configuration."""
import json
import os
from pathlib import Path
import tempfile


class PresetStore:
    def __init__(self, config_path):
        self.path = Path(config_path).parent / 'parameter_presets.json'

    def _read(self):
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if data.get('version') != 1 or not isinstance(data.get('presets'), dict):
                raise ValueError('不支持的预设格式')
            presets = {}
            for name, rows in data['presets'].items():
                self._name(name)
                if not isinstance(rows, list) or not rows:
                    raise ValueError('预设内容为空')
                updates = {}
                for row in rows:
                    if (not isinstance(row, list) or len(row) != 3
                            or not all(isinstance(v, str) and v for v in row[:2])):
                        raise ValueError('预设字段格式错误')
                    key = tuple(row[:2])
                    if key in updates:
                        raise ValueError('预设包含重复字段')
                    updates[key] = row[2]
                presets[name] = updates
            return presets
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError(f'无法读取参数预设，原文件已保留：{exc}') from exc

    @staticmethod
    def _name(name):
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
            raise ValueError('请填写 1–80 个字符的预设名称。')
        return name.strip()

    def names(self):
        return sorted(self._read(), key=str.casefold)

    def load(self, name):
        return self._read()[self._name(name)]

    def save(self, name, updates):
        name = self._name(name)
        presets = self._read()
        presets[name] = updates
        self._write(presets)

    def delete(self, name):
        presets = self._read()
        del presets[self._name(name)]
        self._write(presets)

    def _write(self, presets):
        data = {'version': 1, 'presets': {
            name: [[group, key, value] for (group, key), value in updates.items()]
            for name, updates in presets.items()}}
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                    dir=self.path.parent, suffix='.json', delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write('\n')
            os.replace(temporary, self.path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
