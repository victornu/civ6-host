"""Hash-pinned local copies of the official movement UI functions.

The returned Lua chunk defines local functions only. Callers may prepend their
own verified local bindings for the UI globals listed in UI_GLOBAL_DEPENDENCIES.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
from pathlib import Path
import re
_UI_ROOT = _resolve_resource_path(Path("C:\\Program Files (x86)\\Steam\\steamapps\\common\\Sid Meier's Civilization VI\\Base\\Assets\\UI"))
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_movement_ui_source.py')))).resolve().parents[1]
_PINS = {'WorldInput.lua': '05be449b00f0fc7bed30d23543e31b43f619650ede2da061131f1967b6d32fa8', 'Civ6Common.lua': '6e422dfed29d6e40507b14e234fc84c7647f450200df17dc2383e952a67a371f'}
_EVIDENCE_PINS = {'evidence/native-unit-movement-ui-source.json': 'f1b3d97cce5a2e3d77933464b89c5465d267d5fc5ee9ac6e1cc5666803d56f26', 'evidence/native-move-path-contract.json': '9bb8e252ac99249b2e1da5370a74d4983dd8ebd0e2db632e3fcda74312e49889', 'evidence/native-unit-operation-api.json': '905f1bacd835e72894f8ad46a961ac9d2a1838999c861e4748eb7986c5a6642a', 'evidence/native-unit-action-route.json': '69454efb375425864b82bdb703eeb1e233c6e8107d30e334ab25226ccab3c2e6'}
_FUNCTIONS = (('WorldInput.lua', 'IsPlotPathRestrictedForUnit'), ('WorldInput.lua', 'RealizeMovementPath'), ('Civ6Common.lua', 'MoveUnitToPlot'), ('Civ6Common.lua', 'RequestMoveOperation'))
_DECL = re.compile('^(?:local\\s+)?function\\s+([A-Za-z_][A-Za-z_0-9]*)\\s*\\(')
UI_GLOBAL_DEPENDENCIES = ('GameInfo', 'UI', 'UILens', 'UnitManager', 'Map', 'PlayersVisibility', 'UnitOperationTypes', 'UnitOperationMoveModifiers', 'UnitOperationResults', 'Units', 'MapLayers', 'CombatManager', 'LuaEvents', 'WarTypes', 'table', 'pairs', 'ipairs', 'm_constrainToPlotID', 'm_kTutorialUnitMoveRestrictions', 'm_kTutorialUnitHexRestrictions', 'm_isPlotFlaggedRestricted', 'm_cachedPathUnit', 'm_cachedPathPlotId', 'm_previousTurnsCount', 'g_MovementPath', 'g_Numbers', 'g_AttackRange', 'IsUnitTypeAllowedToMoveToPlot', 'IsPlotPathRestrictedForUnit')

def _extract(path: Path, name: str, expected_sha256: str) -> tuple[bytes, int, int]:
    raw = _resolve_resource_path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise RuntimeError(f'Pinned official UI source changed: {path.name}')
    text = raw.decode('utf-8-sig')
    lines = text.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.startswith(f'function {name}(') or line.startswith(f'local function {name}(')]
    if len(starts) != 1:
        raise RuntimeError(f'Expected one official function anchor for {name}')
    first = starts[0]
    end = next((i for i in range(first + 1, len(lines)) if (m := _DECL.match(lines[i])) is not None), len(lines))
    selected = lines[first:end]
    while selected and (not selected[-1].strip() or selected[-1].lstrip().startswith('--')):
        selected.pop()
    body = ''.join(selected).rstrip() + '\n'
    if not body.rstrip().endswith('end'):
        raise RuntimeError(f'Official function boundary is incomplete: {name}')
    if name == 'RequestMoveOperation':
        body = re.sub('^function RequestMoveOperation\\(', 'RequestMoveOperation = function(', body, count=1)
    else:
        body = re.sub('^function ' + re.escape(name) + '\\(', 'local function ' + name + '(', body, count=1)
    return (body.encode('utf-8'), first + 1, first + len(selected))

def verified_function_sources(*, world_input_path: Path | None=None, common_path: Path | None=None) -> dict[str, tuple[bytes, int, int]]:
    verify_source_evidence()
    paths = {'WorldInput.lua': world_input_path or _UI_ROOT / 'WorldInput.lua', 'Civ6Common.lua': common_path or _UI_ROOT / 'Civ6Common.lua'}
    return {name: _extract(paths[file_name], name, _PINS[file_name]) for file_name, name in _FUNCTIONS}

def verify_source_evidence() -> None:
    verified_files()

def verified_files() -> dict[Path, str]:
    """Return and verify the official UI and native-proof closure dependencies."""
    result = {_UI_ROOT / name: expected for name, expected in _PINS.items()}
    result.update({_ROOT / relative: expected for relative, expected in _EVIDENCE_PINS.items()})
    for path, expected in result.items():
        if hashlib.sha256(_resolve_resource_path(path).read_bytes()).hexdigest() != expected:
            raise RuntimeError('Pinned movement source changed: ' + str(path))
    return result

def functions_source() -> bytes:
    """Return exact pinned function bodies localized in a Lua chunk."""
    funcs = verified_function_sources()
    ordered = ('IsPlotPathRestrictedForUnit', 'RealizeMovementPath', 'MoveUnitToPlot', 'RequestMoveOperation')
    pieces = [b'local RequestMoveOperation\n']
    pieces.extend((funcs[name][0] + b'\n' for name in ordered))
    return b''.join(pieces)

def source_manifest() -> dict:
    funcs = verified_function_sources()
    return {'schema': 'civ6rl.native_movement_ui_source.v1', 'native_execution': False, 'files': {name: {'path': str(_UI_ROOT / name), 'sha256': pin} for name, pin in _PINS.items()}, 'functions': {name: {'file': file_name, 'first_line': line1, 'last_line': line2, 'extracted_sha256': hashlib.sha256(source).hexdigest()} for (file_name, name), (source, line1, line2) in zip(_FUNCTIONS, (funcs[n] for _, n in _FUNCTIONS))}, 'dependencies': {'IsPlotPathRestrictedForUnit': ['IsUnitTypeAllowedToMoveToPlot', 'GameInfo', 'table', 'ipairs', 'm_constrainToPlotID', 'm_kTutorialUnitMoveRestrictions', 'm_kTutorialUnitHexRestrictions', 'm_isPlotFlaggedRestricted'], 'RealizeMovementPath': list(UI_GLOBAL_DEPENDENCIES), 'MoveUnitToPlot': ['UnitOperationTypes', 'PlayersVisibility', 'CombatManager', 'RequestMoveOperation'], 'RequestMoveOperation': ['GameInfo', 'UnitOperationTypes', 'UnitOperationMoveModifiers', 'UnitManager']}}
