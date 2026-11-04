"""Explicit native choices on the saved Base path; no diagnostic policy fallback."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import copy, hashlib, json, time
from civ6_host.runtime.native.native_official_postload import validate_owner
from civ6_host.runtime.native import native_official_load as official
from civ6_host.runtime.native.native_player_observation import observe_player
from civ6_host.runtime.native.native_episode_identity import require_episode
from civ6_host.runtime.native import native_research_catalog as research
from civ6_host.runtime.native import native_saved_research_progress971 as research_progress
from civ6_host.runtime.native import native_saved_treasury980 as treasury
from civ6_host.runtime.native import native_saved_yield_display982 as yield_display
from civ6_host.runtime.native import native_saved_research_info983 as research_info
from civ6_host.runtime.native import native_saved_production_info988 as production_info
from civ6_host.runtime.native import native_production_catalog as production
from civ6_host.runtime.native import native_city_production_observation as queues
from civ6_host.runtime.native import native_saved_production_queue as production_queue
from civ6_host.runtime.native import native_saved_city_shot as city_shot
from civ6_host.runtime.native import native_saved_district_shot as district_shot
from civ6_host.runtime.native import native_saved_trade as trade
from civ6_host.runtime.native import native_saved_trade_origin as trade_origin
from civ6_host.runtime.native import native_unit_skip as skip
from civ6_host.runtime.native import native_policy_catalog as policies
from civ6_host.runtime.native import native_unit_movement as movement
from civ6_host.runtime.native import native_saved_placement as placed
from civ6_host.runtime.native import native_saved_combat as combat
from civ6_host.runtime.native import native_saved_minor_war as minor_war
from civ6_host.runtime.native import native_saved_government as government
from civ6_host.runtime.native import native_saved_pantheon as pantheon
from civ6_host.runtime.native import native_saved_purchases as purchases
from civ6_host.runtime.native import native_saved_city_focus1000 as city_focus
from civ6_host.runtime.native.native_ui_profile import gate_admitted
from civ6_host.runtime.native import native_saved_citizens as citizens
from civ6_host.runtime.native import native_saved_unit_work as unit_work
from civ6_host.runtime.native import native_saved_unit_orders as unit_orders
from civ6_host.runtime.native import native_saved_unit_upgrade as upgrades
from civ6_host.runtime.native import native_saved_promotions as promotions
from civ6_host.runtime.native import native_saved_envoys as envoys
from civ6_host.runtime.native import native_saved_envoy_panel as envoy_panel
from civ6_host.runtime.native import native_saved_great_people as great_people
from civ6_host.runtime.native import native_saved_religion as religion
from civ6_host.runtime.native import native_saved_player_map as player_map
from civ6_host.runtime.native import native_plot_display990 as plot_display
from civ6_host.runtime.native import native_saved_captured_city as captured_city
from civ6_host.runtime.native.native_unit_actions import found_city_catalog_source
from civ6_host.runtime.native.native_unit_actions import parse_founders
from civ6_host.runtime.native.native_turn_decisions import blocker_source
from civ6_host.runtime.native.native_turn_decisions import parse_blockers
from civ6_host.runtime.native.native_endturn_gate import gate_source
from civ6_host.runtime.native.native_endturn_gate import parse_gate
SCHEMA = 'civ6rl.saved_decisions999.v1'
FOCUS_SCHEMA = 'civ6rl.saved_decisions1000.v1'
MANAGEMENT_SCHEMA = 'civ6rl.saved_decisions.city_management.v1'

def movement_options(owner):
    enabled = getattr(owner, 'multiturn_movement_diagnostic', False)
    if type(enabled) is not bool:
        raise ValueError('Exact multi-turn diagnostic flag required')
    return dict(allow_multiturn=True) if enabled else {}

def plot_purchase_catalog_enabled(owner):
    diagnostic = getattr(owner, 'city_management_diagnostic', False)
    if type(diagnostic) is not bool:
        raise ValueError('Exact city-management diagnostic flag required')
    return diagnostic or gate_admitted(owner, 'plot_purchase')
GAPS = ('movement_outside_visible_empty_single_turn_profile', 'attacks_by_cities_districts_and_air_units', 'unit_city_attack_capture_full_game_qualification', 'attacks_requiring_war_declaration', 'nonadjacent_melee_attack_targets', 'melee_orders_when_ranged_is_also_legal', 'unit_orders_outside_move_attack_skip_and_terrain_work', 'terrain_work_tutorial_and_ui_mod_hooks', 'terrain_work_operations_without_native_positive_witness', 'placement_resume_and_repairs', 'hidden_placement_targets', 'preexisting_placement_observations', 'occupied_production_queue_editing', 'purchase_formations_districts_plots', 'government_anarchy_changes', 'paid_policy_changes', 'active_policy_relocation', 'religion_except_pantheon', 'great_people', 'envoys', 'diplomacy', 'other_civilizations_and_rulesets')

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def movement_action(choice):
    return dict(kind='move', **{k: choice[k] for k in movement._CHOICE_FIELDS}, moves_token=choice['moves_token'].decode('ascii'))

def validate_movement_action(action, player_id=0):
    if type(action) is not dict or set(action) != {'kind', 'moves_token', *movement._CHOICE_FIELDS} or action['kind'] != 'move' or (type(action['moves_token']) is not str) or (len(action['moves_token']) > 64):
        raise ValueError('Malformed movement action')
    token = action['moves_token'].encode('ascii')
    _, amount = movement._parse_movement(token)
    movement._validate_choice(dict(player_id=player_id, current_game_turn=0, **{k: action[k] for k in movement._CHOICE_FIELDS}, moves_token=token, moves_remaining=amount))
    return action

def _check_player_context(profile, stage, roster, player_id, player_ids):
    if profile is official.LAN_PROFILE:
        from civ6_host.runtime.network_owner import roster as validate_network_roster
        from civ6_host.runtime.network_owner import STAGE
        validate_network_roster(player_ids)
        if stage != STAGE or player_ids != roster or type(player_id) is not int or (player_id not in roster):
            raise RuntimeError('LAN decisions require the exact admitted roster and boundary')
        return player_id
    if type(player_id) is not int or type(player_ids) is not tuple or (not player_ids) or any((type(pid) is not int or not 0 <= pid <= 63 for pid in player_ids)) or (len(set(player_ids)) != len(player_ids)) or (player_id not in player_ids):
        raise ValueError('Invalid explicit actor or player roster')
    if player_id not in roster:
        raise RuntimeError('Requested actor is absent from the loaded native roster')
    if profile is official.HOTSEAT_FOUR_PROFILE:
        if stage != 'official-hotseat-decision-ready' or player_ids != (0, 1, 2, 3) or roster != (0, 1, 2, 3):
            raise RuntimeError('Four-player decisions require the exact Hotseat roster and ready boundary')
    elif profile is official.HOTSEAT_PROFILE:
        if stage not in ('official-public-observed-awaiting-controlled-stop', 'official-turn-observed-awaiting-controlled-stop') or roster != (0, 1) or player_ids != (0, 1):
            raise RuntimeError('Two-player decisions require the exact loaded Hotseat roster')
    elif profile is official.SINGLE_PROFILE:
        if stage not in ('official-public-observed-awaiting-controlled-stop', 'official-turn-observed-awaiting-controlled-stop') or roster != (0, 1) or player_ids != (0, 1) or (player_id != 0):
            raise RuntimeError('Single-player decisions require the exact loaded roster')
    else:
        raise RuntimeError('Explicit actions require an admitted official save profile')
    return player_id

def boundary(owner, *, player_id=0, player_ids=(0, 1)):
    stage = owner.stage
    validate_owner(owner, stage=stage)
    loaded = owner.loaded_roster
    if type(loaded) is not bytes or len(loaded) > 256:
        raise RuntimeError('Loaded native player roster is unavailable')
    try:
        values = tuple(map(int, loaded.decode('ascii').split('|')))
    except (UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError('Loaded native player roster is malformed') from exc
    if len(values) < 4:
        raise RuntimeError('Loaded native player roster is incomplete')
    _check_player_context(owner.inputs.profile, stage, values[3:], player_id, player_ids)
    if owner.inputs.profile is official.HOTSEAT_FOUR_PROFILE:
        if getattr(owner, 'hotseat_actor', None) != player_id:
            raise RuntimeError('Requested actor differs from the prepared Hotseat actor')
        if type(getattr(owner, 'hotseat_turn', None)) is not int:
            raise RuntimeError('Prepared Hotseat turn is unavailable')
    if owner.inputs.profile is official.LAN_PROFILE:
        from civ6_host.runtime.network_owner import require_actor
        require_actor(owner, player_id, player_ids)
    return owner.prefix

def snapshot(owner, phase):
    """Enter the existing exclusive observer contract on the owning thread."""
    owner.check_thread()
    if owner.busy:
        raise RuntimeError('Explicit snapshot cannot enter a busy owner')
    owner.busy = True
    try:
        return owner.jobs_snapshot(phase)
    finally:
        owner.busy = False

def skip_catalog_source(player_id=0, player_ids=(0, 1)):
    if type(player_id) is not int or type(player_ids) is not tuple or (not player_ids) or any((type(pid) is not int or not 0 <= pid <= 63 for pid in player_ids)) or (len(set(player_ids)) != len(player_ids)) or (player_id not in player_ids):
        raise ValueError('Invalid skip actor or roster')
    skip.verify_source()
    return b'local pid=' + str(player_id).encode('ascii') + b"\nassert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid,'skip perspective changed')\nlocal p=Players[pid]\nassert(p and p:IsAlive()==true and p:IsTurnActive()==true and p:IsTurnActiveComplete()==true,'not ready')\nlocal ids,seen,count,ready={}, {},0,0\nfor _,u in p:GetUnits():Members() do\n count=count+1;assert(count<=4096 and u:GetOwner()==pid,'unbounded or foreign unit collection')\n local id=u:GetID();assert(type(id)=='number' and id%1==0 and id>=0 and id<=4294967295 and not seen[id],'unit ID')\n seen[id]=true\n local r=u:IsReadyToSelect();assert(type(r)=='boolean','readiness type')\n if r then\n  ready=ready+1\n  local can=UnitManager.CanStartOperation(u,'UNITOPERATION_SKIP_TURN',nil,false)\n  assert(type(can)=='boolean','skip legality type')\n  if can then ids[#ids+1]=id end\n end\nend\ntable.sort(ids)\nlocal out={string.format('%d',Game.GetCurrentGameTurn()),string.format('%d',ready)}\nfor _,id in ipairs(ids) do out[#out+1]=string.format('%.0f',id) end\nreturn table.concat(out,'|')\n"

def parse_skips(raw, turn):
    if type(raw) is not bytes or len(raw) > 65536:
        raise ValueError('Skip catalogue exceeds bound')
    parts = raw.split(b'|')
    if len(parts) < 2 or any((not p.isdigit() or str(int(p)).encode() != p for p in parts)):
        raise ValueError('Malformed skip catalogue')
    actual, ready, *ids = map(int, parts)
    if actual != turn or not len(ids) <= ready <= 4096 or ids != sorted(set(ids)) or any((i > 4294967295 for i in ids)):
        raise ValueError('Foreign or unbounded skip catalogue')
    return (ready, ids)

def _read_decisions_without_context(owner, sequence, rounds, *, closed=False, round_limit=8, player_id=0, player_ids=(0, 1)):
    if getattr(owner, 'turn_continuation', None) is not None:
        from civ6_host.runtime.native.native_diplomacy_choices import read
        if player_id != 0:
            raise ValueError('Interrupted Single turn belongs to player0')
        return read(owner, sequence, closed=closed)
    from civ6_host.runtime.native.native_pending_diplomacy import require_no_unhandled_statements
    require_no_unhandled_statements(owner.prefix)
    from civ6_host.runtime.native.native_saved_session_protocol import MAX_EXPLICIT_ROUNDS
    if type(round_limit) is not int or not 1 <= round_limit <= MAX_EXPLICIT_ROUNDS or type(rounds) is not int or (not 0 <= rounds <= round_limit):
        raise ValueError('Invalid explicit decision round budget')
    p = boundary(owner, player_id=player_id, player_ids=player_ids)
    pid = player_id
    phase_started = time.perf_counter()
    obs = observe_player(p.runtime, p.ui_child, pid)
    turn = obs['turn']
    observation_seconds = time.perf_counter() - phase_started
    if hasattr(owner, 'emit'):
        owner.emit('native_reset_timing', phase='decision_player_observation_seconds', elapsed_seconds=observation_seconds, timing_scope='non-overlapping stage', strategic_training_ready=False)
    if type(obs) is not dict or type(obs.get('player_id')) is not int or obs['player_id'] != pid:
        raise RuntimeError('Fresh observation belongs to another actor')
    if getattr(getattr(owner, 'inputs', None), 'profile', None) is official.HOTSEAT_FOUR_PROFILE and (owner.hotseat_actor != pid or owner.hotseat_turn != turn):
        raise RuntimeError('Fresh observation differs from the prepared Hotseat actor or turn')
    initial_jobs = snapshot(owner, 'before')
    phase_started = time.perf_counter()
    map_observation = player_map.observe(p, obs)
    plot_details = plot_display.observe(p, obs)

    def query(source, name, capacity=131072):
        return p.runtime.evaluate_text(p.ui_child, source, name, capacity=capacity)
    actions = []
    raw_catalogs = {}
    research_state = {}
    purchase_catalogs = []
    production_queues = []
    placement_offers = []
    focus_enabled = getattr(owner, 'city_focus_diagnostic', False)
    if type(focus_enabled) is not bool:
        raise ValueError('Exact city-focus diagnostic flag required')
    management_enabled = getattr(owner, 'city_management_diagnostic', False)
    if type(management_enabled) is not bool or (management_enabled and (not focus_enabled)):
        raise ValueError('City-management diagnostic requires the complete city control group')
    focus_enabled = focus_enabled or gate_admitted(owner, 'city_focus')
    management_enabled = management_enabled or gate_admitted(owner, 'city_citizens')
    citizen_catalogs = []
    focus_catalogs = []
    captured_catalog = captured_city.catalog(p, turn, player_id=pid)
    raw_catalogs['captured_city'] = captured_catalog
    actions.extend(captured_city.actions(captured_catalog))
    blockers = parse_blockers(query(blocker_source(pid, player_ids=player_ids), b'@explicit_blockers'), pid, turn, player_ids=player_ids)
    ready, skips = parse_skips(query(skip_catalog_source(pid, player_ids), b'@explicit_skip_catalog'), turn)
    for kind in ('research', 'civic'):
        catalog = research.parse_catalog(query(research.catalog_source(pid, kind, turn), b'@explicit_research_catalog'), pid, kind, turn)
        raw_catalogs[kind] = catalog
        from civ6_host.runtime.native.native_research_actions import effect_source
        from civ6_host.runtime.native.native_research_actions import parse_effect
        selected = parse_effect(query(effect_source(pid, kind, 0), b'@explicit_current_research'), pid, kind, 0, turn)
        research_state[kind] = selected['observed_index']
        actions.extend((dict(kind=kind, index=r['index'], hash=r['hash']) for r in catalog['choices']))
    research_details = research_progress.observe(p, pid, turn, research_state)
    raw_catalogs['research_progress'] = research_details
    research_ui = research_info.observe(p, pid, turn, research_state, {kind: raw_catalogs[kind]['choices'] for kind in ('research', 'civic')})
    raw_catalogs['research_info'] = research_ui
    treasury_details = treasury.observe(p, pid, turn, gold_balance=obs['economy']['gold'])
    raw_catalogs['treasury'] = treasury_details
    yield_details = yield_display.observe(p, obs)
    raw_catalogs['yield_display'] = yield_details
    queue = queues.parse_production_snapshot(query(queues.production_snapshot_source(pid), b'@explicit_queue_snapshot'), pid)
    if queue['game_turn'] != turn:
        raise RuntimeError('Queue observation crossed turns')
    shot_catalog = city_shot.catalog(p, turn, player_id=pid)
    city_shot.compare_own_cities(shot_catalog, obs)
    raw_catalogs['city_shots'] = shot_catalog
    actions.extend(city_shot.actions(shot_catalog))
    district_catalog = district_shot.catalog(p, turn, player_id=pid)
    district_shot.compare_own_cities(district_catalog, obs)
    raw_catalogs['district_shots'] = district_catalog
    actions.extend(district_shot.actions(district_catalog))
    trade_catalog = trade.catalog(p, turn, player_id=pid)
    trade.compare_own(trade_catalog, obs)
    raw_catalogs['trade_routes'] = trade_catalog
    actions.extend(trade.actions(trade_catalog))
    origin_catalog = trade_origin.catalog(p, turn, player_id=pid)
    trade_origin.compare_own(origin_catalog, obs)
    raw_catalogs['trade_origins'] = origin_catalog
    actions.extend(trade_origin.actions(origin_catalog))
    policy_catalog = policies.parse_catalog(query(policies.catalog_source(pid, turn), b'@explicit_policy_catalog', capacity=524289), pid, turn)
    raw_catalogs['policies'] = policy_catalog
    government_catalog = government.catalog(p, turn, player_id=pid)
    raw_catalogs['government'] = government_catalog
    actions.extend(government.actions(government_catalog))
    pantheon_catalog = pantheon.catalog(p, turn, player_id=pid)
    raw_catalogs['pantheon'] = pantheon_catalog
    actions.extend(pantheon.actions(pantheon_catalog))
    envoy_catalog = envoys.catalog(p, turn, player_id=pid)
    raw_catalogs['envoys'] = envoy_catalog
    actions.extend(envoys.actions(envoy_catalog))
    panel_catalog = envoy_panel.catalog(p, turn, player_id=pid)
    raw_catalogs['envoy_panel'] = panel_catalog
    actions.extend(envoy_panel.actions(panel_catalog, envoy_catalog))
    religion_catalog = religion.catalog(p, turn, player_id=pid)
    raw_catalogs['religion'] = religion_catalog
    actions.extend(religion.actions(religion_catalog))
    great_people_catalog = great_people.catalog(p, turn, player_id=pid)
    raw_catalogs['great_people'] = great_people_catalog
    actions.extend(great_people.actions(great_people_catalog))
    if policy_catalog['reason'] == 'available' and policies.can_change(policy_catalog['slots']):
        actions.append(dict(kind='policies', slots=policy_catalog['slots']))
    for city in obs['cities']:
        if management_enabled:
            citizen_catalog = citizens.catalog(p, city['id'], turn, player_id=pid, diagnostic_ui_enabled=True)
            citizen_catalogs.append(citizen_catalog)
            raw_catalogs['citizens-' + str(city['id'])] = citizen_catalog
            actions.extend(citizens.actions(citizen_catalog))
        if focus_enabled:
            focus = city_focus.catalog(p, city['id'], turn, player_id=pid, diagnostic_ui_enabled=True)
            focus_catalogs.append(focus)
            raw_catalogs['city-focus-' + str(city['id'])] = focus
            actions.extend(city_focus.actions(focus))
        queue_catalog = production_queue.catalog(p, city['id'], turn, player_id=pid, enabled=getattr(owner, 'production_queue_diagnostic', False) or gate_admitted(owner, 'production_queue'))
        production_queues.append(queue_catalog)
        raw_catalogs['queue-' + str(city['id'])] = queue_catalog
        actions.extend(production_queue.actions(queue_catalog))
        purchase_catalog = purchases.catalog(p, city['id'], turn, player_id=pid, include_plots=plot_purchase_catalog_enabled(owner))
        purchase_catalogs.append(purchase_catalog)
        raw_catalogs['purchases-' + str(city['id'])] = purchase_catalog
        actions.extend(purchases.actions(purchase_catalog))
        catalog = production.parse_catalog(query(production.catalog_source(pid, city['id'], turn, replace_current=True), b'@explicit_production_catalog'), pid, city['id'], turn)
        raw_catalogs['production-' + str(city['id'])] = catalog
        actions.extend((dict(kind='production', city_id=city['id'], category=r['kind'], index=r['index'], hash=r['hash'], item_type=r['item_type']) for r in catalog['candidates']))
        placement_catalog = placed.catalog(p, city['id'], turn, player_id=pid)
        if (placement_catalog['width'], placement_catalog['height']) != (obs['width'], obs['height']):
            raise RuntimeError('Placement catalogue map differs from published observation')
        raw_catalogs['placement-' + str(city['id'])] = placement_catalog
        offers = placed.actions(placement_catalog, city['id'], player_id=pid)
        placement_offers.extend(offers)
        actions.extend(offers)
    work_catalog = _unit_panel_work_catalog(owner, p, turn, player_id=pid)
    raw_catalogs['unit_work'] = work_catalog
    actions.extend(unit_work.actions(work_catalog))
    cancel_orders = _action_feature_enabled(owner, 'unit_order_cancel')
    if type(cancel_orders) is not bool:
        raise ValueError('Exact unit cancel flag required')
    order_catalog = unit_orders.catalog(p, turn, player_id=pid, **dict(include_cancel=True) if cancel_orders else {})
    raw_catalogs['unit_orders'] = order_catalog
    actions.extend(unit_orders.actions(order_catalog))
    upgrade_catalog = upgrades.catalog(p, turn, player_id=pid)
    raw_catalogs['unit_upgrades'] = upgrade_catalog
    actions.extend(upgrades.actions(upgrade_catalog))
    promotion_catalog = promotions.catalog(p, turn, player_id=pid)
    raw_catalogs['unit_promotions'] = promotion_catalog
    actions.extend(promotion_catalog['offers'])
    actions.extend(parse_founders(query(found_city_catalog_source(pid, turn), b'@explicit_found_city_catalog'), pid, turn))
    movement_information = getattr(owner, 'movement_information_diagnostic', False)
    if type(movement_information) is not bool:
        raise ValueError('Exact movement information flag required')
    preview_options = dict(include_preview=True) if movement_information else {}
    moves = movement.parse_candidates(query(movement.candidate_source(pid, turn, allow_improvements=True, allow_own_cities=True, **movement_options(owner), **preview_options), b'@explicit_movement_catalog', capacity=8 * 1024 * 1024 + 1 if movement_information else 524289), pid, turn, **preview_options)
    if movement_information:
        moves, movement_preview = moves
    move_actions = [movement_action(row) for row in moves['choices']]
    raw_catalogs['movement'] = move_actions
    actions.extend(move_actions)
    world_enabled = _action_feature_enabled(owner, 'world_input')
    if type(world_enabled) is not bool:
        raise ValueError('Exact world-input diagnostic flag required')
    world_state = None
    if world_enabled:
        from civ6_host.runtime.native import native_world_input as world
        world_state = world.observe(owner, obs)
        actions.extend(world.actions(world_state))
    attacks = combat.catalog(p, turn, obs, player_id=pid)
    if (attacks['width'], attacks['height']) != (obs['width'], obs['height']):
        raise RuntimeError('Combat catalogue map differs from observation')
    raw_catalogs['combat'] = attacks
    actions.extend(combat.orders(attacks, player_id=pid))
    combat_units = combat.unit_state(p, turn, obs, player_id=pid)
    queued_orders = combat.queued_orders(p, obs, player_id=pid)
    raw_catalogs['queued_orders'] = queued_orders
    wars = minor_war.catalog(p, turn, player_id=pid)
    raw_catalogs['minor_wars'] = wars
    actions.extend(wars['candidates'])
    actions.extend((dict(kind='skip_unit', unit_id=uid) for uid in skips))
    if not blockers['all'] and (not blockers['has_primary_blocker']) and (ready == 0) and (rounds < round_limit):
        from civ6_host.runtime.native import native_city_range_attack as attack
        status = attack.parse_notification_status(query(attack.notification_status_source(pid), b'@explicit_city_attack_status'), player_id=pid, turn=turn)
        if status in ('none', 'dismissed'):
            gate = parse_gate(query(gate_source(pid, player_ids=player_ids), b'@explicit_endturn_gate'), pid, turn, player_ids=player_ids)
            actions.append(dict(kind='end_turn'))
    force_ui_admitted = gate_admitted(owner, 'force_end_turn')
    if force_ui_admitted and owner.inputs.profile is not official.HOTSEAT_FOUR_PROFILE:
        raise RuntimeError('UI-profile forced EndTurn is restricted to four-player Hotseat')
    if getattr(owner, 'forced_endturn_diagnostic', False) is True or force_ui_admitted:
        if owner.inputs.profile not in (official.SINGLE_PROFILE, official.HOTSEAT_FOUR_PROFILE):
            raise RuntimeError('Forced EndTurn requires an admitted native profile')
        actions.append(dict(kind='force_end_turn'))
    production_details = production_info.observe(p, obs, actions)
    raw_catalogs['production_info'] = production_details
    if closed or rounds == round_limit:
        actions = []
        if movement_information:
            movement_preview = dict(movement_preview, routes=[])
    from civ6_host.contracts.action_budget import validate_action_count
    validate_action_count(actions, world_input=world_state, map_coordinates=owner.inputs.profile is official.LAN_PROFILE)
    candidates = [dict(candidate_id=digest(action), action=action) for action in actions]
    if len({r['candidate_id'] for r in candidates}) != len(candidates):
        raise RuntimeError('Duplicate action identity')
    identity = require_episode(p)
    result = dict(schema=MANAGEMENT_SCHEMA if management_enabled else FOCUS_SCHEMA if focus_enabled else SCHEMA, episode_id=identity.episode_id, game_generation=identity.game_generation, sequence=sequence, player_id=pid, turn=turn, player_map=map_observation, candidates=candidates, blockers=blockers, production=queue, production_queues=production_queues, city_shots=shot_catalog, district_shots=district_catalog, trade_routes=trade_catalog, trade_origins=origin_catalog, research=research_state, policies=policy_catalog, government=government_catalog, unit_orders=order_catalog, unit_upgrades=upgrade_catalog, pantheon=pantheon_catalog, envoys=envoy_catalog, envoy_panel=panel_catalog, great_people=great_people_catalog, religion=religion_catalog, purchases=purchase_catalogs, unit_work=work_catalog, unit_promotions=promotion_catalog, placements=placed.progress(owner, p, turn, player_id=pid), placement_offers=placement_offers, combat_units=combat_units, queued_orders=queued_orders, combat_cities=attacks['cities'], combat_relationships=attacks['relationships'], captured_city=captured_catalog, ready_units=ready, unsupported=list(GAPS), complete_action_space=False)
    result['research_progress'] = research_details
    result['treasury'] = treasury_details
    result['yield_display'] = yield_details
    result['research_info'] = research_ui
    result['production_info'] = production_details
    result['plot_info'] = plot_details
    if focus_enabled:
        result['city_focus_catalogs'] = focus_catalogs
    if management_enabled:
        result['citizen_catalogs'] = citizen_catalogs
    if movement_information:
        from civ6_host.runtime.native.native_movement_preview import validate_and_index
        validate_and_index(movement_preview, obs, candidates)
        result['movement_preview'] = movement_preview
    if world_enabled:
        world.validate_candidates(world_state, candidates, closed=closed or rounds == round_limit)
        result['world_input'] = world_state
        owner.explicit_world_input = copy.deepcopy(world_state)
    result['decision_id'] = digest(result)
    owner.control(empty=True)
    if snapshot(owner, 'after') != initial_jobs:
        raise RuntimeError('Decision readers changed the scheduler')
    owner.explicit_observation = copy.deepcopy(obs)
    owner.explicit_decision_player_id = pid
    owner.explicit_decision_candidates = copy.deepcopy(candidates)
    owner.explicit_combat_units = copy.deepcopy(combat_units)
    owner.explicit_combat_cities = copy.deepcopy(attacks['cities'])
    owner.explicit_government = copy.deepcopy(government_catalog)
    owner.explicit_pantheon = copy.deepcopy(pantheon_catalog)
    owner.explicit_promotions = copy.deepcopy(promotion_catalog)
    owner.explicit_unit_orders = copy.deepcopy(order_catalog)
    owner.explicit_unit_upgrades = copy.deepcopy(upgrade_catalog)
    owner.explicit_production_snapshot = copy.deepcopy(queue)
    owner.explicit_production_queues = copy.deepcopy(production_queues)
    owner.explicit_city_shots = copy.deepcopy(shot_catalog)
    owner.explicit_district_shots = copy.deepcopy(district_catalog)
    owner.explicit_trade_routes = copy.deepcopy(trade_catalog)
    owner.explicit_trade_origins = copy.deepcopy(origin_catalog)
    owner.explicit_envoys = copy.deepcopy(envoy_catalog)
    owner.explicit_envoy_panel = copy.deepcopy(panel_catalog)
    owner.explicit_great_people = copy.deepcopy(great_people_catalog)
    owner.explicit_religion = copy.deepcopy(religion_catalog)
    owner.explicit_captured_city = copy.deepcopy(captured_catalog)
    event_stage = 'official-hotseat-decision-ready' if owner.inputs.profile is official.HOTSEAT_FOUR_PROFILE else 'official_explicit_decisions_observed'
    if hasattr(owner, 'emit'):
        owner.emit('native_reset_timing', phase='decision_catalog_and_menu_seconds', elapsed_seconds=time.perf_counter() - phase_started, timing_scope='non-overlapping stage; excludes player observation and event serialization', strategic_training_ready=False)
    owner.emit(event_stage, decisions=result, native_catalogs=raw_catalogs, observation=obs, player_id=pid, automatic_choices_applied=False, strategic_training_ready=False)
    return (obs, result)

def _apply_choice_without_context(owner, action, turn, *, player_id=0, player_ids=(0, 1)):
    if getattr(owner, 'turn_continuation', None) is not None:
        from civ6_host.runtime.native.native_diplomacy_choices import apply
        if player_id != 0 or action.get('kind') != 'diplomacy_response':
            raise ValueError('Only the pending explicit response is allowed')
        return apply(owner, action)
    p = boundary(owner, player_id=player_id, player_ids=player_ids)
    pid = player_id
    current = observe_player(p.runtime, p.ui_child, pid)
    if current.get('player_id') != pid or type(current.get('player_id')) is not int or current['turn'] != turn:
        raise RuntimeError('Action turn or actor became stale')
    if getattr(getattr(owner, 'inputs', None), 'profile', None) is official.HOTSEAT_FOUR_PROFILE and (owner.hotseat_actor != pid or owner.hotseat_turn != turn):
        raise RuntimeError('Action differs from the prepared Hotseat actor or turn')
    if current != getattr(owner, 'explicit_observation', None):
        raise RuntimeError('Published decision state changed before action')
    if _action_feature_enabled(owner, 'world_input'):
        from civ6_host.runtime.native import native_world_input as world
        state = getattr(owner, 'explicit_world_input', None)
        if state is None or not world.permitted(state, action):
            raise ValueError('Pending world-input popup blocks this action')
    if getattr(getattr(owner, 'inputs', None), 'profile', None) in (official.HOTSEAT_FOUR_PROFILE, official.LAN_PROFILE):
        offers = [row['action'] for row in getattr(owner, 'explicit_decision_candidates', [])]
        admitted = action in offers
        if action.get('kind') == 'policies':
            offer = [row for row in offers if row['kind'] == 'policies']
            candidate = action.get('candidate', {})
            admitted = len(offer) == 1 and candidate.get('player_id') == pid and (candidate == policies.choose(offer[0]['slots'], [h & 4294967295 for _, h in candidate.get('assignments', [])], pid, turn))
        if getattr(owner, 'explicit_decision_player_id', None) != pid or not admitted:
            raise RuntimeError('Action does not belong to the current actor decision digest')
    kind = action['kind']
    before = snapshot(owner, 'before')
    owner.emit('before_official_explicit_action', action=action, player_id=pid, turn=turn, jobs_before=before, automatic_choices_applied=False, strategic_training_ready=False)
    if kind.startswith('world_'):
        if _action_feature_enabled(owner, 'world_input') is not True:
            raise ValueError('World input requires explicit diagnostic admission')
        from civ6_host.runtime.native.native_world_input import apply as apply_world_input
        after = apply_world_input(owner, action, turn, current)
    elif kind == 'found_city':
        catalog = parse_founders(p.runtime.evaluate_text(p.ui_child, found_city_catalog_source(pid, turn), b'@explicit_found_city_revalidation'), pid, turn)
        if action not in catalog:
            raise RuntimeError('Selected foundation is no longer legal')
        effect = p.inspect_found_city(pid, unit_id=action['unit_id'], expected_x=action['x'], expected_y=action['y'])
        after = observe_player(p.runtime, p.ui_child, pid)
        old_units = {u['id'] for u in current['units']}
        new_units = {u['id'] for u in after['units']}
        old_cities = {c['id'] for c in current['cities']}
        new_cities = {c['id'] for c in after['cities']}
        if after['turn'] != turn or action['unit_id'] not in old_units or new_units != old_units - {action['unit_id']} or (new_cities != old_cities | {effect['city_id']}) or (effect['city_id'] in old_cities) or ((effect['consumed_unit_id'], effect['x'], effect['y']) != (action['unit_id'], action['x'], action['y'])) or (not any((c['id'] == effect['city_id'] and (c['x'], c['y']) == (action['x'], action['y']) for c in after['cities']))):
            raise RuntimeError('Selected foundation effect differs from current state')
        owner.official_city_attempted = True
        owner.emit('official_explicit_found_city_effect', action=action, effect=effect, observation_before=current, observation_after=after, automatic_choices_applied=False)
    elif kind == 'move':
        validate_movement_action(action, pid)
        move_options = movement_options(owner)
        catalog = movement.parse_candidates(p.runtime.evaluate_text(p.ui_child, movement.candidate_source(pid, turn, allow_improvements=True, allow_own_cities=True, **move_options), b'@explicit_movement_revalidation', capacity=524289), pid, turn)
        choice = movement.choose(catalog, action['unit_id'], action['destination_plot_id'])
        if movement_action(choice) != action:
            raise RuntimeError('Movement source or remaining moves changed')
        effect = p.inspect_unit_movement(pid, unit_id=action['unit_id'], destination_plot_id=action['destination_plot_id'], allow_improvements=True, allow_own_cities=True, **move_options)
        after = observe_player(p.runtime, p.ui_child, pid)
        moved = [u for u in after['units'] if u['id'] == action['unit_id']]
        partial = bool(move_options) and effect.get('multi_turn_order_verified') is True
        expected_xy = (action['destination_x'], action['destination_y'])
        if partial:
            plot = effect.get('actual_plot_id')
            if type(plot) is not int or not 0 <= plot < after['width'] * after['height'] or effect.get('retained_target_plot_id') != action['destination_plot_id'] or effect['at_destination']:
                raise RuntimeError('Multi-turn movement receipt differs')
            expected_xy = (plot % after['width'], plot // after['width'])
        if after['turn'] != turn or len(moved) != 1 or (not partial and (not effect['at_destination'])) or ((moved[0]['x'], moved[0]['y']) != expected_xy) or (moved[0]['moves'] != effect['moves_remaining']):
            raise RuntimeError('Movement public effect differs')
        owner.emit('official_explicit_movement_effect', action=action, effect=effect, observation_before=current, observation_after=after, automatic_choices_applied=False)
    elif kind == 'city_citizen':
        if getattr(owner, 'city_management_diagnostic', False) is not True and (not gate_admitted(owner, 'city_citizens')):
            raise ValueError('City management requires an admitted UI profile or explicit diagnostic')
        after = citizens.apply(owner, p, action, turn, current, player_id=pid, diagnostic_ui_enabled=True)
    elif kind == 'city_focus':
        if getattr(owner, 'city_focus_diagnostic', False) is not True and (not gate_admitted(owner, 'city_focus')):
            raise RuntimeError('City-focus tutorial gate remains unqualified; explicit diagnostic required')
        after = city_focus.apply(owner, p, action, turn, current, player_id=pid, diagnostic_ui_enabled=True)
    elif kind == 'unit_attack':
        after = combat.apply(owner, p, action, turn, current, player_id=pid)
    elif kind == 'declare_war_minor':
        after = minor_war.apply(owner, p, action, turn, current, player_id=pid)
    elif kind in ('government', 'retain_government'):
        after = government.apply(owner, p, action, turn, current, player_id=pid)
    elif kind == 'pantheon':
        after = pantheon.apply(owner, p, action, turn, current, player_id=pid)
    elif kind == 'promote_unit':
        after = promotions.apply(owner, p, action, turn, current, player_id=pid)
    elif kind in ('send_envoy', 'retain_envoys'):
        after = envoys.apply(owner, p, action, turn, current, player_id=pid)
    elif kind == 'upgrade_unit':
        after = upgrades.apply(owner, p, action, turn, current, player_id=pid)
    elif kind == 'unit_order':
        after = unit_orders.apply(owner, p, action, turn, current, player_id=pid)
    elif kind == 'review_envoys':
        after = envoy_panel.apply(owner, p, action, turn, current, player_id=pid)
    elif kind == 'recruit_great_person':
        after = great_people.apply(owner, p, action, turn, current, player_id=pid)
    elif kind in religion.FIELDS:
        after = religion.apply(owner, p, action, turn, current, player_id=pid)
    elif kind == 'purchase':
        after = purchases.apply(owner, p, action, turn, current, player_id=pid)
    elif kind in production_queue.FIELDS:
        after = production_queue.apply(owner, p, action, turn, current, player_id=pid)
    elif kind == 'city_range_attack':
        after = city_shot.apply(owner, p, action, turn, current, player_id=pid)
    elif kind == 'district_range_attack':
        after = district_shot.apply(owner, p, action, turn, current, player_id=pid)
    elif kind == 'make_trade_route':
        after = trade.apply(owner, p, action, turn, current, player_id=pid)
    elif kind == 'change_trade_origin':
        after = trade_origin.apply(owner, p, action, turn, current, player_id=pid)
    elif kind == 'resolve_captured_city':
        after = captured_city.apply(owner, p, action, turn, current, player_id=pid)
    elif kind in ('build_improvement', 'terrain_operation'):
        after = _apply_unit_panel_terrain(owner, p, action, turn, current, player_id=pid)
    elif kind in ('research', 'civic'):
        raw = p.runtime.evaluate_text(p.ui_child, research.catalog_source(pid, kind, turn), b'@explicit_research_revalidation')
        chosen = research.choose(research.parse_catalog(raw, pid, kind, turn), action['index'])
        if chosen['selected_hash'] != action['hash']:
            raise RuntimeError('Research catalogue identity changed')
        p.inspect_player_research_choice(pid, kind, selected_index=action['index'])
        after = observe_player(p.runtime, p.ui_child, pid)
    elif kind == 'production':
        from civ6_host.runtime.explicit_production_operation import apply as apply_production
        after = apply_production(owner, p, action, turn, player_id=pid)
    elif kind in ('production_placement', 'production_resume'):
        from civ6_host.runtime.explicit_production_operation import apply_placement
        after = apply_placement(owner, p, action, turn, current, player_id=pid)
    elif kind == 'policies':
        from civ6_host.runtime.native import native_policy_actions as native
        expected = action['candidate']
        raw = p.runtime.evaluate_text(p.ui_child, policies.catalog_source(pid, turn), b'@explicit_policy_revalidation', capacity=524289)
        catalog = policies.parse_catalog(raw, pid, turn)
        if catalog['reason'] != 'available':
            raise RuntimeError('Free policy window closed since selection')
        chosen = policies.choose(catalog['slots'], [h & 4294967295 for _, h in expected['assignments']], pid, turn)
        if chosen != expected:
            raise RuntimeError('Policy occupants or assignment changed since selection')
        accepted = native.parse_request_result(p.runtime.evaluate_text(p.ui_child, native.request_source(pid, chosen), b'@explicit_policy_request'), pid, turn, chosen['slot_count'])
        if len(p.actions.pending) != 1:
            raise RuntimeError('Expected one native policy request')
        owner.emit('official_explicit_policy_request_accepted', choice=chosen, accepted=accepted, native_catalog=catalog, action_applied=False)
        p.actions.deliver_one()
        p.deferred_events.drain_empty_receivers()
        p.view_publisher.publish()
        effect = native.parse_effect(p.runtime.evaluate_text(p.ui_child, native.effect_source(pid, chosen), b'@explicit_policy_effect'), pid, chosen, turn)
        owner.emit('official_explicit_policy_effect', choice=chosen, effect=effect, automatic_choices_applied=False)
        after = observe_player(p.runtime, p.ui_child, pid)
    elif kind == 'skip_unit':
        uid = action['unit_id']
        submitted = p.runtime.evaluate_text(p.ui_child, skip.request_source(pid, uid, player_ids=player_ids), b'@explicit_skip_request')
        if submitted != b'submitted' or len(p.actions.pending) != 1:
            raise RuntimeError('Expected one native skip request')
        p.actions.deliver_one()
        p.deferred_events.drain_empty_receivers()
        p.view_publisher.publish()
        effect = skip.parse_effect(p.runtime.evaluate_text(p.ui_child, skip.effect_source(pid, uid, player_ids=player_ids), b'@explicit_skip_effect'), uid)
        if effect['ready'] is not False or effect['first_ready_id'] == uid:
            raise RuntimeError('Native skip effect absent')
        owner.emit('official_explicit_skip_effect', unit_id=uid, effect=effect)
        after = observe_player(p.runtime, p.ui_child, pid)
    elif kind in ('end_turn', 'force_end_turn'):
        force_ui_admitted = gate_admitted(owner, 'force_end_turn')
        if kind == 'force_end_turn' and force_ui_admitted and (owner.inputs.profile is not official.HOTSEAT_FOUR_PROFILE):
            raise RuntimeError('UI-profile forced EndTurn is restricted to four-player Hotseat')
        if kind == 'force_end_turn' and getattr(owner, 'forced_endturn_diagnostic', False) is not True and (not force_ui_admitted):
            raise RuntimeError('Forced EndTurn is restricted to the explicit diagnostic')
        if owner.inputs.profile is official.HOTSEAT_FOUR_PROFILE:
            from civ6_host.runtime.native.native_official_hotseat import run_explicit_actor_turn
            if kind == 'force_end_turn':
                after = run_explicit_actor_turn(owner, turn=turn, player_id=pid, user_forced=True)
            else:
                after = run_explicit_actor_turn(owner, turn=turn, player_id=pid)
        else:
            from civ6_host.runtime.native.native_official_turn import run_explicit_turn
            if kind == 'force_end_turn':
                after = run_explicit_turn(owner, turn=turn, user_forced=True)
            else:
                after = run_explicit_turn(owner, turn=turn)
    else:
        raise ValueError('Unsupported explicit action')
    if owner.inputs.profile is official.LAN_PROFILE:
        from civ6_host.runtime.network_dialogue import retain
        retain(owner)
    interrupted = getattr(owner, 'turn_continuation', None) is not None
    if interrupted:
        from civ6_host.runtime.native.native_turn_continuation import validate
        retained = validate(owner)
        if retained.origin == 'network':
            if type(after) is not dict or after['player_id'] != pid or after['turn'] != turn:
                raise RuntimeError('LAN action-created dialogue changed actor or turn')
        elif retained.origin == 'world_input':
            if kind != 'world_war_response' or action.get('accept') is not True or type(after) is not dict:
                raise RuntimeError('Unexpected action-created diplomacy continuation')
            if after['turn'] != turn or after['player_id'] != pid:
                raise RuntimeError('Action-created dialogue changed turn or player')
        else:
            if kind not in ('end_turn', 'force_end_turn') or after is not None:
                raise RuntimeError('Unexpected interrupted action')
            after = observe_player(p.runtime, p.ui_child, pid)
    else:
        owner.control(empty=True)
    owner.emit('official_explicit_action_observed', action=action, turn=turn, observation=after, jobs_before=before, jobs_after=snapshot(owner, 'after'), automatic_choices_applied=False, player_id=pid, round_completed=kind in ('end_turn', 'force_end_turn') and (not interrupted) and (type(after) is dict) and (type(after.get('turn')) is int) and (after['turn'] > turn), strategic_training_ready=False)
    return after
from civ6_host.runtime.unit_panel_gate import catalog as _unit_panel_work_catalog
from civ6_host.runtime.unit_panel_gate import apply_terrain as _apply_unit_panel_terrain
from civ6_host.runtime.network_ui import feature_enabled as _action_feature_enabled

def read_decisions(owner, sequence, rounds, *, closed=False, round_limit=8, player_id=0, player_ids=(0, 1)):
    if getattr(owner, 'turn_continuation', None) is not None:
        return _read_decisions_without_context(owner, sequence, rounds, closed=closed, round_limit=round_limit, player_id=player_id, player_ids=player_ids)
    prefix = boundary(owner, player_id=player_id, player_ids=player_ids)
    from civ6_host.runtime.native.native_episode_identity import require_episode
    from civ6_host.runtime.decision_context import store_for
    store = store_for(owner)
    store.invalidate_player(owner, player_id, reason='decision_read_replaced')
    missing = object()
    previous_world_input = getattr(owner, 'explicit_world_input', missing)
    if previous_world_input is not missing:
        delattr(owner, 'explicit_world_input')
    try:
        result = _read_decisions_without_context(owner, sequence, rounds, closed=closed, round_limit=round_limit, player_id=player_id, player_ids=player_ids)
        identity = require_episode(prefix)
        observation = result[0]
        decision = result[1]
        store.capture(owner, episode_id=identity.episode_id, game_generation=identity.game_generation, roster=player_ids, player_id=player_id, turn=observation['turn'], decision_id=decision['decision_id'], sequence=decision['sequence'])
        return result
    except BaseException:
        if previous_world_input is not missing:
            owner.explicit_world_input = previous_world_input
        store.invalidate_player(owner, player_id, reason='decision_read_failed')
        raise

def apply_choice(owner, action, turn, *, player_id=0, player_ids=(0, 1)):
    from civ6_host.runtime.decision_context import store_for
    store = store_for(owner)
    if getattr(owner, 'turn_continuation', None) is not None:
        try:
            result = _apply_choice_without_context(owner, action, turn, player_id=player_id, player_ids=player_ids)
        except BaseException:
            store.invalidate_all(owner, reason='continuation_command_failed')
            raise
        store.invalidate_player(owner, player_id, reason='continuation_command_consumed')
        return result
    prefix = boundary(owner, player_id=player_id, player_ids=player_ids)
    from civ6_host.runtime.native.native_episode_identity import require_episode
    identity = require_episode(prefix)
    activated = False
    try:
        with store.activate(owner, episode_id=identity.episode_id, game_generation=identity.game_generation, roster=player_ids, player_id=player_id, turn=turn):
            activated = True
            try:
                result = _apply_choice_without_context(owner, action, turn, player_id=player_id, player_ids=player_ids)
            except BaseException:
                store.invalidate_all(owner, reason='command_failed')
                raise
            store.invalidate_player(owner, player_id, reason='command_consumed')
            return result
    except BaseException:
        if activated:
            store.invalidate_all(owner, reason='apply_failed')
        raise
