"""Add explicit native-name/physical-source separation to the shared registry."""
import ast


def parameterize(name, raw):
    if name != 'civ6rl.native_gameplay_script_registry':
        return raw

    def change(before, after):
        nonlocal raw
        if raw.count(before) != 1:
            raise ValueError('Script wire registry extraction boundary changed: ' + before[:110])
        raw = raw.replace(before, after)

    change('from typing import Iterable',
           'from typing import Iterable\nfrom civ6_host.runtime.script_wire_paths import encode_wire_path, selected_wire_paths, bind_wire_sources')
    change('def __init__(self, asset_roots: Iterable[Path], *, selected_scripts: Iterable[GameplayScriptEntry] | None):',
           'def __init__(self, asset_roots: Iterable[Path], *, selected_scripts: Iterable[GameplayScriptEntry] | None, wire_paths: Iterable[str] | None=None):')
    change('        selected = tuple(selected_scripts)',
           '        selected = tuple(selected_scripts)\n        selected_names = selected_wire_paths(wire_paths, len(selected))\n        names = []')
    change('        for entry in selected:', '        for index, entry in enumerate(selected):')
    change("            encoded = str(path).encode('utf-16-le', 'strict')",
           "            name = str(path) if selected_names is None else selected_names[index]\n            encoded = encode_wire_path(name)\n            names.append(name)")
    change('        self._paths = tuple(paths)', '        self._paths = tuple(paths)\n        self._wire_paths = tuple(names)\n        bind_wire_sources(self._paths, self._wire_paths)')
    change('    def close(self) -> None:',
           '''    @property
    def wire_paths(self) -> tuple[str, ...]:
        """Exact strings returned to native count/index consumers, in order."""
        self._ensure_open()
        return self._wire_paths

    def close(self) -> None:''')
    change('        self._paths = ()', '        self._paths = ()\n        self._wire_paths = ()')
    return ast.unparse(ast.parse(raw)) + '\n'
