"""Bounded diagnostic adapter for a source-backed native city ranged shot.

This is not a complete combat environment or a learner API. It joins the pinned CityManager
route to the already existing NativeActionTransport and fails closed unless a
visible enemy unit at a native-admitted target plot takes damage after delivery.
It deliberately does not emulate the UI's first-city choice or dismiss a
notification.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
import math
from pathlib import Path
from civ6_host.runtime.native.native_city_kill_receipt import KillReceiptWindow
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_city_range_attack.py')))).resolve().parents[1]
RANGE_ROUTE_SHA256 = '264ce2c209d1d30f9ebc371caca8d835fbc89ca3c5975a1c74e281347a15ec9f'
RANGE_ROUTE = ROOT / 'evidence/native-city-range-attack-route' / f'{RANGE_ROUTE_SHA256}.json'
NOTIFICATION_SHA256 = '4c87df1d7afb6d73f7a6b9a90b466438987f589324cc4e8a1fc18c8c579a3fe9'
NOTIFICATION = ROOT / 'evidence/native-city-attack-notification.json'
PLAYER_OBSERVATION_SHA256 = 'ba765cbecf31d5def0f09061ee5f7860c826502fff9de7990403caf95f29fcfc'
PLAYER_OBSERVATION = ROOT / 'civ6rl/native_player_observation.py'

def _pinned(path: Path, expected: str) -> bytes:
    raw = _resolve_resource_path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise RuntimeError(f'work prototype input changed: {path.name}')
    return raw

def verify_inputs() -> dict:
    route = json.loads(_pinned(RANGE_ROUTE, RANGE_ROUTE_SHA256))
    notification = json.loads(_pinned(NOTIFICATION, NOTIFICATION_SHA256))
    _pinned(PLAYER_OBSERVATION, PLAYER_OBSERVATION_SHA256)
    if route.get('schema') != 'civ6rl.native_city_range_attack_route.static.v1':
        raise RuntimeError('unexpected city ranged-attack route proof')
    if route['core_enum_fields']['fields']['CityCommandTypes.RANGE_ATTACK']['numeric_value'] != -1967338303:
        raise RuntimeError('CityCommandTypes.RANGE_ATTACK initializer value changed')
    if route['fresh_core_captures']['functions']['PlayerCities.GetFirstRangedAttackCity']['va'] != '0x180532550':
        raise RuntimeError('GetFirstRangedAttackCity binding changed')
    dismissed = notification['notification_is_dismissed_method']['registration']
    if dismissed['callback_va'] != '0x18056e1e0':
        raise RuntimeError('Notification:IsDismissed binding changed')
    return {'range_route_sha256': RANGE_ROUTE_SHA256, 'notification_sha256': NOTIFICATION_SHA256, 'player_observation_sha256': PLAYER_OBSERVATION_SHA256}

def _pid(value: int) -> int:
    if type(value) is not int or not 0 <= value < 64:
        raise ValueError('player ID must be uint32-domain player [0, 63]')
    return value

def _visible_enemy_rows(rows, player_id: int) -> list[dict]:
    pid = _pid(player_id)
    if type(rows) is not list or len(rows) > 16384:
        raise ValueError('visible enemy rows must be a bounded list')
    result, seen = ([], set())
    keys = {'owner', 'id', 'type', 'x', 'y', 'damage', 'visible'}
    for row in rows:
        if type(row) is not dict or set(row) != keys or row['visible'] is not True:
            raise ValueError('enemy row shape or visibility is invalid')
        if any((type(row[k]) is not int for k in ('owner', 'id', 'type', 'x', 'y'))):
            raise ValueError('enemy identity/coordinates must be exact integers')
        if type(row['damage']) not in (int, float) or not math.isfinite(row['damage']) or row['damage'] < 0:
            raise ValueError('enemy damage is invalid')
        if not 0 <= row['owner'] < 64 or row['owner'] == pid or (not 0 <= row['id'] <= 4294967295) or (not -2147483648 <= row['type'] <= 4294967295) or any((not 0 <= row[k] <= 4294967295 for k in ('x', 'y'))):
            raise ValueError('visible enemy is outside the admitted domain')
        identity = (row['owner'], row['id'])
        if identity in seen:
            raise ValueError('duplicate visible enemy identity')
        seen.add(identity)
        result.append(dict(row))
    return result

def notification_status_source(player_id: int) -> bytes:
    pid = _pid(player_id)
    verify_inputs()
    return f"local pid={pid}\nassert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid,'notification perspective mismatch')\nlocal player=Players[pid]\nassert(player and player:IsAlive() and player:IsTurnActive() and player:IsTurnActiveComplete(),'player is not ready')\nassert(NotificationManager and type(NotificationManager.FindType)=='function' and NotificationTypes and NotificationTypes.CITY_RANGE_ATTACK==-1181197223,'city attack notification API unavailable')\nlocal notification=NotificationManager.FindType(NotificationTypes.CITY_RANGE_ATTACK,pid)\nif notification==nil then return string.format('notification|%d|%d|none',Game.GetCurrentGameTurn(),pid) end\nassert(type(notification.IsDismissed)=='function','Notification:IsDismissed unavailable')\nlocal dismissed=notification:IsDismissed(); assert(type(dismissed)=='boolean','IsDismissed returned non-boolean')\nreturn string.format('notification|%d|%d|%s',Game.GetCurrentGameTurn(),pid,dismissed and 'dismissed' or 'active')\n".encode('ascii')

def parse_notification_status(payload: bytes, *, player_id: int, turn: int) -> str:
    pid = _pid(player_id)
    if type(turn) is not int or turn < 0 or type(payload) is not bytes:
        raise ValueError('notification status inputs are invalid')
    fields = payload.decode('ascii').split('|')
    if len(fields) != 4 or fields[0] != 'notification':
        raise ValueError('notification status is malformed')
    if (int(fields[1]), int(fields[2])) != (turn, pid) or fields[3] not in ('none', 'active', 'dismissed'):
        raise ValueError('notification status is stale or outside its domain')
    return fields[3]

def catalog_source(player_id: int, visible_enemy_units: list[dict]) -> bytes:
    """Use pinned visibility rows and native CanStartCommand for each city/plot."""
    pid = _pid(player_id)
    enemies = _visible_enemy_rows(visible_enemy_units, pid)
    verify_inputs()
    encoded = ','.join(('{%d,%d,%d,%d,%d,%.17g}' % (r['owner'], r['id'], r['type'], r['x'], r['y'], float(r['damage'])) for r in enemies))
    return f"local pid={pid}\nassert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid,'range-attack perspective mismatch')\nlocal player=Players[pid]\nassert(player and player:IsAlive() and player:IsTurnActive() and player:IsTurnActiveComplete(),'player is not ready')\nassert(CityCommandTypes and CityCommandTypes.RANGE_ATTACK==-1967338303 and UnitOperationTypes and UnitOperationTypes.PARAM_X and UnitOperationTypes.PARAM_Y,'city command enum unavailable')\nassert(CityManager and type(CityManager.CanStartCommand)=='function','CityManager.CanStartCommand unavailable')\nassert(PlayersVisibility and PlayersVisibility[pid] and Units and MapLayers and MapLayers.ANY~=nil,'visible target API unavailable')\nlocal inputEnemies={{{encoded}}}; local enemies={{}}\nfor _,enemy in ipairs(inputEnemies) do\n local owner,id,unitType,x,y,damage=enemy[1],enemy[2],enemy[3],enemy[4],enemy[5],enemy[6]\n assert(PlayersVisibility[pid]:IsVisible(x,y),'observation target plot is no longer visible')\n local found=Units.GetUnitsInPlotLayerID(x,y,MapLayers.ANY); local matches=0; local target=nil\n if found~=nil then for _,unit in pairs(found) do\n  if PlayersVisibility[pid]:IsUnitVisible(unit) and not unit:IsDelayedDeath()\n     and unit:GetOwner()==owner and unit:GetID()==id and unit:GetType()==unitType then matches=matches+1; target=unit end\n end end\n assert(matches==1 and target and target:GetDamage()==damage,'visible target changed since observation')\n enemies[#enemies+1]=enemy\nend\nlocal turn=Game.GetCurrentGameTurn()\nlocal out={{string.format('state|%d|%d',turn,pid)}}; local cityCount=0\nlocal enemyCount=#enemies; local cities={{}}; local cityTotal=0\nfor _,city in player:GetCities():Members() do\n cityTotal=cityTotal+1; assert(cityTotal<=4096 and city:GetOwner()==pid,'own city collection invalid')\n cities[cityTotal]=city\nend\nassert(cityTotal>0 and cityTotal*enemyCount<=100000,'city/visible-enemy candidate product exceeds bound')\nfor _,city in ipairs(cities) do\n cityCount=cityCount+1\n for _,enemy in ipairs(enemies) do\n  local owner,id,unitType,x,y,damage=enemy[1],enemy[2],enemy[3],enemy[4],enemy[5],enemy[6]\n  local params={{}}; params[UnitOperationTypes.PARAM_X]=x; params[UnitOperationTypes.PARAM_Y]=y\n  local legal=CityManager.CanStartCommand(city,CityCommandTypes.RANGE_ATTACK,params)\n  assert(type(legal)=='boolean','CanStartCommand returned non-boolean')\n  if legal then\n   out[#out+1]=string.format('candidate|%d|%d|%d|%d|%d|%d|%d|%d|%.17g',city:GetID(),city:GetX(),city:GetY(),owner,id,unitType,x,y,damage)\n  end\n end\nend\nassert(cityCount>0,'no own cities available')\nreturn table.concat(out,'\\n')\n".encode('ascii')

def parse_catalog(payload: bytes, player_id: int) -> dict:
    pid = _pid(player_id)
    if type(payload) is not bytes:
        raise ValueError('catalog result must be bytes')
    try:
        lines = payload.decode('ascii').splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError('catalog is not ASCII') from exc
    if not lines:
        raise ValueError('empty city target catalog')
    state = lines[0].split('|')
    if len(state) != 3 or state[0] != 'state':
        raise ValueError('catalog state row malformed')
    turn, observed_pid = map(int, state[1:])
    if observed_pid != pid or turn < 0:
        raise ValueError('catalog state outside admitted domain')
    candidates = []
    seen = set()
    for line in lines[1:]:
        fields = line.split('|')
        if len(fields) != 10 or fields[0] != 'candidate':
            raise ValueError('candidate row malformed')
        city_id, cx, cy, owner, unit_id, unit_type, x, y = map(int, fields[1:9])
        damage = float(fields[9])
        if min(city_id, cx, cy, x, y, owner, unit_id, unit_type) < 0 or max(city_id, cx, cy, x, y, owner, unit_id, unit_type) > 4294967295 or owner >= 64 or (owner == pid) or (not math.isfinite(damage)) or (not damage.is_integer()) or (damage < 0):
            raise ValueError('candidate values outside admitted domain')
        key = (city_id, owner, unit_id)
        if key in seen:
            raise ValueError('duplicate target candidate')
        seen.add(key)
        candidates.append({'city_id': city_id, 'city_x': cx, 'city_y': cy, 'x': x, 'y': y, 'target_owner': owner, 'target_unit_id': unit_id, 'target_unit_type': unit_type, 'before_damage': int(damage)})
    return {'player_id': pid, 'turn': turn, 'candidates': candidates}

def request_source(player_id: int, turn: int, candidate: dict) -> bytes:
    pid = _pid(player_id)
    if type(turn) is not int or turn < 0:
        raise ValueError('turn must be a nonnegative integer')
    required = ('city_id', 'city_x', 'city_y', 'x', 'y', 'target_owner', 'target_unit_id', 'target_unit_type', 'before_damage')
    if type(candidate) is not dict or any((type(candidate.get(k)) is not int for k in required)):
        raise ValueError('candidate fields must be exact integers')
    c = candidate
    if not 0 <= c['target_owner'] < 64 or c['target_owner'] == pid or any((not 0 <= c[k] <= 4294967295 for k in ('city_id', 'city_x', 'city_y', 'x', 'y', 'target_unit_id'))) or (not -2147483648 <= c['target_unit_type'] <= 4294967295) or (c['before_damage'] < 0):
        raise ValueError('invalid target candidate')
    verify_inputs()
    return f"local pid={pid}; local expectedTurn={turn}\nlocal cityID={c['city_id']}; local cx={c['city_x']}; local cy={c['city_y']}\nlocal x={c['x']}; local y={c['y']}\nlocal targetOwner={c['target_owner']}; local targetID={c['target_unit_id']}; local targetType={c['target_unit_type']}; local beforeDamage={c['before_damage']}\nassert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==expectedTurn,'stale city attack turn/perspective')\nlocal player=Players[pid]; assert(player and player:IsAlive() and player:IsTurnActive() and player:IsTurnActiveComplete(),'player is no longer ready')\nassert(CityCommandTypes and CityCommandTypes.RANGE_ATTACK==-1967338303 and UnitOperationTypes and UnitOperationTypes.PARAM_X and UnitOperationTypes.PARAM_Y,'city command enum unavailable')\nlocal notice=NotificationManager.FindType(NotificationTypes.CITY_RANGE_ATTACK,pid)\nassert(notice~=nil and type(notice.IsDismissed)=='function' and notice:IsDismissed()==false,'city range attack notification is not active')\nlocal city=nil; local count=0\nfor _,item in player:GetCities():Members() do\n if item:GetID()==cityID then count=count+1; city=item end\nend\nassert(count==1 and city and city:GetOwner()==pid and city:GetX()==cx and city:GetY()==cy,'own city identity changed')\nlocal vis=PlayersVisibility[pid]; assert(vis and vis:IsVisible(x,y),'target plot is no longer visible')\nlocal visibleUnits=Units.GetUnitsInPlotLayerID(x,y,MapLayers.ANY); local found=nil; local matches=0\nif visibleUnits~=nil then for _,unit in pairs(visibleUnits) do\n if vis:IsUnitVisible(unit) and not unit:IsDelayedDeath() and unit:GetOwner()==targetOwner and unit:GetID()==targetID and unit:GetType()==targetType then found=unit; matches=matches+1 end\nend end\nassert(matches==1 and found and found:GetDamage()==beforeDamage,'target unit identity/damage changed')\nlocal params={{}}; params[UnitOperationTypes.PARAM_X]=x; params[UnitOperationTypes.PARAM_Y]=y\nlocal legal=CityManager.CanStartCommand(city,CityCommandTypes.RANGE_ATTACK,params)\nassert(type(legal)=='boolean' and legal,'native CanStartCommand refused immediately before request')\nCityManager.RequestCommand(city,CityCommandTypes.RANGE_ATTACK,params)\nreturn string.format('submitted|%d|%d|%d|%d',expectedTurn,cityID,targetOwner,targetID)\n".encode('ascii')

def readback_source(player_id: int, candidate: dict, *, allow_absence=False) -> bytes:
    if type(allow_absence) is not bool:
        raise ValueError('allow_absence must be exact bool')
    pid = _pid(player_id)
    keys = ('x', 'y', 'target_owner', 'target_unit_id', 'target_unit_type')
    if type(candidate) is not dict or any((type(candidate.get(k)) is not int for k in keys)):
        raise ValueError('readback candidate fields must be exact integers')
    c = candidate
    if not 0 <= c['target_owner'] < 64 or any((not 0 <= c[k] <= 4294967295 for k in ('x', 'y', 'target_unit_id'))) or (not -2147483648 <= c['target_unit_type'] <= 4294967295):
        raise ValueError('readback target identity is outside its domain')
    verify_inputs()
    absence_scan = ''
    absence_result = ''
    if allow_absence:
        absence_scan = "local identityCount=0\nif visibleUnits~=nil then for _,unit in pairs(visibleUnits) do\n if vis:IsUnitVisible(unit) and unit:GetOwner()==owner and unit:GetID()==id then identityCount=identityCount+1 end\nend end\nassert(identityCount==count,'target identity remains but type/lifetime changed')\nassert(count==0 or (count==1 and found),'ambiguous target identity')\n"
        absence_result = "if count==0 then return string.format('absent|%d|%d|%d|%d|%d|%s',Game.GetCurrentGameTurn(),pid,owner,id,expectedType,status) end\n"
    return f"""local pid={pid}; local x={c['x']}; local y={c['y']}\nlocal owner={c['target_owner']}; local id={c['target_unit_id']}; local expectedType={c['target_unit_type']}\nassert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid,'readback perspective changed')\nlocal vis=PlayersVisibility and PlayersVisibility[pid]\nassert(vis and vis:IsVisible(x,y),'target is no longer visible')\nlocal visibleUnits=Units.GetUnitsInPlotLayerID(x,y,MapLayers.ANY); local found=nil; local count=0\nif visibleUnits~=nil then for _,unit in pairs(visibleUnits) do\n if vis:IsUnitVisible(unit) and not unit:IsDelayedDeath() and unit:GetOwner()==owner and unit:GetID()==id and unit:GetType()==expectedType then found=unit; count=count+1 end\nend end\n{(absence_scan if allow_absence else "assert(count==1 and found,'target unit no longer exists as one visible object')")}\nlocal notification=NotificationManager.FindType(NotificationTypes.CITY_RANGE_ATTACK,pid)\nlocal status='none'\nif notification~=nil then\n assert(type(notification.IsDismissed)=='function','Notification:IsDismissed unavailable')\n local dismissed=notification:IsDismissed(); assert(type(dismissed)=='boolean','IsDismissed returned non-boolean')\n status=dismissed and 'dismissed' or 'active'\nend\n{absence_result}return string.format('effect|%d|%d|%d|%d|%d|%.17g|%s',Game.GetCurrentGameTurn(),pid,owner,id,expectedType,found:GetDamage(),status)\n""".encode('ascii')

def parse_effect(payload: bytes, *, player_id: int, turn: int, candidate: dict) -> dict:
    _pid(player_id)
    if type(payload) is not bytes:
        raise ValueError('effect result must be bytes')
    fields = payload.decode('ascii').split('|')
    if len(fields) != 8 or fields[0] != 'effect':
        raise ValueError('effect result malformed')
    got_turn, pid, owner, unit_id, unit_type = map(int, fields[1:6])
    damage = float(fields[6])
    notification = fields[7]
    if got_turn != turn or pid != player_id or owner != candidate['target_owner'] or (unit_id != candidate['target_unit_id']) or (unit_type != candidate['target_unit_type']) or (not math.isfinite(damage)) or (not damage.is_integer()) or (damage <= candidate['before_damage']) or (notification not in {'none', 'active', 'dismissed'}):
        raise ValueError('post-delivery native damage/identity readback did not confirm the shot')
    return {'turn': got_turn, 'player_id': pid, 'target_owner': owner, 'target_unit_id': unit_id, 'target_unit_type': unit_type, 'before_damage': candidate['before_damage'], 'after_damage': int(damage), 'notification_after': notification, 'native_effect_verified': True, 'notification_cleared_or_dismissed': notification in {'none', 'dismissed'}}

def parse_effect_or_kill(payload, *, player_id, turn, candidate, window, archive_sha256):
    if type(payload) is not bytes:
        raise ValueError('readback result must be bytes')
    if payload.startswith(b'effect|'):
        return parse_effect(payload, player_id=player_id, turn=turn, candidate=candidate)
    _pid(player_id)
    if type(turn) is not int or not 0 <= turn <= 2147483647 or type(candidate) is not dict or any((type(candidate.get(k)) is not int for k in ('target_owner', 'target_unit_id', 'target_unit_type', 'before_damage'))):
        raise ValueError('absent target readback requires exact candidate/turn integers')
    fields = payload.decode('ascii').split('|')
    if len(fields) != 7 or fields[0] != 'absent':
        raise ValueError('unrecognized city-shot readback')
    expected = [turn, player_id, candidate['target_owner'], candidate['target_unit_id'], candidate['target_unit_type']]
    if list(map(int, fields[1:6])) != expected or fields[6] not in {'none', 'active', 'dismissed'}:
        raise ValueError('absent target identity/perspective changed')
    kill = window.verify(candidate, archive_sha256, attacking_player_id=player_id)
    return {'turn': turn, 'player_id': player_id, 'target_owner': candidate['target_owner'], 'target_unit_id': candidate['target_unit_id'], 'target_unit_type': candidate['target_unit_type'], 'before_damage': candidate['before_damage'], 'after_damage': None, 'damage_readback_unavailable': True, 'target_killed_verified': True, 'target_unit_type_source': 'pre-request-visible-unit', 'native_effect_verified': True, 'effect_kind': 'target-killed-individual-event', 'notification_after': fields[6], 'notification_cleared_or_dismissed': fields[6] in {'none', 'dismissed'}, 'kill_evidence': kill}

def submit_deliver_publish_readback(runtime, ui_child, actions, deferred_events, view_publisher, player_id: int, turn: int, candidate: dict) -> dict:
    """Request one real command, deliver it, publish, then verify target damage.

    Candidates come from the existing visibility-bounded player observation.
    Each candidate is admitted by native CanStartCommand with the same X/Y
    parameters as the official WorldInput click path. No mode parameter,
    geometry rule, or archive is fabricated here.
    """
    if getattr(actions, '_city_range_attack_producing', False) or getattr(actions, '_city_range_attack_poisoned', False):
        raise RuntimeError('city ranged-attack owner is busy or poisoned')
    if ui_child is None or actions.pending or deferred_events.pending:
        raise RuntimeError('city shot requires UI child and empty command/deferred queues')
    notification = parse_notification_status(runtime.evaluate_text(ui_child, notification_status_source(player_id), b'@work_city_range_notification', capacity=4096), player_id=player_id, turn=turn)
    if notification != 'active':
        raise RuntimeError('city attack requires an actually active, non-dismissed notification')
    observation = collect_player_observation(runtime, ui_child, player_id)
    if observation['turn'] != turn:
        raise RuntimeError('player observation turn is stale')
    before = parse_catalog(runtime.evaluate_text(ui_child, catalog_source(player_id, observation['visible_enemy_units']), b'@work_city_range_catalog', capacity=262144), player_id)
    if before['turn'] != turn or candidate not in before['candidates']:
        raise RuntimeError('city attack candidate is stale or no longer native-admitted')
    request = request_source(player_id, turn, candidate)
    actions._city_range_attack_producing = True
    actions._city_range_attack_poisoned = True
    try:
        with KillReceiptWindow(actions, deferred_events, view_publisher) as window:
            request_reply = runtime.evaluate_text(ui_child, request, b'@work_city_range_request', capacity=4096)
            if request_reply != f"submitted|{turn}|{candidate['city_id']}|{candidate['target_owner']}|{candidate['target_unit_id']}".encode('ascii'):
                raise RuntimeError('CityManager.RequestCommand did not return the expected marker')
            if len(actions.pending) != 1:
                raise RuntimeError('RequestCommand did not produce exactly one captured native archive')
            archive_sha256 = hashlib.sha256(actions.pending[0]).hexdigest()
            actions.deliver_one()
            if actions.pending:
                raise RuntimeError('action archive remains queued after delivery')
            deferred_events.drain_empty_receivers()
            if deferred_events.pending:
                raise RuntimeError('deferred native events remain after drain')
            view_publisher.publish()
            if actions.pending or deferred_events.pending:
                raise RuntimeError('host queues are not empty after publish')
            effect = parse_effect_or_kill(runtime.evaluate_text(ui_child, readback_source(player_id, candidate, allow_absence=True), b'@work_city_range_effect', capacity=4096), player_id=player_id, turn=turn, candidate=candidate, window=window, archive_sha256=archive_sha256)
        actions._city_range_attack_poisoned = False
        return {'request_returned': True, 'captured_archive_sha256': archive_sha256, 'archive_fabricated': False, 'received_and_drained': True, 'view_published': True, **effect, 'notification_invalidation_verified': effect['notification_cleared_or_dismissed'], 'eligible_for_training': False}
    except BaseException:
        actions._city_range_attack_poisoned = True
        raise
    finally:
        actions._city_range_attack_producing = False

def collect_player_observation(runtime, child, player_id: int) -> dict:
    _pid(player_id)
    from civ6_host.runtime.native.native_player_observation import observe_player
    return observe_player(runtime, child, player_id)
