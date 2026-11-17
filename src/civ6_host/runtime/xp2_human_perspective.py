"""Borrow one captured LAN human perspective on the installed Gathering Storm Core."""

import ctypes as C
from struct import unpack
from types import SimpleNamespace

from civ6_host.contracts.capability_unit_orders import actions as unit_order_actions, validate_action
from civ6_host.contracts.captured_city import KIND as OCCUPATION
from civ6_host.contracts.great_person_activation import KIND as ACTIVATE_PERSON, validate_action as validate_activation
from civ6_host.contracts import city_buildings, dedications, espionage, governors, network_turn, pantheon, spy_completion, unit_formations
from civ6_host.contracts import air_operations, archaeology, national_parks, rock_bands, unit_work as work_contract
from . import captured_city_session
from . import xp2_lan_ranged_shots
from . import xp2_plot_purchases
from . import xp2_lan_government
from . import xp2_governors
from . import xp2_espionage
from . import xp2_spy_completion
from . import xp2_lan_great_people
from . import xp1_great_person_activation
from . import xp2_lan_religion
from . import xp1_pantheon
from . import xp2_lan_city_states
from . import xp2_diplomatic_relationships
from . import world_score
from . import xp2_lan_unit_work
from . import network_turns, xp2_lan_city_controls, xp2_lan_production, xp2_lan_production_queue, xp2_lan_research
from . import xp2_lan_unit_attacks, xp2_lan_unit_development, xp2_lan_world_input
from . import xp2_local_player_changed
from . import xp2_dedications, xp2_great_work_commands, xp2_trade, xp2_unit_formations, xp2_world_war
from . import xp2_lan_congress
from . import xp2_air_operations, xp2_build_route, xp2_designate_park, xp2_rock_bands
from . import xp2_archaeology, xp2_archaeology_excavation
from .configuration_profiles import XP2_CORE_SHA256, _source
from .xp1_continuation import ACTIVE, READY
from .xp1_turn_boundary import SavedTurnBoundary

SOURCE = (
    'evidence/host-xp2-human-perspective-switch-source.json',
    '1bbd8edd0d16be9796487303fbf7b54a5513838fe39740290e3908eab7bb9071',
)
_UNIT_PANEL_COMMANDS = {air_operations.KIND: xp2_air_operations,
                        work_contract.BUILD_ROUTE: xp2_build_route,
                        national_parks.DESIGNATE: xp2_designate_park,
                        rock_bands.KIND: xp2_rock_bands}


def unit_panel_scope(saved, requested=None):
    kinds = network_turn.SECONDARY_UNIT_PANEL_KINDS
    enabled = tuple(kind for kind in kinds if _UNIT_PANEL_COMMANDS[kind].enabled(saved))
    if requested is None:
        return enabled
    if type(requested) is not tuple or requested != tuple(kind for kind in enabled if kind in requested):
        raise ValueError('Checkpoint UnitPanel families differ from the admitted secondary routes')
    return requested

# The current XP2 round-completion producer reads CvGame's local player at
# dispatch. The constructor serializes that value unchanged as the sender.
_TURN_COMPLETION_SPANS = (
    (0x5cc91, 'e8ca81feff8bd0488d4c2430e8fe91fdff488d4c2430e8049afdff'),
    (0x44e60, '488b0d015cb4004885c90f8510835f0083c8ffc3'),
    (0x63d180, '488b81400200008b80a82d0000c3'),
    (0x35ea0, '488b0559adb20048894110488d059e839800488901488bc1c741085c4fdb1b895118c3'),
)


def verify_turn_completion_player(saved, player_id):
    from .execution_images import _PROFILE
    from .xp1_session_view import _borrowed_xp2_reference

    _borrowed_xp2_reference(saved, player_id)
    b = saved.backend
    if getattr(b.core, '_civ6_host_execution_image', None) is not _PROFILE:
        raise ValueError('Borrowed turn completion requires the current XP2 execution image')
    base, read = b.core._handle, b.runtime.read
    for rva, source in _TURN_COMPLETION_SPANS:
        raw = bytes.fromhex(source)
        if read(base + rva, len(raw)) != raw:
            raise ValueError('Borrowed XP2 completion sender source differs at ' + hex(rva))
    owner, = unpack('<Q', read(base + 0xb8aa68, 8))
    if owner != saved.continuation.lease.identity['game']:
        raise RuntimeError('Borrowed XP2 completion has a different native cache owner')
    game, = unpack('<Q', read(owner + 0x240, 8))
    if unpack('<ii', read(game + 0x2da8, 8)) != (player_id, player_id):
        raise RuntimeError('Borrowed XP2 completion would identify a different player')


class BorrowedTurnBoundary(SavedTurnBoundary):
    borrowed_xp2 = True

    def __init__(self, snapshot, player_id, turn):
        super().__init__(XP2_CORE_SHA256)
        self.snapshot = snapshot
        self.player_id = player_id
        self.turn = turn

    def state(self, saved):
        self._check(saved)
        state = self.snapshot()
        if (state['player'], state['observer'], state['turn']) != (
                self.player_id, self.player_id, self.turn):
            raise RuntimeError('Borrowed XP2 turn request changed its turn or observer')
        saved.network_turn_rows = {row['player_id']: row for row in state['rows']}
        return state


class InactiveHumanView(ValueError):
    """An admitted human seat no longer has a living player view."""


def _live_abi(backend):
    image = getattr(backend.core, '_civ6_host_execution_image', None)
    base, read = backend.core._handle, backend.runtime.read
    xp2_local_player_changed.verify_live(image, base, read)
    proof = _source(SOURCE)
    prior = proof['setter_source']
    if (proof['schema'] != 'civ6-host.xp2-human-perspective-switch-source.static.v1'
            or proof['execution_image'] != image.id
            or proof['image']['sha256'] != image.image_sha256
            or (prior['path'], prior['sha256']) != xp2_local_player_changed.SOURCE):
        raise ValueError('XP2 perspective source differs from the selected image')
    for label, span in proof['spans'].items():
        raw = bytes.fromhex(span['raw_hex'])
        if len(raw) != span['bytes'] or read(base + int(span['rva'], 16), len(raw)) != raw:
            raise ValueError('XP2 perspective live source differs: ' + label)
    return proof['abi']


def _native_route(continuation, abi, players):
    """Join both native CvGame aliases and refuse fallback visibility."""
    backend = continuation.owner
    base, read = backend.core._handle, backend.runtime.read

    def pointer(address):
        value, = unpack('<Q', read(address, 8))
        if not value:
            raise ValueError('XP2 perspective native pointer is absent')
        return value

    game = pointer(base + abi['game_global_rva'])
    owner = pointer(base + abi['owner_global_rva'])
    if (owner != continuation.lease.identity['game']
            or game != pointer(owner + abi['owner_game_offset'])):
        raise ValueError('XP2 perspective native Game aliases differ')
    visibility = pointer(owner + abi['owner_visibility_offset'])
    context = pointer(visibility + abi['visibility_context_offset'])
    if read(context + abi['notification_suppressed_offset'], 1) != b'\0':
        raise ValueError('XP2 perspective native notifications are suppressed')
    indices = pointer(context + abi['visibility_slot_indices_offset'])
    slots = pointer(context + abi['visibility_slots_offset'])
    views = []
    for player in players:
        slot, = unpack('<i', read(indices + 4 * player, 4))
        if not 0 <= slot < 64:
            raise ValueError('XP2 perspective player has no admitted native visibility slot')
        views.append(pointer(slots + 8 * slot))
    if len(set(views)) != len(players):
        raise ValueError('XP2 perspective visibility slots alias each other')
    return game, visibility, context, tuple(views)


def _flags(continuation):
    transport = continuation.transport
    addr = continuation.owner.core._handle + transport.transport_abi.processor_flags_rva
    return unpack('<4B', transport.read(addr, 4))


def _snapshot(saved, abi, route, players, ids, humans, *, dialogue=None):
    from .lan_load import _parse_humans, human_status_readback_source
    from .network_turns import read_activity

    b, p, token = saved.backend, saved.prefix, saved.continuation
    saved._check_active()
    token.transport.require_empty_native_queue()
    if dialogue is None:
        b.control(empty=True)
    else:
        dialogue.check_ledger()
    if b.host._a0_family_owner.unregistered_player_events:
        raise RuntimeError('XP2 perspective encountered an unregistered player callback')
    if _native_route(token, abi, players) != route:
        raise RuntimeError('XP2 perspective native route changed')
    statuses = p.runtime.evaluate_text(p.game_child, human_status_readback_source(ids),
                                       b'@xp2_perspective_humans', capacity=4096)
    if _parse_humans(statuses, ids) != humans:
        raise RuntimeError('XP2 perspective changed the live human roster')
    state = read_activity(saved, core_sha256=XP2_CORE_SHA256)
    game = route[0]
    local, = unpack('<i', b.runtime.read(game + abi['game_local_offset'], 4))
    observer, = unpack('<i', b.runtime.read(game + abi['game_observer_offset'], 4))
    if (state['local_player_id'], state['observer_id']) != (local, observer):
        raise RuntimeError('XP2 perspective native and Lua identities disagree')
    return dict(turn=state['turn'], player=local, observer=observer,
                rows=state['rows'], flags=_flags(token))


def _require_living_humans(prefix, players):
    # Only pre-authorized integer seat IDs reach this local gameplay query.
    ids = ','.join(map(str, players)).encode('ascii')
    source = b'''for _,id in ipairs({''' + ids + b'''}) do
 local p=Players[id]
 assert(p and p:IsHuman()==true,'missing native human seat')
 local alive=p:IsAlive()
 assert(type(alive)=='boolean','invalid native human life status')
 if not alive then return "defeated" end
end
return "living"'''
    status = prefix.runtime.evaluate_text(prefix.game_child, source,
                                          b'@xp2_perspective_living', capacity=32)
    if status == b'defeated':
        raise InactiveHumanView('XP2 perspective requires a living human seat')
    if status != b'living':
        raise RuntimeError('Unknown native human perspective eligibility')


def _switch(saved, abi, game, player_id):
    from .xp2_preload_source import event_reader_scope

    p = saved.prefix
    reader = p.event_arguments.reader
    call = C.WINFUNCTYPE(C.c_uint8, C.c_void_p, C.c_int32)(reader.base + abi['call_rva'])
    with event_reader_scope(reader.base, reader.read):
        if call(game, player_id) != 1:
            raise RuntimeError('XP2 perspective setter returned an unexpected status')
    p.deferred_events.drain()
    saved.continuation.publisher.publish()


def _view(prefix, player):
    from .native.native_player_observation import observe_player
    from .native.native_saved_player_map import observe

    observation = observe_player(prefix.runtime, prefix.ui_child, player)
    return observation, observe(prefix, observation)


def _unit_commands(saved, observation, state, action, *, include_operations):
    from .native import native_saved_unit_orders as orders
    from .xp2_unit_orders_source import bind_owner

    b, p, continuation = saved.backend, saved.prefix, saved.continuation
    player, turn = observation['player_id'], observation['turn']
    row = next(row for row in state['rows'] if row['player_id'] == player)
    if not row['active'] or not row['active_complete'] or row['can_unready']:
        return None, None
    source = f'''assert(Game.GetLocalPlayer()=={player} and Game.GetLocalObserver()=={player}
       and Game.GetCurrentGameTurn()=={turn},'borrowed unit command boundary')
return Game.IsAllowStrategicCommands({player})==true and "allow" or "unavailable"'''.encode('ascii')
    allowed = p.runtime.evaluate_text(p.ui_child, source, b'@xp2_perspective_unit_permissions',
                                      capacity=32)
    if allowed == b'unavailable':
        return None, None
    if allowed != b'allow':
        raise RuntimeError('Invalid native borrowed-unit command permission')
    bind_owner(b, b.core, b.runtime.read)
    options = dict(player_id=player, include_cancel=True, core_sha256=XP2_CORE_SHA256)
    from . import xp2_extra_unit_orders
    if xp2_extra_unit_orders.enabled(saved):
        options['include_extended'] = True
    catalogue = orders.catalog(p, turn, **options)
    def scoped_offers(value):
        if include_operations:
            return value
        return dict(value, offers=[row for row in value['offers'] if row['action']['route'] == 'command'])

    public = scoped_offers(catalogue)
    choices = unit_order_actions(public)
    if action is None or action not in choices:
        return public, None
    effects = []
    current_destination = None
    if action['item_type'] == 'UNITCOMMAND_CANCEL':
        from .native.native_saved_combat import queued_destination
        from .xp1_world_input_profile import bind_owner as bind_world_input

        bind_world_input(b, b.core, b.runtime.read)
        current_destination = queued_destination(
            p, player, turn, action['unit_id'], observation['width'], observation['height'],
            core_sha256=XP2_CORE_SHA256)
        if not current_destination['unit_present']:
            raise RuntimeError('XP2 cancellation target disappeared before submission')

    def emit(stage, **payload):
        if stage != 'official_explicit_unit_order_effect' or effects:
            raise RuntimeError('Unexpected borrowed XP2 unit-command receipt')
        effects.append(payload)
        saved.emit(stage, **payload)

    owner = SimpleNamespace(explicit_unit_orders=catalogue, emit=emit)
    with continuation.transport.require_xp2_unit_order(player, action['unit_id'], action['route']):
        after = orders.apply(owner, p, action, turn, observation, **options)
    if len(effects) != 1 or effects[0]['observation_after'] != after:
        raise RuntimeError('XP2 unit command did not yield its matching native observation')
    effect = effects[0]
    if current_destination is not None:
        resulting_destination = queued_destination(
            p, player, turn, action['unit_id'], after['width'], after['height'],
            core_sha256=XP2_CORE_SHA256)
        if not resulting_destination['unit_present']:
            raise RuntimeError('XP2 cancellation removed the target unit')
        effect = dict(effect, queued_destination_before=current_destination['plot_id'],
                      queued_destination_after=resulting_destination['plot_id'])
    return scoped_offers(orders.catalog(p, turn, **options)), effect


def _decision(saved, player_id):
    token = saved.continuation
    return dict(episode_id=token.identity.episode_id, game_generation=token.identity.game_generation,
                sequence=token.sequence, turn=token.observation['turn'], player_id=player_id)


def _needs_explicit_response(saved, player_id):
    return (saved.continuation.world_input_prompts.get(player_id) is not None
            or bool(saved.prefix.deferred_events.pending_diplomacy_statements))


def _found_city(saved, action, observation):
    """Reuse the saved-owner foundation request with an exact operation guard."""
    p, token = saved.prefix, saved.continuation
    player, unit = observation['player_id'], action['unit_id']
    x, y = action['x'], action['y']
    # Current XP2's parameterless FOUND_CITY archive uses operation 0x0e.
    with token.transport.require_xp2_unit_order(player, unit, 'operation', opcode=0x0e):
        witness = p.inspect_found_city(player, unit_id=unit, expected_x=x, expected_y=y)
    feedback = getattr(token, 'trade_feedback', None)
    if feedback is not None and feedback.events:
        delivered = token.flush_trade_feedback()
        if delivered:
            saved.backend.emit('xp2_bbg_trade_gameplay_delivered', feedback=delivered)
    view = _view(p, player)
    after = view[0]
    old_cities = {row['id'] for row in observation['cities']}
    after_cities = {row['id']: row for row in after['cities']}
    new_id = witness['city_id']
    city = after_cities.get(new_id)
    if (after['turn'] != observation['turn']
            or (witness['player_id'], witness['consumed_unit_id'], witness['x'], witness['y'])
                != (player, unit, x, y)
            or new_id in old_cities or after_cities.keys() != old_cities | {new_id}
            or city is None
            or (city['owner'], city['x'], city['y'], city['population'])
                != (player, x, y, witness['population'])
            or any(row['id'] == unit for row in after['units'])):
        raise RuntimeError('Borrowed XP2 foundation differs from its public city or founder')
    return view


def city_panel_scope(saved, requested=None):
    available = tuple(name for name, enabled in (
        ('city_buildings', getattr(saved, 'xp2_city_buildings', False) is True),
        ('city_growth', getattr(saved, '_expansion_city_growth', None) is not None),
        ('city_loyalty', getattr(saved, '_expansion_city_loyalty', None) is not None),
        ('city_religion', getattr(saved, 'xp2_city_religion_details', False) is True),
        ('rock_bands', xp2_rock_bands.enabled(saved)),
    ) if enabled)
    if requested is None:
        return available
    if type(requested) is not tuple or requested != tuple(name for name in available if name in requested):
        raise ValueError('Borrowed city panels require the source-qualified saved session readers')
    return requested


def _run(saved, player_id, *, include_unit_commands=False, decision=None, network=False,
         expected_city_state=None, restore_envoys=None, city_panel_groups=None, great_people_mode=None,
         great_person_activation_enabled=None,
         pantheon_enabled=None, governors_enabled=None, espionage_enabled=None,
         spy_completion_enabled=None, religion_groups=None, trade_enabled=None, formation_enabled=None,
         dedication_enabled=None, congress_mode=None, congress_sequence=None, congress_checkpoint=None,
         unit_panel_families=None, city_state_peace_enabled=None, dialogue_sequence=None,
         include_wars=False, world_score_enabled=None, archaeology_mode=None):
    """Execute one exclusive view interval and restore the primary seat."""
    from .saved_load_job_observer import require_quiescent
    from .xp1_load_capability import capability_source_scope
    from .xp1_session_view import _reference
    from .xp2_cache_source import update_source_scope

    saved._check('commands', requested='unit_commands_candidate')
    if saved._engine_sha256 != XP2_CORE_SHA256:
        raise ValueError('This perspective route requires installed Gathering Storm')
    if include_wars and (network or include_unit_commands or decision is not None
            or getattr(saved, 'diplomacy_overview_diagnostic', False) is not True):
        raise ValueError('Public war states require the admitted XP2 diplomacy view')
    b, p, token = saved.backend, saved.prefix, saved.continuation
    local = token.observation['player_id']
    ref, ids = _reference(saved, local)
    humans = ref['human_player_ids']
    if type(player_id) is not int or player_id not in humans:
        raise ValueError('XP2 perspective requires a captured human seat')
    identity = _decision(saved, player_id)
    action = None
    if decision is not None:
        expected, action = decision
        if (type(expected) is not dict or expected != identity
                or any(type(expected[key]) is not int for key in ('sequence', 'turn', 'player_id'))):
            raise ValueError('Borrowed XP2 command belongs to another player or decision revision')
    players = (local,) if player_id == local else (local, player_id)
    abi = _live_abi(b)
    route = _native_route(token, abi, players)
    borrowed = getattr(saved, '_xp2_borrowed_war', None)
    dialogue = borrowed
    if borrowed is not None:
        if (token.publishing or network and (player_id != borrowed.player_id
                or action is not None and action['kind'] != 'diplomacy_response')
                or include_unit_commands and not network):
            raise ValueError('Borrowed surprise-war dialogue belongs to its current responding seat')
        borrowed.check_ledger()
    elif (not network and not include_unit_commands and action is None
            and p.deferred_events.pending_diplomacy_statements):
        from .xp2_diplomacy import PublicViewDialogue

        if token.publishing:
            raise ValueError('Cannot read another view during native publication')
        dialogue = PublicViewDialogue(saved)
    else:
        token.check_close()
    _require_living_humans(p, players)
    if player_id != local:
        profile = b.host._a0_family_owner.notification_scope_profile
        if profile is None or profile.records.get(xp2_local_player_changed.KIND) != xp2_local_player_changed.RECORD:
            raise ValueError('XP2 perspective notifications are outside the admitted script scope')

    catalogue, effect, native = None, None, None
    gates, command, research, founders = None, None, None, None
    production, queues, city_controls, world_state = None, None, None, None
    development = None
    attacks = None
    occupation = None
    ranged_shots = None
    purchases = None
    government = None
    war_state = None
    diplomacy = None
    city_states = None
    peace_scope = xp2_lan_city_states.peace_scope(saved, city_state_peace_enabled) if network else False
    city_state_peace = None
    diplomatic_wars = None
    score_enabled = world_score.borrowed_enabled(saved, world_score_enabled) if network else False
    score = None
    artifact_mode = xp2_archaeology.borrowed_mode(saved, archaeology_mode) if network else 'off'
    artifacts = excavations = None
    unit_work = None
    panel_kinds = unit_panel_scope(saved, unit_panel_families) if network and player_id != local else ()
    panel_adapters = {kind: _UNIT_PANEL_COMMANDS[kind] for kind in panel_kinds}
    panel_actions = {}
    city_panels = {}
    groups = city_panel_scope(saved, city_panel_groups) if network else ()
    people_scope = xp2_lan_great_people.mode(saved, great_people_mode) if network else 'off'
    people = None
    activation_scope = (network and player_id != local and
                        xp1_great_person_activation.borrowed_enabled(saved, great_person_activation_enabled))
    activation_state = None
    pantheon_scope = xp1_pantheon.borrowed_enabled(saved, pantheon_enabled) if network else False
    pantheon_state = None
    governor_scope = xp2_governors.borrowed_enabled(saved, governors_enabled) if network else False
    governor_state = None
    espionage_scope = xp2_espionage.borrowed_enabled(saved, espionage_enabled) if network else False
    espionage_state = None
    completion_scope = xp2_spy_completion.borrowed_enabled(saved, spy_completion_enabled) if network else False
    completion_state = None
    religion_scope = xp2_lan_religion.scope(saved, religion_groups) if network else ()
    religious = dict.fromkeys(religion_scope)
    trade_scope = xp2_trade.borrowed_enabled(saved, trade_enabled) if network else False
    trade_states = dict.fromkeys(xp2_trade.FIELDS.values()) if trade_scope else {}
    formation_scope = xp2_unit_formations.borrowed_enabled(saved, formation_enabled) if network else False
    formation_state = None
    dedication_scope = xp2_dedications.borrowed_enabled(saved, dedication_enabled) if network else False
    dedication_state = None
    congress_scope = xp2_lan_congress.mode(saved, congress_mode) if network else 'off'
    congress = {}
    with saved._attempt():
        b.stage, b.busy = ACTIVE, True
        saved._check_active()
        require_quiescent(b.jobs_snapshot('before'))
        with capability_source_scope(b, 'continuation'), update_source_scope():
            def snapshot():
                return _snapshot(saved, abi, route, players, ids, humans, dialogue=dialogue)

            original = snapshot()
            if (original['player'], original['observer'], original['turn']) != (
                    local, local, token.observation['turn']):
                raise RuntimeError('XP2 perspective did not start from the current public boundary')
            original_view = _view(p, local)
            if original_view[0] != token.observation or snapshot() != original:
                raise RuntimeError('XP2 perspective original boundary changed during observation')
            if dialogue is not None and borrowed is None:
                dialogue.check_open()
            switched = player_id != local
            if switched:
                _switch(saved, abi, route[0], player_id)
            target = dict(original, player=player_id, observer=player_id)
            if snapshot() != target:
                raise RuntimeError('XP2 perspective target or native turn state differs')
            if borrowed is not None and borrowed.player_id == player_id:
                borrowed.check_open()

            def restore(state=target, *, unchanged):
                if snapshot() != state:
                    raise RuntimeError('XP2 perspective target boundary changed during observation')
                _switch(saved, abi, route[0], local)
                if snapshot() != dict(state, player=local, observer=local):
                    raise RuntimeError('XP2 perspective failed to restore the original view')
                original_after = _view(p, local)
                if unchanged and original_after != original_view:
                    raise RuntimeError('XP2 perspective failed to restore the original view')
                return original_after

            def can_act(state):
                row = next(row for row in state['rows'] if row['player_id'] == player_id)
                return not network_turn.is_waiting(row)

            def read_congress(observation):
                return xp2_lan_congress.read(saved, observation,
                    token.sequence if congress_sequence is None else congress_sequence,
                    include_results=congress_scope == 'review',
                    can_choose=(congress_sequence is not None or congress_checkpoint is not None) and can_act(after),
                    checkpoint=congress_checkpoint)

            try:
                view = _view(p, player_id) if switched else original_view
                after = target
                if include_wars:
                    diplomatic_wars = xp2_diplomatic_relationships.read_wars(p, player_id, target['turn'])
                if network:
                    from .xp1_session_result import read_borrowed_xp2

                    def outcome_at(turn):
                        options = {} if borrowed is None else {'dialogue': borrowed}
                        return read_borrowed_xp2(saved, player_id, turn, **options)

                    native = outcome_at(target['turn'])
                if (network and action is not None and action['kind'] == 'world_war_response'
                        and not native['episode_terminated']):
                    command, observed = xp2_world_war.respond_borrowed(
                        saved, action, view[0], expected=expected_city_state)
                    if observed is not None:
                        borrowed = dialogue = getattr(saved, '_xp2_borrowed_war', None)
                        view = _view(p, player_id)
                        after = snapshot()
                        if view[0] != observed or (after['player'], after['observer'], after['turn']) != (
                                player_id, player_id, target['turn']):
                            raise RuntimeError('Borrowed war response crossed its observation or seat')
                        native = outcome_at(after['turn'])
                if (network and action is not None and action['kind'] == 'diplomacy_response'
                        and borrowed is not None and not native['episode_terminated']):
                    command, observed = borrowed.respond(action, view[0], expected_city_state)
                    if observed is not None:
                        borrowed = dialogue = None
                        view = _view(p, player_id)
                        after = snapshot()
                        if view[0] != observed or (after['player'], after['observer'], after['turn']) != (
                                player_id, player_id, target['turn']):
                            raise RuntimeError('Borrowed war dialogue crossed its observation or seat')
                        native = outcome_at(after['turn'])
                turn_action = action is not None and action['kind'] in network_turns.TURN_REQUESTS
                research_action = action is not None and action['kind'] in xp2_lan_research.KINDS
                found_action = action is not None and action['kind'] == 'found_city'
                congress_action = action is not None and action['kind'] in xp2_lan_congress.ACTIONS
                modal = network and _needs_explicit_response(saved, player_id)
                if network and congress_action and not native['episode_terminated'] and not modal:
                    command = xp2_lan_congress.submit(saved, action, view[0], published=expected_city_state,
                        available=congress_scope == 'review' and can_act(after))
                    if command['status'] != 'refused':
                        after = BorrowedTurnBoundary(snapshot, player_id, target['turn']).state(saved)
                        view = _view(p, player_id)
                        native = read_borrowed_xp2(saved, player_id, after['turn'])
                        modal = _needs_explicit_response(saved, player_id)
                if network and turn_action and not native['episode_terminated'] and not modal:
                    boundary = BorrowedTurnBoundary(snapshot, player_id, target['turn'])
                    command = network_turns.submit(saved, action, player_id,
                        boundary=boundary, borrowed_xp2=True)
                    if command['status'] != 'refused':
                        after = boundary.state(saved)
                        view = _view(p, player_id)
                        native = read_borrowed_xp2(saved, player_id, after['turn'])
                        modal = _needs_explicit_response(saved, player_id)
                if network and research_action and not native['episode_terminated'] and not modal:
                    research = xp2_lan_research.read(saved, view[0], after)
                    command = xp2_lan_research.apply(saved, action, research)
                    if command['status'] != 'refused':
                        view = _view(p, player_id)
                        native = read_borrowed_xp2(saved, player_id, after['turn'])
                        modal = _needs_explicit_response(saved, player_id)
                        research = None
                if (include_unit_commands and not modal
                        and (native is None or not native['episode_terminated'])):
                    catalogue, effect = _unit_commands(
                        saved, view[0], after, action if action and action['kind'] == 'unit_order' else None,
                        include_operations=network)
                    if effect is not None:
                        view = _view(p, player_id)
                        if view[0] != effect['observation_after']:
                            raise RuntimeError('XP2 borrowed unit command crossed the current observation')
                        if network:
                            native = read_borrowed_xp2(saved, player_id, target['turn'])
                if network:
                    if native['episode_terminated'] or _needs_explicit_response(saved, player_id):
                        catalogue = research = None
                    else:
                        from .xp1_session_view import read_founders

                        def current_founders():
                            if catalogue is None:
                                return None
                            return read_founders(p, player_id, after['turn'], core_sha256=XP2_CORE_SHA256)

                        founders = current_founders()
                        if found_action:
                            if founders is None or action not in founders:
                                command = dict(status='refused', reason='native_foundation_unavailable',
                                               requested_action=action)
                            else:
                                view = _found_city(saved, action, view[0])
                                native = read_borrowed_xp2(saved, player_id, after['turn'])
                                command = dict(status='completed', reason=None, requested_action=action)
                                if native['episode_terminated'] or _needs_explicit_response(saved, player_id):
                                    catalogue = research = founders = None
                                else:
                                    catalogue, _ = _unit_commands(
                                        saved, view[0], after, None, include_operations=True)
                                    founders = current_founders()
                    if not native['episode_terminated'] and not _needs_explicit_response(saved, player_id):
                        if catalogue is not None:
                            production = xp2_lan_production.read(saved, view[0])
                        observed = None
                        kind = action['kind'] if action is not None else None
                        if congress_scope != 'off' and kind in network_turn.CONGRESS_READ_ONLY_KINDS:
                            current_congress = read_congress(view[0])
                            if current_congress['world_congress']['in_session']:
                                congress = current_congress
                                command = dict(status='refused', reason='native_congress_screen_read_only',
                                               requested_action=action)
                                kind = None
                        if kind == 'production':
                            command, observed = xp2_lan_production.apply(
                                saved, action, view[0], production, expected_head=expected_city_state)
                        elif kind in xp2_lan_production_queue.FIELDS:
                            queues = xp2_lan_production_queue.read(saved, view[0], production)
                            command, observed = xp2_lan_production_queue.apply(
                                saved, action, view[0], queues, expected_queue=expected_city_state)
                        elif kind in xp2_lan_city_controls.CATALOGUE_FIELDS:
                            if production is not None:
                                city_controls = xp2_lan_city_controls.read(saved, view[0])
                            command, observed = xp2_lan_city_controls.apply(
                                saved, action, view[0], city_controls, expected_city=expected_city_state)
                        elif kind in xp2_lan_world_input.WORLD_KINDS:
                            if catalogue is not None and xp2_lan_world_input.enabled(saved):
                                world_state = xp2_lan_world_input.read(saved, view[0])
                            command, observed = xp2_lan_world_input.apply(
                                saved, action, view[0], world_state, expected_state=expected_city_state)
                        elif kind in xp2_lan_unit_development.FIELDS:
                            development = xp2_lan_unit_development.read(
                                saved, view[0], after, strategic_allowed=catalogue is not None)
                            command, observed = xp2_lan_unit_development.apply(
                                saved, action, view[0], development, expected_state=expected_city_state)
                        elif kind == 'unit_attack':
                            if catalogue is not None and xp2_lan_unit_attacks.enabled(saved):
                                world_state = xp2_lan_world_input.read(saved, view[0])
                                attacks = xp2_lan_unit_attacks.read(saved, view[0], queued_orders=world_state[1])
                            command, observed = xp2_lan_unit_attacks.apply(
                                saved, action, view[0], attacks, expected=expected_city_state)
                        elif kind == OCCUPATION:
                            occupation = captured_city_session.borrowed_snapshot(saved, view[0], after)
                            command, observed = captured_city_session.apply_borrowed(
                                saved, action, view[0], occupation, expected=expected_city_state)
                        elif kind in xp2_lan_ranged_shots.FIELDS:
                            ranged_shots = xp2_lan_ranged_shots.read(
                                saved, view[0], strategic_allowed=catalogue is not None)
                            command, observed = xp2_lan_ranged_shots.apply(
                                saved, action, view[0], ranged_shots, expected=expected_city_state)
                        elif kind == 'purchase':
                            purchases = xp2_plot_purchases.borrowed_catalogue(
                                saved, view[0], strategic_allowed=catalogue is not None)
                            command, observed = xp2_plot_purchases.apply_borrowed(
                                saved, action, view[0], purchases)
                        elif kind in xp2_lan_government.FIELDS:
                            government = xp2_lan_government.read(
                                saved, view[0], strategic_allowed=catalogue is not None)
                            command, observed = xp2_lan_government.apply(
                                saved, action, view[0], government, expected=expected_city_state)
                        elif kind in xp2_lan_city_states.FIELDS:
                            city_states = xp2_lan_city_states.read(
                                saved, view[0], after, strategic_allowed=catalogue is not None)
                            command, observed = xp2_lan_city_states.apply(
                                saved, action, view[0], city_states, expected=expected_city_state)
                        elif kind == 'diplomacy_initiate' and xp2_lan_city_states.is_peace(action):
                            command, observed = xp2_lan_city_states.apply_peace(
                                saved, action, view[0], expected=expected_city_state,
                                available=peace_scope and catalogue is not None and can_act(after))
                        elif kind in xp2_lan_great_people.KINDS:
                            command, observed = xp2_lan_great_people.apply(
                                saved, action, view[0], after, published=expected_city_state, scope=people_scope)
                        elif kind == ACTIVATE_PERSON:
                            command, observed = xp1_great_person_activation.apply_borrowed(
                                saved, action, view[0], expected=expected_city_state,
                                available=activation_scope and catalogue is not None and can_act(after))
                        elif kind == pantheon.KIND:
                            command, observed = xp1_pantheon.apply_borrowed(saved, action, view[0],
                                expected=expected_city_state, available=pantheon_scope and catalogue is not None)
                        elif kind in governors.ACTION_FIELDS:
                            command, observed = xp2_governors.apply_borrowed(saved, action, view[0],
                                expected=expected_city_state, available=governor_scope and catalogue is not None)
                        elif kind in espionage.ACTION_FIELDS:
                            command, observed = xp2_espionage.apply_borrowed(saved, action, view[0],
                                expected=expected_city_state, available=espionage_scope and can_act(after))
                        elif kind in spy_completion.ACTION_FIELDS:
                            command, observed = xp2_spy_completion.apply_borrowed(saved, action, view[0],
                                expected=expected_city_state, available=completion_scope, waiting=not can_act(after))
                        elif kind in xp2_trade.FIELDS:
                            command, observed = xp2_trade.apply_borrowed(saved, action, view[0],
                                expected=expected_city_state, enabled=trade_scope, ready=can_act(after),
                                strategic_allowed=catalogue is not None)
                        elif kind == unit_formations.KIND:
                            command, observed = xp2_unit_formations.apply_borrowed(saved, action, view[0],
                                expected=expected_city_state, available=formation_scope and catalogue is not None)
                        elif kind == city_buildings.GREAT_WORK_MOVE:
                            eligible = (xp2_great_work_commands.enabled(saved) and 'city_buildings' in groups
                                and catalogue is not None and can_act(after) and expected_city_state is not None
                                and action in city_buildings.great_work_actions(expected_city_state))
                            if eligible:
                                effect_result = xp2_great_work_commands.apply(saved, action, view[0], borrowed=True)
                                command = dict(status=effect_result['status'], requested_action=action,
                                               reason=effect_result['refusal_code'])
                                if command['status'] == 'completed':
                                    observed = effect_result['observation']
                            else:
                                command = dict(status='refused', requested_action=action,
                                               reason='native_great_work_acting_boundary_unavailable')
                        elif kind == dedications.KIND:
                            command, observed = xp2_dedications.apply_borrowed(saved, action, view[0],
                                expected=expected_city_state, available=dedication_scope and can_act(after))
                        elif kind in xp2_lan_religion.FIELDS:
                            command, observed = xp2_lan_religion.apply(saved, action, view[0],
                                published=expected_city_state, fields=religion_scope, available=catalogue is not None)
                        elif kind in xp2_lan_unit_work.KINDS:
                            unit_work = xp2_lan_unit_work.read(saved, view[0], after)
                            command, observed = xp2_lan_unit_work.apply(saved, action, view[0], unit_work)
                        elif kind in (archaeology.KIND, archaeology.EXCAVATE):
                            eligible = (artifact_mode == 'commands' and can_act(after)
                                and (kind == archaeology.EXCAVATE or (
                                    expected_city_state is not None and action in archaeology.actions(expected_city_state))))
                            if eligible:
                                from .xp1_session_view import _borrowed_xp2_reference

                                _borrowed_xp2_reference(saved, player_id)
                                if kind == archaeology.EXCAVATE:
                                    result = xp2_archaeology_excavation.apply(saved, action, view[0])
                                else:
                                    result = xp2_archaeology.apply(saved, action, view[0],
                                                                  borrowed_public=expected_city_state)
                                command = dict(status=result['status'], reason=result['refusal_code'],
                                               requested_action=action)
                                if command['status'] != 'refused':
                                    observed = result['observation']
                            else:
                                command = dict(status='refused', reason='secondary_native_archaeology_unavailable',
                                               requested_action=action)
                        elif kind in _UNIT_PANEL_COMMANDS:
                            adapter = panel_adapters.get(kind)
                            if adapter is not None and can_act(after):
                                from .xp1_session_view import _borrowed_xp2_reference

                                _borrowed_xp2_reference(saved, player_id)
                                result = adapter.apply(saved, action, view[0])
                                command = dict(status=result['status'], reason=result['refusal_code'],
                                               requested_action=action)
                                if kind == rock_bands.KIND and result['status'] == 'completed':
                                    command['concert'] = rock_bands.validate_result(
                                        result['receipt']['concert'], player_id, view[0]['turn'], action)
                                if result['status'] != 'refused':
                                    observed = result['observation']
                            else:
                                command = dict(status='refused', reason='secondary_native_choice_unavailable',
                                               requested_action=action)
                        if observed is not None:
                            view = _view(p, player_id)
                            if view[0] != observed:
                                raise RuntimeError('Borrowed action differs from its public observation')
                            if (kind in (OCCUPATION, pantheon.KIND) or kind in xp2_lan_ranged_shots.FIELDS
                                    or kind in xp2_lan_government.FIELDS or kind in xp2_lan_city_states.FIELDS
                                    or kind == 'diplomacy_initiate'
                                    or kind in xp2_lan_great_people.KINDS or kind in xp2_lan_religion.FIELDS
                                    or kind in governors.ACTION_FIELDS or kind in espionage.ACTION_FIELDS
                                    or kind in spy_completion.ACTION_FIELDS or kind in xp2_trade.FIELDS
                                    or kind in (archaeology.KIND, archaeology.EXCAVATE) or kind in _UNIT_PANEL_COMMANDS
                                    or kind in (unit_formations.KIND, dedications.KIND, city_buildings.GREAT_WORK_MOVE,
                                                ACTIVATE_PERSON)):
                                after = snapshot()
                                if (after['player'], after['observer'], after['turn']) != (
                                        player_id, player_id, target['turn']):
                                    raise RuntimeError('Borrowed city command crossed its turn or actor')
                            native = read_borrowed_xp2(saved, player_id, after['turn'])
                            city_controls = world_state = development = attacks = occupation = ranged_shots = None
                            purchases = government = city_states = unit_work = people = None
                            if native['episode_terminated'] or _needs_explicit_response(saved, player_id):
                                catalogue = research = founders = production = queues = None
                            else:
                                if (kind in ('unit_attack', OCCUPATION, 'purchase', pantheon.KIND)
                                        or kind in xp2_lan_ranged_shots.FIELDS
                                        or kind in xp2_lan_world_input.WORLD_KINDS or kind in xp2_lan_government.FIELDS
                                        or kind in xp2_lan_city_states.FIELDS or kind == 'diplomacy_initiate'
                                        or kind in xp2_lan_great_people.KINDS
                                        or kind in governors.ACTION_FIELDS
                                        or kind in espionage.ACTION_FIELDS
                                        or kind in spy_completion.ACTION_FIELDS
                                        or kind in xp2_trade.FIELDS
                                        or kind in (unit_formations.KIND, dedications.KIND, city_buildings.GREAT_WORK_MOVE,
                                                    ACTIVATE_PERSON)
                                        or kind in xp2_lan_religion.FIELDS
                                        or kind in xp2_lan_unit_work.KINDS
                                        or kind in (archaeology.KIND, archaeology.EXCAVATE) or kind in _UNIT_PANEL_COMMANDS
                                        or kind in xp2_lan_unit_development.FIELDS):
                                    catalogue, _ = _unit_commands(
                                        saved, view[0], after, None, include_operations=True)
                                    founders = current_founders()
                                production = (xp2_lan_production.read(saved, view[0])
                                              if catalogue is not None else None)
                                queues = None
                        if queues is None:
                            queues = xp2_lan_production_queue.read(saved, view[0], production)
                        if city_controls is None and production is not None:
                            city_controls = xp2_lan_city_controls.read(saved, view[0])
                        if world_state is None and catalogue is not None and xp2_lan_world_input.enabled(saved):
                            world_state = xp2_lan_world_input.read(saved, view[0])
                        if attacks is None and world_state is not None and xp2_lan_unit_attacks.enabled(saved):
                            attacks = xp2_lan_unit_attacks.read(saved, view[0], queued_orders=world_state[1])
                        if ranged_shots is None and catalogue is not None and xp2_lan_ranged_shots.enabled(saved):
                            ranged_shots = xp2_lan_ranged_shots.read(saved, view[0], strategic_allowed=True)
                        if purchases is None and catalogue is not None and xp2_plot_purchases.borrowed_enabled(saved):
                            purchases = xp2_plot_purchases.borrowed_catalogue(saved, view[0], strategic_allowed=True)
                        if government is None and catalogue is not None and xp2_lan_government.enabled(saved):
                            government = xp2_lan_government.read(saved, view[0], strategic_allowed=True)
                        if (development is None and not native['episode_terminated']
                                and not _needs_explicit_response(saved, player_id)):
                            development = xp2_lan_unit_development.read(
                                saved, view[0], after, strategic_allowed=catalogue is not None)
                    if not native['episode_terminated'] and not _needs_explicit_response(saved, player_id):
                        city_state_peace = xp2_lan_city_states.read_peace(
                            saved, view[0], available=peace_scope and catalogue is not None and can_act(after))
                        if pantheon_scope and catalogue is not None:
                            pantheon_state = xp1_pantheon.borrowed_state(saved, view[0])
                        if governor_scope and catalogue is not None:
                            governor_state = xp2_governors.catalogue(saved, view[0], borrowed=True)
                        if espionage_scope and can_act(after):
                            espionage_state = xp2_espionage.borrowed_catalogue(saved, view[0])
                        if completion_scope:
                            completion_state = xp2_spy_completion.borrowed_catalogue(
                                saved, view[0], waiting=not can_act(after))
                        if trade_scope:
                            trade_states = xp2_trade.read_borrowed(saved, view[0], ready=can_act(after),
                                strategic_allowed=catalogue is not None)
                        if formation_scope and catalogue is not None:
                            formation_state = xp2_unit_formations.read_borrowed(saved, view[0])
                        if dedication_scope and can_act(after):
                            dedication_state = xp2_dedications.read_borrowed(saved, view[0])
                        if religion_scope:
                            religious = xp2_lan_religion.read_all(saved, view[0], religion_scope,
                                                                 available=catalogue is not None)
                        if people_scope != 'off' and people is None:
                            people = xp2_lan_great_people.read(saved, view[0], after, scope=people_scope)
                        if activation_scope and catalogue is not None and can_act(after):
                            activation_state = xp1_great_person_activation.borrowed_state(saved, view[0])
                        if city_states is None:
                            city_states = xp2_lan_city_states.read(saved, view[0], after,
                                strategic_allowed=catalogue is not None, restore_envoys=restore_envoys)
                        if unit_work is None:
                            unit_work = xp2_lan_unit_work.read(saved, view[0], after)
                        if occupation is None:
                            occupation = captured_city_session.borrowed_snapshot(saved, view[0], after)
                        if not turn_action:
                            verify_turn_completion_player(saved, player_id)
                        boundary = BorrowedTurnBoundary(snapshot, player_id, after['turn'])
                        gates = boundary.gates(saved, player_id, after['turn'])
                        row = next(row for row in after['rows'] if row['player_id'] == player_id)
                        if any(gates['diagnostics'][key] != row[key]
                               for key in ('active', 'active_complete', 'can_unready')):
                            raise RuntimeError('Borrowed XP2 turn UI and scheduler disagree')
                        if research is None:
                            research = xp2_lan_research.read(saved, view[0], after)
                if network and not native['episode_terminated']:
                    if token.world_input_prompts.get(player_id) is not None:
                        war_state = xp2_world_war.read_borrowed(saved, view[0])
                    elif borrowed is not None:
                        if dialogue_sequence is None:
                            raise RuntimeError('Borrowed war dialogue requires the public decision revision')
                        diplomacy = borrowed.read(dialogue_sequence, view[0])
                    elif congress_scope != 'off' and not congress:
                        congress = read_congress(view[0])
                    if not _needs_explicit_response(saved, player_id):
                        if score_enabled:
                            score = world_score.read(saved, view[0])
                        panel_actions = {kind: adapter.read(saved, view[0], borrowed=True) if can_act(after) else []
                                         for kind, adapter in panel_adapters.items()}
                if groups and not native['episode_terminated'] and borrowed is None:
                    from . import expansion_city_growth, expansion_city_loyalty, xp1_city_religion, xp2_city_buildings

                    readers = {'city_buildings': xp2_city_buildings.read,
                               'city_growth': expansion_city_growth.read,
                               'city_loyalty': expansion_city_loyalty.read,
                               'city_religion': xp1_city_religion.read_details,
                               'rock_bands': xp2_rock_bands.read_panel}
                    city_panels = {key: readers[key](saved, view[0], borrowed=True) for key in groups}
                    if 'city_buildings' in city_panels and network:
                        city_panels['city_buildings'] = xp2_great_work_commands.public_panel(
                            saved, city_panels['city_buildings'], can_act=catalogue is not None and can_act(after))
                if (artifact_mode != 'off' and not native['episode_terminated']
                        and not _needs_explicit_response(saved, player_id)):
                    from .xp1_session_view import _borrowed_xp2_reference

                    _borrowed_xp2_reference(saved, player_id)
                    artifacts = xp2_archaeology.read(saved, view[0], panel=city_panels.get('city_buildings'),
                                                     borrowed=True)
                    if artifact_mode == 'commands':
                        excavations = (xp2_archaeology_excavation.read(saved, view[0], borrowed=True)
                                       if can_act(after) else [])
            except BaseException:
                # A failed command may have queued or already applied work.
                # The owner quarantines that process without a second mutation.
                if switched and action is None:
                    restore(unchanged=True)
                raise
            changed = effect is not None or (command is not None and command['status'] != 'refused')
            if borrowed is not None and borrowed.player_id == player_id:
                borrowed.check_open()
            restored = restore(after, unchanged=not changed) if switched else view
            original = dict(after, player=local, observer=local)
            if snapshot() != original:
                raise RuntimeError('XP2 perspective did not preserve the original turn and observer')
            if dialogue is not None and borrowed is None:
                dialogue.check_open()
        require_quiescent(b.jobs_snapshot('after'))
        if changed:
            token.observation = restored[0]
            token.sequence += 1
        b.stage, b.busy = READY, False
        saved._finish('commands')

    row = next(row for row in original['rows'] if row['player_id'] == player_id)
    result = dict(observation=view[0], player_map=view[1],
                  player_turn=dict(active=row['active'], turn_active_complete=row['active_complete']))
    if include_wars:
        result['diplomatic_wars'] = diplomatic_wars
    if network:
        development = development or {}
        ranged_shots = ranged_shots or {}
        government = government or {}
        city_states = city_states or {}
        return SimpleNamespace(view=result, unit_orders=catalogue, unit_effect=effect,
            outcome=native, state=original, gates=gates, receipt=command,
            research=xp2_lan_research.project(research), founders=founders,
            production=xp2_lan_production.project(production), queues=queues,
            city_focus_catalogs=None if city_controls is None else city_controls[0],
            citizen_catalogs=None if city_controls is None else city_controls[1],
            world_input=None if world_state is None else world_state[0],
            war_state=war_state, diplomacy=diplomacy,
            queued_orders=None if world_state is None else world_state[1],
            unit_promotions=development.get('promote_unit', (None, None))[1],
            unit_upgrades=development.get('upgrade_unit', (None, None))[1],
            unit_attacks=None if attacks is None else attacks[1],
            captured_city=None if occupation is None else occupation[1],
            city_shots=ranged_shots.get('city_range_attack'),
            district_shots=ranged_shots.get('district_range_attack'),
            plot_purchases=None if purchases is None else purchases[0],
            city_purchases=None if purchases is None else purchases[1],
            government=government.get('government'), policies=government.get('policies'),
            policy_unlock=government.get('policy_unlock'), envoys=city_states.get('envoys'),
            city_state_levies=city_states.get('city_state_levies'), unit_levies=city_states.get('unit_levies'),
            city_state_peace=city_state_peace, city_state_peace_enabled=peace_scope,
            world_score=score, world_score_enabled=score_enabled,
            archaeology=artifacts, archaeology_mode=artifact_mode, excavation_actions=excavations,
            unit_work=None if unit_work is None else unit_work[0],
            unit_work_state=None if unit_work is None else unit_work[1],
            unit_work_info=None if unit_work is None else unit_work[2], city_panels=city_panels,
            unit_panel_actions=panel_actions,
            great_people=people, great_people_mode=people_scope,
            great_person_activation=activation_state, great_person_activation_enabled=activation_scope,
            pantheon=pantheon_state, pantheon_enabled=pantheon_scope, governors=governor_state,
            governors_enabled=governor_scope, espionage=espionage_state,
            espionage_enabled=espionage_scope, spy_completion=completion_state,
            spy_completion_enabled=completion_scope, religion=religious, trade=trade_states,
            formations=formation_state, formation_enabled=formation_scope,
            dedications=dedication_state, dedication_enabled=dedication_scope, congress=congress)
    return result, identity, catalogue, effect


def collect(saved, player_id, *, include_wars=False):
    """Read a registered human view without submitting commands."""
    view, _, _, _ = _run(saved, player_id, include_wars=include_wars)
    return view


def unit_commands(saved, player_id):
    """Return the current Wake/Cancel offers from the selected seat's native UI."""
    view, identity, catalogue, _ = _run(saved, player_id, include_unit_commands=True)
    return dict(**view, decision=identity, actions=[] if catalogue is None else unit_order_actions(catalogue))


def execute_unit_command(saved, player_id, decision, action):
    """Deliver a selected ordinary unit command and report its observed effect."""
    validate_action(action)
    if action['route'] != 'command':
        raise ValueError('Only ordinary XP2 Wake and Cancel use this archive route')
    view, identity, _, effect = _run(saved, player_id, include_unit_commands=True,
                                     decision=(decision, action))
    if effect is None:
        raise ValueError('XP2 unit command was not offered for this seat at the current revision')
    status = 'completed' if unit_command_effect_observed(effect) else 'submitted_effect_unresolved'
    queue = {key: effect[key] for key in ('queued_destination_before', 'queued_destination_after')
             if key in effect}
    return dict(**view, decision=identity, new_sequence=saved.continuation.sequence,
                status=status, unit_before=effect['unit_before'], unit_after=effect['unit_after'],
                **queue)


def unit_command_effect_observed(effect):
    return (effect['state_changed'] or (effect.get('queued_destination_before') is not None
                                       and effect.get('queued_destination_after') is None))


def read_network_boundary(saved, player_id, action, *, expected_city_state=None, restore_envoys=None,
                          city_panel_groups=None, great_people_mode=None, great_person_activation_enabled=None,
                          pantheon_enabled=None,
                          governors_enabled=None, espionage_enabled=None, spy_completion_enabled=None,
                          religion_groups=None, trade_enabled=None, formation_enabled=None, dedication_enabled=None,
                          congress_mode=None, congress_sequence=None, congress_checkpoint=None,
                          unit_panel_families=None, city_state_peace_enabled=None, dialogue_sequence=None,
                          world_score_enabled=None, archaeology_mode=None):
    """Read or execute one qualified secondary LAN choice."""
    if action is not None:
        if restore_envoys is not None:
            raise ValueError('A live action cannot restore envoy consideration')
        kind = action.get('kind') if type(action) is dict else None
        if kind == 'found_city':
            from civ6_host.contracts.capability_choices import validate_founder_action
            validate_founder_action(action)
        elif kind in (*xp2_lan_research.KINDS, 'production'):
            from civ6_host.contracts.capability_choices import validate_action as validate_choice
            validate_choice(action)
        elif type(kind) is str and kind in xp2_lan_production_queue.FIELDS:
            from civ6_host.contracts.production_queue import validate_action as validate_queue
            validate_queue(action)
        elif type(kind) is str and kind in xp2_lan_city_controls.CATALOGUE_FIELDS:
            xp2_lan_city_controls.validate_action(action)
        elif type(kind) is str and kind in xp2_lan_world_input.WORLD_KINDS:
            from civ6_host.contracts.capability_world_input import validate_action as validate_world
            validate_world(action)
        elif kind == 'world_war_response':
            from civ6_host.contracts.xp2_war_confirmation import validate_action as validate_war

            validate_war(action)
        elif kind == 'diplomacy_response':
            if (set(action) != {'kind', 'session_id', 'statement_sequence', 'choice'}
                    or type(action['session_id']) is not int or not 0 < action['session_id'] <= 0xffffffff
                    or type(action['statement_sequence']) is not int
                    or not 0 < action['statement_sequence'] <= 0x7fffffff
                    or action['choice'] != 'CHOICE_EXIT'):
                raise ValueError('Invalid borrowed surprise-war response')
        elif kind == 'diplomacy_initiate' and xp2_lan_city_states.is_peace(action):
            from civ6_host.contracts.diplomacy_overview import validate_action as validate_diplomacy

            validate_diplomacy(action)
        elif kind == 'promote_unit':
            from civ6_host.contracts.unit_promotions import validate_action as validate_promotion
            validate_promotion(action)
        elif kind == 'upgrade_unit':
            from civ6_host.contracts.unit_upgrades import validate_action as validate_upgrade
            validate_upgrade(action)
        elif kind == 'unit_attack':
            from civ6_host.contracts.capability_unit_attacks import validate_action as validate_attack
            validate_attack(action)
        elif kind == OCCUPATION:
            from civ6_host.contracts.captured_city import validate_action as validate_occupation
            validate_occupation(action)
        elif kind == 'city_range_attack':
            from civ6_host.contracts.city_ranged import city_validate_action
            city_validate_action(action)
        elif kind == 'district_range_attack':
            from civ6_host.contracts.city_ranged import district_validate_action
            district_validate_action(action)
        elif kind == 'purchase':
            from civ6_host.contracts.plot_purchases import validate_purchase_action
            validate_purchase_action(action, allow_faith=True)
        elif type(kind) is str and kind in xp2_lan_government.FIELDS:
            xp2_lan_government.validate_action(action)
        elif type(kind) is str and kind in xp2_lan_city_states.FIELDS:
            xp2_lan_city_states.validate_action(action)
        elif type(kind) is str and kind in xp2_lan_great_people.KINDS:
            xp2_lan_great_people.validate_action(action)
        elif kind == ACTIVATE_PERSON:
            validate_activation(action)
        elif kind == pantheon.KIND:
            pantheon.validate_action(action)
        elif type(kind) is str and kind in governors.ACTION_FIELDS:
            governors.validate_action(action)
        elif type(kind) is str and kind in espionage.ACTION_FIELDS:
            espionage.validate_action(action)
        elif type(kind) is str and kind in spy_completion.ACTION_FIELDS:
            spy_completion.validate_action(action)
        elif type(kind) is str and kind in xp2_trade.FIELDS:
            xp2_trade.validate_action(action, expected_city_state)
        elif kind == unit_formations.KIND:
            unit_formations.validate_action(action)
        elif kind == city_buildings.GREAT_WORK_MOVE:
            city_buildings.validate_great_work_action(action)
        elif kind == dedications.KIND:
            dedications.validate_action(action)
        elif type(kind) is str and kind in xp2_lan_congress.ACTIONS:
            from civ6_host.contracts.world_congress import validate_action as validate_congress_action
            validate_congress_action(action)
        elif type(kind) is str and kind in xp2_lan_religion.FIELDS:
            xp2_lan_religion.validate_action(action)
        elif type(kind) is str and kind in xp2_lan_unit_work.KINDS:
            from civ6_host.contracts.unit_work import validate_action as validate_work
            validate_work(action)
        elif kind == air_operations.KIND:
            air_operations.validate(action)
        elif kind == work_contract.BUILD_ROUTE:
            work_contract.validate_route(action)
        elif kind == national_parks.DESIGNATE:
            national_parks.validate_designation(action)
        elif kind == rock_bands.KIND:
            rock_bands.validate_action(action)
        elif kind == archaeology.EXCAVATE:
            archaeology.validate_excavation(action)
        elif kind == archaeology.KIND:
            archaeology.validate_action(action)
        elif not (type(kind) is str and kind in network_turns.TURN_REQUESTS and set(action) == {'kind'}):
            validate_action(action)
    return _run(saved, player_id, include_unit_commands=True, network=True,
                expected_city_state=expected_city_state, restore_envoys=restore_envoys,
                city_panel_groups=city_panel_groups, great_people_mode=great_people_mode,
                great_person_activation_enabled=great_person_activation_enabled,
                pantheon_enabled=pantheon_enabled, governors_enabled=governors_enabled,
                espionage_enabled=espionage_enabled, spy_completion_enabled=spy_completion_enabled,
                religion_groups=religion_groups, trade_enabled=trade_enabled, formation_enabled=formation_enabled,
                dedication_enabled=dedication_enabled, congress_mode=congress_mode, congress_sequence=congress_sequence,
                congress_checkpoint=congress_checkpoint, unit_panel_families=unit_panel_families,
                city_state_peace_enabled=city_state_peace_enabled,
                world_score_enabled=world_score_enabled,
                archaeology_mode=archaeology_mode,
                dialogue_sequence=dialogue_sequence,
                decision=(_decision(saved, player_id), action) if action is not None else None)
