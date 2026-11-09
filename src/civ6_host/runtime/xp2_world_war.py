"""Publish an actually pending XP2 WorldInput war prompt in the common API.

The producer reads the same owned UI child and retained prompt used by map
input. It does not manufacture a prompt, infer a target or advance the game.
Ordinary v31/v32 catalogues remain unchanged before and after this modal.
"""
from copy import deepcopy
import json
import re

from ..contracts import world_war_decisions as modal
from ..contracts import xp2_war_confirmation as war
from ..contracts.network_turn import digest
from .configuration_profiles import XP2_CORE_SHA256


def source_pin(value, input_profile):
    """Select the renderer independently from its future response payload."""
    if value is None:
        return None
    if (input_profile != 'xp2-lan' or type(value) is not str
            or re.fullmatch('[0-9a-f]{64}', value) is None):
        raise ValueError('An XP2 war renderer requires its explicit source digest')
    from . import xp2_world_war_display as display
    if display.verify_source()['source_sha256'] != value:
        raise ValueError('XP2 war renderer differs from the selected source profile')
    return value


def request_source(saved, pid, turn, uid, destination, *, core_sha256):
    """Retain official UI-only prompts only in an explicitly selected session.

    Native operations other than MOVE_TO/SWAP_UNITS remain guarded. This seam
    changes only the handling of the official Lua confirmation event.
    """
    from .native.native_world_click import request_source as inherited
    pin = getattr(saved, 'war_source_sha256', None)
    if core_sha256 != XP2_CORE_SHA256 or pin is None:
        raise ValueError('War prompt requests require the selected XP2 session source')
    source_pin(pin, 'xp2-lan')
    raw = inherited(pid, turn, uid, destination, core_sha256=core_sha256)
    old = (b"if unqualified or warPrompt~=nil then\n"
           b" assert(requestCount==(unqualified and 1 or 0),'ambiguous unqualified click')\n")
    new = b"if unqualified then\n assert(requestCount==1,'ambiguous unqualified click')\n"
    if raw.count(old) != 1:
        raise ValueError('The inherited XP2 movement/war guard changed')
    return raw.replace(old, new)


def read(saved, observation, controls, sequence):
    from .xp1_world_input import _owner, _BoundWorldOwner, _Catalogue
    from .native.native_world_input import catalog_source
    from . import xp2_world_war_display as display

    backend, continuation, prefix, identity = _owner(saved, active=False)
    if backend.load_abi.core_sha256 != XP2_CORE_SHA256:
        raise ValueError('War modal requires the selected XP2 backend')
    if type(sequence) is not int or sequence < 0:
        raise ValueError('War modal must use a valid shared session revision')
    native_sequence = continuation.sequence
    if type(observation) is not dict or observation != continuation.observation:
        raise ValueError('War modal lacks its exact current public observation')
    pid, turn = observation['player_id'], observation['turn']
    renderer_source = display.verify_source()['source_sha256']
    if getattr(saved, 'war_source_sha256', None) != renderer_source:
        raise ValueError('War modal requires the independently selected session source profile')
    prompt = deepcopy(continuation.world_input_prompts.get(pid))
    war.validate_prompt(prompt, pid)
    continuation._xp1_world_input_catalogue = None
    continuation.explicit_world_input = None
    continuation.transport.require_empty_native_queue()
    backend.control(empty=True)
    bound = _BoundWorldOwner(saved, active=False)
    rows = json.loads(prefix.runtime.evaluate_text(prefix.ui_child,
        catalog_source(pid, turn, core_sha256=XP2_CORE_SHA256),
        b'@xp2_war_modal_own_units', capacity=262145))
    selected = continuation.world_input_selections.get(pid)
    if selected is not None and not any(r['unit_id'] == selected and not r['ignore_moves'] for r in rows):
        selected = None
    rendered = display.read(bound, observation, prompt)
    state = dict(schema=modal.WORLD_INPUT_SCHEMA, player_id=pid, turn=turn,
        width=observation['width'], height=observation['height'], units=rows,
        selected_unit_id=selected, war_prompt=prompt, war_display=rendered)
    candidates = [dict(candidate_id=digest(action), action=action)
                  for action in war.actions(prompt, pid)]
    value = dict(schema=modal.SCHEMA, episode_id=identity.episode_id,
        game_generation=identity.game_generation, sequence=sequence,
        player_id=pid, turn=turn, turn_controls=deepcopy(controls),
        complete_action_space=False, world_input=state, candidates=candidates)
    value['decision_id'] = digest(value)
    modal.validate(value, identity, sequence, turn, player_id=pid,
                   observation=observation, expected_source_sha256=renderer_source)
    checked_backend, checked_continuation, checked_prefix, checked_identity = _owner(saved, active=False)
    if (checked_backend is not backend or checked_continuation is not continuation
            or checked_prefix is not prefix or checked_identity is not identity
            or continuation.sequence != native_sequence or continuation.observation != observation
            or continuation.world_input_prompts.get(pid) != prompt):
        raise RuntimeError('War modal crossed its retained owner, prompt or observation')
    continuation.transport.require_empty_native_queue()
    backend.control(empty=True)
    catalogue = _Catalogue(saved, backend, continuation, prefix, identity,
        identity.episode_id, identity.game_generation, native_sequence, deepcopy(observation),
        deepcopy(state), tuple(deepcopy(row['action']) for row in candidates), {})
    continuation.explicit_world_input = deepcopy(state)
    continuation._xp1_world_input_catalogue = catalogue
    return value


def _state_source(pid, turn, defender):
    """Read the native war state and the official minor-operation scalar keys."""
    for value, maximum in ((pid, 63), (defender, 63), (turn, 0xffffffff)):
        if type(value) is not int or not 0 <= value <= maximum:
            raise ValueError('Invalid war response native query identity')
    if pid == defender:
        raise ValueError('A war response cannot target its own actor')
    return (f'local pid,turn,target={pid},{turn},{defender}\n'.encode() + b"""
assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and
 Game.GetCurrentGameTurn()==turn,'war response perspective changed')
local player=Players[pid]
assert(player and player:IsAlive() and player:IsTurnActive() and
 player:IsTurnActiveComplete() and Game.IsAllowStrategicCommands(pid),
 'war response actor not ready')
local value=player:GetDiplomacy():IsAtWarWith(target)
assert(type(value)=='boolean','native war state unavailable')
local function word(n)
 assert(type(n)=='number' and n==math.floor(n) and n>=-2147483648 and n<=4294967295,
  'native player operation enum unavailable')
 return string.format('%.0f',n%4294967296)
end
assert(PlayerOperations,'native player operation namespace unavailable')
return '{"player_id":'..pid..',"turn":'..turn..',"defender_player_id":'..target..
 ',"at_war":'..tostring(value)..',"operation":'..word(PlayerOperations.DIPLOMACY_DECLARE_WAR)..
 ',"player_one_key":'..word(PlayerOperations.PARAM_PLAYER_ONE)..
 ',"player_two_key":'..word(PlayerOperations.PARAM_PLAYER_TWO)..'}'
""")


def _read_state(prefix, pid, turn, defender):
    raw = prefix.runtime.evaluate_text(prefix.ui_child, _state_source(pid, turn, defender),
        b'@xp2_explicit_war_state', capacity=2049)
    if type(raw) is not bytes or not raw or len(raw) > 2048:
        raise ValueError('Invalid native war response query size')
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError('Duplicate native war response field')
            value[key] = item
        return value
    def constant(value):
        raise ValueError('Nonfinite native war response field')
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
    if (type(value) is not dict or set(value) != {'player_id', 'turn', 'defender_player_id',
            'at_war', 'operation', 'player_one_key', 'player_two_key'}
            or any(type(value[k]) is not int or value[k] != expected
                   for k, expected in (('player_id', pid), ('turn', turn), ('defender_player_id', defender)))
            or type(value['at_war']) is not bool
            or any(type(value[k]) is not int or not 0 <= value[k] <= 0xffffffff
                   for k in ('operation', 'player_one_key', 'player_two_key'))
            or value['player_one_key'] == value['player_two_key']):
        raise ValueError('Native war response state or parameters differ')
    return value


def respond(saved, action, before):
    """Execute an explicit offered response; unknown continuations are refused.

    Major diplomacy requires the explicitly installed current-image receiver.
    A missing receiver is infrastructure failure, never game illegality.
    """
    from .xp1_world_input import _check_catalogue
    from .native import native_world_click as click
    from .native.native_player_observation import observe_player
    from . import xp2_world_configuration as configuration
    from .saved_load_job_observer import require_quiescent

    war.validate_action(action)
    catalogue = getattr(saved.continuation, '_xp1_world_input_catalogue', None)
    backend, continuation, prefix, _ = _check_catalogue(saved, catalogue, active=True)
    if (backend.load_abi.core_sha256 != XP2_CORE_SHA256 or before != catalogue.observation
            or action not in catalogue.actions or catalogue.world_input['schema'] != modal.WORLD_INPUT_SCHEMA):
        raise ValueError('War response was not offered by this exact XP2 modal')
    pid, turn = before['player_id'], before['turn']
    prompt = catalogue.world_input['war_prompt']
    war.validate_prompt(prompt, pid)
    if continuation.world_input_prompts.get(pid) != prompt:
        raise ValueError('The retained war prompt changed before its response')
    source_pin(getattr(saved, 'war_source_sha256', None), 'xp2-lan')
    if getattr(saved, 'war_source_sha256', None) != catalogue.world_input['war_display']['source_sha256']:
        raise ValueError('War response renderer profile changed')
    continuation.transport.require_empty_native_queue()
    backend.control(empty=True)
    jobs = backend.jobs_snapshot('before')
    require_quiescent(jobs)
    receipt = dict(action=deepcopy(action), prompt=deepcopy(prompt), native_callback_invoked=False,
        archive_delivered=False, archive_hex=None, automatic_choices_applied=False,
        observation_before=deepcopy(before), host_refusal=None)
    major_route=False
    pending_statement=False
    try:
        configuration_snapshot = configuration.read(backend, [prompt['defending_player']]) if action['accept'] else None
        if action['accept']:
            # Reuse the selected popup's classification. Do not infer major
            # status from IDs, visibility, strings or a different Lua helper.
            classify = configuration.lua_bindings(configuration_snapshot) + click._war_function('CanDeclareWar')
            classify += f'\nreturn tostring(CanDeclareWar({prompt["defending_player"]}))'.encode()
            major = prefix.runtime.evaluate_text(prefix.ui_child, classify, b'@xp2_war_target_kind', capacity=16)
            if major not in (b'true', b'false'):
                raise ValueError('Official war target classification unavailable')
            if major == b'true':
                from .a0_diplomacy_statement import require_receiver
                if not require_receiver(saved):
                    receipt['host_refusal'] = 'xp2_war_major_continuation_unqualified'
                    receipt['observation_after'] = deepcopy(before)
                    saved.emit('xp2_world_war_response_refused', **receipt)
                    return dict(status='refused', refusal_code=receipt['host_refusal'],
                                observation=deepcopy(before), receipt=receipt)
                from .xp2_statement_factory import verify_request
                receipt['factory_binding'] = verify_request(
                    backend.core._handle, backend.runtime.read,
                    execution_image=getattr(backend.core, '_civ6_host_execution_image', None))
                saved.emit('xp2_major_statement_factory_verified', **receipt['factory_binding'])
                major_route=True
        code = click.war_response_source(pid, turn, prompt['defending_player'], prompt['war_type'], action['accept'])
        if configuration_snapshot is not None:
            code = configuration.lua_bindings(configuration_snapshot) + code
        raw = prefix.runtime.evaluate_text(prefix.ui_child, code, b'@xp2_official_world_war_response', capacity=4097)
        requested = click.parse_war_response_result(raw, pid, turn, prompt['defending_player'], prompt['war_type'], action['accept'])
        receipt['request'] = requested
        if action['accept'] and major_route:
            if requested['status']!='session_request' or len(prefix.actions.pending)!=1:
                raise RuntimeError('Major war did not create its explicit native session request')
            archive=bytes(prefix.actions.pending[0])
            from .native.native_diplomacy_choices import deliver_statement_request
            from .native import native_pending_diplomacy as pending
            deliver_statement_request(prefix.actions)
            prefix.deferred_events.drain()
            prefix.view_publisher.publish()
            ledger=prefix.deferred_events.pending_diplomacy_statements
            if len(ledger)!=1:
                raise RuntimeError('Major war requires one explicit native statement continuation')
            statement=ledger[0]
            raw=prefix.runtime.evaluate_text(prefix.ui_child,pending.source(statement,pid),
                b'@xp2_world_war_pending_session',capacity=2048)
            session=pending.parse(raw,statement,pid)
            if (session['is_open'] is not True or session['statement_type']!='DECLARE_SURPRISE_WAR'
                    or {session['from_player'],session['to_player']}!={pid,prompt['defending_player']}):
                raise RuntimeError('Major war retained another or closed native dialogue')
            pending_statement=True
            receipt.update(native_callback_invoked=True,archive_delivered=True,archive_hex=archive.hex(),
                           pending_statement_retained=True,pending_session=deepcopy(session),
                           automatic_choices_applied=False)
        elif action['accept']:
            if requested['status'] != 'minor_route':
                raise RuntimeError('War response reached an unqualified native request route')
            state = _read_state(prefix, pid, turn, prompt['defending_player'])
            if state['at_war']:
                raise RuntimeError('War declaration became stale before its request')
            from .native.native_player_operation_request import request_player_operation
            parameters = {state['player_one_key']: pid, state['player_two_key']: prompt['defending_player']}
            result = request_player_operation(backend.core, backend.context, pid, state['operation'],
                                              parameters, core_sha256=XP2_CORE_SHA256)
            if not result['can_start'] or not result['request_invoked']:
                raise RuntimeError('Native CanStart refused the explicit minor war request')
            if len(prefix.actions.pending) != 1 or bytes(prefix.actions.pending[0][:4]) != (3294486831).to_bytes(4, 'little'):
                raise RuntimeError('Minor war request did not create one native player-operation archive')
            receipt.update(native_callback_invoked=True, archive_hex=bytes(prefix.actions.pending[0]).hex(),
                           operation_receipt=result, parameters=parameters)
            prefix.actions.deliver_one()
            prefix.deferred_events.drain()
            prefix.view_publisher.publish()
            after_state = _read_state(prefix, pid, turn, prompt['defending_player'])
            if after_state['at_war'] is not True:
                raise RuntimeError('Minor war request has no observed native war effect')
            receipt.update(archive_delivered=True, native_war_state_before=state, native_war_state_after=after_state)
        elif requested['status'] != 'declined' or requested['native_callback_invoked']:
            raise RuntimeError('Declining war unexpectedly submitted a game request')
        continuation.transport.require_empty_native_queue()
        backend.control(empty=True,**({'allow_diplomacy':True} if pending_statement else {}))
        observed = observe_player(prefix.runtime, prefix.ui_child, pid)
        if (observed['player_id'], observed['turn']) != (pid, turn):
            raise RuntimeError('War response crossed its native player/turn boundary')
        after_jobs = backend.jobs_snapshot('after')
        require_quiescent(after_jobs)
        if not action['accept'] and (observed != before or after_jobs != jobs):
            raise RuntimeError('Declining war changed the native game or scheduler')
        _check_catalogue(saved, catalogue, active=True)
        if continuation.world_input_prompts.get(pid) != prompt:
            raise RuntimeError('War prompt changed during its explicit response')
        continuation.world_input_prompts[pid] = None
        receipt['observation_after'] = deepcopy(observed)
        saved.emit('xp2_world_war_response_effect', **receipt)
        return dict(status='completed', refusal_code=None, observation=observed, receipt=receipt,
                    pending_statement_retained=pending_statement)
    finally:
        continuation._xp1_world_input_catalogue = None
        continuation.explicit_world_input = None
