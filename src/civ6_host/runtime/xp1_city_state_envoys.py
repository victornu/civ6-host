"""Read own effective envoys through the installed Rise and Fall city-state UI bindings."""

from pathlib import Path

from civ6_host.contracts import city_state_envoys

from .configuration_profiles import _source
from .execution_images import _XP1_PROFILE, identity
from .paths import resource_root
from .xp1_saved_load import REFERENCE


SOURCE = ('evidence/host-xp1-installed-city-state-envoys-source.json',
          '94643137bd07dfb99a73fa8ebdb98ab4e81661696b588b499e7bd4ba1b217082')
ACTION_SOURCE = ('evidence/host-xp1-installed-envoy-operations-source.json',
                 '4f3e181cfee1a09c8e93a76d50f2b704cd7c9a59f910ff021807cabbea6720f4')
CHECKPOINT_SOURCE = ('evidence/host-xp1-envoy-checkpoint-consideration-source.json',
                     '9bb05aae227b79f04cd3f90c164a12f26bb6d42c029e212246ac18697a07883a')
_BINDINGS = {'GetID', 'GetAliveMinors', 'GetDiplomacy', 'HasMet', 'GetInfluence',
             'CanReceiveInfluence', 'GetTokensReceived'}
_CAPACITY = 4096


def action_source(execution_image):
    from .native import native_envoy_actions as native

    count = source(execution_image)
    proof = _source(ACTION_SOURCE)
    parents = proof['parents']
    legacy_path = f'evidence/native-envoy-actions/{native.PROOF_SHA256}.json'
    if (proof['schema'] != 'civ6-host.xp1-envoy-operations.source.v1'
            or proof['image'] != count['image'] or proof['official_bundle'] != count['official_bundle']
            or (parents['player_counts']['path'], parents['player_counts']['sha256']) != SOURCE
            or (parents['shared_operations']['path'], parents['shared_operations']['sha256']) !=
                (legacy_path, native.PROOF_SHA256)
            or set(proof['bindings']) != {'CanGiveInfluence', 'CanGiveTokensToPlayer',
                'GetTokensToGive', 'IsGivingTokensConsidered', 'SetGivingTokensConsidered',
                'GetAllEndTurnBlocking'}
            or proof['constants'] != {'operation': 0x99ec0bce, 'target_key': 0x0483191c,
                                      'blocker': native.BLOCKER}
            or proof['contract'] != dict(catalogue_player_scoped=True, confirmation_native=True,
                retain_setter=True, retain_archives_player_command=False,
                reserve_and_effect_native=True, checkpoint_consideration_admitted=False)):
        raise ValueError('Rise and Fall envoy operation source differs')
    return proof


def source(execution_image):
    proof = _source(SOURCE)
    bundle = proof['official_bundle']
    if (execution_image is not _XP1_PROFILE or proof['image'] != identity(execution_image)
            or proof['schema'] != 'civ6-host.xp1-city-state-envoys.source.v1'
            or (Path(bundle['path']).as_posix(), bundle['sha256']) != REFERENCE
            or set(proof['ui']) != {'base', 'expansion1', 'modinfo'}
            or set(proof['bindings']) != _BINDINGS
            or any(len(rows) != 2 or any(set(row) != {'registration', 'callback'} for row in rows)
                   for rows in proof['bindings'].values())
            or proof['rules']['capability'] != 'CAPABILITY_CITY_STATES_VIEW'
            or proof['contract'] != dict(known_living_minors_only=True,
                requires_can_receive_influence=True,
                tokens_native_method='PlayerInfluence.GetTokensReceived', actor_envoys_only=True)):
        raise ValueError('Rise and Fall city-state envoy source differs')
    return proof


def checkpoint_source(execution_image):
    actions = action_source(execution_image)
    proof = _source(CHECKPOINT_SOURCE)
    parent = proof['parent']
    if (proof['schema'] != 'civ6-host.xp1-envoy-checkpoint-consideration-source.v1'
            or proof['image'] != actions['image'] or proof['official_bundle'] != actions['official_bundle']
            or (parent['path'], parent['sha256']) != ACTION_SOURCE
            or proof['source_contract'] != dict(constructor_default=True,
                archive_records_consideration=False, native_consideration_field_offset=0x458,
                restore_native_setter_only=True, strict_post_restore_catalogue=True)):
        raise ValueError('Rise and Fall envoy checkpoint source differs')
    return proof


def source_dependencies(execution_image):
    from .native import native_envoy_actions as native
    from .xp1_governors_source import _path

    proof = source(execution_image)
    actions = action_source(execution_image)
    checkpoint_source(execution_image)
    result = {str((resource_root() / path).resolve()): digest
              for path, digest in (SOURCE, ACTION_SOURCE, CHECKPOINT_SOURCE)}
    for row in (*proof['ui'].values(), proof['rules']['gameplay_database']):
        result[str(_path(row))] = row['sha256']
    for row in (*actions['parents'].values(), *native.verify_source()['parents'].values()):
        result[str(_path(row))] = row['sha256']
    return result


def query_source(player_id, turn):
    empty = dict(schema=city_state_envoys.SCHEMA, player_id=player_id, turn=turn, city_states=[])
    city_state_envoys.validate(empty, player_id, turn)
    return f'local pid, turn = {player_id}, {turn}\n'.encode('ascii') + _READ


_READ = b"""
local function context()
 assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid
        and Game.GetCurrentGameTurn()==turn,'foreign city-state envoy perspective')
end
local function integer(v, maximum)
 assert(type(v)=='number' and v==math.floor(v) and v>=0 and v<=maximum,
        'invalid city-state envoy integer')
 return v
end
context()
assert(GameInfo.GameCapabilities['CAPABILITY_CITY_STATES_VIEW'],'city-state panel capability unavailable')
local diplomacy=assert(Players[pid]:GetDiplomacy(),'city-state contact unavailable')
local minors=PlayerManager.GetAliveMinors()
assert(type(minors)=='table' and #minors<=63,'invalid living minor list')
local rows, seen={},{}
for _,minor in ipairs(minors) do
 local id=integer(minor:GetID(),63)
 assert(id~=pid and not seen[id],'duplicate or own minor identity')
 seen[id]=true
 local met=diplomacy:HasMet(id)
 assert(type(met)=='boolean','invalid city-state contact flag')
 if met then
  local influence=minor:GetInfluence()
  if influence then
   local receives=influence:CanReceiveInfluence()
   assert(type(receives)=='boolean','invalid city-state influence flag')
   if receives then
    rows[#rows+1]={id,integer(influence:GetTokensReceived(pid),2147483647)}
   end
  end
 end
end
table.sort(rows,function(a,b) return a[1]<b[1] end)
local fields={string.format('%d:%d',pid,turn)}
for _,row in ipairs(rows) do
 fields[#fields+1]=string.format('%d:%d',row[1],row[2])
end
context()
return table.concat(fields,'|')
"""


def parse(raw, player_id, turn):
    if type(raw) is not bytes or not 0 < len(raw) < _CAPACITY:
        raise ValueError('Invalid city-state envoy wire size')
    header, *rows = raw.split(b'|')
    if header != f'{player_id}:{turn}'.encode('ascii'):
        raise ValueError('Foreign city-state envoy wire header')
    result = dict(schema=city_state_envoys.SCHEMA, player_id=player_id, turn=turn, city_states=[])
    for row in rows:
        fields = row.split(b':')
        if len(fields) != 2 or any(not f.isdigit() or len(f) > 10 for f in fields):
            raise ValueError('Invalid city-state envoy wire row')
        owner, count = map(int, fields)
        if row != f'{owner}:{count}'.encode('ascii'):
            raise ValueError('Noncanonical city-state envoy wire row')
        result['city_states'].append(dict(player_id=owner, own_envoys=count))
    return city_state_envoys.validate(result, player_id, turn)


def _bind_count(saved, *, active):
    from .xp1_governors_source import _verify_live, bind_owner

    bind_owner(saved, active=active)
    backend, prefix = saved.backend, saved.prefix
    core = backend.core
    lifetime = (core, prefix)
    if getattr(saved, '_xp1_city_state_envoys_lifetime', None) != lifetime:
        proof = source(core._civ6_host_execution_image)
        spans = [span for rows in proof['bindings'].values()
                 for row in rows for span in row.values()]
        _verify_live(core._handle, backend.runtime.read, spans)
        saved._xp1_city_state_envoys_lifetime = lifetime


def bind_actions(saved, *, active):
    from .xp1_governors_source import _verify_live

    _bind_count(saved, active=active)
    backend, prefix = saved.backend, saved.prefix
    core = backend.core
    lifetime = (core, prefix)
    if getattr(saved, '_xp1_envoy_actions_lifetime', None) != lifetime:
        proof = action_source(core._civ6_host_execution_image)
        spans = [span for row in proof['bindings'].values() for span in row.values()]
        spans.extend(proof['native'].values())
        _verify_live(core._handle, backend.runtime.read, spans)
        saved._xp1_envoy_actions_lifetime = lifetime


def read(saved, observation):
    _bind_count(saved, active=False)
    prefix = saved.prefix
    player_id, turn = observation['player_id'], observation['turn']
    raw = prefix.runtime.evaluate_text(prefix.ui_child, query_source(player_id, turn),
                                       b'@xp1_city_state_envoys', capacity=_CAPACITY)
    return parse(raw, player_id, turn)
