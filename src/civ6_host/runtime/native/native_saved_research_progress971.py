"""Read the active saved player's native technology and civic progress.

The installed UI scripts and pinned GameCore wrapper evidence are the source
of the getter names. This module only reads the selected research item; it does
not reproduce unlock, cost, or progress rules and does not submit choices.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
import math
from pathlib import Path
from civ6_host.runtime.native import native_research_actions
SCHEMA = 'civ6rl.native_saved_research_progress971.v1'
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_saved_research_progress971.py')))).resolve().parents[1]
_ASSETS = _resolve_resource_path(Path("C:\\Program Files (x86)\\Steam\\steamapps\\common\\Sid Meier's Civilization VI\\Base\\Assets\\UI"))
_SUPPORT_REL = 'TechAndCivicSupport.lua'
_SUPPORT_SHA256 = '5cb782dac930afe89f25c76cdec26ce9331f6229611661746e361799ac5c3365'
_LAUNCHBAR_REL = 'LaunchBar.lua'
_LAUNCHBAR_SHA256 = 'f61262cfc927a5b156f5eb7c0aaa1e8750f2c545db59f2ac7ec7bf8f22d8d0cf'
_XREF_PATH = _ROOT / 'evidence/rea-phase3/research-xrefs.json'
_XREF_SHA256 = 'a2488c986f048b9b0d645a85c6ab116297caec86f0d035b00c321076b4d5fa09'
_REA_ROOT = _ROOT / 'evidence/rea-phase3'
_REA_EXTRACT_SHA256 = {'wrappers-disassembly.txt': 'e6c4872066101d6797356d90ac71eeda2bd061f6adea9762eeee7fbfbabd9ffd', '0301-culture-cost-wrapper.c': '07956396b0c39b167c186218dfe3fc0b1668a7fa8af5a239816dab7e0f970145', '0303-research-cost-wrapper.c': '08bb2f793177800ff5cd8683f97c2b8eee0264d042f2f37ea4f4eebaf4ebb029'}
_MAX_PLAYER_ID = 63
_FIELDS = {'index', 'cost', 'progress', 'remaining'}

def verify_source() -> None:
    """Verify installed getter-use Lua and the extracted, pinned Core xrefs."""
    native_research_actions.verify_source()
    support = _resolve_resource_path(_ASSETS / _SUPPORT_REL).read_bytes()
    if hashlib.sha256(support).hexdigest() != _SUPPORT_SHA256:
        raise RuntimeError('Installed research progress getter source changed')
    launchbar = _resolve_resource_path(_ASSETS / _LAUNCHBAR_REL).read_bytes()
    if hashlib.sha256(launchbar).hexdigest() != _LAUNCHBAR_SHA256:
        raise RuntimeError('Installed selected-research display source changed')
    if hashlib.sha256(_resolve_resource_path(_XREF_PATH).read_bytes()).hexdigest() != _XREF_SHA256:
        raise RuntimeError('Pinned GameCore research getter xrefs changed')
    for name, expected in _REA_EXTRACT_SHA256.items():
        if hashlib.sha256(_resolve_resource_path(_REA_ROOT / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'Pinned GameCore research extract changed: {name}')

def _player_id(value: int) -> bytes:
    if type(value) is not int or not 0 <= value <= _MAX_PLAYER_ID:
        raise ValueError('player_id must be an integer in [0, 63]')
    return str(value).encode('ascii')

def source(player_id: int) -> bytes:
    """Build a bounded Lua read for the current tech and civic only."""
    pid = _player_id(player_id)
    verify_source()
    return b'local pid=' + pid + b'\nassert(Game and type(Game.GetLocalPlayer)==\'function\' and Game.GetLocalPlayer()==pid,\n       \'research observation perspective differs from requested player\')\nassert(type(Game.GetLocalObserver)==\'function\' and Game.GetLocalObserver()==pid,\n       \'research observation observer differs from requested player\')\nlocal player=Players and Players[pid]\nassert(player~=nil,\'research player unavailable\')\nlocal techs=player:GetTechs()\nlocal culture=player:GetCulture()\nassert(techs and type(techs.GetResearchingTech)==\'function\' and\n       type(techs.GetResearchCost)==\'function\' and type(techs.GetResearchProgress)==\'function\',\n       \'native technology progress getters unavailable\')\nassert(culture and type(culture.GetProgressingCivic)==\'function\' and\n       type(culture.GetCultureCost)==\'function\' and type(culture.GetCulturalProgress)==\'function\',\n       \'native civic progress getters unavailable\')\nlocal function whole(v,label)\n  assert(type(v)==\'number\' and v==math.floor(v) and v==v and\n         v~=math.huge and v~=-math.huge, \'invalid \'..label)\n  return v\nend\nlocal turnBefore=whole(Game.GetCurrentGameTurn(),\'turn before research read\')\nlocal function finite(v,label)\n  assert(type(v)==\'number\' and v==v and v~=math.huge and v~=-math.huge,\n         \'invalid \'..label)\n  return v\nend\nlocal function row(manager,index,costMethod,progressMethod,label)\n  index=whole(index,\'current \'..label..\' index\')\n  -- The shipped chooser treats a negative current ID as no selection.\n  if index<0 then return \'{"index":null,"cost":null,"progress":null,"remaining":null}\' end\n  assert(index<=4294967295,\'out-of-range \'..label..\' index\')\n  local cost=finite(manager[costMethod](manager,index),label..\' cost\')\n  local progress=finite(manager[progressMethod](manager,index),label..\' progress\')\n  return \'{"index":\'..string.format(\'%.0f\',index)..\n    \',"cost":\'..string.format(\'%.17g\',cost)..\n    \',"progress":\'..string.format(\'%.17g\',progress)..\n    \',"remaining":\'..string.format(\'%.17g\',cost-progress)..\'}\'\nend\nlocal technology=row(techs,techs:GetResearchingTech(),\n  \'GetResearchCost\',\'GetResearchProgress\',\'technology\')\nlocal civic=row(culture,culture:GetProgressingCivic(),\n  \'GetCultureCost\',\'GetCulturalProgress\',\'civic\')\nlocal turnAfter=whole(Game.GetCurrentGameTurn(),\'turn after research read\')\nassert(turnAfter==turnBefore,\'game turn changed during research observation\')\nassert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid,\n       \'research observation perspective changed during read\')\nreturn \'{"schema":"civ6rl.native_saved_research_progress971.v1","player_id":\'..\n  string.format(\'%.0f\',pid)..\',"turn":\'..string.format(\'%.0f\',turnBefore)..\n  \',"technology":\'..technology..\',"civic":\'..civic..\'}\'\n'

def _checked_number(value, label: str, *, integer: bool=False, nonnegative: bool=False) -> int | float:
    if type(value) not in (int, float):
        raise ValueError(f'Invalid {label}')
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite or (nonnegative and value < 0):
        raise ValueError(f'Invalid {label}')
    if integer and type(value) is not int:
        raise ValueError(f'Invalid {label}')
    return value

def _parse_item(value, label: str) -> dict:
    if type(value) is not dict or set(value) != _FIELDS:
        raise ValueError(f'Malformed {label} progress row')
    if value['index'] is None:
        if any((value[key] is not None for key in ('cost', 'progress', 'remaining'))):
            raise ValueError(f'Incomplete empty {label} row')
        return dict(index=None, cost=None, progress=None, remaining=None)
    index = _checked_number(value['index'], f'{label} index', integer=True, nonnegative=True)
    if index > 4294967295:
        raise ValueError(f'Invalid {label} index')
    cost = _checked_number(value['cost'], f'{label} cost')
    progress = _checked_number(value['progress'], f'{label} progress')
    remaining = _checked_number(value['remaining'], f'{label} remaining')
    if remaining != cost - progress:
        raise ValueError(f'Inconsistent {label} cost/progress/remaining')
    return dict(index=index, cost=cost, progress=progress, remaining=remaining)

def parse(raw: bytes | str, player_id: int) -> dict:
    """Parse one JSON response, refusing schema, actor, and value drift."""
    expected = _player_id(player_id)
    if type(raw) is bytes:
        try:
            raw = raw.decode('ascii')
        except UnicodeDecodeError as exc:
            raise ValueError('Research progress response must be ASCII JSON') from exc
    if type(raw) is not str or len(raw) > 16384:
        raise ValueError('Research progress response is malformed or oversized')
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object)
    except json.JSONDecodeError as exc:
        raise ValueError('Research progress response is not valid JSON') from exc
    if type(value) is not dict or set(value) != {'schema', 'player_id', 'turn', 'technology', 'civic'} or value['schema'] != SCHEMA or (type(value['player_id']) is not int) or (value['player_id'] != int(expected)):
        raise ValueError('Research progress response identity or schema mismatch')
    turn = _checked_number(value['turn'], 'turn', integer=True)
    return dict(schema=SCHEMA, player_id=int(expected), turn=turn, technology=_parse_item(value['technology'], 'technology'), civic=_parse_item(value['civic'], 'civic'))

def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f'Duplicate JSON key: {key}')
        value[key] = item
    return value

def validate(value: dict, player_id: int, turn: int, selected: dict) -> dict:
    """Bind the read to the same decision boundary and existing selected IDs."""
    parsed = parse(json.dumps(value, allow_nan=False), player_id)
    if parsed['turn'] != turn:
        raise ValueError('Research progress crossed decision turns')
    if parsed['technology']['index'] != selected['research'] or parsed['civic']['index'] != selected['civic']:
        raise ValueError('Research progress selection differs from native catalogue')
    return parsed

def observe(prefix, player_id: int, turn: int, selected: dict) -> dict:
    raw = prefix.runtime.evaluate_text(prefix.ui_child, source(player_id), b'@explicit_research_progress971', capacity=16385)
    return validate(parse(raw, player_id), player_id, turn, selected)
