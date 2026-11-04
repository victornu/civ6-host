"""Explicit known-city-state war declaration via the official player operation.

Majors use the distinct DiplomacyManager session path in DeclareWarPopup and
are deliberately not routed through this minor-specific adapter.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib, struct
from civ6_host.runtime.native import native_envoy_actions as envoy
from civ6_host.runtime.native import native_player_operation_request as operation
from civ6_host.runtime.native.native_player_observation import observe_player
UI_PATH = envoy.UI_PATH.parents[1] / 'Popups/DeclareWarPopup.lua'
UI_SHA256 = 'f95b880edb5ee6deb5244b0d82429d8541de93f3cf1c8840bf09fd4deaadd208'

def _player_id(value):
    return envoy._integer(value, 'player', 63)

def source(turn, *, player_id=0):
    pid = _player_id(player_id)
    envoy._integer(turn, 'turn', 100000)
    envoy.verify_source()
    if hashlib.sha256(_resolve_resource_path(UI_PATH).read_bytes()).hexdigest() != UI_SHA256:
        raise RuntimeError('Native war UI source changed')
    return "local turn=__TURN__\nassert(Game.GetLocalPlayer()==__PID__ and Game.GetLocalObserver()==__PID__ and Game.GetCurrentGameTurn()==turn,'war perspective changed')\nlocal p=Players[__PID__]\nassert(p and p:IsAlive() and p:IsTurnActive() and p:IsTurnActiveComplete() and Game.IsAllowStrategicCommands(__PID__),'war player not ready')\nlocal d=p:GetDiplomacy()\nassert(d and type(d.HasMet)=='function' and type(d.CanDeclareWarOn)=='function' and type(d.IsAtWarWith)=='function','native diplomacy unavailable')\nlocal function n(v)\n assert(type(v)=='number' and v%1==0 and v>=-2147483648 and v<=4294967295,'invalid native war enum')\n return string.format('%.0f',v%4294967296)\nend\nlocal out={n(turn),n(PlayerOperations.DIPLOMACY_DECLARE_WAR),n(PlayerOperations.PARAM_PLAYER_ONE),n(PlayerOperations.PARAM_PLAYER_TWO)}\nlocal minors=PlayerManager.GetAliveMinors();assert(type(minors)=='table' and #minors<=63,'invalid minors')\nlocal seen={}\nfor _,minor in ipairs(minors) do\n local id=minor:GetID();assert(type(id)=='number' and id%1==0 and id>=1 and id<=63 and not seen[id],'invalid minor identity');seen[id]=true\n local met=d:HasMet(id);assert(type(met)=='boolean','invalid contact state')\n if met then\n  local war,can=d:IsAtWarWith(id),d:CanDeclareWarOn(id)\n  assert(type(war)=='boolean' and type(can)=='boolean','invalid war state')\n  out[#out+1]=n(id)..':'..(war and '1' or '0')..':'..(can and '1' or '0')\n end\nend\nreturn table.concat(out,'|')\n".replace('__PID__', str(pid)).replace('__TURN__', str(turn)).encode('ascii')

def parse(raw, turn, *, player_id=0):
    pid = _player_id(player_id)
    if type(raw) is not bytes or len(raw) > 8192:
        raise ValueError('Invalid minor war result')
    parts = raw.decode('ascii').split('|')

    def number(v):
        if not v.isascii() or not v.isdecimal() or str(int(v)) != v or (int(v) > 4294967295):
            raise ValueError('Malformed minor war integer')
        return int(v)
    if len(parts) < 4 or number(parts[0]) != turn:
        raise ValueError('Stale minor war catalogue')
    op, one, two = map(number, parts[1:4])
    if one == two:
        raise ValueError('War parameter keys collide')
    rows = []
    seen = set()
    for token in parts[4:]:
        fields = token.split(':')
        if len(fields) != 3:
            raise ValueError('Malformed minor war row')
        target, war, can = map(number, fields)
        if not 1 <= target <= 63 or target in seen or war not in (0, 1) or (can not in (0, 1)):
            raise ValueError('Invalid minor war state')
        seen.add(target)
        rows.append(dict(target_player_id=target, at_war=bool(war), can_declare=bool(can)))
    return dict(player_id=pid, turn=turn, operation=op, player_one_key=one, player_two_key=two, rows=rows)

def parameters(catalog, target, *, player_id=None):
    pid = _player_id(catalog.get('player_id', 0) if player_id is None else player_id)
    if catalog.get('player_id', pid) != pid:
        raise ValueError('Minor war catalogue belongs to another actor')
    target = _player_id(target)
    if target == pid:
        raise ValueError('A player cannot declare war on itself')
    return {catalog['player_one_key']: pid, catalog['player_two_key']: target}

def catalog(prefix, turn, *, player_id=0):
    pid = _player_id(player_id)
    result = parse(prefix.runtime.evaluate_text(prefix.ui_child, source(turn, player_id=pid), b'@explicit_minor_war_catalog'), turn, player_id=pid)
    result['candidates'] = []
    for row in result['rows']:
        if row['target_player_id'] == pid:
            continue
        if row['at_war'] or not row['can_declare']:
            continue
        check = operation.request_player_operation(prefix.core, prefix.context, pid, result['operation'], parameters(result, row['target_player_id'], player_id=pid), submit=False)
        if check['request_invoked']:
            raise RuntimeError('Read-only war eligibility submitted an order')
        if check['can_start']:
            result['candidates'].append(dict(kind='declare_war_minor', target_player_id=row['target_player_id']))
    return result

def apply(owner, prefix, action, turn, before, *, player_id=0):
    pid = _player_id(player_id)
    actor = before.get('player_id') if type(before) is dict else None
    observed_turn = before.get('turn') if type(before) is dict else None
    if type(actor) is not int or actor != pid or type(observed_turn) is not int or (observed_turn != turn):
        raise RuntimeError('Minor war action lacks matching actor observation')
    fresh = catalog(prefix, turn, player_id=pid)
    if action not in fresh['candidates']:
        raise RuntimeError('Minor war declaration no longer offered')
    target = action['target_player_id']
    params = parameters(fresh, target, player_id=pid)
    receipt = operation.request_player_operation(prefix.core, prefix.context, pid, fresh['operation'], params)
    if not receipt['can_start'] or not receipt['request_invoked'] or len(prefix.actions.pending) != 1:
        raise RuntimeError('Native minor war operation not queued exactly once')
    if prefix.actions.pending[0][:4] != struct.pack('<I', 3294486831):
        raise RuntimeError('Unexpected native player operation archive')
    prefix.actions.deliver_one()
    prefix.deferred_events.drain_empty_receivers()
    prefix.view_publisher.publish()
    after = observe_player(prefix.runtime, prefix.ui_child, pid)
    observed = parse(prefix.runtime.evaluate_text(prefix.ui_child, source(turn, player_id=pid), b'@explicit_minor_war_effect'), turn, player_id=pid)
    matches = [r for r in observed['rows'] if r['target_player_id'] == target]
    if len(matches) != 1 or matches[0]['at_war'] is not True:
        raise RuntimeError('Native war state did not change')
    owner.emit('official_explicit_minor_war_effect', action=action, operation_receipt=receipt, operation_parameters=params, before=fresh, after=observed, observation_before=before, observation_after=after, automatic_choices_applied=False, ui_source_sha256=UI_SHA256, native_war_verified=True)
    return after
