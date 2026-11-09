"""Explicit unit selection and world clicks; game outcomes remain native.

Selection is host UI state scoped to a player/session, not a game command.
No path query or hidden target property decides the click candidate mask.
"""
from __future__ import annotations
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _WORLD_BASE_CORE_SHA256
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import copy, json
SCHEMA = 'civ6rl.world_input.v1'
WAR_DISPLAY_SCHEMA = 'civ6rl.world_input.v2'
FIELDS = {'world_select_unit': {'kind', 'unit_id'}, 'world_deselect_unit': {'kind'}, 'world_plot_click': {'kind', 'unit_id', 'plot_id', 'x', 'y'}, 'world_war_response': {'kind', 'accept'}}

def validate(value, pid, turn, *, own_ids=None, width=None, height=None):
    keys = {'schema', 'player_id', 'turn', 'width', 'height', 'units', 'selected_unit_id', 'war_prompt'}
    displayed = type(value) is dict and value.get('schema') == WAR_DISPLAY_SCHEMA
    if displayed:
        keys.add('war_display')
    if type(value) is not dict or set(value) != keys or value['schema'] not in (SCHEMA, WAR_DISPLAY_SCHEMA) or any((type(value[k]) is not int for k in ('player_id', 'turn', 'width', 'height'))) or ((value['player_id'], value['turn']) != (pid, turn)) or (not 1 <= value['width'] <= 512) or (not 1 <= value['height'] <= 512) or (value['width'] * value['height'] > 16384) or (width is not None and (value['width'], value['height']) != (width, height)) or (type(value['units']) is not list) or (len(value['units']) > 4096):
        raise ValueError('Invalid public world-input state')
    ids = []
    for row in value['units']:
        if type(row) is not dict or set(row) != {'unit_id', 'ignore_moves'} or type(row['unit_id']) is not int or (not 0 <= row['unit_id'] <= 4294967295) or (type(row['ignore_moves']) is not bool):
            raise ValueError('Invalid own world-input unit')
        ids.append(row['unit_id'])
    if ids != sorted(set(ids)) or (own_ids is not None and ids != sorted(own_ids)):
        raise ValueError('World-input roster differs from own units')
    selected = value['selected_unit_id']
    allowed = [r['unit_id'] for r in value['units'] if not r['ignore_moves']]
    if selected is not None and (type(selected) is not int or selected not in allowed):
        raise ValueError('World-input selection is not a movable own unit')
    prompt = value['war_prompt']
    if prompt is not None:
        if type(prompt) is not dict or set(prompt) != {'attacking_player', 'defending_player', 'war_type'} or any((type(v) is not int for v in prompt.values())) or (prompt['attacking_player'] != pid) or (not 0 <= prompt['defending_player'] <= 63) or (prompt['defending_player'] == pid) or (not -(1 << 31) <= prompt['war_type'] <= 4294967295):
            raise ValueError('Invalid public war prompt')
    if displayed:
        if prompt is None:
            raise ValueError('Displayed war confirmation requires a pending prompt')
        from civ6_host.runtime.native.native_world_war_display import parse_display
        parse_display(json.dumps(value['war_display']).encode('utf8'), pid, turn, [prompt['defending_player']], prompt['war_type'])
    return value

def actions(state):
    validate(state, state['player_id'], state['turn'])
    if state['war_prompt'] is not None:
        return [dict(kind='world_war_response', accept=v) for v in (False, True)]
    result = [dict(kind='world_select_unit', unit_id=r['unit_id']) for r in state['units'] if not r['ignore_moves']]
    selected = state['selected_unit_id']
    if selected is not None:
        result.append(dict(kind='world_deselect_unit'))
        result.extend((dict(kind='world_plot_click', unit_id=selected, plot_id=i, x=i % state['width'], y=i // state['width']) for i in range(state['width'] * state['height'])))
    return result

def validate_candidates(state, candidates, *, closed=False):
    expected = actions(state) if not closed else []
    actual = [row['action'] for row in candidates if row['action'].get('kind') in FIELDS]
    key = lambda v: json.dumps(v, sort_keys=True)
    if sorted(actual, key=key) != sorted(expected, key=key):
        raise ValueError('World-input choices differ from exact public unit/map selection')

def permitted(state, action):
    return state['war_prompt'] is None or action.get('kind') == 'world_war_response'

def catalog_source(pid, turn, *, core_sha256=_WORLD_BASE_CORE_SHA256):
    if core_sha256 != _WORLD_BASE_CORE_SHA256:
        from civ6_host.runtime.xp1_world_input_profile import verify_source
        verify_source(core_sha256)
    if type(pid) is not int or not 0 <= pid <= 63 or type(turn) is not int or (not 0 <= turn <= 4294967295):
        raise ValueError('Invalid world-input perspective')
    return (f'local pid,turn={pid},{turn}\n' + '\nassert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,\n \'world-input perspective changed\')\nlocal p=Players[pid]\nassert(p and p:IsAlive() and p:IsTurnActive() and p:IsTurnActiveComplete() and Game.IsAllowStrategicCommands(pid))\nlocal rows={}\nfor _,u in p:GetUnits():Members() do\n assert(u:GetOwner()==pid and #rows<4096,\'invalid own unit roster\')\n local id=u:GetID();assert(type(id)==\'number\' and id%1==0 and id>=0 and id<=4294967295)\n local info=GameInfo.Units[u:GetUnitType()];assert(info and (info.IgnoreMoves==nil or type(info.IgnoreMoves)==\'boolean\'))\n rows[#rows+1]={id=id,ignore=info.IgnoreMoves==true}\nend\ntable.sort(rows,function(a,b)return a.id<b.id end)\nlocal out={}\nfor i,r in ipairs(rows) do\n out[i]=\'{"unit_id":\'..string.format(\'%.0f\',r.id)..\',"ignore_moves":\'..(r.ignore and \'true\' or \'false\')..\'}\'\nend\nreturn \'[\'..table.concat(out,\',\')..\']\'\n').encode()

def observe(owner, obs, *, core_sha256=_WORLD_BASE_CORE_SHA256):
    from civ6_host.runtime.xp1_world_input_profile import require_no_prompt
    require_no_prompt(owner, obs['player_id'], core_sha256)
    pid, turn = (obs['player_id'], obs['turn'])
    p = owner.prefix
    rows = json.loads(p.runtime.evaluate_text(p.ui_child, catalog_source(pid, turn, core_sha256=core_sha256), b'@world_input_own_units', capacity=262145))
    selections = getattr(owner, 'world_input_selections', {})
    prompts = getattr(owner, 'world_input_prompts', {})
    selected = selections.get(pid)
    if selected is not None and (not any((r['unit_id'] == selected and (not r['ignore_moves']) for r in rows))):
        selected = None
    state = dict(schema=SCHEMA, player_id=pid, turn=turn, width=obs['width'], height=obs['height'], units=rows, selected_unit_id=selected, war_prompt=copy.deepcopy(prompts.get(pid)))
    if state['war_prompt'] is not None:
        from civ6_host.runtime.native.native_world_war_display import read as read_war_display
        state['schema'] = WAR_DISPLAY_SCHEMA
        state['war_display'] = read_war_display(owner, obs, state['war_prompt'])
    validate(state, pid, turn, own_ids=[u['id'] for u in obs['units']], width=obs['width'], height=obs['height'])
    return state

def apply(owner, action, turn, before, *, core_sha256=_WORLD_BASE_CORE_SHA256, snapshot_reader=None, request_source_reader=None):
    if core_sha256 != _WORLD_BASE_CORE_SHA256 and action.get('kind') == 'world_war_response':
        raise ValueError('XP1 war confirmation is not qualified')
    from civ6_host.runtime.native.native_player_observation import observe_player
    from civ6_host.runtime.native.native_saved_actions import snapshot
    if snapshot_reader is not None:
        if not callable(snapshot_reader):
            raise TypeError('Snapshot reader must be callable')
        snapshot = snapshot_reader
    from civ6_host.runtime.native.native_saved_combat import queued_destination
    from civ6_host.runtime.native import native_world_click as click
    build_request = click.request_source if request_source_reader is None else request_source_reader
    if not callable(build_request):
        raise TypeError('World click request source reader must be callable')
    pid = before['player_id']
    p = owner.prefix
    state = observe(owner, before, core_sha256=core_sha256)
    if state != getattr(owner, 'explicit_world_input', None) or not permitted(state, action):
        raise RuntimeError('World-input state changed or a war prompt blocks this action')
    if action not in actions(state):
        raise ValueError('World-input action is not offered')
    jobs = snapshot(owner, 'before')
    if p.actions.pending or p.deferred_events.pending:
        raise RuntimeError('World click requires empty transports')
    kind = action['kind']
    request = None
    archive = None
    delegated_minor = False
    if not hasattr(owner, 'world_input_selections'):
        owner.world_input_selections = {}
    if not hasattr(owner, 'world_input_prompts'):
        owner.world_input_prompts = {}
    if kind == 'world_select_unit':
        owner.world_input_selections[pid] = action['unit_id']
    elif kind == 'world_deselect_unit':
        owner.world_input_selections[pid] = None
    elif kind == 'world_plot_click':
        raw = p.runtime.evaluate_text(p.ui_child, build_request(pid, turn, action['unit_id'], action['plot_id'], core_sha256=core_sha256), b'@official_world_click', capacity=4097)
        request = click.parse_request_result(raw, pid, turn, action['unit_id'], action['plot_id'], core_sha256=core_sha256)
        if request['status'] == 'request':
            if len(p.actions.pending) != 1 or p.deferred_events.pending:
                raise RuntimeError('World click did not produce exactly one native archive')
            archive = bytes(p.actions.pending[0])
            p.actions.deliver_one()
            p.deferred_events.drain_empty_receivers()
            p.view_publisher.publish()
        elif request['status'] == 'war_prompt':
            owner.world_input_prompts[pid] = dict(attacking_player=pid, defending_player=request['defender_player_id'], war_type=request['war_type'])
    elif kind == 'world_war_response':
        prompt = state['war_prompt']
        source = click.war_response_source(pid, turn, prompt['defending_player'], prompt['war_type'], action['accept'])
        if action['accept']:
            from civ6_host.runtime.native.native_world_configuration import read as read_configuration
            from civ6_host.runtime.native.native_world_configuration import lua_bindings
            configuration = read_configuration(owner, [prompt['defending_player']])
            source = lua_bindings(configuration) + source
        raw = p.runtime.evaluate_text(p.ui_child, source, b'@official_world_war_response', capacity=4097)
        request = click.parse_war_response_result(raw, pid, turn, prompt['defending_player'], prompt['war_type'], action['accept'])
        if request['status'] == 'minor_route':
            from civ6_host.runtime.native.native_saved_minor_war import apply as minor_war
            minor_war(owner, p, dict(kind='declare_war_minor', target_player_id=prompt['defending_player']), turn, before, player_id=pid)
            delegated_minor = True
        elif request['status'] == 'session_request':
            if len(p.actions.pending) != 1:
                raise RuntimeError('War session did not produce one native archive')
            from civ6_host.runtime.native.native_diplomacy_choices import deliver_statement_request
            archive = bytes(p.actions.pending[0])
            deliver_statement_request(p.actions)
            p.deferred_events.drain_empty_receivers()
            p.view_publisher.publish()
        owner.world_input_prompts[pid] = None
    if p.actions.pending or p.deferred_events.pending:
        raise RuntimeError('World click transport did not drain')
    action_dialogue = False
    if request is not None and request['status'] == 'session_request' and p.deferred_events.pending_diplomacy_statements:
        from civ6_host.runtime.native.native_turn_continuation import begin_action_dialogue
        after = begin_action_dialogue(owner, turn, player_id=pid)
        action_dialogue = True
    else:
        owner.control(empty=True)
        after = observe_player(p.runtime, p.ui_child, pid)
    if after['turn'] != turn:
        raise RuntimeError('World click unexpectedly changed the game turn')
    if kind in ('world_select_unit', 'world_deselect_unit') or (request is not None and request['status'] in ('noop', 'war_prompt', 'declined', 'unsupported')):
        if before != after or snapshot(owner, 'after') != jobs:
            raise RuntimeError('UI-only world interaction changed simulation')
    queued = None
    if kind == 'world_plot_click' and any((u['id'] == action['unit_id'] for u in after['units'])):
        queued = queued_destination(p, pid, turn, action['unit_id'], after['width'], after['height'], core_sha256=core_sha256)
    owner.emit('official_world_input_result', action=action, request=request, archive_hex=archive.hex() if archive is not None else None, archive_delivered=archive is not None or delegated_minor, delegated_minor_war=delegated_minor, queued_destination_after=queued, observation_before=before, observation_after=after, base_observation_changed=before != after, action_dialogue_retained=action_dialogue, automatic_choices_applied=False, strategic_training_ready=False)
    return after
