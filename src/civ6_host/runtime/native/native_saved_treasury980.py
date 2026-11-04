"""Read the active saved player's treasury values without changing game state.

The getters and net-yield arithmetic are pinned to the installed TopPanel.lua.
This module only serializes their current values; it does not model economy
rules or perform treasury operations.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
import math
from pathlib import Path
from civ6_host.runtime.native import native_research_actions
SCHEMA = 'civ6rl.native_saved_treasury980.v1'
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_saved_treasury980.py')))).resolve().parents[1]
_ASSETS = _resolve_resource_path(Path("C:\\Program Files (x86)\\Steam\\steamapps\\common\\Sid Meier's Civilization VI\\Base\\Assets\\UI"))
_TOP_PANEL_REL = 'TopPanel.lua'
_TOP_PANEL_SHA256 = '045a0d9e08ba63ee9a151810eb49f31bc11603cff7f159e07d3419c0f008cd7b'
_BINDING_PROOF = _ROOT / 'evidence/rea-phase13b/phase13b-731.response.json'
_BINDING_SHA256 = '60c357ee19a6d4375000aeeea76116bb471c714c991f0c226bcab323689e7383'
_DISPLAY_SOURCES = {'Civ6Common.lua': '6e422dfed29d6e40507b14e234fc84c7647f450200df17dc2383e952a67a371f', 'Screens/ReportScreen.lua': 'a16478a7ef08ee0754b6deac706ec6e4199c895cd0cdc77fcb0cd57828f73d44'}
_MAX_PLAYER_ID = 63
_MAX_RESPONSE_BYTES = 16384
_FIELDS = {'schema', 'player_id', 'turn', 'gold_balance', 'gold_yield', 'total_maintenance', 'net_gold_yield', 'public_display'}
DISPLAY_SCHEMA = 'civ6rl.native_treasury_display980.v1'

def verified_files() -> dict[Path, str]:
    """Return every local source/evidence file pinned by this observer."""
    native_research_actions.verify_source()
    proof_path = native_research_actions._PROOF_PATH
    files = {_ASSETS / _TOP_PANEL_REL: _TOP_PANEL_SHA256, proof_path: native_research_actions._PROOF_SHA256, _BINDING_PROOF: _BINDING_SHA256}
    files.update({_ASSETS / relative: expected for relative, expected in _DISPLAY_SOURCES.items()})
    for relative, expected in native_research_actions._SOURCE_HASHES.values():
        files[native_research_actions._ASSETS / relative] = expected
    for path, expected in files.items():
        if hashlib.sha256(_resolve_resource_path(path).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'Pinned treasury observer source changed: {path.name}')
    return files

def verify_source() -> None:
    """Pin the installed display source and the shared Base DLL route proof."""
    verified_files()

def _player_id(value: int) -> bytes:
    if type(value) is not int or not 0 <= value <= _MAX_PLAYER_ID:
        raise ValueError('player_id must be an integer in [0, 63]')
    return str(value).encode('ascii')

def source(player_id: int) -> bytes:
    """Build a bounded Lua read for the selected player's current treasury."""
    pid = _player_id(player_id)
    verify_source()
    return b'local pid=' + pid + b'\nassert(Game and type(Game.GetLocalPlayer)==\'function\' and Game.GetLocalPlayer()==pid,\n       \'treasury observation perspective differs from requested player\')\nassert(type(Game.GetLocalObserver)==\'function\' and Game.GetLocalObserver()==pid,\n       \'treasury observation observer differs from requested player\')\nlocal player=Players and Players[pid]\nassert(player~=nil,\'treasury player unavailable\')\nassert(type(player.GetTreasury)==\'function\',\'native treasury manager unavailable\')\nlocal treasury=player:GetTreasury()\nassert(treasury and type(treasury.GetGoldBalance)==\'function\' and\n       type(treasury.GetGoldYield)==\'function\' and\n       type(treasury.GetTotalMaintenance)==\'function\',\n       \'native treasury getters unavailable\')\nlocal function whole(v,label)\n  assert(type(v)==\'number\' and v==math.floor(v) and v==v and\n         v~=math.huge and v~=-math.huge,\'invalid \'..label)\n  return v\nend\nlocal function finite(v,label)\n  assert(type(v)==\'number\' and v==v and v~=math.huge and v~=-math.huge,\n         \'invalid \'..label)\n  return v\nend\nlocal turnBefore=whole(Game.GetCurrentGameTurn(),\'turn before treasury read\')\nlocal goldBalance=finite(treasury:GetGoldBalance(),\'gold balance\')\nlocal goldYield=finite(treasury:GetGoldYield(),\'gold yield\')\nlocal totalMaintenance=finite(treasury:GetTotalMaintenance(),\'total maintenance\')\n-- The shipped TopPanel.lua computes displayed net yield as yield minus maintenance.\nlocal netGoldYield=goldYield-totalMaintenance\nassert(netGoldYield==netGoldYield and netGoldYield~=math.huge and netGoldYield~=-math.huge,\n       \'invalid net gold yield\')\n-- Reuse the official localization formatter. Never emulate its rounding in\n-- Python. The transport accepts only the pinned en_US/fr_FR public number\n-- grammars; it preserves this exact native text in the response.\nassert(Locale and type(Locale.Lookup)==\'function\',\'native number formatter unavailable\')\nlocal function display(v)\n  local pattern=(v==0) and \'{1: number #,###.#}\' or \'{1: number +#,###.#;-#,###.#}\'\n  local text=Locale.Lookup(pattern,v)\n  assert(type(text)==\'string\' and #text<=64,\'unsupported native finance display\')\n  local i=1\n  while i<=#text do\n    local b=string.byte(text,i)\n    if b==194 then\n      assert(string.byte(text,i+1)==160,\'unsupported native finance display\')\n      i=i+2\n    else\n      assert((b>=48 and b<=57) or b==43 or b==45 or b==44 or b==46,\n             \'unsupported native finance display\')\n      i=i+1\n    end\n  end\n  return text\nend\nlocal shownIncome=display(goldYield)\nlocal shownExpense=display(-totalMaintenance)\nlocal shownNet=display(netGoldYield)\nlocal turnAfter=whole(Game.GetCurrentGameTurn(),\'turn after treasury read\')\nassert(turnAfter==turnBefore,\'game turn changed during treasury observation\')\nassert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid,\n       \'treasury observation perspective changed during read\')\nreturn \'{"schema":"civ6rl.native_saved_treasury980.v1","player_id":\'..\n  string.format(\'%.0f\',pid)..\',"turn":\'..string.format(\'%.0f\',turnBefore)..\n  \',"gold_balance":\'..string.format(\'%.17g\',goldBalance)..\n  \',"gold_yield":\'..string.format(\'%.17g\',goldYield)..\n  \',"total_maintenance":\'..string.format(\'%.17g\',totalMaintenance)..\n  \',"net_gold_yield":\'..string.format(\'%.17g\',netGoldYield)..\n  \',"public_display":{"schema":"civ6rl.native_treasury_display980.v1","gold_balance":\'..\n  string.format(\'%.0f\',math.floor(goldBalance))..\',"gold_yield":"\'..shownIncome..\n  \'","gold_expense":"\'..shownExpense..\'","net_gold_yield":"\'..shownNet..\'"}}\'\n'

def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f'Duplicate JSON key: {key}')
        value[key] = item
    return value

def _number(value, label: str, *, integer: bool=False) -> int | float:
    if type(value) not in (int, float):
        raise ValueError(f'Invalid {label}')
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite or (integer and type(value) is not int):
        raise ValueError(f'Invalid {label}')
    return value

def parse(raw: bytes | str, player_id: int) -> dict:
    """Parse one bounded UTF-8 JSON response for the requested player."""
    _player_id(player_id)
    expected_player = player_id
    if type(raw) is bytes:
        try:
            if len(raw) > _MAX_RESPONSE_BYTES:
                raise ValueError('Treasury response is malformed or oversized')
            raw = raw.decode('utf-8', errors='strict')
        except UnicodeDecodeError as exc:
            raise ValueError('Treasury response must be UTF-8 JSON') from exc
    elif type(raw) is str:
        try:
            raw_size = len(raw.encode('utf-8', errors='strict'))
        except UnicodeEncodeError as exc:
            raise ValueError('Treasury response must be UTF-8 JSON') from exc
        if raw_size > _MAX_RESPONSE_BYTES:
            raise ValueError('Treasury response is malformed or oversized')
    if type(raw) is not str:
        raise ValueError('Treasury response is malformed or oversized')
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object)
    except json.JSONDecodeError as exc:
        raise ValueError('Treasury response is not valid JSON') from exc
    if type(value) is not dict or set(value) != _FIELDS or value['schema'] != SCHEMA or (type(value['player_id']) is not int) or (value['player_id'] != expected_player):
        raise ValueError('Treasury response identity or schema mismatch')
    turn = _number(value['turn'], 'turn', integer=True)
    gold_balance = _number(value['gold_balance'], 'gold balance')
    gold_yield = _number(value['gold_yield'], 'gold yield')
    total_maintenance = _number(value['total_maintenance'], 'total maintenance')
    net_gold_yield = _number(value['net_gold_yield'], 'net gold yield')
    if net_gold_yield != gold_yield - total_maintenance:
        raise ValueError('Inconsistent net gold yield')
    display = value['public_display']
    if type(display) is not dict or set(display) != {'schema', 'gold_balance', 'gold_yield', 'gold_expense', 'net_gold_yield'} or display['schema'] != DISPLAY_SCHEMA or (type(display['gold_balance']) is not int) or (display['gold_balance'] != math.floor(gold_balance)):
        raise ValueError('Invalid treasury public display identity or balance')
    for key, native in (('gold_yield', gold_yield), ('gold_expense', -total_maintenance), ('net_gold_yield', net_gold_yield)):
        text = display[key]
        try:
            display_bytes = len(text.encode('utf-8', errors='strict')) if type(text) is str else 65
        except UnicodeEncodeError as exc:
            raise ValueError('Unsupported native treasury display number') from exc
        if display_bytes > 64:
            raise ValueError('Unsupported native treasury display number')
        from civ6_host.contracts.yield_display982 import public_number
        try:
            shown = public_number(text)
        except ValueError as exc:
            raise ValueError('Unsupported native treasury display number') from exc
        if not math.isfinite(shown) or abs(shown - native) > 0.100000001:
            raise ValueError('Treasury display differs from native value')
    return dict(schema=SCHEMA, player_id=expected_player, turn=turn, gold_balance=gold_balance, gold_yield=gold_yield, total_maintenance=total_maintenance, net_gold_yield=net_gold_yield, public_display=dict(display))

def validate(value: dict, player_id: int, turn: int, gold_balance: int | float | None=None) -> dict:
    """Bind treasury read to the same player, turn, and optional observed balance."""
    try:
        raw = json.dumps(value, allow_nan=False, separators=(',', ':'))
    except (TypeError, ValueError) as exc:
        raise ValueError('Treasury value cannot be normalized') from exc
    parsed = parse(raw, player_id)
    if type(turn) is not int or parsed['turn'] != turn:
        raise ValueError('Treasury observation crossed decision turns')
    if gold_balance is not None:
        expected = _number(gold_balance, 'expected gold balance')
        if parsed['gold_balance'] != expected:
            raise ValueError('Treasury gold balance differs from player observation')
    return parsed

def observe(prefix, player_id: int, turn: int, gold_balance: int | float | None=None) -> dict:
    """Read and validate the current selected player's treasury in a prefix."""
    from civ6_host.runtime.native.native_locale_arguments import attach
    attach(prefix)
    raw = prefix.runtime.evaluate_text(prefix.ui_child, source(player_id), b'@explicit_treasury980', capacity=_MAX_RESPONSE_BYTES + 1)
    return validate(parse(raw, player_id), player_id, turn, gold_balance)

def collect(arena, player_id: int, turn: int, gold_balance: int | float | None=None) -> dict:
    """Alias for callers that name saved-state collection explicitly."""
    return observe(arena, player_id, turn, gold_balance)
__all__ = ['SCHEMA', 'source', 'parse', 'validate', 'observe', 'collect', 'verify_source', 'verified_files']
