"""Read official initial-diplomacy choices and request selected sessions.

This is a partial projection of DiplomacyActionView's overview. Availability,
choice parsing, and direct RequestSession dispatch remain in official Lua.
Deal screens and choices without a direct RequestSession route are listed but
never exposed as executable actions here.
"""
from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping

SCHEMA = 'civ6-host.diplomacy-overview.v1'
UI_SHA256 = '246409606568dc3f6f2b913334dbc626d9b59e81efc02df0d28409a6ae959cfc'
SUPPORT_SHA256 = 'b9d573f6a93a8dc43bc8804b4faf53510dcbe795862f64dece76e1434bc5a0fb'
PROOF_PATH = 'work/host-simultaneous/dialogue/overview-source.json'
# Filled with the generated proof's immutable digest below.
PROOF_SHA256 = '284a188e67dd8494b8e525d3b807a9b5cbbf0d7197ec26def611fdcffba6b63d'
PAUSE_PROOF_PATH = 'work/host-simultaneous/dialogue/overview-paused-source.json'
PAUSE_PROOF_SHA256 = '55c67661acc132fc5d52db8f068262359d9aa04a570ce73cabde6325dd66c65d'

DIRECT_REQUEST_CHOICES = frozenset({
    'CHOICE_DECLARE_SURPRISE_WAR', 'CHOICE_DECLARE_FORMAL_WAR',
    'CHOICE_DECLARE_HOLY_WAR', 'CHOICE_DECLARE_LIBERATION_WAR',
    'CHOICE_DECLARE_RECONQUEST_WAR', 'CHOICE_DECLARE_PROTECTORATE_WAR',
    'CHOICE_DECLARE_COLONIAL_WAR', 'CHOICE_DECLARE_TERRITORIAL_WAR',
    'CHOICE_DENOUNCE', 'CHOICE_DIPLOMATIC_DELEGATION',
    'CHOICE_DECLARE_FRIENDSHIP', 'CHOICE_RESIDENT_EMBASSY',
    'CHOICE_OPEN_BORDERS', 'CHOICE_DEMAND_PROMISE_DONT_SPY',
    'CHOICE_DEMAND_PROMISE_DONT_SETTLE_TOO_NEAR',
    'CHOICE_DEMAND_PROMISE_DONT_CONVERT_CITY',
    'CHOICE_DEMAND_PROMISE_DONT_DIG_ARTIFACTS',
})
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
}
UNSUPPORTED_OVERVIEW_CHOICES = frozenset({
    'CHOICE_MAKE_PEACE', 'CHOICE_MAKE_DEAL', 'CHOICE_VIEW_DEAL',
    'CHOICE_MAKE_DEMAND', 'CHOICE_VIEW_DEMAND',
})


def _verify_proof():
    from .provenance import resource_root
    from .native.native_source_cache import load_pinned_json
    if PROOF_SHA256 == 'PENDING':
        raise RuntimeError('Diplomacy overview source proof is not pinned')
    proof = load_pinned_json(resource_root() / PROOF_PATH, PROOF_SHA256)
    if (proof.get('schema') != 'civ6-host.diplomacy-overview-source.v1'
            or proof.get('official_ui_sha256') != UI_SHA256
            or proof.get('official_support_sha256') != SUPPORT_SHA256
            or tuple(proof.get('request_choices', ())) != tuple(sorted(DIRECT_REQUEST_CHOICES))
            or tuple(proof.get('unsupported_choices', ())) != tuple(sorted(UNSUPPORTED_OVERVIEW_CHOICES))
            or dict(proof.get('request_statement_types', {})) != REQUEST_STATEMENT_TYPES
            or proof.get('game_capabilities_source', {}).get('sha256') !=
               '0e81de39aa32033e4b3ed0660e72f6ca63f3f3bec28ec35d3b61ef780f1ceb0c'):
        raise ValueError('Diplomacy overview source proof differs')
    ui = _official_source('DiplomacyActionView.lua', UI_SHA256)
    for name, row in proof.get('functions', {}).items():
        if (not isinstance(row, Mapping) or type(row.get('byte_offset')) is not int
                or type(row.get('bytes')) is not int or row['byte_offset'] < 0
                or row['bytes'] <= 0 or row['byte_offset'] + row['bytes'] > len(ui)):
            raise ValueError('Malformed diplomacy overview source slice')
        captured = ui[row['byte_offset']:row['byte_offset'] + row['bytes']]
        if (hashlib.sha256(captured).hexdigest() != row.get('sha256')
                or captured.decode('utf-8') != row.get('source')):
            raise ValueError('Official diplomacy overview function changed')
    return proof


def _official_source(name: str, digest: str) -> bytes:
    from .native.native_diplomacy_choices import official_source
    return official_source(name, digest)


def _lua_helpers() -> bytes:
    _verify_proof()
    ui = _official_source('DiplomacyActionView.lua', UI_SHA256)
    support = _official_source('DiplomacyStatementSupport.lua', SUPPORT_SHA256)
    from .native.native_diplomacy_default import handler_source
    return support + b'\n' + handler_source()


def _verify_capability_source() -> None:
    from .native.native_plot_display990 import _UI, CAPABILITY_SOURCE_SHA256
    from .resource_resolution import resolve_path
    path = resolve_path(_UI / 'Scripts/GameCapabilities.lua')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CAPABILITY_SOURCE_SHA256:
        raise ValueError('Official GameCapabilities source changed')


def _lua_core(player_id: int, turn: int) -> bytes:
    if type(player_id) is not int or not 0 <= player_id < 64:
        raise ValueError('Invalid diplomacy overview player')
    if type(turn) is not int or not 0 <= turn < (1 << 31):
        raise ValueError('Invalid diplomacy overview turn')
    # This uses the exact AddStatmentOptions extraction contract: GREETING,
    # NONE, local player as speaker, ANY mood, HUMAN initiator, official
    # RemoveInvalidSelections, then the official EXIT removal helper.
    return (b'\nlocal pid=%d; local requestedTurn=%d\n' % (player_id, turn) + r'''
local function quote(s)
 if s==nil then return 'null' end
 assert(type(s)=='string' and #s<=4096,'Malformed diplomacy text')
 local out={'"'}
 for i=1,#s do
  local n=string.byte(s,i); local c=string.sub(s,i,i)
  if n==34 or n==92 then out[#out+1]=string.char(92)..c
  elseif n<32 then out[#out+1]=string.char(92)..string.format('u%04x',n)
  else out[#out+1]=c end
 end
 out[#out+1]='"'; return table.concat(out)
end
local function statementOptions(other)
 local kind='GREETING'
 local handler=GetStatementHandler(kind)
 local parsed=handler.ExtractStatement(handler,kind,'NONE',pid,DiplomacyMoodTypes.ANY,DiplomacyInitiatorTypes.HUMAN)
 handler.RemoveInvalidSelections(parsed,pid,other)
 DiplomacySupport_RemoveSelectionByKey(parsed,'CHOICE_EXIT')
 assert(type(parsed.Selections)=='table' and #parsed.Selections<=64,'Malformed greeting options')
 local rows,seen={},{}
 for _,s in ipairs(parsed.Selections) do
  assert(type(s.Key)=='string' and not seen[s.Key],'Malformed or duplicate greeting key')
  assert(s.IsDisabled==nil or type(s.IsDisabled)=='boolean','Malformed greeting availability')
  seen[s.Key]=true
  local supported=(s.Key=='CHOICE_DECLARE_SURPRISE_WAR' or s.Key=='CHOICE_DECLARE_FORMAL_WAR' or
   s.Key=='CHOICE_DECLARE_HOLY_WAR' or s.Key=='CHOICE_DECLARE_LIBERATION_WAR' or
   s.Key=='CHOICE_DECLARE_RECONQUEST_WAR' or s.Key=='CHOICE_DECLARE_PROTECTORATE_WAR' or
   s.Key=='CHOICE_DECLARE_COLONIAL_WAR' or s.Key=='CHOICE_DECLARE_TERRITORIAL_WAR' or
   s.Key=='CHOICE_DENOUNCE' or s.Key=='CHOICE_DIPLOMATIC_DELEGATION' or
   s.Key=='CHOICE_DECLARE_FRIENDSHIP' or s.Key=='CHOICE_RESIDENT_EMBASSY' or
   s.Key=='CHOICE_OPEN_BORDERS' or s.Key=='CHOICE_DEMAND_PROMISE_DONT_SPY' or
   s.Key=='CHOICE_DEMAND_PROMISE_DONT_SETTLE_TOO_NEAR' or
   s.Key=='CHOICE_DEMAND_PROMISE_DONT_CONVERT_CITY' or
   s.Key=='CHOICE_DEMAND_PROMISE_DONT_DIG_ARTIFACTS')
  rows[#rows+1]='{"key":'..quote(s.Key)..',"disabled":'..(s.IsDisabled==true and 'true' or 'false')..
   ',"supported":'..(supported and 'true' or 'false')..',"text":'..quote(s.Text)..
   ',"tooltip":'..quote(s.Tooltip)..',"diplomatic_action_type":'..quote(s.DiplomaticActionType)..'}'
 end
 return '['..table.concat(rows,',')..']',seen
end
assert(Game and Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and
 Game.GetCurrentGameTurn()==requestedTurn,'Diplomacy overview identity or turn changed')
assert(GameInfo and GameInfo.GameCapabilities,'Diplomacy capability table unavailable')
local capability=GameInfo.GameCapabilities['CAPABILITY_DIPLOMACY']~=nil
local paused=GameConfiguration.IsPaused()
assert(type(paused)=='boolean','Diplomacy pause state unavailable')
local localPlayer=Players[pid]
assert(localPlayer~=nil and localPlayer:GetID()==pid,'Missing requested player')
local targets={}
if capability then
 local diplomacy=localPlayer:GetDiplomacy()
 for _,p in ipairs(PlayerManager.GetAliveMajors()) do
  local other=p:GetID()
  if other~=pid and p:IsMajor() and diplomacy:HasMet(other) then
   local selections=statementOptions(other)
   targets[#targets+1]='{"player_id":'..tostring(other)..',"selections":'..selections..'}'
  end
 end
end
return '{"schema":"civ6-host.diplomacy-overview.v1","player_id":'..tostring(pid)..
 ',"turn":'..tostring(requestedTurn)..',"capability":'..(capability and 'true' or 'false')..
 ',"paused":'..(paused and 'true' or 'false')..',"targets":['..table.concat(targets,',')..
 '],"complete_action_space":false}'
'''.encode('ascii'))


def _configuration_bindings(configuration, player_id: int) -> bytes:
    """Lexical copies of live application getters, never global replacements."""
    from .native.native_diplomacy_configuration import lua_bindings
    if (type(configuration) is not dict or set(configuration) != {
            'initiator', 'players', 'paused'}
            or type(configuration['initiator']) is not int
            or not -(1 << 31) <= configuration['initiator'] < (1 << 32)
            or type(configuration['paused']) is not bool
            or type(configuration['players']) is not dict
            or type(configuration['players'].get(player_id)) is not dict
            or 'leader' not in configuration['players'][player_id]):
        raise ValueError('Missing live diplomacy application configuration')
    initiator = configuration['initiator']
    expected = {player_id}
    if 0 <= initiator < 64:
        expected.add(initiator)
        if type(configuration['players'].get(initiator, {}).get('human')) is not bool:
            raise ValueError('Missing native initiator configuration')
    if set(configuration['players']) != expected:
        raise ValueError('Unexpected diplomacy configuration participants')
    return (lua_bindings(configuration['players']) +
            b'local GameConfiguration={IsPaused=function() return ' +
            str(configuration['paused']).lower().encode('ascii') + b' end}\n' +
            b'assert(DiplomacyInitiatorTypes.HUMAN==' + str(initiator).encode('ascii') +
            b",'Diplomacy initiator enumeration changed')\n")


def _verify_pause_source():
    from .provenance import resource_root
    from .native.native_source_cache import load_pinned_json
    from .native.native_configuration_finalization import CORE_SHA256, EXE_SHA256
    from .native.native_game_configuration import game_configuration_hash
    proof = load_pinned_json(resource_root() / PAUSE_PROOF_PATH, PAUSE_PROOF_SHA256)
    if (proof['schema'] != 'civ6-host.lan-dialogue-paused-static.v1'
            or proof['images']['exe']['sha256'] != EXE_SHA256
            or proof['images']['gamecore']['sha256'] != CORE_SHA256
            or proof['binding']['callback_rva'] != '0x10c140'
            or proof['pause_property']['string'] != 'GAME_PAUSED'
            or proof['pause_property']['value_hash_decimal'] !=
               game_configuration_hash('GAME_PAUSED')
            or proof['read_path']['boolean_lookup_body']['raw_sha256'] !=
               '12800cbf8b5aea831584e374df7077eed4e164d5d539d7e16c4f94275c2564b3'):
        raise ValueError('Official IsPaused source contract changed')
    return proof


def paused_from_variant(raw):
    """Exact EXE102430/10c140 variant branches; missing memory is an error."""
    if type(raw) is not bytes or len(raw) != 24:
        raise ValueError('IsPaused requires an exact native variant')
    tag = struct.unpack_from('<H', raw)[0]
    flags = struct.unpack_from('<I', raw, 20)[0]
    if flags & (1 << 29):
        return False
    if tag in (1, 5):
        return raw[8] != 0
    if tag in (2, 3):
        return struct.unpack_from('<I', raw, 8)[0] != 0
    if tag in (20, 21):
        return struct.unpack_from('<Q', raw, 8)[0] != 0
    # This false branch is in the official helper, not an invented default for
    # absent data. The caller must first obtain the complete native variant.
    return False


def read_pause(owner):
    from .native import native_world_configuration as configuration
    owner.check_thread()
    _verify_pause_source()
    app, base = owner.owner, owner.core._handle
    reader = owner.runtime.read
    call = getattr(owner.runtime, 'call', None)
    app.require_context(base, owner.context)
    before = app.snapshot()
    configuration._live_getter(base, reader, configuration.verify_source())
    raw = configuration._value(base, before['normalized'], reader, call, 'GAME_PAUSED')
    paused = paused_from_variant(raw)
    if app.snapshot() != before:
        raise RuntimeError('Application provider changed during IsPaused read')
    if getattr(owner, '_diplomacy_pause_logged', None) != raw:
        owner.emit('official_lan_pause_projection', paused=paused,
            variant_tag=struct.unpack_from('<H', raw)[0],
            provider='restored_application_B', source_sha256=PAUSE_PROOF_SHA256,
            native_configuration_written=False, strategic_training_ready=False)
        owner._diplomacy_pause_logged = raw
    return paused


def read_configuration(owner, player_id: int):
    """Read the same application participant fields used by official GREETING."""
    from .native.native_diplomacy_configuration import read
    owner.check_thread()
    if type(player_id) is not int or not 0 <= player_id < 64:
        raise ValueError('Invalid diplomacy configuration participant')
    p = owner.prefix
    raw = p.runtime.evaluate_text(p.ui_child,
        b'local n=DiplomacyInitiatorTypes.HUMAN\n'
        b"assert(type(n)=='number' and n%1==0,'Missing native diplomacy enum')\n"
        b'return tostring(n)', b'@lan_diplomacy_initiator', capacity=64)
    if type(raw) is not bytes or len(raw) > 12:
        raise ValueError('Invalid native diplomacy initiator')
    initiator = int(raw)
    if not -(1 << 31) <= initiator < (1 << 32):
        raise ValueError('Native diplomacy initiator exceeds its ABI')
    # This reader takes the two official ExtractStatement inputs. The dict is
    # an internal read argument, never an invented game event or session.
    players = read(owner, {'fields': {'FromPlayer': player_id, 'Initiator': initiator}})
    result = dict(initiator=initiator, players=players, paused=read_pause(owner))
    _configuration_bindings(result, player_id)
    return result


def source(player_id: int, turn: int, *, configuration) -> bytes:
    _verify_capability_source()
    return (_configuration_bindings(configuration, player_id) +
            _lua_helpers() + _lua_core(player_id, turn))


def _validate_data(data, player_id: int, turn: int):
    from civ6_host.contracts.diplomacy_overview import validate
    validate(data, player_id, turn)
    _validate_source_choices(data)


def _validate_source_choices(data):
    for target in data['targets']:
        for row in target['selections']:
            if (row['key'] == 'CHOICE_EXIT'
                    or row['supported'] != (row['key'] in DIRECT_REQUEST_CHOICES)):
                raise ValueError('Diplomacy source choice mapping differs')
    if not data['capability'] and data['targets']:
        raise ValueError('Diplomacy target exposed without capability')
    return data


def parse(payload: bytes, pid: int, turn: int) -> dict:
    if type(payload) is not bytes or len(payload) > 256 * 1024:
        raise ValueError('Unbounded diplomacy overview response')
    if type(pid) is not int or not 0 <= pid < 64 or type(turn) is not int or turn < 0:
        raise ValueError('Invalid diplomacy overview identity')
    try:
        data = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('Malformed diplomacy overview JSON') from exc
    _validate_data(data, pid, turn)
    return data


def candidates(data: dict) -> list[dict]:
    from civ6_host.contracts.diplomacy_overview import candidates as public_candidates
    result = public_candidates(data)
    _validate_source_choices(data)
    return result


def validate_action(action, data: dict):
    _validate_data(data, data.get('player_id'), data.get('turn'))
    if (type(action) is not dict or set(action) != {
            'kind', 'target_player_id', 'choice'}
            or action['kind'] != 'diplomacy_initiate'
            or type(action['target_player_id']) is not int
            or type(action['choice']) is not str):
        raise ValueError('Malformed diplomacy initiation action')
    if action not in candidates(data):
        raise ValueError('Diplomacy initiation is not currently available')
    return action


def request_source(pid: int, turn: int, target: int, key: str, *, configuration) -> bytes:
    if (type(pid) is not int or not 0 <= pid < 64 or type(turn) is not int
            or turn < 0 or type(target) is not int or not 0 <= target < 64
            or target == pid or type(key) is not str
            or key not in DIRECT_REQUEST_CHOICES):
        raise ValueError('Invalid diplomacy initiation request')
    _verify_capability_source()
    ui = _official_source('DiplomacyActionView.lua', UI_SHA256)
    from .native.native_diplomacy_default import handler_source
    # Function bodies are verified against offsets and hashes in the private
    # source proof before insertion; the official branch remains the dispatcher.
    proof = _verify_proof()
    functions = proof['functions']
    snippets = []
    for name in ('CanInitiateDiplomacyStatement', 'OnSelectInitialDiplomacyStatement'):
        row = functions[name]
        start, size = row['byte_offset'], row['bytes']
        raw = ui[start:start + size]
        if hashlib.sha256(raw).hexdigest() != row['sha256'] or raw.decode('utf-8') != row['source']:
            raise RuntimeError('Official initial diplomacy dispatcher changed')
        snippets.append(raw)
    prelude = (b'\nlocal pid=%d; local requestedTurn=%d; local target=%d; local key=%s\n' %
               (pid, turn, target, json.dumps(key).encode('ascii')))
    # Re-run the official availability extraction in this same native eval,
    # then invoke the captured original overview handler and count its native
    # RequestSession dispatch.
    validate = _lua_core(pid, turn).decode('ascii')
    validate = validate[:validate.index("return '{\"schema\":")]
    validate += r'''
local allowed=false
if capability and not paused then
 for _,p in ipairs(PlayerManager.GetAliveMajors()) do
  if p:GetID()==target and p:IsMajor() and localPlayer:GetDiplomacy():HasMet(target) then
   local _,seen=statementOptions(target)
   -- Re-extract full rows so disabled status is checked fresh too.
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
    # Preserve the exact statement-dispatch body; only its locals are supplied.
    dispatch = (b'\nlocal ms_LocalPlayerID=pid\nlocal ms_SelectedPlayerID=target\n' +
                snippets[0] + b'\n' + snippets[1])
    tail = r'''
assert(type(nativeDiplomacy.RequestSession)=='function','Native RequestSession unavailable')
local ok,err=pcall(OnSelectInitialDiplomacyStatement,key)
if not ok then error(err) end
assert(calls==1,'Official choice did not request exactly one session')
return 'requested'
'''
    expected_type = REQUEST_STATEMENT_TYPES[key]
    proxy = (b'\nlocal nativeDiplomacy=DiplomacyManager\nlocal calls=0\n'
        b'local DiplomacyManager=setmetatable({RequestSession=function(attacker,recipient,kind)\n'
        b' assert(calls==0 and attacker==pid and recipient==target and kind==' +
        json.dumps(expected_type).encode('ascii') +
        b",'Official RequestSession identity/type differs')\n"
        b' calls=calls+1; return nativeDiplomacy.RequestSession(attacker,recipient,kind)\n'
        b'end},{__index=nativeDiplomacy})\n')
    return (_configuration_bindings(configuration, pid) +
            _lua_helpers() + prelude + validate.encode('ascii') + proxy +
            dispatch + tail.encode('ascii'))
