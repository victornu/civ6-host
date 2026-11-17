"""Publish an actually pending XP2 WorldInput war prompt in the common API.

The producer reads the same owned UI child and retained prompt used by map
input. It does not manufacture a prompt, infer a target or advance the game.
Ordinary v31/v32 catalogues remain unchanged before and after this modal.
"""
from copy import deepcopy
from hashlib import sha256
import json
import re
from struct import iter_unpack, pack, unpack_from
from types import SimpleNamespace

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
    backend, continuation, prefix, identity = _owner(saved, active=False)
    if type(sequence) is not int or sequence < 0:
        raise ValueError('War modal must use a valid shared session revision')
    native_sequence = continuation.sequence
    if type(observation) is not dict or observation != continuation.observation:
        raise ValueError('War modal lacks its exact current public observation')
    continuation._xp1_world_input_catalogue = None
    continuation.explicit_world_input = None
    state = _read_prompt_state(_BoundWorldOwner(saved, active=False), observation)
    pid, prompt = observation['player_id'], state['war_prompt']
    value = public_decisions(state, observation, identity, sequence, controls,
                             expected_source=saved.war_source_sha256)
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
        deepcopy(state), tuple(deepcopy(row['action']) for row in value['candidates']), {})
    continuation.explicit_world_input = deepcopy(state)
    continuation._xp1_world_input_catalogue = catalogue
    return value


def _read_prompt_state(bound, observation):
    from .native.native_world_input import catalog_source
    from . import xp2_world_war_display as display

    backend, continuation, prefix, _ = bound._check()
    if backend.load_abi.core_sha256 != XP2_CORE_SHA256:
        raise ValueError('War modal requires the selected XP2 backend')
    pid, turn = observation['player_id'], observation['turn']
    if source_pin(getattr(bound.saved, 'war_source_sha256', None), 'xp2-lan') is None:
        raise ValueError('War modal requires the independently selected session source profile')
    prompt = deepcopy(continuation.world_input_prompts.get(pid))
    war.validate_prompt(prompt, pid)
    continuation.transport.require_empty_native_queue()
    backend.control(empty=True)
    rows = json.loads(prefix.runtime.evaluate_text(prefix.ui_child,
        catalog_source(pid, turn, core_sha256=XP2_CORE_SHA256),
        b'@xp2_war_modal_own_units', capacity=262145))
    selected = continuation.world_input_selections.get(pid)
    if selected is not None and not any(r['unit_id'] == selected and not r['ignore_moves'] for r in rows):
        selected = None
    rendered = display.read(bound, observation, prompt)
    continuation.transport.require_empty_native_queue()
    if continuation.world_input_prompts.get(pid) != prompt:
        raise RuntimeError('Native war prompt changed during display')
    return dict(schema=modal.WORLD_INPUT_SCHEMA, player_id=pid, turn=turn,
        width=observation['width'], height=observation['height'], units=rows,
        selected_unit_id=selected, war_prompt=prompt, war_display=rendered)


def public_decisions(state, observation, identity, sequence, controls, *, expected_source):
    pid, turn = observation['player_id'], observation['turn']
    candidates = [dict(candidate_id=digest(action), action=action)
                  for action in war.actions(state['war_prompt'], pid)]
    value = dict(schema=modal.SCHEMA, episode_id=identity.episode_id,
        game_generation=identity.game_generation, sequence=sequence,
        player_id=pid, turn=turn, turn_controls=deepcopy(controls),
        complete_action_space=False, world_input=state, candidates=candidates)
    value['decision_id'] = digest(value)
    return modal.validate(value, identity, sequence, turn, player_id=pid,
                          observation=observation, expected_source_sha256=expected_source)


def read_borrowed(saved, observation):
    from .xp1_session_view import _borrowed_xp2_reference
    from .xp1_world_input import _owner

    _borrowed_xp2_reference(saved, observation['player_id'])
    bound = SimpleNamespace(saved=saved,
        _check=lambda: _owner(saved, active=True), active=True, control=saved.backend.control)
    return _read_prompt_state(bound, observation)


def verify_minor_archive(payload, sender, operation, parameters):
    """Match the accepted native two-parameter war archive."""
    header = pack('<6I', 0xc45de12f, sender, operation, 2, 0x80000001, 2)
    a, b = (pack('<IHH10xI', key, 0, 2, value) for key, value in parameters.items())
    if type(payload) is not bytes or payload not in (header + a + b, header + b + a):
        raise RuntimeError('Minor war archive differs from native sender or targets')


def _scalar_archive(payload, expected_kind, sender, *, tags, label):
    if type(payload) is not bytes or not 16 <= len(payload) <= 6784:
        raise RuntimeError(f'Invalid native {label} archive')
    kind, actor, recipient, count = unpack_from('<4I', payload)
    if kind != expected_kind or actor != sender or len(payload) != 16 + count * 20:
        raise RuntimeError(f'{label} archive differs from native sender or framing')
    fields = {}
    for key, tag, reserved_a, reserved_b, value in iter_unpack('<5I', payload[16:]):
        if key in fields or tag not in tags or reserved_a or reserved_b:
            raise RuntimeError(f'Invalid native {label} scalar field')
        fields[key] = tag, value
    return recipient, fields


def verify_major_archive(payload, sender, defender):
    """Bind the official RequestSession archive to the selected war prompt."""
    from .native.native_diplomacy_statement import NAMES
    from .xp2_statement_factory import REQUEST_HASH

    session_id, fields = _scalar_archive(payload, 0xa4172391, sender, tags=(2, 3), label='Major-war')
    expected = {'FromPlayer': (2, sender), 'ToPlayer': (2, defender),
                'StatementType': (3, REQUEST_HASH), 'SessionID': (3, session_id)}
    if session_id == 0 or any(fields.get(NAMES[name]) != entry for name, entry in expected.items()):
        raise RuntimeError('Major-war archive differs from the requested session or parties')
    return session_id


_CLOSE_WRITER_SPANS = (
    (0x7b300, 40, 'f386885186480000fbc2bb37a737d2f9b2744c0f400c74e64d3b38d1569b36ea'),
    (0x183f20, 50, '7a4a1ab7ace70b4e9ea0d6d19da39d83bd346b596827368c6c4bb6c6450124d2'),
    (0x188880, 69, 'f82f2a37a33e6e68cae1793b2ea04313c18607ac6a0533c1780843ebee52bc22'),
    (0x35570, 110, '73b18ebe1b14f6c0f2a29a246cbf88863c675e81fa0752d143533eb08bbaa4c7'),
    (0x35910, 123, 'e3239ae2c7ba84443790b89edaa377a698e1de503435c3a5e3a72a5446e66e9b'),
)

_HUMAN_WAR_SPANS = (
    (0x2f9820, 34, 'c99282f1fad58796f6c885c7abfeaba55d5ef2ac0b113df23ce7c1fe8a2a3082'),
    (0x164d60, 27, '8b588d0476ccb7528fdf3cfe16a8d5d14c172a4c114e20c23a0deddb059ca029'),
    (0x16a6f0, 98, 'dbd410577686fd7a40878acc677a9c5248783506c7118f9bd69c5a7767994dff'),
    (0x44e60, 20, 'edcbd3345991b433c2f02e46349b98241eb6c84255543df0bc4c30d64412b3a8'),
    (0x63d180, 14, 'fcb873f4d609ce4448cc0779ec7b3f535f7143d31d6d69f1a1959c611e8469ce'),
    (0x184240, 98, '10448ec192dfd664ca2d9a493722b1fe38aeb1602829d816c1abe047081139b8'),
    (0x188a10, 70, 'b56014defb6ade8ba71036b9105c2c25a1185ec637ad057b8c616a221392a027'),
    (0x186b30, 143, '449d206b94eafb2e74488e328e9dd9bbebefc6f0ef1be7516380fca48d4ba670'),
    (0x183380, 174, '521732f6e110ebba0d7ae4a3a794d5de657f75d2430b9322a7199a2d8f844ed4'),
    (0x187d40, 386, '38ae19f57ac1561d3532e6a82749d5c578ffdf00a95aab2f2128c34ed3bf1114'),
    (0x34f80, 55, 'da848fda495141842666b8c618e6f571c0fbe90fb84c6bc62845c182ad3e244b'),
    (0x35160, 29, 'f8f986f507afa1a02ab012ecb0421c103912cc904b0bdf40ef2d2835ea951e1d'),
)


def _verify_spans(backend, spans, error):
    base, read = backend.core._handle, backend.runtime.read
    for rva, size, expected in spans:
        raw = read(base + rva, size)
        if type(raw) is not bytes or len(raw) != size or sha256(raw).hexdigest() != expected:
            raise ValueError(error)


def verify_close_writer(backend):
    """Check the current XP2 CloseSession writer and selected serializer."""
    from .execution_images import identity

    image = getattr(backend.core, '_civ6_host_execution_image', None)
    identity(image)
    if image.id != 'xp2-gamecore-current-092abfbb':
        raise ValueError('Surprise-war CloseSession requires its selected XP2 image')
    base, read = backend.core._handle, backend.runtime.read
    _verify_spans(backend, _CLOSE_WRITER_SPANS, 'Native surprise-war CloseSession writer differs')
    if read(base + 0x9bdfe0 + 0x20, 8) != pack('<Q', base + 0x35910):
        raise ValueError('Native surprise-war CloseSession serializer differs')


def verify_exit_archive(payload, player_id, session_id):
    if (type(player_id) is not int or not 0 <= player_id < 64
            or type(session_id) is not int or not 0 < session_id <= 0xffffffff):
        raise ValueError('Invalid XP2 war dialogue player or session')
    expected = pack('<6I', 0x08a6cf5f, session_id, 0x1baabc8b, player_id, 0, 0)
    if type(payload) is not bytes or payload != expected:
        raise RuntimeError('Native surprise-war exit archive differs from its session or player')


def require_closed_war(prefix, session, turn):
    pid, sid = session['player_id'], session['session_id']
    target = session['to_player'] if session['from_player'] == pid else session['from_player']
    source = f'''local pid,sid,turn,target={pid},{sid},{turn},{target}
assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid
   and Game.GetCurrentGameTurn()==turn,'war dialogue exit crossed perspective')
local open=DiplomacyManager.IsSessionIDOpen(sid)
local atWar=Players[pid]:GetDiplomacy():IsAtWarWith(target)
assert(type(open)=='boolean' and type(atWar)=='boolean','war dialogue exit state unavailable')
return (not open and atWar) and "closed_at_war" or "effect_unverified"
'''.encode('ascii')
    raw = prefix.runtime.evaluate_text(prefix.ui_child, source, b'@xp2_surprise_war_exit_effect', capacity=32)
    if raw != b'closed_at_war':
        raise RuntimeError('Native surprise-war exit did not close the session with war in effect')


def verify_human_war_writer(backend):
    verify_close_writer(backend)
    _verify_spans(backend, _HUMAN_WAR_SPANS, 'Native human surprise-war writer differs')


def verify_war_action_archive(payload, sender, defender):
    from .native.native_diplomacy_statement import NAMES

    target, fields = _scalar_archive(payload, 0xa797ad1c, sender, tags=(1, 2, 3), label='War follow-up')
    if (target != defender or fields.get(NAMES['FromPlayer']) != (2, sender)
            or fields.get(NAMES['ToPlayer']) != (2, defender)
            or fields.get(0x0a653b30) != (2, 0x4396d725)):
        raise RuntimeError('War follow-up archive differs from the selected parties or action')


def _deliver_human_war(transport, pid, defender, session_id):
    from .native.native_diplomacy_choices import deliver_statement_request

    delivered = []

    def verify_followup(payload, native_action_kind):
        if not delivered:
            if native_action_kind != 0xa797ad1c:
                raise RuntimeError('Human war uses an unknown follow-up transport')
            verify_war_action_archive(payload, pid, defender)
        elif len(delivered) == 1:
            verify_exit_archive(payload, pid, session_id)
        else:
            raise RuntimeError('Human war produced additional native follow-ups')
        delivered.append(payload.hex())

    deliver_statement_request(transport, check_followup=verify_followup)
    if len(delivered) != 2:
        raise RuntimeError('Human war requires its native action and automatic close archives')
    return delivered


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

    war.validate_action(action)
    catalogue = getattr(saved.continuation, '_xp1_world_input_catalogue', None)
    owner = _check_catalogue(saved, catalogue, active=True)
    backend, continuation, _, _ = owner
    if (backend.load_abi.core_sha256 != XP2_CORE_SHA256 or before != catalogue.observation
            or action not in catalogue.actions or catalogue.world_input['schema'] != modal.WORLD_INPUT_SCHEMA):
        raise ValueError('War response was not offered by this exact XP2 modal')
    pid = before['player_id']
    prompt = catalogue.world_input['war_prompt']
    war.validate_prompt(prompt, pid)
    if continuation.world_input_prompts.get(pid) != prompt:
        raise ValueError('The retained war prompt changed before its response')
    source_pin(getattr(saved, 'war_source_sha256', None), 'xp2-lan')
    if getattr(saved, 'war_source_sha256', None) != catalogue.world_input['war_display']['source_sha256']:
        raise ValueError('War response renderer profile changed')
    return _respond(saved, action, before, prompt, owner=owner, catalogue=catalogue)


def respond_borrowed(saved, action, before, *, expected):
    from .xp1_world_input import _owner

    war.validate_action(action)
    pid = before['player_id']
    refusal = dict(status='refused', requested_action=action)
    if expected is None or saved.continuation.world_input_prompts.get(pid) is None:
        return dict(refusal, reason='native_war_prompt_unavailable'), None
    current = read_borrowed(saved, before)
    if (current != expected or action not in war.actions(current['war_prompt'], pid)):
        return dict(refusal, reason='native_war_prompt_changed'), None
    result = _respond(saved, action, before, current['war_prompt'], owner=_owner(saved, active=True), borrowed=True)
    if result.get('pending_statement_retained'):
        from .xp2_diplomacy import BorrowedWarDialogue

        saved._xp2_borrowed_war = BorrowedWarDialogue(saved, result['receipt']['pending_session'], before['turn'])
    return dict(status=result['status'], reason=result['refusal_code'], requested_action=action), (
        result['observation'] if result['status'] == 'completed' else None)


def _respond(saved, action, before, prompt, *, owner, catalogue=None, borrowed=False):
    from .xp1_world_input import _check_catalogue
    from .native import native_world_click as click
    from .native.native_player_observation import observe_player
    from . import xp2_world_configuration as configuration
    from .saved_load_job_observer import require_quiescent

    backend, continuation, prefix, _ = owner
    pid, turn = before['player_id'], before['turn']
    continuation.transport.require_empty_native_queue()
    backend.control(empty=True)
    jobs = backend.jobs_snapshot('before')
    require_quiescent(jobs)
    receipt = dict(action=deepcopy(action), prompt=deepcopy(prompt), native_callback_invoked=False,
        archive_delivered=False, archive_hex=None, automatic_choices_applied=False,
        observation_before=deepcopy(before), host_refusal=None)
    major_route=False
    human_route=False
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
                target = prompt['defending_player']
                target_human = configuration_snapshot.get('players', {}).get(target, {}).get('is_human')
                lan = (getattr(saved, '_xp2_lan_world_input_enabled', False) is True
                       and configuration_snapshot.get('is_any_multiplayer') is True)
                human_route = (lan and target_human is True
                    and target in saved.network_reference['human_player_ids'])
                eligible = human_route or (target_human is not True and (catalogue is not None or (borrowed
                    and lan and target_human is False
                    and target not in saved.network_reference['human_player_ids'])))
                if not eligible or not require_receiver(saved):
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
                if human_route:
                    verify_human_war_writer(backend)
                    human_before = _read_state(prefix, pid, turn, target)
                    if human_before['at_war']:
                        raise RuntimeError('Human war declaration became stale before its request')
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
            archive = prefix.actions.pending[0]
            session_id = verify_major_archive(archive, pid, prompt['defending_player'])
            from .native.native_diplomacy_choices import deliver_statement_request
            from .native import native_pending_diplomacy as pending
            if human_route:
                followups = _deliver_human_war(prefix.actions, pid, target, session_id)
            else:
                deliver_statement_request(prefix.actions)
            prefix.deferred_events.drain()
            prefix.view_publisher.publish()
            ledger=prefix.deferred_events.pending_diplomacy_statements
            receipt.update(native_callback_invoked=True, archive_delivered=True, archive_hex=archive.hex())
            if human_route:
                if ledger:
                    raise RuntimeError('Human war retained an unexpected declarer dialogue')
                require_closed_war(prefix, dict(player_id=pid, session_id=session_id,
                                               from_player=pid, to_player=target), turn)
                receipt.update(native_automatic_close=True, native_followup_archives=followups,
                               native_war_state_before=human_before, native_war_effect_verified=True)
            else:
                if len(ledger)!=1:
                    raise RuntimeError('Major war requires one explicit native statement continuation')
                statement=ledger[0]
                raw=prefix.runtime.evaluate_text(prefix.ui_child,pending.source(statement,pid),
                    b'@xp2_world_war_pending_session',capacity=2048)
                session=pending.parse(raw,statement,pid)
                if (session['is_open'] is not True or session['session_id'] != session_id
                        or session['statement_type']!='DECLARE_SURPRISE_WAR'
                        or {session['from_player'],session['to_player']}!={pid,prompt['defending_player']}):
                    raise RuntimeError('Major war retained another or closed native dialogue')
                pending_statement=True
                receipt.update(pending_statement_retained=True,pending_session=deepcopy(session))
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
            if catalogue is None:
                verify_minor_archive(prefix.actions.pending[0], pid, state['operation'], parameters)
            receipt.update(native_callback_invoked=True, archive_hex=bytes(prefix.actions.pending[0]).hex(),
                           operation_receipt=result, parameters=parameters)
            prefix.actions.deliver_one()
            prefix.deferred_events.drain()
            prefix.view_publisher.publish()
            # A city-state war can revoke Amani's BBG bonus through the
            # installed UI-to-gameplay callbacks. Settle that native work
            # before reading the completed action's public observation.
            feedback_owner = getattr(continuation, 'trade_feedback', None)
            if feedback_owner is not None and feedback_owner.events:
                feedback = continuation.flush_trade_feedback()
                if feedback:
                    backend.emit('xp2_bbg_trade_gameplay_delivered', feedback=feedback)
                receipt['bbg_feedback_flushed'] = True
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
        if catalogue is not None:
            _check_catalogue(saved, catalogue, active=True)
        if continuation.world_input_prompts.get(pid) != prompt:
            raise RuntimeError('War prompt changed during its explicit response')
        continuation.world_input_prompts[pid] = None
        receipt['observation_after'] = deepcopy(observed)
        saved.emit('xp2_world_war_response_effect', **receipt)
        return dict(status='completed', refusal_code=None, observation=observed, receipt=receipt,
                    pending_statement_retained=pending_statement)
    finally:
        if catalogue is not None:
            continuation._xp1_world_input_catalogue = None
            continuation.explicit_world_input = None
