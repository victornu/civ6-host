"""XP2 initial diplomacy choices from the selected official XP1 UI overlay.

The public shape and shared GREETING reader come from diplomacy_overview. This
provider adds the three direct XP1 RequestSession routes and leaves every other
offered row visible but non-executable.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path

from .paths import resource_root
from .resource_resolution import resolve_path

SCHEMA = 'civ6-host.diplomacy-overview.v1'
PROFILE_PATH = 'work/bbg751-turn-source-scope/war-confirmation/initial-diplomacy/source-profile.json'
PROFILE_SHA256 = '92f83b4e4b13b336529ed2f28b6552eb6958d16a5578ba5fea23f7fde5f48055'
SOURCE_PROFILE_PATH = 'work/bbg751-turn-source-scope/war-confirmation/major-dialogue/source-profile.json'
SOURCE_PROFILE_SHA256 = 'c174fdd3559007895a8bf1dbdaf0e0cbcf3b0ae8cf807788b34d331dbb856c3f'
CURRENT_IMAGE_ID = 'xp2-gamecore-current-092abfbb'
CURRENT_IMAGE_SHA256 = '092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f'

REQUEST_STATEMENT_TYPES = {
    'CHOICE_DECLARE_SURPRISE_WAR': 'DECLARE_SURPRISE_WAR',
    'CHOICE_DECLARE_FORMAL_WAR': 'DECLARE_FORMAL_WAR',
    'CHOICE_DECLARE_HOLY_WAR': 'DECLARE_HOLY_WAR',
    'CHOICE_DECLARE_LIBERATION_WAR': 'DECLARE_LIBERATION_WAR',
    'CHOICE_DECLARE_RECONQUEST_WAR': 'DECLARE_RECONQUEST_WAR',
    'CHOICE_DECLARE_PROTECTORATE_WAR': 'DECLARE_PROTECTORATE_WAR',
    'CHOICE_DECLARE_COLONIAL_WAR': 'DECLARE_COLONIAL_WAR',
    'CHOICE_DECLARE_TERRITORIAL_WAR': 'DECLARE_TERRITORIAL_WAR',
    'CHOICE_DENOUNCE': 'DENOUNCE',
    'CHOICE_DIPLOMATIC_DELEGATION': 'DIPLOMATIC_DELEGATION',
    'CHOICE_DECLARE_FRIENDSHIP': 'DECLARE_FRIEND',
    'CHOICE_RESIDENT_EMBASSY': 'RESIDENT_EMBASSY',
    'CHOICE_OPEN_BORDERS': 'OPEN_BORDERS',
    'CHOICE_DEMAND_PROMISE_DONT_SPY': 'WARNING_STOP_SPYING_ON_ME',
    'CHOICE_DEMAND_PROMISE_DONT_SETTLE_TOO_NEAR': 'WARNING_DONT_SETTLE_NEAR_ME',
    'CHOICE_DEMAND_PROMISE_DONT_CONVERT_CITY': 'WARNING_STOP_CONVERTING_MY_CITIES',
    'CHOICE_DEMAND_PROMISE_DONT_DIG_ARTIFACTS': 'WARNING_STOP_DIGGING_UP_ARTIFACTS',
    'CHOICE_DECLARE_GOLDEN_AGE_WAR': 'DECLARE_GOLDEN_WAR',
    'CHOICE_DECLARE_WAR_OF_RETRIBUTION': 'DECLARE_WAR_OF_RETRIBUTION',
    'CHOICE_DECLARE_IDEOLOGICAL_WAR': 'DECLARE_IDEOLOGICAL_WAR',
}
DIRECT_REQUEST_CHOICES = frozenset(REQUEST_STATEMENT_TYPES)
UNSUPPORTED_OVERVIEW_CHOICES = frozenset({
    'CHOICE_MAKE_PEACE', 'CHOICE_MAKE_DEAL', 'CHOICE_VIEW_DEAL',
    'CHOICE_MAKE_DEMAND', 'CHOICE_VIEW_DEMAND', 'CHOICE_RENEW_ALLIANCE',
    'CHOICE_ALLIANCE_RELIGIOUS', 'CHOICE_ALLIANCE_RELIGIOUS_TEAM',
    'CHOICE_ALLIANCE_RESEARCH', 'CHOICE_ALLIANCE_RESEARCH_TEAM',
    'CHOICE_ALLIANCE_CULTURAL', 'CHOICE_ALLIANCE_CULTURAL_TEAM',
    'CHOICE_ALLIANCE_ECONOMIC', 'CHOICE_ALLIANCE_ECONOMIC_TEAM',
    'CHOICE_ALLIANCE_MILITARY', 'CHOICE_ALLIANCE_MILITARY_TEAM',
})


def _verify_image(execution_image):
    if execution_image is None:
        raise ValueError('XP2 diplomacy requires an explicit current XP2 execution image')
    from .execution_images import identity
    selected = identity(execution_image)
    if (selected.get('profile_id') != CURRENT_IMAGE_ID
            or selected.get('image_sha256') != CURRENT_IMAGE_SHA256):
        raise ValueError('XP2 diplomacy is not qualified for this execution image')
    return selected


def _load_profile():
    from .native.native_source_cache import load_pinned_json
    profile = load_pinned_json(resource_root() / PROFILE_PATH, PROFILE_SHA256)
    source_profile = load_pinned_json(resource_root() / SOURCE_PROFILE_PATH,
                                      SOURCE_PROFILE_SHA256)
    if (profile.get('schema') != 'civ6-host.xp2-initial-diplomacy-source.v1'
            or profile.get('selected_profile') != dict(path=SOURCE_PROFILE_PATH,
                                                        sha256=SOURCE_PROFILE_SHA256)
            or list(profile.get('selected_overlay_chain', ())) !=
               ['xp2_view', 'xp1_view', 'base_view']
            or dict(profile.get('request_statement_types', {})) != {
                key: REQUEST_STATEMENT_TYPES[key] for key in (
                    'CHOICE_DECLARE_GOLDEN_AGE_WAR',
                    'CHOICE_DECLARE_WAR_OF_RETRIBUTION',
                    'CHOICE_DECLARE_IDEOLOGICAL_WAR')}
            or profile.get('native_execution') is not False
            or profile.get('whole_game_compatibility') is not False
            or source_profile.get('schema') != 'civ6-host.xp2-dialogue-lua-boundary-source.v1'
            or source_profile.get('actual_image', {}).get('sha256') != CURRENT_IMAGE_SHA256):
        raise ValueError('XP2 initial diplomacy source profile differs')
    official = profile.get('official_files')
    if not isinstance(official, Mapping) or set(official) != {
            'base_view', 'support', 'tooltip', 'xp1_view', 'xp2_view',
            'xp1_modinfo', 'xp2_modinfo', 'bbg_modinfo'}:
        raise ValueError('Incomplete selected diplomacy source inputs')
    expected = {
        'base_view': '246409606568dc3f6f2b913334dbc626d9b59e81efc02df0d28409a6ae959cfc',
        'support': 'b9d573f6a93a8dc43bc8804b4faf53510dcbe795862f64dece76e1434bc5a0fb',
        'xp1_view': 'aee6e35dba8a732a7a98674153965bd197fe90f4cfee3c51fecaf57167dc0e6a',
        'xp2_view': '652552cff5f5bb18634ed16ce4951a4f18d4ca33e7085b18371490b4555d2648',
        'xp1_modinfo': 'ed8e3ef9276d694f91e76fe8237361b457a0a6ee653cd506ca8dc4089e56db7d',
        'xp2_modinfo': 'b528a7c25f5977aed1ace8a54a0828025e061d880685d347c8bcf5ccd1473d87',
        'bbg_modinfo': 'f4f918bd18a7189d9f8ee64a4123952e72bded754e5154d7521d25f90bf305a5',
    }
    for name, digest in expected.items():
        if official[name].get('sha256') != digest:
            raise ValueError('Selected official diplomacy dependency differs: ' + name)
    return profile


def _official_bytes(profile, name: str) -> bytes:
    row = profile['official_files'][name]
    path = resolve_path(Path(row['path']))
    raw = path.read_bytes()
    if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
        raise ValueError('Selected official diplomacy source changed: ' + name)
    return raw


def _function(profile, group: str, name: str) -> bytes:
    row = profile['functions'][group][name]
    source = row['source'].encode('utf-8')
    raw = _official_bytes(profile, 'base_view' if group == 'base' else 'xp1_view')
    start, size = row['byte_offset'], row['bytes']
    captured = raw[start:start + size]
    if (size != len(source) or hashlib.sha256(captured).hexdigest() != row['sha256']
            or captured != source):
        raise ValueError('Official diplomacy function slice changed: ' + name)
    return captured


def source_dependencies(*, execution_image):
    _verify_image(execution_image)
    profile = _load_profile()
    pins = {}
    for name, row in profile['official_files'].items():
        raw = _official_bytes(profile, name)
        pins[str(resolve_path(Path(row['path'])).resolve())] = hashlib.sha256(raw).hexdigest()
    pins[str((resource_root() / PROFILE_PATH).resolve())] = PROFILE_SHA256
    pins[str((resource_root() / SOURCE_PROFILE_PATH).resolve())] = SOURCE_PROFILE_SHA256
    module_refs = {
        'diplomacy_overview.py': '715d53af2582a31874133344199366b8d7a87a27a88452808babcd84bf546336',
        'native/native_diplomacy_choices.py': '4d47b1ed1ada0b6d9e2590215ca4529d790e016ae3d9c6648f32bb368e9a08e4',
        'native/native_diplomacy_default.py': '0457f83b38b527dbe83178a9814b91a340c68cdc0937f44c09a4da72f87f4cba',
        'native/native_diplomacy_configuration.py': 'e3b57ae22ea79f3d614efaa22ed8f8ca5b0ccbacf5016ee1c5bb11be41dfc65f',
    }
    for relative, expected in module_refs.items():
        path = Path(__file__).resolve().parent / relative
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('Shared diplomacy source helper changed: ' + relative)
        pins[str(path)] = expected
    pins[execution_image.path] = execution_image.image_sha256
    return pins


def _validate_identity(pid: int, turn: int) -> None:
    if type(pid) is not int or not 0 <= pid < 64 or type(turn) is not int or not 0 <= turn < (1 << 31):
        raise ValueError('Invalid XP2 diplomacy identity')


def _lua_core(pid: int, turn: int) -> bytes:
    from . import diplomacy_overview as base
    core = base._lua_core(pid, turn)
    start = core.index(b'local supported=(')
    end = core.index(b"\n  rows[#rows+1]", start)
    supported = ('local supported=(' + ' or '.join(
        f"s.Key=={json.dumps(key)}" for key in sorted(DIRECT_REQUEST_CHOICES)) + ')').encode('ascii')
    return core[:start] + supported + core[end:]


def _configuration(configuration, pid: int) -> bytes:
    from .diplomacy_overview import _configuration_bindings
    return _configuration_bindings(configuration, pid)


def _helpers() -> bytes:
    from .diplomacy_overview import _lua_helpers
    return _lua_helpers()


def source(pid: int, turn: int, *, configuration, execution_image) -> bytes:
    _verify_image(execution_image)
    _validate_identity(pid, turn)
    _load_profile()
    from .diplomacy_overview import _verify_capability_source
    _verify_capability_source()
    return _configuration(configuration, pid) + _helpers() + _lua_core(pid, turn)


def _selected_dispatch(profile) -> bytes:
    base = _function(profile, 'base', 'OnSelectInitialDiplomacyStatement')
    xp1 = _function(profile, 'xp1', 'OnSelectInitialDiplomacyStatement')
    # Firaxis declaration-only annotations are not Lua 5.1 syntax. The behavior
    # and statements remain the verified official source slice.
    base = re.sub(rb'(?<=local handled):boolean', b'', base)
    xp1 = re.sub(rb'(?<=local handled):boolean', b'', xp1)
    return (base.replace(b'function OnSelectInitialDiplomacyStatement',
                         b'function BASE_OnSelectInitialDiplomacyStatement', 1)
            + b'\n' + xp1)


def request_source(pid: int, turn: int, target: int, key: str, *, configuration,
                   execution_image) -> bytes:
    _verify_image(execution_image)
    _validate_identity(pid, turn)
    if (type(target) is not int or not 0 <= target < 64 or target == pid
            or type(key) is not str or key not in DIRECT_REQUEST_CHOICES):
        raise ValueError('Invalid XP2 diplomacy initiation request')
    profile = _load_profile()
    from .diplomacy_overview import _verify_capability_source
    _verify_capability_source()
    prelude = (b'\nlocal pid=%d; local requestedTurn=%d; local target=%d; local key=%s\n' %
               (pid, turn, target, json.dumps(key).encode('ascii')))
    validate = _lua_core(pid, turn).decode('ascii')
    validate = validate[:validate.index("return '{\"schema\":")]
    validate += r'''
local allowed=false
if capability and not paused then
 for _,p in ipairs(PlayerManager.GetAliveMajors()) do
  if p:GetID()==target and p:IsMajor() and localPlayer:GetDiplomacy():HasMet(target) then
   local kind='GREETING'; local h=GetStatementHandler(kind)
   local parsed=h.ExtractStatement(h,kind,'NONE',pid,DiplomacyMoodTypes.ANY,DiplomacyInitiatorTypes.HUMAN)
   h.RemoveInvalidSelections(parsed,pid,target); DiplomacySupport_RemoveSelectionByKey(parsed,'CHOICE_EXIT')
   for _,s in ipairs(parsed.Selections) do
    if s.Key==key and s.IsDisabled~=true then allowed=true end
   end
  end
 end
end
assert(allowed,'Diplomacy choice is no longer available')
'''
    bindings = (b'\nlocal ms_LocalPlayerID=pid\nlocal ms_SelectedPlayerID=target\n'
                + _function(profile, 'base', 'CanInitiateDiplomacyStatement'))
    dispatch = _selected_dispatch(profile)
    request_map = (b'\nlocal nativeDiplomacy=DiplomacyManager\nlocal calls=0\nlocal accepted=false\n'
        b'local DiplomacyManager=setmetatable({RequestSession=function(attacker,recipient,kind)\n'
        b' assert(calls==0 and attacker==pid and recipient==target and kind==' +
        json.dumps(REQUEST_STATEMENT_TYPES[key]).encode('ascii') +
        b",'Official RequestSession identity/type differs')\n"
        b' calls=calls+1; local result=nativeDiplomacy.RequestSession(attacker,recipient,kind)\n'
        b" assert(type(result)=='boolean','Native RequestSession result is unavailable')\n"
        b' accepted=result; return result\nend},{__index=nativeDiplomacy})\n')
    tail = r'''
local ok,err=pcall(OnSelectInitialDiplomacyStatement,key)
if not ok then error(err) end
assert(calls==1,'Official choice did not request exactly one session')
return accepted and 'requested' or 'not_requested'
'''
    return (_configuration(configuration, pid) + _helpers() + prelude +
            validate.encode('ascii') + bindings + request_map + dispatch + tail.encode('ascii'))


def _validate_source_choices(data):
    from civ6_host.contracts.diplomacy_overview import validate
    validate(data, data.get('player_id'), data.get('turn'))
    for target in data['targets']:
        for row in target['selections']:
            if (row['key'] == 'CHOICE_EXIT'
                    or row['supported'] != (row['key'] in DIRECT_REQUEST_CHOICES)):
                raise ValueError('XP2 diplomacy source choice mapping differs')
    if not data['capability'] and data['targets']:
        raise ValueError('Diplomacy target exposed without capability')
    return data


def parse(raw: bytes, pid: int, turn: int) -> dict:
    if type(raw) is not bytes or len(raw) > 256 * 1024:
        raise ValueError('Unbounded XP2 diplomacy overview response')
    _validate_identity(pid, turn)
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('Malformed XP2 diplomacy overview JSON') from exc
    return _validate_source_choices(data)


def candidates(data: dict) -> list[dict]:
    from civ6_host.contracts.diplomacy_overview import candidates as public_candidates
    _validate_source_choices(data)
    return public_candidates(data)


def validate_action(action, data: dict):
    _validate_source_choices(data)
    if (type(action) is not dict or set(action) != {
            'kind', 'target_player_id', 'choice'}
            or action['kind'] != 'diplomacy_initiate'
            or type(action['target_player_id']) is not int
            or type(action['choice']) is not str
            or action not in candidates(data)):
        raise ValueError('XP2 diplomacy initiation is not currently available')
    return action
