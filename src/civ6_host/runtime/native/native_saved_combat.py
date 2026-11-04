"""Player-visible combat orders to plots, executed by the official UnitManager.

An order names a plot, not a chosen defender. Native combat selects the defender.
Readback reports actual own-unit/visible-unit changes and never infers a kill
from disappearance. Damage, capture and retreat rules remain inside GameCore.
"""
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _UNIT_ATTACK_BASE_CORE_SHA256
from civ6_host.contracts.capability_unit_attacks import validate_action, validate_units, verify_observation, validate_relationships
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _WORLD_BASE_CORE_SHA256
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import json, math
from pathlib import Path
from civ6_host.runtime.native import native_combat_actions as native
from civ6_host.runtime.native import native_saved_city_targets as city_targets
from civ6_host.runtime.native.native_player_observation import observe_player
FIELDS = {'kind', 'unit_id', 'operation', 'input_route', 'plot_id', 'x', 'y'}
UNIT_FIELDS = {'unit_id', 'unit_type', 'x', 'y', 'damage', 'moves', 'attacks_remaining'}
QUEUED_SOURCE_SHA = '1de3fd72c31544439f906499a80d3e69a531771f729fc5b126f0bf6f26373273'

def queued_destination_source(player_id, turn, unit_id, *, core_sha256=_WORLD_BASE_CORE_SHA256):
    if core_sha256 == _WORLD_BASE_CORE_SHA256:
        from civ6_host.runtime.native.native_source_cache import load_pinned_json
        proof = load_pinned_json(_resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_saved_combat.py')))).resolve().parents[1] / 'work/capture941/queued-source.json', QUEUED_SOURCE_SHA)
        if proof['registration']['callback_va'] != '0x180549470' or proof['core']['sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
            raise ValueError('Queued destination source changed')
    else:
        from civ6_host.runtime.xp1_world_input_profile import verify_source
        verify_source(core_sha256)
    _player_id(player_id)
    native._uint(turn, 'turn')
    native._uint(unit_id, 'unit')
    return "local pid,turn,id=__PID__,__TURN__,__UNIT__\nassert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,'queued-order perspective changed')\nlocal player=Players[pid]\nassert(player and player:IsAlive() and player:IsTurnActive() and player:IsTurnActiveComplete(),'queued-order player not ready')\nlocal found=nil\nfor _,u in player:GetUnits():Members() do\n assert(u:GetOwner()==pid,'foreign unit in own roster')\n if u:GetID()==id then assert(found==nil,'duplicate own unit'); found=u end\nend\nif found==nil then return 'absent' end\nassert(type(UnitManager.GetQueuedDestination)=='function','native queued destination unavailable')\nlocal p=UnitManager.GetQueuedDestination(found)\nif p==nil then return 'none' end\nassert(type(p)=='number' and p%1==0 and p>=0 and p<Map.GetPlotCount(),'invalid queued plot')\nreturn string.format('%d',p)\n".replace('__PID__', str(player_id)).replace('__TURN__', str(turn)).replace('__UNIT__', str(unit_id)).encode('ascii')

def queued_destination(prefix, player_id, turn, unit_id, width, height, *, core_sha256=_WORLD_BASE_CORE_SHA256):
    raw = prefix.runtime.evaluate_text(prefix.ui_child, queued_destination_source(player_id, turn, unit_id, core_sha256=core_sha256), b'@explicit_own_queued_destination', capacity=32)
    if raw in (b'absent', b'none'):
        return dict(unit_present=raw != b'absent', plot_id=None)
    if type(raw) is not bytes or not raw.isdigit() or len(raw) > 5:
        raise ValueError('Invalid queued destination readback')
    plot = int(raw)
    if not 0 <= plot < width * height or str(plot).encode() != raw:
        raise ValueError('Queued destination outside map')
    return dict(unit_present=True, plot_id=plot)

def queued_orders_source(player_id, turn, *, core_sha256=_WORLD_BASE_CORE_SHA256):
    queued_destination_source(player_id, turn, 0, core_sha256=core_sha256)
    return 'local pid,turn=__PID__,__TURN__\nassert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,\'queued-order perspective changed\')\nlocal player=Players[pid]\nassert(player and player:IsAlive() and player:IsTurnActive() and player:IsTurnActiveComplete(),\'queued-order player not ready\')\nassert(type(UnitManager.GetQueuedDestination)==\'function\',\'native queued destination unavailable\')\nlocal width,height=Map.GetGridSize()\nassert(type(width)==\'number\' and type(height)==\'number\' and width%1==0 and height%1==0 and width>0 and height>0\n and width*height==Map.GetPlotCount() and width*height<=16384,\'queued-order map invalid\')\nlocal rows,seen={},{}\nfor _,u in player:GetUnits():Members() do\n assert(#rows<4096 and u:GetOwner()==pid,\'unbounded or foreign own unit collection\')\n local id=u:GetID()\n assert(type(id)==\'number\' and id%1==0 and id>=0 and id<=4294967295 and not seen[id],\'queued-order unit identity invalid\')\n seen[id]=true\n local p=UnitManager.GetQueuedDestination(u)\n assert(p==nil or (type(p)==\'number\' and p%1==0 and p>=0 and p<width*height),\'invalid queued plot\')\n rows[#rows+1]=\'{"unit_id":\'..string.format(\'%.0f\',id)..\',"plot_id":\'..(p==nil and \'null\' or string.format(\'%d\',p))..\'}\'\nend\nreturn \'{"player_id":\'..pid..\',"turn":\'..turn..\',"width":\'..width..\',"height":\'..height..\',"units":[\'..table.concat(rows,\',\')..\']}\'\n'.replace('__PID__', str(player_id)).replace('__TURN__', str(turn)).encode('ascii')

def validate_queued_orders(value, player_id, turn, width, height, unit_ids):
    _player_id(player_id)
    native._uint(turn, 'turn')
    if type(value) is not dict or set(value) != {'player_id', 'turn', 'width', 'height', 'units'} or any((type(value[k]) is not int for k in ('player_id', 'turn', 'width', 'height'))) or ((value['player_id'], value['turn'], value['width'], value['height']) != (player_id, turn, width, height)) or (not 0 < width * height <= 16384) or (type(value['units']) is not list) or (len(value['units']) > 4096):
        raise ValueError('Invalid own queued-order observation identity or bounds')
    ids = []
    for row in value['units']:
        if type(row) is not dict or set(row) != {'unit_id', 'plot_id'}:
            raise ValueError('Malformed queued-order unit')
        native._uint(row['unit_id'], 'unit')
        ids.append(row['unit_id'])
        validate_queued_destination(dict(unit_present=True, plot_id=row['plot_id']), width, height)
    if ids != sorted(set(ids)) or ids != sorted(unit_ids):
        raise ValueError('Queued-order roster differs from own units')
    return value

def queued_orders(prefix, observation, *, player_id=0, core_sha256=_WORLD_BASE_CORE_SHA256):
    if type(observation) is not dict or type(observation.get('player_id')) is not int or observation['player_id'] != player_id:
        raise ValueError('Queued-order observation actor differs')
    turn = observation['turn']
    width = observation['width']
    height = observation['height']
    raw = prefix.runtime.evaluate_text(prefix.ui_child, queued_orders_source(player_id, turn, core_sha256=core_sha256), b'@explicit_own_queued_orders', capacity=262145)
    if type(raw) is not bytes or len(raw) > 262144:
        raise ValueError('Unbounded queued-order observation')
    value = json.loads(raw, object_pairs_hook=native._pairs_no_duplicates)
    if type(value) is not dict or type(value.get('units')) is not list:
        raise ValueError('Malformed queued-order observation')
    if any((type(r) is not dict or type(r.get('unit_id')) is not int for r in value['units'])):
        raise ValueError('Malformed queued-order roster')
    value['units'].sort(key=lambda r: r['unit_id'])
    return validate_queued_orders(value, player_id, turn, width, height, [u['id'] for u in observation['units']])

def _player_id(value):
    return native._player_id(value)

def orders(catalog, *, player_id=0):
    pid = _player_id(player_id)
    if catalog.get('player_id', 0) != pid:
        raise ValueError('Combat catalogue belongs to another actor')
    result = {}
    wars = {r['owner']: r['at_war'] for r in validate_relationships(catalog['relationships'], player_id=pid)}
    for row in catalog['candidates'] + catalog.get('city_candidates', []):
        if row['target_owner'] == pid:
            raise ValueError('Combat candidate targets its own actor')
        if row['target_owner'] not in wars:
            raise ValueError('Visible target has no diplomacy observation')
        if not wars[row['target_owner']]:
            continue
        value = dict(kind='unit_attack', unit_id=row['unit_id'], operation=row['operation'], input_route=row['input_route'], plot_id=row['y'] * catalog['width'] + row['x'], x=row['x'], y=row['y'])
        validate_action(value, catalog['width'], catalog['height'])
        result[value['unit_id'], value['operation'], value['input_route'], value['plot_id']] = value
    return [result[k] for k in sorted(result)]

def relationships(prefix, turn, observation, *, player_id=0, cities=(), core_sha256=_UNIT_ATTACK_BASE_CORE_SHA256):
    if core_sha256 != _UNIT_ATTACK_BASE_CORE_SHA256:
        from civ6_host.runtime.xp1_unit_attack_profile import verify_source as selected_source
        selected_source(core_sha256)
    pid = _player_id(player_id)
    if type(observation) is not dict or type(observation.get('player_id')) is not int or observation.get('player_id') != pid or (observation.get('turn') != turn):
        raise ValueError('Combat relationship observation actor/turn differs')
    owners = sorted({r['owner'] for r in observation['visible_enemy_units']} | {r['owner'] for r in cities if r['owner'] != pid})
    if any((type(o) is not int or not 0 <= o <= 63 or o == pid for o in owners)):
        raise ValueError('Foreign owner outside native player domain')
    native._uint(turn, 'turn')
    source = 'local turn=__TURN__\nassert(Game.GetLocalPlayer()==__PID__ and Game.GetLocalObserver()==__PID__ and Game.GetCurrentGameTurn()==turn,\'diplomacy perspective changed\')\nlocal diplomacy=Players[__PID__]:GetDiplomacy()\nassert(diplomacy and type(diplomacy.IsAtWarWith)==\'function\',\'native own diplomacy unavailable\')\nlocal rows={}\nfor _,owner in ipairs({__OWNERS__}) do\n local war=diplomacy:IsAtWarWith(owner)\n assert(type(war)==\'boolean\',\'invalid native war state\')\n rows[#rows+1]=\'{"owner":\'..string.format(\'%d\',owner)..\',"at_war":\'..(war and \'true\' or \'false\')..\'}\'\nend\nreturn \'[\'..table.concat(rows,\',\')..\']\'\n'.replace('__PID__', str(pid)).replace('__TURN__', str(turn)).replace('__OWNERS__', ','.join(map(str, owners))).encode('ascii')
    raw = prefix.runtime.evaluate_text(prefix.ui_child, source, b'@explicit_visible_combat_diplomacy', capacity=8193)
    if type(raw) is not bytes or len(raw) > 8192:
        raise ValueError('Unbounded native diplomacy result')
    rows = validate_relationships(json.loads(raw, object_pairs_hook=native._pairs_no_duplicates), player_id=pid)
    if [r['owner'] for r in rows] != owners:
        raise ValueError('Diplomacy result differs from visible target owners')
    return rows

def catalog(prefix, turn, observation, *, player_id=0, core_sha256=_UNIT_ATTACK_BASE_CORE_SHA256, visible_scope=None):
    from civ6_host.runtime.xp1_attack_visible_scope import check, checked_result
    check(visible_scope, prefix, turn, player_id, core_sha256)
    pid = _player_id(player_id)
    if type(observation) is not dict or type(observation.get('player_id')) is not int or observation.get('player_id') != pid or (observation.get('turn') != turn):
        raise ValueError('Combat catalogue observation actor/turn differs')
    result = None
    for route in ('enemy_flag', 'dedicated_ranged'):
        raw = native.parse_candidates(prefix.runtime.evaluate_text(prefix.ui_child, native.candidate_source(pid, turn, ranged_modifier=route == 'enemy_flag', core_sha256=core_sha256), b'@explicit_combat_catalog', capacity=2097153), pid, turn, core_sha256=core_sha256)
        if result is None:
            result = {k: v for k, v in raw.items() if k != 'candidates'}
            result['candidates'] = []
        elif (raw['width'], raw['height']) != (result['width'], result['height']):
            raise ValueError('Combat input routes crossed map identity')
        result['candidates'].extend((dict(row, input_route=route) for row in raw['candidates'] if route == 'enemy_flag' or row['operation'] == 'RANGE_ATTACK'))
    city_catalog = city_targets.catalog(prefix, turn, player_id=pid, core_sha256=core_sha256, visible_scope=visible_scope)
    if (city_catalog['width'], city_catalog['height']) != (result['width'], result['height']):
        raise ValueError('City targets crossed native map identity')
    result['cities'] = city_catalog['cities']
    result['city_candidates'] = city_catalog['candidates']
    result['relationships'] = relationships(prefix, turn, observation, player_id=pid, cities=result['cities'], core_sha256=core_sha256)
    return checked_result(visible_scope, prefix, turn, player_id, core_sha256, result)

def unit_state_source(turn, *, player_id=0, core_sha256=_UNIT_ATTACK_BASE_CORE_SHA256):
    pid = _player_id(player_id)
    native._uint(turn, 'turn')
    native.verify_source_evidence(core_sha256=core_sha256)
    return 'local pid,expectedTurn=__PID__,__TURN__\nassert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==expectedTurn,\n \'combat unit state perspective or turn changed\')\nlocal player=Players[pid]\nassert(player and player:IsAlive() and player:IsTurnActive() and player:IsTurnActiveComplete(),\'combat player not ready\')\nlocal rows={}\nlocal function n(v)\n assert(type(v)==\'number\' and v==v and v~=math.huge and v~=-math.huge,\'invalid own combat state\')\n return string.format(\'%.17g\',v)\nend\nfor _,u in player:GetUnits():Members() do\n assert(#rows<4096 and u:GetOwner()==pid,\'own combat roster invalid\')\n assert(type(u.GetAttacksRemaining)==\'function\',\'native attack count unavailable\')\n rows[#rows+1]=\'{"unit_id":\'..n(u:GetID())..\',"unit_type":\'..n(u:GetType())..\n  \',"x":\'..n(u:GetX())..\',"y":\'..n(u:GetY())..\',"damage":\'..n(u:GetDamage())..\n  \',"moves":\'..n(u:GetMovesRemaining())..\',"attacks_remaining":\'..n(u:GetAttacksRemaining())..\'}\'\nend\nreturn \'{"player_id":\'..n(pid)..\',"turn":\'..n(expectedTurn)..\',"units":[\'..table.concat(rows,\',\')..\']}\'\n'.replace('__PID__', str(pid)).replace('__TURN__', str(turn)).encode('ascii')

def unit_state(prefix, turn, observation, *, player_id=0, core_sha256=_UNIT_ATTACK_BASE_CORE_SHA256):
    pid = _player_id(player_id)
    if type(observation) is not dict or type(observation.get('player_id')) is not int or observation.get('player_id') != pid or (observation.get('turn') != turn):
        raise ValueError('Combat unit observation actor/turn differs')
    raw = prefix.runtime.evaluate_text(prefix.ui_child, unit_state_source(turn, player_id=pid, core_sha256=core_sha256), b'@explicit_combat_units', capacity=1048577)
    if type(raw) is not bytes or len(raw) > 1048576:
        raise ValueError('Combat state response exceeds bound')
    value = json.loads(raw, object_pairs_hook=native._pairs_no_duplicates)
    if type(value) is not dict or set(value) != {'player_id', 'turn', 'units'} or type(value['player_id']) is not int or (value['player_id'] != pid) or (type(value['turn']) is not int) or (value['turn'] != turn):
        raise ValueError('Stale combat unit state')
    rows = validate_units(value['units'])
    verify_observation(rows, observation)
    return sorted(rows, key=lambda r: r['unit_id'])

def validate_queued_destination(value, width, height):
    if type(value) is not dict or set(value) != {'unit_present', 'plot_id'} or type(value['unit_present']) is not bool or (value['plot_id'] is not None and (type(value['plot_id']) is not int or not 0 <= value['plot_id'] < width * height)) or (not value['unit_present'] and value['plot_id'] is not None):
        raise ValueError('Invalid queued movement witness')
    return value

def effect(before, after, units_before, units_after, selected, *, player_id=0, cities_before=None, cities_after=None, queued_before=None, queued_after=None, delivery_window=None, core_sha256=_UNIT_ATTACK_BASE_CORE_SHA256):
    if core_sha256 != _UNIT_ATTACK_BASE_CORE_SHA256:
        from civ6_host.runtime.xp1_unit_attack_profile import verify_source as selected_source
        selected_source(core_sha256)
    pid = _player_id(player_id)
    if type(before) is not dict or type(after) is not dict or type(before.get('player_id')) is not int or (before['player_id'] != pid) or (type(after.get('player_id')) is not int) or (after['player_id'] != pid):
        raise ValueError('Combat effect observations belong to another actor')
    validate_action(selected, before['width'], before['height'])
    if before['turn'] != after['turn'] or (before['width'], before['height']) != (after['width'], after['height']):
        raise ValueError('Combat publication crossed turn or map')
    validate_units(units_before)
    validate_units(units_after)
    verify_observation(units_before, before)
    verify_observation(units_after, after)
    old = [r for r in units_before if r['unit_id'] == selected['unit_id']]
    new = [r for r in units_after if r['unit_id'] == selected['unit_id']]
    if len(old) != 1 or len(new) > 1:
        raise ValueError('Combat actor identity unavailable')
    targets = [r for r in before['visible_enemy_units'] if (r['x'], r['y']) == (selected['x'], selected['y'])]
    cities_before = city_targets.validate_cities([] if cities_before is None else cities_before, before['width'], before['height'])
    cities_after = city_targets.validate_cities([] if cities_after is None else cities_after, after['width'], after['height'])
    old_cities = [r for r in cities_before if r['plot_id'] == selected['plot_id']]
    new_cities = [r for r in cities_after if r['plot_id'] == selected['plot_id']]
    if not targets and (not old_cities):
        raise ValueError('No visible unit or city witness on selected attack plot')
    identities = {(r['owner'], r['id']) for r in targets}
    observed_after = [r for r in after['visible_enemy_units'] if (r['owner'], r['id']) in identities]
    immediate = old != new or targets != observed_after or old_cities != new_cities
    queued = False
    if queued_before is not None or queued_after is not None:
        validate_queued_destination(queued_before, before['width'], before['height'])
        validate_queued_destination(queued_after, after['width'], after['height'])
        if queued_before['unit_present'] != bool(old) or queued_after['unit_present'] != bool(new):
            raise ValueError('Queued movement actor differs from own roster')
        queued = selected['operation'] == 'MOVE_TO' and queued_after['unit_present'] and (queued_after['plot_id'] == selected['plot_id']) and (queued_before['plot_id'] != queued_after['plot_id'])
    changed = immediate or queued
    lifecycle = None
    if not changed and delivery_window is not None:
        if core_sha256 != _UNIT_ATTACK_BASE_CORE_SHA256:
            raise RuntimeError('Expansion attack lifecycle-only no-change readback is unqualified')
        from civ6_host.runtime.native.native_operation_lifecycle import completed_cycle
        lifecycle = completed_cycle(delivery_window, selected, pid, queued_before, queued_after)
    if not changed and lifecycle is None:
        raise RuntimeError('Attack delivered without a verified observable change or native operation lifecycle')
    return dict(actor_before=old[0], actor_after=new[0] if new else None, visible_targets_before=targets, visible_targets_after=observed_after, visible_cities_before=old_cities, visible_cities_after=new_cities, city_ownership_changed=bool(old_cities and new_cities and (old_cities[0]['owner'] != new_cities[0]['owner'])), actor_absent_from_own_roster=not new, observable_native_change=changed, operation_lifecycle=lifecycle, combat_resolution_inferred_from_lifecycle=False, immediate_state_change=immediate, queued_move_to_selected_plot=queued, queued_destination_before=queued_before, queued_destination_after=queued_after, combat_resolution_inferred_from_queue=False, target_visible_damage_increased=any((a['owner'] == b['owner'] and a['id'] == b['id'] and (a['damage'] > b['damage']) for a in observed_after for b in targets)), selected_defender_claimed=False, death_or_capture_inferred_from_absence=False)

def apply(owner, prefix, selected, turn, before, *, player_id=0, core_sha256=_UNIT_ATTACK_BASE_CORE_SHA256):
    from civ6_host.runtime.xp1_unit_attack_profile import selected_proof, selected_queued_proof
    pid = _player_id(player_id)
    if type(before) is not dict or type(before.get('player_id')) is not int or before.get('player_id') != pid or (before.get('turn') != turn):
        raise RuntimeError('Combat action lacks matching actor observation')
    validate_action(selected, before['width'], before['height'])
    fresh = catalog(prefix, turn, before, player_id=pid, core_sha256=core_sha256)
    if selected not in orders(fresh, player_id=pid):
        raise RuntimeError('Selected native attack plot is no longer legal')
    witnesses = [r for r in fresh['candidates'] if r['unit_id'] == selected['unit_id'] and r['operation'] == selected['operation'] and (r['input_route'] == selected['input_route']) and ((r['x'], r['y']) == (selected['x'], selected['y']))]
    units_before = unit_state(prefix, turn, before, player_id=pid, core_sha256=core_sha256)
    if units_before != getattr(owner, 'explicit_combat_units', None):
        raise RuntimeError('Published combat unit state became stale')
    cities_before = fresh.get('cities', [])
    if cities_before != getattr(owner, 'explicit_combat_cities', []):
        raise RuntimeError('Published visible city defenses became stale')
    city_witnesses = [r for r in fresh.get('city_candidates', []) if r['unit_id'] == selected['unit_id'] and r['operation'] == selected['operation'] and (r['input_route'] == selected['input_route']) and ((r['x'], r['y']) == (selected['x'], selected['y']))]
    if city_witnesses:
        city = next((r for r in cities_before if r['plot_id'] == selected['plot_id']))
        source = city_targets.request_source(turn, selected, city, player_id=pid, core_sha256=core_sha256)
    else:
        witness = {k: v for k, v in witnesses[0].items() if k != 'input_route'}
        source = native.request_source(pid, turn, witness, width=fresh['width'], height=fresh['height'], ranged_modifier=selected['input_route'] == 'enemy_flag', core_sha256=core_sha256)
    queued_before = queued_destination(prefix, pid, turn, selected['unit_id'], before['width'], before['height'], core_sha256=core_sha256)
    if prefix.actions.pending or prefix.deferred_events.pending:
        raise RuntimeError('Attack delivery requires empty command and event transports')
    consumed_before = prefix.deferred_events.consumed_count
    submitted = prefix.runtime.evaluate_text(prefix.ui_child, source, b'@explicit_unit_attack_request')
    if submitted != b'submitted' or len(prefix.actions.pending) != 1 or prefix.deferred_events.pending:
        raise RuntimeError('Expected exactly one native attack archive')
    from civ6_host.runtime.native.native_operation_lifecycle import DeliveryWindow
    archive = prefix.actions.pending[0]
    prefix.actions.deliver_one()
    records = tuple(prefix.deferred_events.pending)
    prefix.deferred_events.drain_empty_receivers()
    if prefix.actions.pending or prefix.deferred_events.pending:
        raise RuntimeError('Attack command/event transports did not drain')
    window = DeliveryWindow(archive, records, consumed_before, prefix.deferred_events.consumed_count)
    prefix.view_publisher.publish()
    after = observe_player(prefix.runtime, prefix.ui_child, pid)
    units_after = unit_state(prefix, turn, after, player_id=pid, core_sha256=core_sha256)
    cities_after = city_targets.catalog(prefix, turn, player_id=pid, collect=False, core_sha256=core_sha256)['cities']
    queued_after = queued_destination(prefix, pid, turn, selected['unit_id'], before['width'], before['height'], core_sha256=core_sha256)
    owner.emit('official_explicit_unit_attack_readback', action=selected, own_units_before=units_before, own_units_after=units_after, observation_before=before, observation_after=after, queued_before=queued_before, queued_after=queued_after, queued_source_sha256=selected_queued_proof(QUEUED_SOURCE_SHA, core_sha256), relationships=fresh['relationships'], native_defender_selection=True, effect_verified=False)
    receipt = effect(before, after, units_before, units_after, selected, player_id=pid, cities_before=cities_before, cities_after=cities_after, queued_before=queued_before, queued_after=queued_after, delivery_window=window, core_sha256=core_sha256)
    owner.emit('official_explicit_unit_attack_effect', action=selected, effect=receipt, observation_before=before, observation_after=after, automatic_choices_applied=False, native_defender_selection=True, source_proof_sha256=selected_proof(native._PROOF_SHA256, core_sha256), city_target_source_sha256=selected_proof(city_targets.SOURCE_SHA, core_sha256) if city_witnesses else None)
    return after
