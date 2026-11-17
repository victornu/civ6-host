"""XP2 alliance propose/renew requests and alliance state readback.

Requests run the pinned official overview dispatcher
(OnSelectInitialDiplomacyStatement) with a proxied DiplomacyManager
.RequestSession, exactly like the existing direct routes; the dispatcher
itself adds the locked AGREEMENTS/ALLIANCE deal item for propose choices and
requests MAKE_DEAL, while CHOICE_RENEW_ALLIANCE requests RENEW_ALLIANCE. The
expected statement type per choice comes from xp2_alliances_source. Alliance
state is read back through the native GetAllianceType /
GetAllianceTurnsUntilExpiration pair already used by the public
relationships panel.

Readback seam split (proof handoffs/private-env/alliances/readback/
host-xp2-alliance-readback-source.json, sha256 be15eca6...): this module owns
exactly the pact seam — active/type/turns via GetAllianceType +
GetAllianceTurnsUntilExpiration for every met major including humans
(AddIntelAlliance has no human restriction, unlike AddIntelRelationship).
The progression getters GetAllianceLevel / GetAlliancePointsPerTurn /
GetAllianceTurnsThisLevel / GetAllianceTurnsToNextLevel and the
ALLIANCE_POINTS_MULTIPLIER division belong solely to the spy worker's
xp2_alliance_readback_source.py and are never re-read here.
"""
from __future__ import annotations

import json

from . import xp2_alliances_source as facts

SCHEMA = facts.SCHEMA


def source_dependencies(*, execution_image, stock=False):
    from . import xp2_diplomacy_overview_source as ui
    pins = dict(ui.source_dependencies(execution_image=execution_image, stock=stock))
    profile = ui._load_profile()
    for path, digest in facts.source_dependencies(
            profile['official_files']['xp2_view']['path']).items():
        if path in pins and pins[path] != digest:
            raise ValueError('Alliance source closure has conflicting pins')
        pins[path] = digest
    return pins


def _verify_image(execution_image):
    from . import xp2_diplomacy_overview_source as ui
    return ui._verify_image(execution_image)


def _validate_identity(pid: int, turn: int) -> None:
    if type(pid) is not int or not 0 <= pid < 64 or type(turn) is not int or not 0 <= turn < (1 << 31):
        raise ValueError('Invalid XP2 alliance identity')


def request_source(pid: int, turn: int, target: int, key: str, *, configuration,
                   execution_image) -> bytes:
    """Build the native eval that runs the official choice dispatcher once."""
    _verify_image(execution_image)
    _validate_identity(pid, turn)
    if (type(target) is not int or not 0 <= target < 64 or target == pid
            or type(key) is not str or key not in facts.ALLIANCE_REQUESTS):
        raise ValueError('Invalid XP2 alliance initiation request')
    from . import xp2_diplomacy_overview_source as ui
    statement_name = facts.ALLIANCE_REQUESTS[key]
    propose = key in facts.ALLIANCE_PROPOSALS
    profile = ui._load_profile()
    from .diplomacy_overview import _verify_capability_source
    _verify_capability_source()
    prelude = (b'\nlocal pid=%d; local requestedTurn=%d; local target=%d; local key=%s\n' %
               (pid, turn, target, json.dumps(key).encode('ascii')))
    validate = ui._lua_core(pid, turn).decode('ascii')
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
assert(allowed,'Alliance choice is no longer available')
'''
    if propose:
        validate += r'''
assert(Players[target]:IsHuman()==false and DealManager.HasPendingDeal(pid,target)==false,
 'Outgoing alliance deal requires an AI counterparty without a pending deal')
'''
    bindings = (b'\nlocal ms_LocalPlayerID=pid\nlocal ms_SelectedPlayerID=target\n'
                + ui._function(profile, 'base', 'CanInitiateDiplomacyStatement'))
    request_map = (b'\nlocal nativeDiplomacy=DiplomacyManager\nlocal calls=0\nlocal accepted=false\n'
        b'local DiplomacyManager=setmetatable({RequestSession=function(attacker,recipient,kind)\n'
        b' assert(calls==0 and attacker==pid and recipient==target and kind==' +
        json.dumps(statement_name).encode('ascii') +
        b",'Official RequestSession identity/type differs')\n"
        b' calls=calls+1; local result=nativeDiplomacy.RequestSession(attacker,recipient,kind)\n'
        b" assert(type(result)=='boolean','Native RequestSession result is unavailable')\n"
        b' accepted=result; return result\nend},{__index=nativeDiplomacy})\n')
    tail = r'''
local ok,err=pcall(OnSelectInitialDiplomacyStatement,key)
if not ok then error(err) end
assert(calls==1,'Official alliance choice did not request exactly one session')
return accepted and 'requested' or 'not_requested'
'''
    return (ui._configuration(configuration, pid) + ui._helpers() + prelude +
            validate.encode('ascii') + bindings + request_map +
            ui._selected_dispatch(profile) + tail.encode('ascii'))


_READ_ALLIANCES = r'''
assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,
 'Alliance reader crossed its player or turn')
local diplomacy=Players[pid]:GetDiplomacy()
assert(type(AllianceTypes)=='table','Missing native alliance enum')
local names={}
local known={'ALLIANCE_RESEARCH','ALLIANCE_CULTURAL','ALLIANCE_ECONOMIC','ALLIANCE_MILITARY','ALLIANCE_RELIGIOUS'}
for _,name in ipairs(known) do
 local v=AllianceTypes[name]
 assert(type(v)=='number' and v%1==0 and v>=-2147483648 and v<2147483648 and names[v]==nil,
  'Malformed native alliance enum')
 names[v]=name
end
assert(names[-1]==nil,'Native no-alliance value collides with a real alliance type')
local function integer(value)
 assert(type(value)=='number' and value%1==0 and value>=-2147483648 and value<2147483648,
  'Invalid alliance integer')
 return tostring(value)
end
local rows={}
for _,targetID in ipairs(targets) do
 local target=Players[targetID]
 assert(target and target:GetID()==targetID and target:IsMajor() and diplomacy:HasMet(targetID),
  'Alliance readback requires a met major')
 local alliance=diplomacy:GetAllianceType(targetID)
 assert(type(alliance)=='number' and alliance%1==0,'Missing native alliance type')
 local value='null'
 if alliance~=-1 then
  local name=names[alliance]
  assert(name~=nil,'Unrecognized native alliance type')
  -- The row and tab transmit GetAllianceTurnsUntilExpiration unchanged when
  -- type ~= -1; only the signed-32 representation is checked, no bound.
  local remaining=diplomacy:GetAllianceTurnsUntilExpiration(targetID)
  assert(type(remaining)=='number' and remaining%1==0,'Missing native alliance expiration')
  value='{"type":"'..name..'","turns_remaining":'..integer(remaining)..'}'
 end
 rows[#rows+1]='{"player_id":'..integer(targetID)..',"alliance":'..value..'}'
end
return '['..table.concat(rows,',')..']'
'''.encode('ascii')


def _source(overview) -> bytes:
    from civ6_host.contracts import diplomacy_overview
    pid, turn = overview['player_id'], overview['turn']
    diplomacy_overview.validate(overview, pid, turn)
    ids = ','.join(str(row['player_id']) for row in overview['targets'])
    return f'local pid,turn,targets={pid},{turn},{{{ids}}}\n'.encode('ascii') + _READ_ALLIANCES


def parse(overview, raw):
    """Public alliance view (contracts/alliances.py shape) from a raw readback."""
    from civ6_host.contracts import diplomacy_overview
    pid, turn = overview['player_id'], overview['turn']
    diplomacy_overview.validate(overview, pid, turn)
    if overview['schema'] != diplomacy_overview.SCHEMA or type(raw) is not bytes or len(raw) > 32768:
        raise ValueError('Invalid XP2 alliance readback')
    rows = json.loads(raw)
    targets = overview['targets']
    if (type(rows) is not list or len(rows) != len(targets)
            or any(type(row) is not dict or set(row) != {'player_id', 'alliance'}
                   or type(row['player_id']) is not int
                   or not (row['alliance'] is None or (
                       type(row['alliance']) is dict
                       and set(row['alliance']) == {'type', 'turns_remaining'}
                       and row['alliance']['type'] in facts.ALLIANCE_TYPES
                       and type(row['alliance']['turns_remaining']) is int
                       and -(1 << 31) <= row['alliance']['turns_remaining'] < (1 << 31)))
                   for row in rows)):
        raise ValueError('Malformed XP2 alliance readback')
    by_id = {row['player_id']: row['alliance'] for row in rows}
    if set(by_id) != {target['player_id'] for target in targets}:
        raise ValueError('XP2 alliances differ from the current met targets')
    # The public view is ordered and unique by target, like the contract.
    view = [dict(player_id=target_id, alliance=by_id[target_id]) for target_id in sorted(by_id)]
    return dict(schema=SCHEMA, player_id=pid, turn=turn, targets=view)


def read(prefix, overview):
    raw = (prefix.runtime.evaluate_text(prefix.ui_child, _source(overview),
               b'@xp2_alliance_readback', capacity=32768)
           if overview['targets'] else b'[]')
    return parse(overview, raw)


def candidates(data: dict) -> list[dict]:
    """Alliance initiation candidates from a validated overview document."""
    from civ6_host.contracts.diplomacy_overview import validate
    validate(data, data.get('player_id'), data.get('turn'))
    if data['paused'] or not data['capability']:
        return []
    return [dict(kind='diplomacy_initiate', target_player_id=target['player_id'],
                 choice=selection['key'])
            for target in data['targets'] for selection in target['selections']
            if selection['key'] in facts.ALLIANCE_CHOICES
            and selection['supported'] and not selection['disabled']]


def validate_action(action, data: dict):
    if (type(action) is not dict or set(action) != {'kind', 'target_player_id', 'choice'}
            or action['kind'] != 'diplomacy_initiate'
            or type(action['target_player_id']) is not int
            or type(action['choice']) is not str
            or action['choice'] not in facts.ALLIANCE_REQUESTS
            or action not in candidates(data)):
        raise ValueError('Alliance initiation is not currently available')
    return action
