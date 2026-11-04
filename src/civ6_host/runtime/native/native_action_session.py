"""Explicit catalogue/choice extension of the bounded native saved session."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import copy
from civ6_host.runtime.native.native_saved_session import NativeSavedSession
from civ6_host.runtime.native.native_saved_session_protocol import SessionProtocol
from civ6_host.runtime.native.native_saved_session_protocol import SCHEMA as OLD_SCHEMA
from civ6_host.runtime.native.native_saved_session_protocol import validate_response as validate_envelope
from civ6_host.runtime.native.native_saved_session_protocol import MAX_EXPLICIT_ROUNDS
from civ6_host.runtime.native.native_saved_session_protocol import MAX_EXPLICIT_COMMANDS
from civ6_host.runtime.native.native_saved_actions import SCHEMA as DECISIONS_SCHEMA
from civ6_host.runtime.native.native_saved_actions import FOCUS_SCHEMA
from civ6_host.runtime.native.native_saved_actions import MANAGEMENT_SCHEMA
from civ6_host.runtime.native.native_saved_actions import digest
from civ6_host.runtime.native.native_saved_actions import GAPS
from civ6_host.runtime.native.native_saved_actions import validate_movement_action
from civ6_host.runtime.native import native_policy_catalog as policies
from civ6_host.runtime.native import native_saved_placement as placement
from civ6_host.runtime.native import native_saved_combat as combat
from civ6_host.runtime.native import native_saved_government as government
from civ6_host.runtime.native import native_saved_pantheon as pantheon
from civ6_host.runtime.native import native_saved_purchases as purchases
from civ6_host.runtime.native import native_saved_city_focus1000 as city_focus
from civ6_host.runtime.native import native_saved_citizens as citizens
from civ6_host.runtime.native import native_saved_unit_work as unit_work
from civ6_host.runtime.native import native_saved_promotions as promotions
from civ6_host.runtime.native import native_saved_unit_orders as unit_orders
from civ6_host.runtime.native import native_saved_unit_upgrade as upgrades
from civ6_host.runtime.native import native_saved_production_queue as production_queue
from civ6_host.runtime.native import native_saved_city_shot as city_shot
from civ6_host.runtime.native import native_saved_district_shot as district_shot
from civ6_host.runtime.native import native_saved_trade as trade
from civ6_host.runtime.native import native_saved_trade_origin as trade_origin
from civ6_host.runtime.native import native_saved_research_progress971 as research_progress
from civ6_host.runtime.native import native_saved_treasury980 as treasury
from civ6_host.runtime.native import native_saved_yield_display982 as yield_display
from civ6_host.runtime.native import native_saved_research_info983 as research_info
from civ6_host.runtime.native import native_saved_production_info988 as production_info
from civ6_host.runtime.native import native_saved_envoys as envoys
from civ6_host.runtime.native import native_saved_envoy_panel as envoy_panel
from civ6_host.runtime.native import native_saved_great_people as great_people
from civ6_host.runtime.native import native_saved_religion as religion
from civ6_host.runtime.native import native_saved_player_map as player_map
from civ6_host.runtime.native import native_plot_display990 as plot_display
from civ6_host.runtime.native import native_saved_captured_city as captured_city
from civ6_host.runtime.native import native_diplomacy_choices as diplomacy
SCHEMA = 'civ6rl.action_session920.v1'

def validate_decisions(value, identity, sequence, turn, *, player_id=0, actions_closed=False, map_coordinates=False):
    if type(actions_closed) is not bool:
        raise ValueError('Explicit action closure must be boolean')
    if diplomacy.is_catalog(value):
        return diplomacy.validate_catalog(value, identity, sequence, turn, player_id=player_id, actions_closed=actions_closed)
    from civ6_host.runtime.native.native_player_observation import _player_id
    _player_id(player_id)
    expected = {'schema', 'episode_id', 'game_generation', 'sequence', 'player_id', 'turn', 'player_map', 'candidates', 'blockers', 'production', 'production_queues', 'city_shots', 'district_shots', 'trade_routes', 'trade_origins', 'research', 'policies', 'government', 'pantheon', 'envoys', 'envoy_panel', 'great_people', 'religion', 'purchases', 'unit_work', 'unit_orders', 'unit_upgrades', 'unit_promotions', 'placements', 'placement_offers', 'combat_units', 'queued_orders', 'combat_cities', 'combat_relationships', 'captured_city', 'ready_units', 'unsupported', 'complete_action_space', 'decision_id'}
    expected.add('research_progress')
    expected.add('treasury')
    expected.add('yield_display')
    expected.add('research_info')
    if type(value) is dict and value.get('schema') in (MANAGEMENT_SCHEMA, FOCUS_SCHEMA, DECISIONS_SCHEMA, 'civ6rl.saved_decisions990.v1', 'civ6rl.saved_decisions989.v1', 'civ6rl.saved_decisions988.v1'):
        expected.add('production_info')
    if type(value) is dict and value.get('schema') in (MANAGEMENT_SCHEMA, FOCUS_SCHEMA, DECISIONS_SCHEMA, 'civ6rl.saved_decisions990.v1'):
        expected.add('plot_info')
    if type(value) is dict and value.get('schema') in (FOCUS_SCHEMA, MANAGEMENT_SCHEMA):
        expected.add('city_focus_catalogs')
    if type(value) is dict and value.get('schema') == MANAGEMENT_SCHEMA:
        expected.add('citizen_catalogs')
    if type(value) is dict and 'movement_preview' in value:
        expected.add('movement_preview')
    if type(value) is dict and 'world_input' in value:
        expected.add('world_input')
    if type(value) is not dict or set(value) != expected or value['schema'] not in (MANAGEMENT_SCHEMA, FOCUS_SCHEMA, DECISIONS_SCHEMA, 'civ6rl.saved_decisions990.v1', 'civ6rl.saved_decisions989.v1', 'civ6rl.saved_decisions988.v1', 'civ6rl.saved_decisions983.v1') or (value['episode_id'] != identity.episode_id) or (value['game_generation'] != identity.game_generation) or (type(value['sequence']) is not int) or (value['sequence'] != sequence) or (type(value['turn']) is not int) or (value['turn'] != turn) or (type(value['player_id']) is not int) or (value['player_id'] != player_id) or (value['complete_action_space'] is not False) or (value['unsupported'] != list(GAPS)) or (type(value['ready_units']) is not int) or (not 0 <= value['ready_units'] <= 4096):
        raise ValueError('Foreign or malformed decision catalogue')
    body = {k: v for k, v in value.items() if k != 'decision_id'}
    if value['decision_id'] != digest(body):
        raise ValueError('Decision catalogue digest differs')
    if type(value['research']) is not dict or set(value['research']) != {'research', 'civic'} or any((v is not None and (type(v) is not int or not 0 <= v <= 4294967295) for v in value['research'].values())):
        raise ValueError('Invalid current research observation')
    research_progress.validate(value['research_progress'], player_id, turn, value['research'])
    treasury.validate(value['treasury'], player_id, turn)
    yield_display.validate(value['yield_display'], player_id, turn)
    if value['schema'] in (MANAGEMENT_SCHEMA, FOCUS_SCHEMA, DECISIONS_SCHEMA, 'civ6rl.saved_decisions990.v1', 'civ6rl.saved_decisions989.v1', 'civ6rl.saved_decisions988.v1'):
        _validate_production_inputs(value['production_info'], player_id, turn, candidates=value['candidates'], ended=actions_closed)
    if actions_closed and value['candidates']:
        raise ValueError('Ended diagnostic still offers actions')
    research_info.validate(value['research_info'], player_id, turn, research=value['research'], candidates=None if actions_closed else value['candidates'])
    rows = value['candidates']
    if 'world_input' in value:
        from civ6_host.runtime.native import native_world_input as world
        world.validate(value['world_input'], player_id, turn, own_ids=[u['unit_id'] for u in value['combat_units']], width=value['player_map']['width'], height=value['player_map']['height'])
        world.validate_candidates(value['world_input'], rows, closed=actions_closed)
    player_map.validate(value['player_map'], player_id, turn)
    if value['schema'] in (MANAGEMENT_SCHEMA, FOCUS_SCHEMA, DECISIONS_SCHEMA, 'civ6rl.saved_decisions990.v1'):
        from civ6_host.contracts.plot_display990 import validate_and_index
        validate_and_index(value['plot_info'], player_id, turn, value['player_map'])
    policy_catalog = policies.validate_catalog(value['policies'], player_id, turn)
    placement.validate_progress(value['placements'], turn, player_id=player_id)
    placement.validate_offers(value['placement_offers'], player_id=player_id)
    for a in value['placement_offers']:
        if a['kind'] == 'production_placement':
            width, height = (value['player_map']['width'], value['player_map']['height'])
            if a['x'] >= width or a['y'] >= height or a['plot_id'] != a['y'] * width + a['x']:
                raise ValueError('Placement target outside player map')
    combat.validate_units(value['combat_units'])
    combat.validate_queued_orders(value['queued_orders'], player_id, turn, value['player_map']['width'], value['player_map']['height'], [u['unit_id'] for u in value['combat_units']])
    combat.city_targets.validate_cities(value['combat_cities'], value['player_map']['width'], value['player_map']['height'])
    visible = {r['index'] for r in value['player_map']['plots'] if r['visible']}
    if any((r['plot_id'] not in visible for r in value['combat_cities'])):
        raise ValueError('City defenses outside currently visible player map')
    combat.validate_relationships(value['combat_relationships'], player_id=player_id)
    captured_city.validate_catalog(value['captured_city'], player_id, turn)
    cap = value['captured_city']['city']
    if cap is not None and (not any((r['visible'] and r['owner'] == player_id and ((r['x'], r['y']) == (cap['x'], cap['y'])) for r in value['player_map']['plots']))):
        raise ValueError('Captured city outside visible own territory')
    government.validate_catalog(value['government'], turn, player_id=player_id)
    pantheon.validate_catalog(value['pantheon'], turn, player_id=player_id)
    unit_work.validate_catalog(value['unit_work'], player_id, turn)
    promotions.validate_catalog(value['unit_promotions'], player_id, turn)
    unit_orders.validate_catalog(value['unit_orders'], player_id, turn)
    upgrades.validate_catalog(value['unit_upgrades'], player_id, turn)
    production_queue.validate_all(value['production_queues'], player_id, turn)
    city_shot.validate_catalog(value['city_shots'], player_id, turn)
    district_shot.validate_catalog(value['district_shots'], player_id, turn)
    trade.validate_catalog(value['trade_routes'], player_id, turn)
    trade_origin.validate_catalog(value['trade_origins'], player_id, turn)
    queue_offers = [a for q in value['production_queues'] for a in production_queue.actions(q)]
    envoys.validate_catalog(value['envoys'], turn, player_id=player_id)
    envoy_panel.validate_catalog(value['envoy_panel'], turn, player_id=player_id)
    great_people.validate_catalog(value['great_people'], turn, player_id=player_id)
    religion.validate_catalog(value['religion'], turn, player_id=player_id)
    if value['unit_work']['enabled'] is not True:
        raise ValueError('Current session cannot silently disable native terrain work')
    if type(value['purchases']) is not list or len(value['purchases']) > 4096:
        raise ValueError('Unbounded purchase cities')
    purchase_offers = []
    purchase_cities = set()
    for catalog in value['purchases']:
        purchases.validate_catalog(catalog, player_id, turn)
        if catalog['city_id'] in purchase_cities:
            raise ValueError('Duplicate purchase city')
        purchase_cities.add(catalog['city_id'])
        purchase_offers.extend(purchases.actions(catalog))
        public_plots = {plot['index']: plot for plot in value['player_map']['plots']}
        width, height = (value['player_map']['width'], value['player_map']['height'])
        for offer in catalog['offers']:
            a = offer['action']
            if 'plot_id' in a:
                public = public_plots.get(a['plot_id'])
                if a['x'] >= width or a['y'] >= height or a['plot_id'] != a['y'] * width + a['x'] or (public is None) or ((public['x'], public['y']) != (a['x'], a['y'])):
                    raise ValueError('Purchase target outside the published player map')
    focus_offers = []
    if value['schema'] in (FOCUS_SCHEMA, MANAGEMENT_SCHEMA):
        catalogs = value['city_focus_catalogs']
        if type(catalogs) is not list or len(catalogs) > 4096:
            raise ValueError('Unbounded focus cities')
        focus_cities = set()
        for catalog in catalogs:
            city_focus.validate_catalog(catalog, player_id, turn)
            if catalog['city_id'] in focus_cities:
                raise ValueError('Duplicate focus city')
            focus_cities.add(catalog['city_id'])
            focus_offers.extend(city_focus.actions(catalog))
        if focus_cities != purchase_cities:
            raise ValueError('Focus city roster differs from own purchase cities')
    citizen_offers = []
    if value['schema'] == MANAGEMENT_SCHEMA:
        catalogs = value['citizen_catalogs']
        if type(catalogs) is not list or len(catalogs) > 4096:
            raise ValueError('Unbounded citizen cities')
        citizen_cities = set()
        public_plots = {plot['index']: plot for plot in value['player_map']['plots']}
        for catalog in catalogs:
            citizens.validate_catalog(catalog, player_id, turn)
            if catalog['city_id'] in citizen_cities:
                raise ValueError('Duplicate citizen city')
            citizen_cities.add(catalog['city_id'])
            citizen_offers.extend(citizens.actions(catalog))
            for plot in catalog['plots']:
                public = public_plots.get(plot['plot_id'])
                if public is None or (public['x'], public['y']) != (plot['x'], plot['y']):
                    raise ValueError('Citizen target outside the published player map')
        if citizen_cities != purchase_cities:
            raise ValueError('Citizen city roster differs from own cities')
    if type(rows) is not list:
        raise ValueError('Unbounded action catalogue')
    from civ6_host.contracts.action_budget import validate_action_count
    validate_action_count([row.get('action') if type(row) is dict else None for row in rows], world_input=value.get('world_input'), map_coordinates=map_coordinates)
    seen = set()
    shapes = {'research': {'kind', 'index', 'hash'}, 'civic': {'kind', 'index', 'hash'}, 'production': {'kind', 'city_id', 'category', 'index', 'hash', 'item_type'}, 'production_placement': placement.FIELDS, **production_queue.FIELDS, 'city_range_attack': city_shot.FIELDS, 'production_resume': placement.RESUME_FIELDS, 'district_range_attack': district_shot.FIELDS, 'make_trade_route': trade.FIELDS, 'change_trade_origin': trade_origin.FIELDS, 'unit_attack': combat.FIELDS, 'declare_war_minor': {'kind', 'target_player_id'}, 'government': {'kind', 'index', 'hash'}, 'retain_government': {'kind', 'index'}, 'pantheon': {'kind', 'index', 'hash'}, 'purchase': purchases.FIELDS, 'city_focus': city_focus.FIELDS, 'city_citizen': citizens.FIELDS, 'promote_unit': promotions.FIELDS, 'unit_order': unit_orders.FIELDS, 'upgrade_unit': upgrades.FIELDS, **envoys.FIELDS, **religion.FIELDS, 'review_envoys': envoy_panel.FIELDS, 'recruit_great_person': great_people.FIELDS, 'resolve_captured_city': captured_city.FIELDS, 'build_improvement': unit_work.BUILD_FIELDS, 'terrain_operation': unit_work.OP_FIELDS, 'found_city': {'kind', 'unit_id', 'x', 'y'}, 'skip_unit': {'kind', 'unit_id'}, 'end_turn': {'kind'}, 'force_end_turn': {'kind'}, 'policies': {'kind', 'slots'}, 'move': {'kind', 'unit_id', 'source_plot_id', 'source_x', 'source_y', 'destination_plot_id', 'destination_x', 'destination_y', 'moves_token'}}
    if 'world_input' in value:
        shapes.update(world.FIELDS)
    for row in rows:
        if type(row) is not dict or set(row) != {'candidate_id', 'action'}:
            raise ValueError('Malformed candidate')
        action = row['action']
        if type(action) is not dict or action.get('kind') not in shapes:
            raise ValueError('Unsupported action shape')
        fields = purchases.action_fields(action) if action['kind'] == 'purchase' else shapes[action['kind']]
        if set(action) != fields:
            raise ValueError('Unsupported action shape')
        if action['kind'] == 'policies':
            if policy_catalog['reason'] != 'available' or action['slots'] != policy_catalog['slots'] or (not policies.can_change(action['slots'])):
                raise ValueError('Policy offer differs from the native slot catalogue')
        if action['kind'] == 'move':
            validate_movement_action(action, player_id)
        if action['kind'] in ('production_placement', 'production_resume'):
            placement.validate_action(action, player_id=player_id)
            if action not in value['placement_offers']:
                raise ValueError('Placement action differs from native offers')
        if action['kind'] == 'city_range_attack':
            city_shot.validate_action(action, value['city_shots']['width'], value['city_shots']['height'])
            if action not in city_shot.actions(value['city_shots']):
                raise ValueError('City shot differs from native target offers')
        if action['kind'] == 'district_range_attack':
            district_shot.validate_action(action, value['district_shots']['width'], value['district_shots']['height'])
            if action not in district_shot.actions(value['district_shots']):
                raise ValueError('District shot differs from native target offers')
        if action['kind'] == 'make_trade_route':
            trade.validate_action(action, value['trade_routes']['width'], value['trade_routes']['height'])
            if action not in trade.actions(value['trade_routes']):
                raise ValueError('Trade differs from native offers')
        if action['kind'] == 'change_trade_origin':
            trade_origin.validate_action(action, value['trade_origins']['width'], value['trade_origins']['height'])
            if action not in trade_origin.actions(value['trade_origins']):
                raise ValueError('Origin differs from native offers')
        if action['kind'] in production_queue.FIELDS:
            production_queue.validate_action(action)
            if action not in queue_offers:
                raise ValueError('Queue action differs from native offers')
        if action['kind'] == 'unit_attack':
            combat.validate_action(action)
        if action['kind'] in ('government', 'retain_government') and action not in government.actions(value['government']):
            raise ValueError('Government offer differs from native catalogue')
        if action['kind'] == 'pantheon' and action not in pantheon.actions(value['pantheon']):
            raise ValueError('Pantheon offer differs from native catalogue')
        if action['kind'] == 'promote_unit':
            promotions.validate_action(action)
            if action not in value['unit_promotions']['offers']:
                raise ValueError('Promotion offer differs from native catalogue')
        if action['kind'] in envoys.FIELDS:
            envoys.validate_action(action)
            if action not in envoys.actions(value['envoys']):
                raise ValueError('Envoy offer differs from native catalogue')
        if action['kind'] == 'upgrade_unit':
            upgrades.validate_action(action)
            if action not in upgrades.actions(value['unit_upgrades']):
                raise ValueError('Upgrade differs from native quote/offer')
        if action['kind'] == 'unit_order':
            unit_orders.validate_action(action)
            if action not in unit_orders.actions(value['unit_orders']):
                raise ValueError('Unit order differs from native catalogue')
        if action['kind'] == 'review_envoys' and action not in envoy_panel.actions(value['envoy_panel'], value['envoys']):
            raise ValueError('Envoy panel offer differs from native access')
        if action['kind'] == 'recruit_great_person':
            great_people.validate_action(action)
            if action not in great_people.actions(value['great_people']):
                raise ValueError('Great Person offer differs from native catalogue')
        if action['kind'] in religion.FIELDS:
            religion.validate_action(action)
            if action not in religion.actions(value['religion']):
                raise ValueError('Religion offer differs from native catalogue')
        if action['kind'] == 'purchase':
            purchases.validate_action(action)
            if action not in purchase_offers:
                raise ValueError('Purchase offer differs from native catalogue')
        if action['kind'] == 'city_focus':
            city_focus.validate_action(action)
            if action not in focus_offers:
                raise ValueError('Focus gesture differs from native public state')
        if action['kind'] == 'city_citizen':
            citizens.validate_action(action)
            if action not in citizen_offers:
                raise ValueError('Citizen gesture differs from native public state')
        if action['kind'] == 'resolve_captured_city':
            captured_city.validate_action(action)
            if action not in captured_city.actions(value['captured_city']):
                raise ValueError('Captured-city offer differs from native catalogue')
        if action['kind'] in ('build_improvement', 'terrain_operation'):
            unit_work.validate_action(action)
            if action not in unit_work.actions(value['unit_work']):
                raise ValueError('Unit work offer differs from native catalogue')
        if action['kind'] == 'declare_war_minor' and (type(action['target_player_id']) is not int or not 0 <= action['target_player_id'] <= 63 or action['target_player_id'] == player_id):
            raise ValueError('Invalid minor war target')
        for name, v in action.items():
            if action['kind'] == 'world_war_response' and name == 'accept':
                if type(v) is not bool:
                    raise ValueError('War confirmation must be a Boolean choice')
                continue
            if action['kind'] == 'city_citizen' and name in ('occupied', 'locked', 'workers', 'capacity'):
                continue
            if action['kind'] == 'city_focus' and name in ('yield_type', 'favored', 'disfavored'):
                continue
            if action['kind'] == 'policies' and name == 'slots':
                continue
            if action['kind'] == 'move' and name == 'moves_token':
                continue
            if action['kind'] == 'purchase' and name in ('price_token', 'currency'):
                continue
            if action['kind'] in ('build_improvement', 'terrain_operation') and name == 'moves_token':
                continue
            if name in ('kind', 'category', 'item_type', 'mode', 'operation', 'input_route', 'directive', 'class', 'route'):
                if type(v) is not str or not v or len(v) > 128:
                    raise ValueError('Invalid action label')
            elif type(v) is not int or not 0 <= v <= 4294967295:
                raise ValueError('Invalid action integer')
        if action['kind'] == 'production' and action['category'] not in ('unit', 'building', 'project', 'district'):
            raise ValueError('Unknown production category')
        if row['candidate_id'] != digest(action) or row['candidate_id'] in seen:
            raise ValueError('Candidate digest or uniqueness differs')
        seen.add(row['candidate_id'])
    if value['schema'] in (FOCUS_SCHEMA, MANAGEMENT_SCHEMA) and (not actions_closed):
        if {digest(r['action']) for r in rows if r['action']['kind'] == 'city_focus'} != {digest(a) for a in focus_offers}:
            raise ValueError('Focus gesture set differs from the six public yield controls')
    if value['schema'] == MANAGEMENT_SCHEMA and (not actions_closed):
        if {digest(r['action']) for r in rows if r['action']['kind'] == 'city_citizen'} != {digest(a) for a in citizen_offers}:
            raise ValueError('Citizen gesture set differs from native public buttons')
    return value

class ActionProtocol(SessionProtocol):
    schema = SCHEMA
    require_city = False
    max_round_limit = MAX_EXPLICIT_ROUNDS
    max_commands = MAX_EXPLICIT_COMMANDS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.decisions = None

    def selected(self, request):
        selection = request.get('selection')
        if type(selection) is not dict or set(selection) not in ({'decision_id', 'candidate_id'}, {'decision_id', 'candidate_id', 'parameters'}) or self.decisions is None or (selection['decision_id'] != self.decisions['decision_id']):
            raise ValueError('Stale or missing decision catalogue')
        matches = [r['action'] for r in self.decisions['candidates'] if r['candidate_id'] == selection['candidate_id']]
        if len(matches) != 1:
            raise ValueError('Choice is absent from the native catalogue')
        action = matches[0]
        if 'world_input' in self.decisions:
            from civ6_host.runtime.native.native_world_input import permitted
            if not permitted(self.decisions['world_input'], action):
                raise ValueError('A pending war prompt blocks this choice')
        if action['kind'] == 'policies':
            params = selection.get('parameters')
            if type(params) is not dict or set(params) != {'assignments'}:
                raise ValueError('Explicit policy assignment parameters required')
            return dict(kind='policies', candidate=policies.choose(action['slots'], params['assignments'], self.decisions['player_id'], self.decisions['turn']))
        if 'parameters' in selection:
            raise ValueError('This action takes no parameters')
        return action

    def mapped(self, request):
        if type(request) is not dict or request.get('schema') != self.schema:
            raise ValueError('Wrong explicit session schema')
        base = {k: v for k, v in request.items() if k != 'selection'}
        base['schema'] = OLD_SCHEMA
        operation = request.get('operation')
        if operation == 'act':
            action = self.selected(request)
            base['operation'] = 'diagnostic_development_turn' if action['kind'] in ('end_turn', 'force_end_turn') else 'observe'
        elif operation not in ('observe', 'close') or 'selection' in request:
            raise ValueError('Automatic choices are not supported by the explicit session')
        return base

    def validate(self, request):
        SessionProtocol.validate(self, self.mapped(request))
        return request['operation']

    def commit(self, request, *, native_terminated=False, turn_completed=None):
        self.validate(request)
        mapped = self.mapped(request)
        if type(native_terminated) is not bool:
            raise ValueError('Exact native terminal flag required')
        selected = self.selected(request) if request['operation'] == 'act' else None
        if turn_completed is None:
            turn_completed = mapped['operation'] == 'diagnostic_development_turn'
        if type(turn_completed) is not bool or (turn_completed and (selected is None or selected['kind'] not in ('end_turn', 'force_end_turn', 'diplomacy_response'))):
            raise ValueError('Invalid explicit round completion')
        self.sequence = request['sequence']
        if selected is not None and selected['kind'] == 'found_city':
            self.city = True
        if turn_completed:
            self.rounds += 1
        self.closed = mapped['operation'] == 'close'
        self.ended = native_terminated or self.rounds == self.limit or self.closed

def response_completes_turn(response, protocol, request):
    if request is None or request['operation'] != 'act':
        return False
    if 'turn_reactivation' in response:
        return False
    kind = protocol.selected(request)['kind']
    if kind in ('end_turn', 'force_end_turn'):
        return not diplomacy.is_catalog(response.get('decisions'))
    if kind == 'diplomacy_response' and diplomacy.is_catalog(protocol.decisions):
        origin = protocol.decisions.get('continuation_origin', 'end_turn')
        return origin == 'end_turn' and (not diplomacy.is_catalog(response.get('decisions')))
    return False

def validate_turn_reactivation(receipt, action, protocol, response, *, initial_turn, expected_player=0):
    from civ6_host.runtime.native import native_host_turn_reactivation as reactivation
    fields = {'schema', 'turn', 'player_id', 'callback_sequence', 'reason', 'source_sha256'}
    was_interrupted = diplomacy.is_catalog(protocol.decisions)
    prior_origin = protocol.decisions.get('continuation_origin', 'end_turn') if was_interrupted else None
    if type(receipt) is not dict or set(receipt) != fields or receipt.get('schema') != 'civ6rl.native_turn_reactivation.v1' or (action is None) or (action.get('kind') not in ('end_turn', 'force_end_turn', 'diplomacy_response')) or (action.get('kind') == 'diplomacy_response' and (not was_interrupted)) or (action.get('kind') == 'diplomacy_response' and prior_origin != 'end_turn') or diplomacy.is_catalog(response.get('decisions')) or (type(receipt.get('turn')) is not int) or (receipt['turn'] != initial_turn + protocol.rounds) or (type(expected_player) is not int) or (not 0 <= expected_player < 64) or (type(receipt.get('player_id')) is not int) or (receipt['player_id'] != expected_player) or (type(receipt.get('callback_sequence')) is not int) or (receipt['callback_sequence'] <= 0) or (type(receipt.get('reason')) is not int) or (not 0 <= receipt['reason'] <= 4294967295) or (receipt['reason'] == reactivation.TIMER_REASON) or (receipt.get('source_sha256') != reactivation.PROOF_SHA256) or (type(response.get('observation')) is not dict) or (response['observation'].get('turn') != receipt['turn']):
        raise ValueError('Invalid same-turn reactivation receipt')

def validate_action_response(response, protocol, operation, *, request=None, expected_player=0, initial_turn=1):
    if type(response) is not dict or response.get('schema') != protocol.schema or response.get('operation') != operation or (response.get('automatic_choices_applied') is not False) or ('decisions' not in response) or ('applied_action' not in response):
        raise ValueError('Explicit action response is malformed or claims automatic decisions')
    action = protocol.selected(request) if operation == 'act' else None
    if response['applied_action'] != action:
        raise ValueError('Response action differs from the caller choice')
    reactivated = 'turn_reactivation' in response
    if reactivated:
        if operation != 'act':
            raise ValueError('Reactivation receipt outside an action response')
        validate_turn_reactivation(response['turn_reactivation'], action, protocol, response, initial_turn=initial_turn, expected_player=expected_player)
    mapped = protocol.mapped(request)['operation'] if request else 'reset'
    interrupted = diplomacy.is_catalog(response.get('decisions'))
    was_interrupted = diplomacy.is_catalog(protocol.decisions)
    prior_origin = protocol.decisions.get('continuation_origin', 'end_turn') if was_interrupted else None
    if interrupted:
        origin = response['decisions'].get('continuation_origin', 'end_turn')
        opens_from_endturn = not was_interrupted and action is not None and (action['kind'] in ('end_turn', 'force_end_turn')) and (origin == 'end_turn')
        opens_from_world_input = not was_interrupted and action is not None and (action.get('kind') == 'world_war_response') and (action.get('accept') is True) and (origin == 'world_input')
        follows_same_origin = was_interrupted and origin == prior_origin and (operation in ('observe', 'close') and action is None or (operation == 'act' and action is not None and (action.get('kind') == 'diplomacy_response')))
        if operation == 'reset' or not (opens_from_endturn or opens_from_world_input or follows_same_origin) or response['decisions']['origin_turn'] != initial_turn + protocol.rounds:
            raise ValueError('Unexpected interrupted turn')
        observed_turn = response['observation']['turn']
        allowed_turns = (initial_turn + protocol.rounds,) if origin == 'world_input' else (initial_turn + protocol.rounds, initial_turn + protocol.rounds + 1)
        if type(observed_turn) is not int or observed_turn not in allowed_turns:
            raise ValueError('Pending turn escaped its native interval')
        if origin == 'end_turn':
            initial_turn += observed_turn - (initial_turn + protocol.rounds)
        mapped = 'close' if operation == 'close' else 'observe'
    elif was_interrupted and operation != 'close':
        if action is None or action['kind'] != 'diplomacy_response':
            raise ValueError('Pending turn vanished without a response')
        if prior_origin == 'world_input':
            if type(response.get('observation')) is not dict or response['observation'].get('turn') != initial_turn + protocol.rounds:
                raise ValueError('Action-created dialogue response changed the current turn')
            mapped = 'observe'
        else:
            mapped = 'diagnostic_development_turn'
    proxy = {k: v for k, v in response.items() if k not in ('decisions', 'applied_action', 'turn_reactivation')}
    if reactivated:
        mapped = 'observe'
    proxy.update(schema=OLD_SCHEMA, operation=mapped, automatic_choices_applied=mapped == 'diagnostic_development_turn')
    validate_envelope(proxy, protocol, mapped, expected_player=expected_player, initial_turn=initial_turn)
    decisions = response['decisions']
    if decisions is None:
        if response['outcome']['terminated'] is not True:
            raise ValueError('Missing decisions outside a native terminal')
    else:
        validate_decisions(decisions, protocol.identity, response['sequence'], response['observation']['turn'], player_id=expected_player, actions_closed=response['outcome']['truncated'] or response['outcome']['terminated'])
        player_map.validate(decisions['player_map'], expected_player, response['observation']['turn'], visible=response['observation'])
        if not diplomacy.is_catalog(decisions) and [u['unit_id'] for u in decisions['unit_orders']['units']] != sorted((u['id'] for u in response['observation']['units'])):
            raise ValueError('Unit-order status roster differs from player observation')
        if not diplomacy.is_catalog(decisions) and (not {r['unit_id'] for r in decisions['unit_upgrades']['offers']}.issubset({u['id'] for u in response['observation']['units']})):
            raise ValueError('Upgrade offer for unit outside own observation')
        if decisions.get('schema') == diplomacy.CURRENT_SCHEMA:
            yield_display.validate(decisions['yield_display'], expected_player, response['observation']['turn'], response['observation'])
        if not diplomacy.is_catalog(decisions):
            if 'movement_preview' in decisions:
                from civ6_host.runtime.native.native_movement_preview import validate_and_index
                validate_and_index(decisions['movement_preview'], response['observation'], decisions['candidates'])
            if decisions['schema'] in (MANAGEMENT_SCHEMA, FOCUS_SCHEMA, DECISIONS_SCHEMA, 'civ6rl.saved_decisions990.v1', 'civ6rl.saved_decisions989.v1', 'civ6rl.saved_decisions988.v1'):
                _validate_production_inputs(decisions['production_info'], expected_player, response['observation']['turn'], candidates=decisions['candidates'], observation=response['observation'], ended=response['outcome']['truncated'] or response['outcome']['terminated'])
            yield_display.validate(decisions['yield_display'], expected_player, response['observation']['turn'], response['observation'])
            treasury.validate(decisions['treasury'], expected_player, response['observation']['turn'], gold_balance=response['observation']['economy']['gold'])
            city_shot.compare_own_cities(decisions['city_shots'], response['observation'])
            district_shot.compare_own_cities(decisions['district_shots'], response['observation'])
            trade.compare_own(decisions['trade_routes'], response['observation'])
            trade_origin.compare_own(decisions['trade_origins'], response['observation'])
            if decisions['schema'] in (FOCUS_SCHEMA, MANAGEMENT_SCHEMA) and {c['city_id'] for c in decisions['city_focus_catalogs']} != {c['id'] for c in response['observation']['cities']}:
                raise ValueError('Focus city roster differs from player observation')
            if not {a['city_id'] for a in decisions['placement_offers']}.issubset({c['id'] for c in response['observation']['cities']}):
                raise ValueError('Placement offer outside own city roster')
            if [q['city_id'] for q in decisions['production_queues']] != sorted((c['id'] for c in response['observation']['cities'])):
                raise ValueError('Production queue roster differs from own cities')
            production_queue.check_heads(decisions['production_queues'], decisions['production'])
        if (response['outcome']['truncated'] or response['outcome']['terminated']) and decisions['candidates']:
            raise ValueError('Ended diagnostic still offers actions')
    return response

class NativeActionSession(NativeSavedSession):
    worker_name = 'official_action_worker920.py'
    closure_schema = 'civ6rl.action_session920.closure.v1'
    protocol_class = ActionProtocol
    response_validator = staticmethod(validate_action_response)
    command_schema = SCHEMA

    def reset(self):
        self.last_native_turn_reactivation = None
        return super().reset()

    def request(self, request):
        self.last_native_turn_reactivation = None
        response = super().request(request)
        receipt = response.pop('turn_reactivation', None)
        if receipt is not None:
            self.last_native_turn_reactivation = dict(episode_id=response['episode_id'], game_generation=response['game_generation'], sequence=response['sequence'], receipt=copy.deepcopy(receipt))
        public = copy.deepcopy(response)
        self.last = copy.deepcopy(public)
        return public

    def __init__(self, run_root=None, *, round_limit=8, lifetime_seconds=45, stdout_limit_mib=64, checkpoint_on_close=False, checkpoint=None, forced_endturn_diagnostic=False, production_queue_diagnostic=False, privileged_critic_diagnostic=False, city_focus_diagnostic=False, city_management_diagnostic=False, official_bundle=None, episode_budget=None, multiturn_movement_diagnostic=False, movement_information_diagnostic=False, unit_order_cancel_diagnostic=False, movement_ui_probe=None, world_input_diagnostic=False, ui_profile=None, _admitted_bundle=None):
        self.ui_profile_admission = None
        if ui_profile is not None:
            from civ6_host.runtime.native.native_ui_profile import admit
            if any((city_management_diagnostic, city_focus_diagnostic, production_queue_diagnostic)):
                raise ValueError('UI profile admission cannot be mixed with city/queue diagnostic overrides')
            if checkpoint is not None or checkpoint_on_close:
                raise ValueError('UI profile admission requires its exact official bundle reset')
            self.ui_profile_admission = admit(ui_profile, official_bundle=official_bundle, input_profile=self.input_profile)
        if official_bundle is not None and (checkpoint is not None or checkpoint_on_close):
            raise ValueError('Captured bundle checkpoint ancestry is not yet supported; reset reloads the exact official save')
        from civ6_host.runtime.native.native_saved_session import ROOT
        if type(checkpoint_on_close) is not bool or (checkpoint_on_close and type(self) is not NativeActionSession):
            raise ValueError('Checkpoint save is an explicit Single-session administrative option')
        if type(forced_endturn_diagnostic) is not bool:
            raise ValueError('Forced turns require an exact explicit diagnostic option')
        self.forced_endturn_diagnostic = forced_endturn_diagnostic
        if type(production_queue_diagnostic) is not bool:
            raise ValueError('Queue gestures require an exact explicit diagnostic option')
        if type(multiturn_movement_diagnostic) is not bool:
            raise ValueError('Multi-turn movement requires an exact explicit diagnostic option')
        self.multiturn_movement_diagnostic = multiturn_movement_diagnostic
        if type(movement_information_diagnostic) is not bool:
            raise ValueError('Movement information requires an exact explicit diagnostic option')
        self.movement_information_diagnostic = movement_information_diagnostic
        if type(unit_order_cancel_diagnostic) is not bool:
            raise ValueError('Unit cancel requires an exact explicit diagnostic option')
        self.unit_order_cancel_diagnostic = unit_order_cancel_diagnostic
        if type(world_input_diagnostic) is not bool:
            raise ValueError('World input requires an exact explicit diagnostic option')
        self.world_input_diagnostic = world_input_diagnostic
        if world_input_diagnostic and checkpoint_on_close:
            raise ValueError('Saving host UI selection with a native checkpoint is not yet qualified')
        self.movement_ui_probe = None
        if movement_ui_probe is not None:
            from civ6_host.runtime.native.native_movement_ui import validate_targets
            if type(self) is not NativeActionSession:
                raise ValueError('Movement UI instrumentation requires an exact Single session')
            self.movement_ui_probe = copy.deepcopy(validate_targets(movement_ui_probe))
        if forced_endturn_diagnostic or production_queue_diagnostic or multiturn_movement_diagnostic or movement_information_diagnostic or unit_order_cancel_diagnostic or world_input_diagnostic:
            from civ6_host.runtime.native.native_hotseat_session import NativeHotseatActionSession
            if type(self) not in (NativeActionSession, NativeHotseatActionSession):
                raise ValueError('Turn and queue diagnostics require an exact Single or Hotseat session')
        self.production_queue_diagnostic = production_queue_diagnostic
        if type(city_management_diagnostic) is not bool:
            raise ValueError('City management requires an exact diagnostic option')
        self.city_management_diagnostic = city_management_diagnostic
        if type(city_focus_diagnostic) is not bool:
            raise ValueError('City focus requires an exact diagnostic option')
        city_focus_diagnostic = city_focus_diagnostic or city_management_diagnostic
        if city_focus_diagnostic:
            from civ6_host.runtime.native.native_hotseat_session import NativeHotseatActionSession
            if type(self) not in (NativeActionSession, NativeHotseatActionSession):
                raise ValueError('City focus diagnostic requires an admitted native session')
        self.city_focus_diagnostic = city_focus_diagnostic
        if type(privileged_critic_diagnostic) is not bool:
            raise ValueError('Privileged sidecar requires an exact explicit diagnostic option')
        if privileged_critic_diagnostic:
            from civ6_host.runtime.native.native_hotseat_session import NativeHotseatActionSession
            if type(self) not in (NativeActionSession, NativeHotseatActionSession):
                raise ValueError('Privileged sidecar requires an exact Single or Hotseat diagnostic session')
        self.privileged_critic_diagnostic = privileged_critic_diagnostic
        self.checkpoint_on_close = checkpoint_on_close
        self.checkpoint = None
        self.initial_turn = 1
        if checkpoint is not None:
            from civ6_host.runtime.native.native_session_resume import normalize_reference
            from civ6_host.runtime.native.native_session_resume import manifest
            if type(self) is not NativeActionSession:
                raise ValueError('Checkpoint requires the Single session')
            self.checkpoint = normalize_reference(checkpoint)
            self.initial_turn = manifest(self.checkpoint)['observed_game_turn']
            from functools import partial
            self.response_validator = partial(validate_action_response, initial_turn=self.initial_turn)
        super().__init__(run_root or ROOT / 'work/explicit-government920/runs', round_limit=round_limit, lifetime_seconds=lifetime_seconds, stdout_limit_mib=stdout_limit_mib, official_bundle=official_bundle, episode_budget=episode_budget, _admitted_bundle=_admitted_bundle)

    def _set_bundle_initial_turn(self, turn):
        if type(turn) is not int or not 1 <= turn <= 100000:
            raise ValueError('Invalid captured initial turn')
        self.initial_turn = turn
        if self.input_profile == 'single':
            from functools import partial
            self.response_validator = partial(validate_action_response, initial_turn=turn)

    def _configure_closure(self, closure):
        from civ6_host.runtime.native.native_saved_session import ROOT
        from civ6_host.runtime.native import native_event_45b517d6 as world_text
        world_text.verify_city_source()
        research_progress.verify_source()
        treasury.verify_source()
        for path, pin in treasury.verified_files().items():
            closure['pins'][str(path)] = pin
        for path, pin in yield_display.verified_files().items():
            closure['pins'][str(path)] = pin
        for path, pin in research_info.verified_files().items():
            closure['pins'][str(path)] = pin
        for path, pin in production_info.verified_files().items():
            closure['pins'][str(path)] = pin
        for path, pin in plot_display.verified_sources().items():
            closure['pins'][str(path)] = pin
        from civ6_host.runtime.native.native_unit_movement import verified_improvement_sources
        for path, pin in verified_improvement_sources().items():
            closure['pins'][str(path)] = pin
        closure['pins'][str(world_text.CITY_PROOF.relative_to(ROOT))] = world_text.CITY_PROOF_SHA256
        upgrades.verify_source()
        closure['pins'][str(upgrades.PROOF.relative_to(ROOT))] = upgrades.PROOF_SHA
        production_queue.verify_source()
        closure['pins'][str(production_queue.PROOF.relative_to(ROOT))] = production_queue.PROOF_SHA
        closure['pins'][str(production_queue.PUBLIC_PROOF.relative_to(ROOT))] = production_queue.PUBLIC_PROOF_SHA
        city_shot.verify_source()
        closure['pins'][str(city_shot.PROOF.relative_to(ROOT))] = city_shot.PROOF_SHA
        district_shot.verify_source()
        closure['pins'][str(district_shot.PROOF.relative_to(ROOT))] = district_shot.PROOF_SHA
        trade_proof = trade.verify_source()
        closure['pins'][str(trade.PROOF.relative_to(ROOT))] = trade.PROOF_SHA
        trade_origin.verify_source()
        closure['pins'][str(trade_origin.PROOF.relative_to(ROOT))] = trade_origin.PROOF_SHA
        closure['pins'][trade_proof['official_helper']['path']] = trade_proof['official_helper']['sha256']
        from civ6_host.runtime.native.native_locale_arguments import verified_files
        locale_files, _ = verified_files()
        for path, pin in locale_files.items():
            closure['pins'][str(path.relative_to(ROOT))] = pin
        placement.placement.verify_resume_source()
        closure['pins'][str(placement.placement.RESUME_PROOF.relative_to(ROOT))] = placement.placement.RESUME_SHA
        from civ6_host.runtime.native import native_production_catalog as production
        production.verify_replacement_source()
        closure['pins'][str(production.REPLACEMENT_PROOF.relative_to(ROOT))] = production.REPLACEMENT_SHA
        promotions.verify_source()
        closure['pins'][str(promotions.PROOF_PATH.relative_to(ROOT))] = promotions.PROOF_SHA
        unit_orders.verify_source()
        closure['pins'][str(unit_orders.PROOF.relative_to(ROOT))] = unit_orders.PROOF_SHA
        if self.unit_order_cancel_diagnostic or self.input_profile == 'lan':
            closure['pins'][str(unit_orders.CANCEL_PROOF.relative_to(ROOT))] = unit_orders.CANCEL_PROOF_SHA
            for path, pin in unit_orders.cancel_verified_files().items():
                closure['pins'][str(path)] = pin
        if self.movement_ui_probe is not None:
            from civ6_host.runtime.native.native_movement_ui_source import verified_files
            for path, pin in verified_files().items():
                closure['pins'][str(path)] = pin
            closure['movement_ui_probe'] = copy.deepcopy(self.movement_ui_probe)
        if self.world_input_diagnostic or self.input_profile == 'lan':
            from civ6_host.runtime.native.native_world_click import verified_files
            for path, pin in verified_files().items():
                closure['pins'][str(path)] = pin
            from civ6_host.runtime.native import native_world_configuration as world_configuration
            from civ6_host.runtime.native import native_world_war_display as world_war_display
            world_configuration.verify_source()
            config_proof = ROOT / 'evidence/native-world-configuration' / f'{world_configuration.PROOF_SHA256}.json'
            closure['pins'][str(config_proof.relative_to(ROOT))] = world_configuration.PROOF_SHA256
            for path, pin in world_war_display.verified_files().items():
                closure['pins'][str(path)] = pin
            from civ6_host.runtime.native.native_aux_map_conversion import STRING_KEYS_PROOF
            from civ6_host.runtime.native.native_aux_map_conversion import STRING_KEYS_PROOF_SHA256
            closure['pins'][str(STRING_KEYS_PROOF.relative_to(ROOT))] = STRING_KEYS_PROOF_SHA256
            from civ6_host.runtime.native.native_event_133d411c import ABSENT_DESCRIPTOR_PROOF
            from civ6_host.runtime.native.native_event_133d411c import ABSENT_DESCRIPTOR_PROOF_SHA256
            from civ6_host.runtime.native.native_event_133d411c import verify_absent_descriptor_source
            verify_absent_descriptor_source()
            closure['pins'][str(ABSENT_DESCRIPTOR_PROOF.relative_to(ROOT))] = ABSENT_DESCRIPTOR_PROOF_SHA256
            closure['world_input_diagnostic'] = self.world_input_diagnostic
        envoys.native.verify_source()
        envoy_panel.verify_source()
        closure['pins'][str(envoy_panel.PROOF.relative_to(ROOT))] = envoy_panel.PROOF_SHA256
        path = ROOT / 'evidence/native-envoy-actions' / f'{envoys.native.PROOF_SHA256}.json'
        closure['pins'][str(path.relative_to(ROOT))] = envoys.native.PROOF_SHA256
        for module in (religion.observation, religion.prophet, religion.founding, religion.beliefs):
            module.verify_source()
        for path, pin in [(religion.prophet.PROOF, religion.prophet.PROOF_SHA256), (religion.beliefs.PROOF, religion.beliefs.PROOF_SHA256), (ROOT / 'evidence/native-religion-founding-effect' / f'{religion.founding.EFFECT_PROOF_SHA256}.json', religion.founding.EFFECT_PROOF_SHA256)]:
            closure['pins'][str(path.relative_to(ROOT))] = pin
        gp = great_people.native
        gp.verify_source()
        from civ6_host.runtime.native.native_absent_achievements import INFLUENCE_CONTINUATION_PROOF_SHA256
        from civ6_host.runtime.native.native_absent_achievements import INFLUENCE_GROUP_PROOF_SHA256
        closure['pins']['work/greatpeople955/achievement-source.json'] = INFLUENCE_CONTINUATION_PROOF_SHA256
        closure['pins']['work/greatpeople955/achievement-group-source.json'] = INFLUENCE_GROUP_PROOF_SHA256
        for path, pin in [(gp._PROOF, gp.PINNED_EVIDENCE_SHA256), (gp._ENUM_PROOF, gp._ENUM_PROOF_SHA256), (gp._TRANSITION_PROOF, gp._TRANSITION_PROOF_SHA256)]:
            closure['pins'][str(path.relative_to(ROOT))] = pin
        if type(self) is NativeActionSession:
            from civ6_host.runtime.native.native_saved_session import ROOT
            from civ6_host.runtime.native.native_host_turn_reactivation import verify_source
            from civ6_host.runtime.native.native_host_turn_reactivation import PROOF_PATH
            from civ6_host.runtime.native.native_host_turn_reactivation import PROOF_SHA256
            verify_source()
            closure['pins'][str(PROOF_PATH.relative_to(ROOT))] = PROOF_SHA256
            from civ6_host.runtime.native.native_event_8953f126 import SELECTOR_PATH
            from civ6_host.runtime.native.native_event_8953f126 import SELECTOR_SHA256
            closure['pins'][str(SELECTOR_PATH.relative_to(ROOT))] = SELECTOR_SHA256
            from civ6_host.runtime.native.native_diplomacy_default import PROOF_PATH as DEFAULT_PATH
            from civ6_host.runtime.native.native_diplomacy_default import PROOF_SHA256 as DEFAULT_SHA
            from civ6_host.runtime.native.native_diplomacy_default import verify_source as verify_default
            verify_default()
            closure['pins'][str(DEFAULT_PATH.relative_to(ROOT))] = DEFAULT_SHA
            from civ6_host.runtime.native.native_diplomacy_display986 import PROOF as DISPLAY_PATH
            from civ6_host.runtime.native.native_diplomacy_display986 import PROOF_SHA as DISPLAY_SHA
            from civ6_host.runtime.native.native_diplomacy_display986 import verify_source as verify_display
            verify_display()
            closure['pins'][str(DISPLAY_PATH.relative_to(ROOT))] = DISPLAY_SHA
            from civ6_host.runtime.native.native_event_great_work import PROOF_PATH as GREAT_PATH
            from civ6_host.runtime.native.native_event_great_work import PROOF_SHA256 as GREAT_SHA
            from civ6_host.runtime.native.native_event_great_work import verify_source as verify_great
            verify_great()
            closure['pins'][str(GREAT_PATH.relative_to(ROOT))] = GREAT_SHA
            for name, pin in (('DiplomacyStatementSupport.lua', diplomacy.SUPPORT_SHA), ('DiplomacyActionView.lua', diplomacy.VIEW_SHA)):
                diplomacy.official_source(name, pin)
                path = ROOT / 'work/diplomacy948/official-source' / pin / name
                closure['pins'][str(path.relative_to(ROOT))] = pin
        if self.forced_endturn_diagnostic:
            closure['forced_endturn_diagnostic'] = True
        if self.production_queue_diagnostic:
            closure['production_queue_diagnostic'] = True
        if self.ui_profile_admission is not None:
            from civ6_host.runtime.native.native_ui_profile import admit
            from civ6_host.runtime.native.native_ui_profile import dependencies
            fresh = admit(self.ui_profile_admission['profile_id'], official_bundle=self.official_bundle, input_profile=self.input_profile)
            if fresh != self.ui_profile_admission:
                raise ValueError('UI profile changed between construction and reset')
            closure['ui_profile_admission'] = copy.deepcopy(fresh)
            closure['pins'].update(dependencies(fresh))
            city_focus.verify_source()
            citizens.verify_source()
            closure['pins']['work/city-focus1000/source.json'] = city_focus.SOURCE_SHA
            closure['pins'][str(citizens.PROOF.relative_to(ROOT))] = citizens.SOURCE_SHA
        if self.multiturn_movement_diagnostic:
            closure['multiturn_movement_diagnostic'] = True
        if self.movement_information_diagnostic:
            closure['movement_information_diagnostic'] = True
        if self.unit_order_cancel_diagnostic:
            closure['unit_order_cancel_diagnostic'] = True
        if self.city_focus_diagnostic:
            city_focus.verify_source()
            closure['city_focus_diagnostic'] = True
            closure['pins']['work/city-focus1000/source.json'] = city_focus.SOURCE_SHA
        if self.privileged_critic_diagnostic:
            closure['privileged_critic_diagnostic'] = True
        if self.city_management_diagnostic:
            citizens.verify_source()
            closure['city_management_diagnostic'] = True
            closure['pins'][str(citizens.PROOF.relative_to(ROOT))] = citizens.SOURCE_SHA
        if self.checkpoint_on_close:
            closure['checkpoint_on_close'] = True
        if self.checkpoint is not None:
            from civ6_host.runtime.native.native_session_resume import configure_closure
            configure_closure(closure, self.checkpoint)

    def _accepted_response(self, response):
        decisions = response['decisions']
        if decisions is not None and (not diplomacy.is_catalog(decisions)):
            if ('movement_preview' in decisions) != getattr(self, 'movement_information_diagnostic', False):
                raise ValueError('Movement preview differs from explicit session option')
            if not self._cancel_offer_admitted():
                if any((r['action'].get('item_type') == unit_orders.CANCEL_NAME for r in decisions.get('unit_orders', {}).get('offers', []))):
                    raise ValueError('Unit cancel differs from explicit session option')
        self.protocol.decisions = copy.deepcopy(decisions)

    def _commit_response(self, request, response):
        if type(self.protocol) is not ActionProtocol:
            return super()._commit_response(request, response)
        self.protocol.commit(request, native_terminated=response['outcome']['terminated'], turn_completed=response_completes_turn(response, self.protocol, request))

    def act(self, candidate_id, *, assignments=None):
        self._owner()
        if self.protocol is None or self.protocol.decisions is None:
            raise RuntimeError('No current decision catalogue')
        p = self.protocol
        selection = dict(decision_id=p.decisions['decision_id'], candidate_id=candidate_id)
        if assignments is not None:
            selection['parameters'] = dict(assignments=assignments)
        return self.request(dict(schema=self.command_schema, nonce=self.nonce, episode_id=p.identity.episode_id, game_generation=p.identity.game_generation, sequence=p.sequence + 1, operation='act', selection=selection))

    def _cancel_offer_admitted(self):
        return getattr(self, 'unit_order_cancel_diagnostic', False)
from civ6_host.contracts.production_inputs import validate as _validate_production_inputs
