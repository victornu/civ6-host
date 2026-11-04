"""Pure schema helpers for LAN per-player turn controls and catalogues."""
from __future__ import annotations

import hashlib
import json
import copy
import re

SCHEMA = 'civ6-host.network-decisions.v3'
WORK_SCHEMA = 'civ6-host.network-decisions.v4'
INFO_SCHEMA = 'civ6-host.network-decisions.v5'
GROWTH_SCHEMA = 'civ6-host.network-decisions.v6'
PRODUCTION_SCHEMA = 'civ6-host.network-decisions.v7'
LATEST_SCHEMA = PRODUCTION_SCHEMA
GROWTH_SCHEMAS = (PRODUCTION_SCHEMA, GROWTH_SCHEMA)
INFO_SCHEMAS = (PRODUCTION_SCHEMA, GROWTH_SCHEMA, INFO_SCHEMA)
WORK_SCHEMAS = (PRODUCTION_SCHEMA, GROWTH_SCHEMA, INFO_SCHEMA, WORK_SCHEMA)
PREVIOUS_SCHEMA = 'civ6-host.network-decisions.v2'
LEGACY_SCHEMA = 'civ6-host.network-decisions.v1'
CAPABILITY_SCHEMA = 'civ6-host.network-capability-decisions.v1'
CAPABILITY_CHOICES_SCHEMA = 'civ6-host.network-capability-decisions.v2'
CAPABILITY_TURNS_SCHEMA = 'civ6-host.network-capability-decisions.v3'
CAPABILITY_WORLD_SCHEMA = 'civ6-host.network-capability-decisions.v4'
CAPABILITY_UNIT_ORDERS_SCHEMA = 'civ6-host.network-capability-decisions.v5'
CAPABILITY_PRODUCTION_QUEUE_SCHEMA = 'civ6-host.network-capability-decisions.v6'
CAPABILITY_PLACEMENT_SCHEMA = 'civ6-host.network-capability-decisions.v7'
CAPABILITY_PLACEMENT_INVENTORY_SCHEMA = 'civ6-host.network-capability-decisions.v8'
CAPABILITY_UNIT_ATTACKS_SCHEMA = 'civ6-host.network-capability-decisions.v9'
CAPABILITY_COMBAT_PUBLIC_SCHEMA = 'civ6-host.network-capability-decisions.v10'
CAPABILITY_COMBAT_READINESS_SCHEMA = 'civ6-host.network-capability-decisions.v11'
CAPABILITY_CITY_CONTROLS_SCHEMA = 'civ6-host.network-capability-decisions.v12'
CAPABILITY_CITY_SHOT_SCHEMA = 'civ6-host.network-capability-decisions.v13'
CAPABILITY_DISTRICT_SHOT_SCHEMA = 'civ6-host.network-capability-decisions.v14'
CAPABILITY_UNIT_WORK_SCHEMA = 'civ6-host.network-capability-decisions.v15'
CAPABILITY_UNIT_WORK_STATE_SCHEMA = 'civ6-host.network-capability-decisions.v16'
CAPABILITY_UNIT_WORK_INFO_SCHEMA = 'civ6-host.network-capability-decisions.v17'
CAPABILITY_CURRENT_PRODUCTION_SCHEMA = 'civ6-host.network-capability-decisions.v18'
CAPABILITY_XP2_UNIT_SKIP_SCHEMA = 'civ6-host.network-capability-decisions.v19'
CAPABILITY_XP2_PLOT_PURCHASE_SCHEMA = 'civ6-host.network-capability-decisions.v20'
CAPABILITY_XP2_CITY_PURCHASE_SCHEMA = 'civ6-host.network-capability-decisions.v21'
CAPABILITY_XP2_PROMOTION_SCHEMA = 'civ6-host.network-capability-decisions.v22'
CAPABILITY_XP2_UNIT_UPGRADE_SCHEMA = 'civ6-host.network-capability-decisions.v23'
CAPABILITY_XP2_STRATEGIC_RESOURCES_SCHEMA = 'civ6-host.network-capability-decisions.v24'
# Known capability revisions in wire order. Each revision inherits the earlier
# groups, with field and migration exceptions handled by their own validators.
_CAPABILITY_SCHEMAS = (
    CAPABILITY_SCHEMA,
    CAPABILITY_CHOICES_SCHEMA,
    CAPABILITY_TURNS_SCHEMA,
    CAPABILITY_WORLD_SCHEMA,
    CAPABILITY_UNIT_ORDERS_SCHEMA,
    CAPABILITY_PRODUCTION_QUEUE_SCHEMA,
    CAPABILITY_PLACEMENT_SCHEMA,
    CAPABILITY_PLACEMENT_INVENTORY_SCHEMA,
    CAPABILITY_UNIT_ATTACKS_SCHEMA,
    CAPABILITY_COMBAT_PUBLIC_SCHEMA,
    CAPABILITY_COMBAT_READINESS_SCHEMA,
    CAPABILITY_CITY_CONTROLS_SCHEMA,
    CAPABILITY_CITY_SHOT_SCHEMA,
    CAPABILITY_DISTRICT_SHOT_SCHEMA,
    CAPABILITY_UNIT_WORK_SCHEMA,
    CAPABILITY_UNIT_WORK_STATE_SCHEMA,
    CAPABILITY_UNIT_WORK_INFO_SCHEMA,
    CAPABILITY_CURRENT_PRODUCTION_SCHEMA,
    CAPABILITY_XP2_UNIT_SKIP_SCHEMA,
    CAPABILITY_XP2_PLOT_PURCHASE_SCHEMA,
    CAPABILITY_XP2_CITY_PURCHASE_SCHEMA,
    CAPABILITY_XP2_PROMOTION_SCHEMA,
    CAPABILITY_XP2_UNIT_UPGRADE_SCHEMA,
    CAPABILITY_XP2_STRATEGIC_RESOURCES_SCHEMA,
)


def _capability_schemas_from(first):
    return _CAPABILITY_SCHEMAS[_CAPABILITY_SCHEMAS.index(first):]


_TURN_CAPABILITY_SCHEMAS = _capability_schemas_from(CAPABILITY_TURNS_SCHEMA)
ATTACK_CAPABILITY_SCHEMAS = _capability_schemas_from(CAPABILITY_UNIT_ATTACKS_SCHEMA)
PUBLIC_COMBAT_CAPABILITY_SCHEMAS = _capability_schemas_from(CAPABILITY_COMBAT_PUBLIC_SCHEMA)
COMBAT_READINESS_CAPABILITY_SCHEMAS = _capability_schemas_from(CAPABILITY_COMBAT_READINESS_SCHEMA)
UNIT_WORK_STATE_CAPABILITY_SCHEMAS = _capability_schemas_from(CAPABILITY_UNIT_WORK_STATE_SCHEMA)
CURRENT_PRODUCTION_CAPABILITY_SCHEMAS = _capability_schemas_from(CAPABILITY_CURRENT_PRODUCTION_SCHEMA)

COMBAT_READINESS_SOURCE_SHA256 = '3441a99fe192ace6b1d57af5813b834f54c7b57bd3237669d20667dbed4c7477'
_XP1_COMBAT_CORE='259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83'
_XP2_COMBAT_CORE='324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'
_XP2_COMBAT_SOURCE='94562a3ba9e6988fde63a146dd1228b2454b5b1dbee93ffc12a25d83756d95e2'

def combat_checkpoint_sources(core_sha256=None):
    # Pure, pinned schema contract. No runtime/resource import in portable clients.
    from .capability_unit_attacks import PUBLIC_PRECISION_SHA256
    if core_sha256 in (None,_XP1_COMBAT_CORE):
        return PUBLIC_PRECISION_SHA256,COMBAT_READINESS_SOURCE_SHA256
    if core_sha256==_XP2_COMBAT_CORE:return _XP2_COMBAT_SOURCE,_XP2_COMBAT_SOURCE
    raise ValueError('Combat checkpoint transition requires its exact engine')

SUPPORTED_SCHEMAS = (PRODUCTION_SCHEMA, GROWTH_SCHEMA, INFO_SCHEMA, WORK_SCHEMA,
                     SCHEMA, PREVIOUS_SCHEMA, LEGACY_SCHEMA, *_CAPABILITY_SCHEMAS)
MAP_SCHEMAS = (PRODUCTION_SCHEMA, GROWTH_SCHEMA, INFO_SCHEMA, WORK_SCHEMA, SCHEMA)
TURN_CONTROLS_SCHEMA = 'civ6-host.turn-controls.v1'
DIALOGUE_SCHEMAS = frozenset(('civ6rl.diplomacy_decisions948.v1',
                              'civ6rl.diplomacy_decisions987.v1'))
_WAITING_FIELDS = {
    'schema', 'base_schema', 'episode_id', 'game_generation', 'sequence',
    'player_id', 'turn', 'player_map', 'candidates', 'turn_controls',
    'unsupported', 'complete_action_space', 'decision_id',
}
_CAPABILITY_FIELDS = {
    'schema', 'episode_id', 'game_generation', 'sequence', 'player_id', 'turn',
    'turn_controls', 'candidates', 'families', 'family_inventory_complete',
    'complete_action_space', 'decision_id',
}
_CAPABILITY_ACTION_FIELDS = {'found_city': frozenset(('kind', 'unit_id', 'x', 'y'))}
_CAPABILITY_TURN_KINDS = frozenset(('end_turn', 'force_end_turn', 'unready_turn'))


def is_capability_catalogue(value):
    return type(value) is dict and value.get('schema') in _CAPABILITY_SCHEMAS


def offered_forced_turn(value, action):
    """Same inactive-player exception on client and server, after validation.

    This consumes an explicit native UI offer; it does not derive availability
    from activity flags or upgrade legacy catalogues.
    """
    return (type(value) is dict and value.get('schema') in _TURN_CAPABILITY_SCHEMAS
            and action=={'kind':'force_end_turn'}
            and value['turn_availability']['force_end_turn'] is True
            and any(row['action']==action for row in value['candidates']))


def validate_capability_catalogue(value, identity, sequence, turn, *, player_id,
                                  actions_closed=False, observation=None):
    """Validate a partial family query, never certify native availability.

    ``queried_complete`` describes only that named family's full native query
    at this boundary. Its candidate IDs must cover exactly its offered choices.
    ``unqualified`` has no candidate list: absence of a query is not an empty
    native result. Providers must authenticate the actual reads separately.
    Unknown/unlisted families remain unqualified; this inventory is incomplete.
    No Base catalogue, revealed map or information group is fabricated here.
    """
    if type(actions_closed) is not bool or not is_capability_catalogue(value):
        raise ValueError('Unexpected capability catalogue fields')
    version = _CAPABILITY_SCHEMAS.index(value['schema']) + 1
    resources_v24 = version >= 24
    upgrade_v23 = version >= 23
    promotion_v22 = version >= 22
    city_purchase_v21 = version >= 21
    purchase_v20 = version >= 20
    skip_v19 = version >= 19
    current_production_v18 = version >= 18
    work_info_v17 = version >= 17
    work_state_v16 = version >= 16
    unit_work_v15 = version >= 15
    district_shot_v14 = version >= 14
    city_shot_v13 = version >= 13
    city_controls_v12 = version == 12 or city_shot_v13 and 'city_focus_catalogs' in value
    public_combat_v10 = version >= 10
    attacks_v9 = version >= 9
    inventory_v8 = version >= 8
    placements_v7 = version >= 7
    queues_v6 = version >= 6
    orders_v5 = version >= 5
    world_v4 = version >= 4
    turns_v3 = version >= 3
    choices_v2 = version >= 2
    fields = (_CAPABILITY_FIELDS | ({'choice_state'} if choices_v2 else set())
              | ({'turn_availability'} if turns_v3 else set())
              | ({'world_input', 'queued_orders'} if world_v4 else set())
              | ({'unit_orders'} if orders_v5 else set())
              | ({'production_queues'} if queues_v6 else set())
              | ({'placements','placement_offers','placement_observation_scope'} if placements_v7 else set())
              | ({'placement_inventory'} if inventory_v8 else set())
              | ({'unit_attacks'} if attacks_v9 else set())
              | ({'city_shots'} if city_shot_v13 else set())
              | ({'district_shots'} if district_shot_v14 else set())
              | ({'unit_work'} if unit_work_v15 else set())
              | ({'unit_work_state'} if work_state_v16 else set())
              | ({'unit_work_info'} if work_info_v17 else set())
              | ({'production_current'} if current_production_v18 else set())
              | ({'plot_purchases'} if purchase_v20 else set())
              | ({'city_purchases'} if city_purchase_v21 else set())
              | ({'unit_promotions'} if promotion_v22 else set())
              | ({'unit_upgrades'} if upgrade_v23 else set())
              | ({'strategic_resources'} if resources_v24 else set())
              | ({'city_focus_catalogs','citizen_catalogs'} if city_controls_v12 else set()))
    from .capability_choices import ACTION_FIELDS, validate_action, validate_state
    action_fields = dict(_CAPABILITY_ACTION_FIELDS)
    if choices_v2:
        action_fields.update(ACTION_FIELDS)
    if turns_v3:
        action_fields.update({name: frozenset(('kind',)) for name in _CAPABILITY_TURN_KINDS})
    if world_v4:
        from . import capability_world_input as world
        from .action_budget import MAP_CELL_LIMIT, ORDINARY_ACTION_LIMIT, validate_action_count
        action_fields.update(world.ACTION_FIELDS)
    if orders_v5:
        from . import capability_unit_orders as orders
        action_fields.update(orders.ACTION_FIELDS)
    if queues_v6:
        from . import production_queue as queues
        action_fields.update(queues.FIELDS)
    if placements_v7:
        from . import placement
        action_fields.update(placement.ACTION_FIELDS)
    if attacks_v9:
        from . import capability_unit_attacks as attacks
        action_fields.update(attacks.ACTION_FIELDS)
    if city_shot_v13:
        from . import city_ranged
        action_fields['city_range_attack'] = city_ranged.CITY_FIELDS
    if district_shot_v14:
        action_fields['district_range_attack'] = city_ranged.DISTRICT_FIELDS
    if unit_work_v15:
        from . import unit_work
        action_fields.update(unit_work.NETWORK_ACTION_FIELDS)
    if purchase_v20:
        from . import plot_purchases
        action_fields['purchase'] = plot_purchases.FIELDS
    if promotion_v22:
        from . import unit_promotions
        action_fields['promote_unit'] = unit_promotions.FIELDS
    if upgrade_v23:
        from . import unit_upgrades
        action_fields['upgrade_unit'] = unit_upgrades.FIELDS
    if city_controls_v12:
        from . import capability_city_controls as city_controls
        action_fields.update(city_controls.ACTION_FIELDS)
    if set(value) != fields:
        raise ValueError('Unexpected capability catalogue fields')
    for name, expected in (('sequence', sequence), ('player_id', player_id), ('turn', turn)):
        if (type(expected) is not int or expected < 0
                or type(value[name]) is not int or value[name] != expected):
            raise ValueError('Foreign capability catalogue boundary')
    if (player_id >= 64 or value['episode_id'] != identity.episode_id
            or value['game_generation'] != identity.game_generation
            or type(value['episode_id']) is not str or type(value['game_generation']) is not str
            or value['complete_action_space'] is not False
            or value['family_inventory_complete'] is not False):
        raise ValueError('Foreign or overstated capability catalogue')
    controls = validate_turn_controls(value['turn_controls'], player_id, turn)
    if resources_v24:
        from . import strategic_resources
        resources = value['strategic_resources']
        if (resources is None) != actions_closed:
            raise ValueError('Strategic resources differ from the session closure')
        if resources is not None:
            strategic_resources.validate(resources, player_id, turn)
    if (type(value['decision_id']) is not str or value['decision_id'] != digest(
            {key: item for key, item in value.items() if key != 'decision_id'})):
        raise ValueError('Capability catalogue digest differs')
    families, candidates = value['families'], value['candidates']
    if (type(families) is not dict or not 1 <= len(families) <= 128
            or type(candidates) is not list
            or len(candidates) > (ORDINARY_ACTION_LIMIT + MAP_CELL_LIMIT if world_v4 else 4096)
            or actions_closed and candidates):
        raise ValueError('Malformed or closed capability catalogue')
    if turns_v3:
        availability = value['turn_availability']
        if (type(availability) is not dict or set(availability) != _CAPABILITY_TURN_KINDS
                or any(item is not None and type(item) is not bool for item in availability.values())
                or not _CAPABILITY_TURN_KINDS <= set(families)
                or actions_closed and any(item is not None for item in availability.values())):
            raise ValueError('Malformed, missing or closed native turn availability')
    if world_v4 and not world.WORLD_KINDS <= set(families):
        raise ValueError('Missing world-input capability families')
    if orders_v5 and 'unit_order' not in families:
        raise ValueError('Missing unit-order capability family')
    if queues_v6 and not set(queues.FIELDS)<=set(families):
        raise ValueError('Missing production-queue capability families')
    if placements_v7 and not set(placement.ACTION_FIELDS)<=set(families):
        raise ValueError('Missing placement capability families')
    if attacks_v9 and 'unit_attack' not in families:
        raise ValueError('Missing unit-attack capability family')
    if city_shot_v13:
        shots = value['city_shots']
        shot_family = families.get('city_range_attack', {})
        if shots is not None:
            city_ranged.city_validate_catalog(shots, player_id, turn)
            if observation is not None:
                city_ranged.city_compare_own_cities(shots, observation)
        if shot_family.get('status') != ('unqualified' if shots is None else 'queried_complete'):
            raise ValueError('City-shot query and family status differ')
    if district_shot_v14:
        district_shots = value['district_shots']
        if district_shots is not None:
            city_ranged.district_validate_catalog(district_shots, player_id, turn)
            if observation is not None:
                city_ranged.district_compare_own_cities(district_shots, observation)
        if families.get('district_range_attack', {}).get('status') != (
                'unqualified' if district_shots is None else 'queried_complete'):
            raise ValueError('District-shot query and family status differ')
    if unit_work_v15:
        work_catalogue = value['unit_work']
        work_status = 'unqualified' if work_catalogue is None else 'queried_partial'
        if any(families.get(kind, {}).get('status') != work_status
               for kind in unit_work.NETWORK_ACTION_FIELDS):
            raise ValueError('Unit-work query and family status differ')
        if work_catalogue is not None:
            if actions_closed or is_waiting(controls):
                raise ValueError('Unit-work query requires the native acting boundary')
            unit_work.validate_network_catalog(work_catalogue, player_id, turn, observation=observation)
        if work_state_v16:
            state = value['unit_work_state']
            if (state is None) != (work_catalogue is None):
                raise ValueError('Unit-work state and catalogue availability differ')
            if state is not None:
                from .unit_work_state import validate as validate_work_state
                validate_work_state(state, player_id, turn, observation=observation,
                                    work_catalog=work_catalogue, include_plot=True)
        if work_info_v17:
            info = value['unit_work_info']
            if (info is None) != (work_catalogue is None):
                raise ValueError('Unit-work information and catalogue availability differ')
            if info is not None:
                from .unit_work_info import validate as validate_work_info
                validate_work_info(info, player_id, turn, observation=observation,
                                   work_catalog=work_catalogue, work_state=state)
    by_family = {}
    for name, family in families.items():
        if (type(name) is not str or re.fullmatch(r'[a-z][a-z0-9_.]{0,63}', name) is None
                or type(family) is not dict):
            raise ValueError('Invalid capability family')
        status = family.get('status')
        if status in ('queried_complete', 'queried_partial'):
            ids = family.get('candidate_ids')
            partial = status == 'queried_partial'
            if (name not in action_fields
                    or partial and not choices_v2
                    or turns_v3 and name in _CAPABILITY_TURN_KINDS and partial
                    or name == 'production' and not partial
                    or orders_v5 and name == 'unit_order' and not partial
                    or attacks_v9 and name == 'unit_attack' and not partial
                    or queues_v6 and name in queues.FIELDS and partial != (name=='queue_append')
                    or placements_v7 and name in placement.ACTION_FIELDS and not partial
                    or set(family) != ({'status', 'candidate_ids', 'unqualified'} if partial else {'status', 'candidate_ids'})
                    or world_v4 and name in world.WORLD_KINDS
                       and partial != (name == 'world_plot_click')
                    or type(ids) is not list
                    or len(ids) > (MAP_CELL_LIMIT if world_v4 and name == 'world_plot_click' else 4096)
                    or any(type(item) is not str or re.fullmatch(r'[0-9a-f]{64}', item) is None
                           for item in ids)
                    or len(set(ids)) != len(ids)):
                raise ValueError('Unsupported or malformed completed family query')
            if partial:
                gaps = family['unqualified']
                if (type(gaps) is not list or not gaps or len(gaps) > 128
                        or any(type(gap) is not str or not gap.strip() or len(gap) > 256 for gap in gaps)
                        or len(set(gaps)) != len(gaps)):
                    raise ValueError('Partial family query must list its unqualified choices')
                if world_v4 and name == 'world_plot_click' and gaps != list(world.UNQUALIFIED_WORLD_CLICK):
                    raise ValueError('World-input click must retain its exact unqualified branches')
                if orders_v5 and name == 'unit_order' and gaps != list(orders.UNQUALIFIED_UNIT_ORDERS):
                    raise ValueError('Unit-order query must retain its exact unqualified branches')
                if attacks_v9 and name=='unit_attack' and gaps!=list(attacks.UNQUALIFIED_UNIT_ATTACKS):
                    raise ValueError('Unit-attack query must retain its exact unqualified routes')
                if queues_v6 and name=='queue_append' and gaps!=list(queues.UNQUALIFIED_APPEND):
                    raise ValueError('Queue append must retain its exact unqualified branches')
                if unit_work_v15 and name in unit_work.NETWORK_GAPS and gaps != list(unit_work.NETWORK_GAPS[name]):
                    raise ValueError('Unit-work query must retain its unqualified routes')
                if placements_v7 and name in placement.GAPS and gaps!=list(placement.GAPS[name]):
                    raise ValueError('Placement query must retain its exact unqualified branches')
            if actions_closed or (is_waiting(controls) and not (turns_v3 and name in _CAPABILITY_TURN_KINDS)):
                raise ValueError('Choice query requires the native acting boundary')
            by_family[name] = []
        elif status == 'unqualified':
            reason = family.get('reason')
            if (set(family) != {'status', 'reason'} or type(reason) is not str
                    or not reason.strip() or len(reason) > 512):
                raise ValueError('Unqualified family cannot substitute an empty query')
        else:
            raise ValueError('Unknown capability family status')

    own_units = own_cities = None
    if observation is not None:
        from civ6_host.player_view import _validate_observation
        _validate_observation(observation, player_id, turn)
        own_units = {unit['id']: unit for unit in observation['units']}
        own_cities = {city['id']: city for city in observation['cities']}
        if len(own_units) != len(observation['units']):
            raise ValueError('Ambiguous owned-unit observation')
        if len(own_cities) != len(observation['cities']):
            raise ValueError('Ambiguous owned-city observation')
    if purchase_v20:
        purchases = value['plot_purchases']
        city_purchases = value['city_purchases'] if city_purchase_v21 else None
        unavailable = actions_closed or is_waiting(controls)
        family = families.get('purchase', {})
        if (unavailable != (purchases is None)
                or city_purchase_v21 and unavailable != (city_purchases is None)
                or family.get('status') != ('unqualified' if unavailable else 'queried_partial')):
            raise ValueError('Plot purchase query differs from its native acting boundary')
        if not unavailable:
            dimensions = observation if observation is not None else value['world_input']
            if type(dimensions) is not dict or any(
                    type(dimensions.get(k)) is not int or dimensions[k] <= 0 for k in ('width', 'height')):
                raise ValueError('Plot purchase catalogue lacks map dimensions')
            gaps = plot_purchases.CITY_GAPS if city_purchase_v21 else plot_purchases.GAPS
            if family.get('unqualified') != list(gaps):
                raise ValueError('Plot purchase family must retain its exact unqualified routes')
            plot_purchases.validate_catalogue(purchases, player_id, turn, width=dimensions['width'],
                                               height=dimensions['height'], own_cities=own_cities)
            if city_purchase_v21:
                plot_purchases.validate_catalogue(city_purchases, player_id, turn,
                    own_cities=[city['city_id'] for city in purchases], city_items=True)
    if choices_v2:
        validate_state(value['choice_state'], own_cities,
                       unavailable=actions_closed or is_waiting(controls))
    if world_v4:
        missing_world = value['world_input'] is None
        unavailable = actions_closed or is_waiting(controls) or missing_world
        world.validate_state(value['world_input'], player_id, turn,
                             observation=observation, unavailable=unavailable)
        world.validate_queued_orders(value['queued_orders'], player_id, turn,
            observation=observation, world_input=value['world_input'], unavailable=unavailable)
        for kind in world.WORLD_KINDS:
            expected_status = ('unqualified' if unavailable else
                               'queried_partial' if kind == 'world_plot_click' else 'queried_complete')
            if families[kind]['status'] != expected_status:
                raise ValueError('World-input family differs from its public query availability')
    if orders_v5:
        unavailable = actions_closed or is_waiting(controls) or value['unit_orders'] is None
        orders.validate_catalog(value['unit_orders'], player_id, turn,
                                observation=observation, unavailable=unavailable, allow_skip=skip_v19)
        if families['unit_order']['status'] != ('unqualified' if unavailable else 'queried_partial'):
            raise ValueError('Unit-order family differs from its native query availability')
        if not unavailable and value['world_input'] is not None:
            if ([row['unit_id'] for row in value['unit_orders']['units']]
                    != [row['unit_id'] for row in value['world_input']['units']]):
                raise ValueError('Unit-order and world-input own rosters differ')
    if queues_v6:
        unavailable=actions_closed or is_waiting(controls) or value['production_queues'] is None
        queues.validate_public(value['production_queues'],player_id,turn,observation=observation,
            choice_state=value['choice_state'],unavailable=unavailable)
        if current_production_v18:
            current_production = value['production_current']
            if (current_production is None) != unavailable:
                raise ValueError('Current production and queue catalogue availability differ')
            if not unavailable:
                from .production_inputs import validate_current
                validate_current(current_production, player_id, turn, observation=observation,
                                 queues=value['production_queues'])
        for kind in queues.FIELDS:
            expected_status='unqualified' if unavailable else 'queried_partial' if kind=='queue_append' else 'queried_complete'
            if families[kind]['status']!=expected_status:
                raise ValueError('Queue family differs from its native query availability')
    if placements_v7:
        unavailable=actions_closed or is_waiting(controls) or value['placement_offers'] is None
        placement.validate_public(value['placement_offers'],value['placements'],value['placement_observation_scope'],
            player_id,turn,observation=observation,unavailable=unavailable)
        for kind in placement.ACTION_FIELDS:
            if families[kind]['status']!=('unqualified' if unavailable else 'queried_partial'):
                raise ValueError('Placement family differs from its native query availability')
    if inventory_v8:
        from .placement_inventory import validate as validate_inventory
        # This is an observation, independent of action availability/tracking.
        validate_inventory(value['placement_inventory'],player_id,turn,observation=observation)
    if attacks_v9:
        unavailable=actions_closed or is_waiting(controls) or value['unit_attacks'] is None
        attack_validator=attacks.validate_public_catalog if public_combat_v10 else attacks.validate_catalog
        attack_validator(value['unit_attacks'],player_id,turn,observation=observation,
            queued_orders=value['queued_orders'],unavailable=unavailable)
        if not unavailable and value['queued_orders'] is None:
            raise ValueError('Unit attacks require the same native queued-order observation')
        if families['unit_attack']['status']!=('unqualified' if unavailable else 'queried_partial'):
            raise ValueError('Unit-attack family differs from its native query availability')
    if city_controls_v12:
        city_controls.validate_families(value,player_id,turn,observation=observation,
            unavailable=actions_closed or is_waiting(controls))
    if promotion_v22:
        unavailable = actions_closed or is_waiting(controls)
        promotion_catalogue = value['unit_promotions']
        if ((promotion_catalogue is None) != unavailable
                or families['promote_unit']['status'] != ('unqualified' if unavailable else 'queried_complete')):
            raise ValueError('Promotion family differs from its native query availability')
        if not unavailable:
            unit_promotions.validate_catalogue(promotion_catalogue, player_id, turn, observation=observation)
    if upgrade_v23:
        unavailable = actions_closed or is_waiting(controls)
        upgrade_catalogue = value['unit_upgrades']
        if ((upgrade_catalogue is None) != unavailable
                or families.get('upgrade_unit', {}).get('status') !=
                   ('unqualified' if unavailable else 'queried_complete')):
            raise ValueError('Upgrade family differs from its native query availability')
        if not unavailable:
            unit_upgrades.validate_catalogue(upgrade_catalogue, player_id, turn, observation=observation)
    seen = set()
    for row in candidates:
        if type(row) is not dict or set(row) != {'candidate_id', 'action'}:
            raise ValueError('Malformed capability candidate')
        action = row['action']
        if type(action) is not dict or type(action.get('kind')) is not str:
            raise ValueError('Malformed capability action')
        kind = action['kind']
        city_purchase = city_purchase_v21 and kind == 'purchase' and set(action) == plot_purchases.CITY_FIELDS
        if kind not in by_family or (set(action) != action_fields[kind] and not city_purchase):
            raise ValueError('Action has no completed qualified family query')
        if kind == 'found_city':
            for key, maximum in (('unit_id', 0xffffffff), ('x', 65535), ('y', 65535)):
                if type(action[key]) is not int or not 0 <= action[key] <= maximum:
                    raise ValueError('Malformed foundation action')
            if own_units is not None:
                unit = own_units.get(action['unit_id'])
                if unit is None or (unit['x'], unit['y']) != (action['x'], action['y']):
                    raise ValueError('Foundation action differs from its own-unit observation')
        elif world_v4 and kind in world.WORLD_KINDS:
            world.validate_action(action, width=value['world_input']['width'],
                                  height=value['world_input']['height'])
        elif orders_v5 and kind == 'unit_order':
            orders.validate_action(action)
        elif attacks_v9 and kind=='unit_attack':
            attacks.validate_action(action,value['unit_attacks']['width'],value['unit_attacks']['height'])
        elif queues_v6 and kind in queues.FIELDS:
            queues.validate_action(action)
        elif placements_v7 and kind in placement.ACTION_FIELDS:
            placement.validate_action(action,player_id=player_id)
        elif city_shot_v13 and kind == 'city_range_attack':
            city_ranged.city_validate_action(action, shots['width'], shots['height'])
        elif district_shot_v14 and kind == 'district_range_attack':
            city_ranged.district_validate_action(action, district_shots['width'], district_shots['height'])
        elif unit_work_v15 and kind in unit_work.NETWORK_ACTION_FIELDS:
            unit_work.validate_action(action)
        elif purchase_v20 and kind == 'purchase':
            plot_purchases.validate_purchase_action(action)
        elif promotion_v22 and kind == 'promote_unit':
            unit_promotions.validate_action(action)
        elif upgrade_v23 and kind == 'upgrade_unit':
            unit_upgrades.validate_action(action)
        elif city_controls_v12 and kind in city_controls.ACTION_FIELDS:
            city_controls.validate_action(action)
        elif not (turns_v3 and kind in _CAPABILITY_TURN_KINDS):
            validate_action(action, own_cities)
        candidate_id = row['candidate_id']
        if (type(candidate_id) is not str or candidate_id != digest(action)
                or candidate_id in seen):
            raise ValueError('Duplicate or mismatched capability candidate identity')
        seen.add(candidate_id)
        by_family[kind].append(candidate_id)
    if any(families[name]['candidate_ids'] != ids for name, ids in by_family.items()):
        raise ValueError('Completed family query does not exactly cover its candidates')
    if world_v4:
        validate_action_count([row['action'] for row in candidates],
                              world_input=value['world_input'], map_coordinates=True)
        world.validate_candidates(value['world_input'], candidates)
    if orders_v5:
        orders.validate_candidates(value['unit_orders'], candidates)
    if queues_v6:
        queues.validate_candidates(value['production_queues'],candidates)
    if placements_v7:
        placement.validate_candidates(value['placement_offers'],candidates)
    if attacks_v9:
        attacks.validate_candidates(value['unit_attacks'],candidates)
    if city_shot_v13:
        offered = [row['action'] for row in candidates if row['action']['kind'] == 'city_range_attack']
        if offered != ([] if shots is None else city_ranged.city_actions(shots)):
            raise ValueError('City-shot candidates differ from their native catalogue')
    if district_shot_v14:
        offered = [row['action'] for row in candidates if row['action']['kind'] == 'district_range_attack']
        if offered != ([] if district_shots is None else city_ranged.district_actions(district_shots)):
            raise ValueError('District-shot candidates differ from their native catalogue')
    if promotion_v22:
        offered = [row['action'] for row in candidates if row['action']['kind'] == 'promote_unit']
        if offered != ([] if promotion_catalogue is None else promotion_catalogue['offers']):
            raise ValueError('Promotion candidates differ from their native catalogue')
    if upgrade_v23:
        offered = [row['action'] for row in candidates if row['action']['kind'] == 'upgrade_unit']
        if offered != ([] if upgrade_catalogue is None else unit_upgrades.actions(upgrade_catalogue)):
            raise ValueError('Upgrade candidates differ from their native catalogue')
    if unit_work_v15:
        offered = [row['action'] for row in candidates if row['action']['kind'] in unit_work.NETWORK_ACTION_FIELDS]
        if offered != ([] if work_catalogue is None else unit_work.actions(work_catalogue)):
            raise ValueError('Unit-work candidates differ from their native catalogue')
    if purchase_v20:
        offered = [row['action'] for row in candidates if row['action']['kind'] == 'purchase']
        expected = [] if purchases is None else plot_purchases.actions(purchases)
        if city_purchases is not None:
            expected.extend(plot_purchases.actions(city_purchases))
        if offered != expected:
            raise ValueError('Purchase candidates differ from their native catalogue')
    if turns_v3:
        for kind, available in availability.items():
            family = families[kind]
            # This joins provider results, never reconstructs native predicates
            # from UI controls or removes a choice for strategic reasons.
            if available is None:
                if family['status'] != 'unqualified':
                    raise ValueError('Unqueried turn availability must remain unqualified')
            elif (family['status'] != 'queried_complete'
                    or len(family['candidate_ids']) != int(available)):
                raise ValueError('Native turn availability differs from its exact choices')
    return value


def select_capability(value, selection):
    """Resolve an exact choice from an already validated capability catalogue."""
    if (not is_capability_catalogue(value) or type(selection) is not dict
            or set(selection) != {'decision_id', 'candidate_id'}
            or selection['decision_id'] != value['decision_id']
            or type(selection['candidate_id']) is not str):
        raise ValueError('Malformed or stale capability selection')
    matches = [row['action'] for row in value['candidates']
               if row['candidate_id'] == selection['candidate_id']]
    if len(matches) != 1:
        raise ValueError('Choice is absent from the completed family queries')
    return copy.deepcopy(matches[0])


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'),
                     ensure_ascii=True, allow_nan=False).encode('ascii')
    return hashlib.sha256(raw).hexdigest()


def _checkpoint_attack_gap_projection(current, saved, projected):
    """Compare an older receipt without rewriting its omitted audit limitation.

    This changes only the comparison copy. Current/live catalogues must still
    list every current gap; the ordinary validator never accepts the old list.
    """
    from .capability_unit_attacks import UNQUALIFIED_UNIT_ATTACKS
    added='native_legal_targets_without_visible_witness'
    full=list(UNQUALIFIED_UNIT_ATTACKS)
    old=[gap for gap in full if gap!=added]
    previous=saved.get('families',{}).get('unit_attack',{})
    live=current.get('families',{}).get('unit_attack',{})
    if (previous.get('status')=='queried_partial' and previous.get('unqualified')==old
            and live.get('status')=='queried_partial' and live.get('unqualified')==full):
        projected['families']['unit_attack']['unqualified']=old
        return ['unit_attack.'+added]
    return []


def _checkpoint_busy_attack_projection(current, saved, projected):
    """Exclude only newly exposed busy-unit attacks from a comparison copy.

    Public state is never projected. The caller still compares every field and
    the full observation. Missing historical actions and changes to an existing
    offer remain errors; this does not filter live candidates or native legality.
    """
    previous={row['candidate_id']:row['action'] for row in saved['candidates']}
    live={row['candidate_id']:row['action'] for row in current['candidates']}
    if any(key not in live or live[key]!=action for key,action in previous.items()):
        raise ValueError('Combat readiness transition lost a historical action')
    rows=current['unit_orders']
    ready={} if rows is None else {row['unit_id']:row['ready'] for row in rows['units']}
    added=[row for row in current['candidates'] if row['candidate_id'] not in previous]
    if any(row['action']['kind']!='unit_attack'
           or ready.get(row['action']['unit_id']) is not False for row in added):
        raise ValueError('Combat readiness transition added an action outside not-ready units')
    # Readiness/queues cannot be changed to justify an added choice. All other
    # state remains untouched for the caller's exact join.
    if current['unit_orders']!=saved['unit_orders'] or current['queued_orders']!=saved['queued_orders']:
        raise ValueError('Combat readiness transition changed public readiness or queues')
    ids={row['candidate_id'] for row in added}
    projected['candidates']=[row for row in projected['candidates'] if row['candidate_id'] not in ids]
    family=projected['families']['unit_attack']
    if 'candidate_ids' in family:
        family['candidate_ids']=[key for key in family['candidate_ids'] if key not in ids]
    if projected['unit_attacks'] is not None:
        projected['unit_attacks']['offers']=[action for action in projected['unit_attacks']['offers']
                                            if digest(action) not in ids]
    return copy.deepcopy(added)


def checkpoint_catalogue(current, saved, observation, *, production_evidence=None, combat_evidence=None, combat_source_sha256=None, combat_readiness_source_sha256=None, core_sha256=None):
    """Explicit source-bound readback transitions; never rewrite old data.

    All historical fields/actions still have to compare exactly in the caller.
    New families and the proven not-ready unit attack offers are excluded only
    from a validated comparison copy. Other schema changes remain mismatches.
    """
    precision_pin,readiness_pin=(combat_checkpoint_sources(core_sha256)
        if core_sha256 is None or core_sha256 in (_XP1_COMBAT_CORE,_XP2_COMBAT_CORE)
        else (None,None))
    if core_sha256 is not None and core_sha256 not in (_XP1_COMBAT_CORE,_XP2_COMBAT_CORE,
            'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
        raise ValueError('Unknown checkpoint transition engine')
    additions = {
        CAPABILITY_XP2_STRATEGIC_RESOURCES_SCHEMA: (CAPABILITY_XP2_UNIT_UPGRADE_SCHEMA, 'strategic_resources'),
        CAPABILITY_CURRENT_PRODUCTION_SCHEMA: (CAPABILITY_UNIT_WORK_INFO_SCHEMA, 'production_current'),
        CAPABILITY_UNIT_WORK_INFO_SCHEMA: (CAPABILITY_UNIT_WORK_STATE_SCHEMA, 'unit_work_info'),
        CAPABILITY_UNIT_WORK_STATE_SCHEMA: (CAPABILITY_UNIT_WORK_SCHEMA, 'unit_work_state'),
    }
    current_schema = current.get('schema')
    if current_schema in (CAPABILITY_XP2_PLOT_PURCHASE_SCHEMA, CAPABILITY_XP2_CITY_PURCHASE_SCHEMA,
                          CAPABILITY_XP2_PROMOTION_SCHEMA, CAPABILITY_XP2_UNIT_UPGRADE_SCHEMA
                          ) and saved.get('schema') != current_schema:
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('This checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        del projected['decision_id']
        if current_schema == CAPABILITY_XP2_UNIT_UPGRADE_SCHEMA:
            projected['schema'] = CAPABILITY_XP2_PROMOTION_SCHEMA
            del projected['unit_upgrades'], projected['families']['upgrade_unit']
            projected['candidates'] = [row for row in projected['candidates']
                                       if row['action']['kind'] != 'upgrade_unit']
            added = 'upgrade_unit'
        elif current_schema == CAPABILITY_XP2_PROMOTION_SCHEMA:
            projected['schema'] = CAPABILITY_XP2_CITY_PURCHASE_SCHEMA
            del projected['unit_promotions'], projected['families']['promote_unit']
            projected['candidates'] = [row for row in projected['candidates']
                                       if row['action']['kind'] != 'promote_unit']
            added = 'promote_unit'
        elif current_schema == CAPABILITY_XP2_CITY_PURCHASE_SCHEMA:
            from .plot_purchases import GAPS
            projected['schema'] = CAPABILITY_XP2_PLOT_PURCHASE_SCHEMA
            del projected['city_purchases']
            removed = {row['candidate_id'] for row in projected['candidates']
                       if row['action']['kind'] == 'purchase' and 'plot_id' not in row['action']}
            family = projected['families']['purchase']
            if family['status'] == 'queried_partial':
                family['unqualified'] = list(GAPS)
                family['candidate_ids'] = [key for key in family['candidate_ids'] if key not in removed]
            projected['candidates'] = [row for row in projected['candidates'] if row['candidate_id'] not in removed]
            added = 'standard_gold_unit_building_purchase'
        else:
            projected['schema'] = CAPABILITY_XP2_UNIT_SKIP_SCHEMA
            del projected['plot_purchases'], projected['families']['purchase']
            projected['candidates'] = [row for row in projected['candidates'] if row['action']['kind'] != 'purchase']
            added = 'purchase'
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_action_families'] = transition.get('added_action_families', []) + [added]
        return projected, transition
    if current_schema == CAPABILITY_XP2_UNIT_SKIP_SCHEMA and saved.get('schema') != current_schema:
        from types import SimpleNamespace
        from .capability_unit_orders import SKIP_TURN

        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Skip-turn checkpoint transition requires Gathering Storm')
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        if projected['unit_orders'] is not None:
            orders = projected['unit_orders']['offers']
            removed = {digest(row['action']) for row in orders if row['action']['item_type'] == SKIP_TURN}
            projected['unit_orders']['offers'] = [row for row in orders if digest(row['action']) not in removed]
            projected['candidates'] = [row for row in projected['candidates'] if row['candidate_id'] not in removed]
            family = projected['families']['unit_order']
            family['candidate_ids'] = [key for key in family['candidate_ids'] if key not in removed]
        projected['schema'] = CAPABILITY_CURRENT_PRODUCTION_SCHEMA
        del projected['decision_id']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current_schema,
                          historical_fields_unchanged=True, added_unit_order=SKIP_TURN)
        return projected, transition
    if current_schema in additions and saved.get('schema') != current_schema:
        previous_schema, added_field = additions[current_schema]
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Public information checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = {key: item for key, item in current.items() if key not in (added_field, 'decision_id')}
        projected['schema'] = previous_schema
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current['schema'],
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + [added_field]
        return projected, transition
    if current.get('schema') == CAPABILITY_UNIT_WORK_SCHEMA and saved.get('schema') != CAPABILITY_UNIT_WORK_SCHEMA:
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Unit-work checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace
        from .unit_work import NETWORK_ACTION_FIELDS
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        del projected['unit_work']
        projected['schema'] = CAPABILITY_DISTRICT_SHOT_SCHEMA
        projected['candidates'] = [row for row in projected['candidates']
                                   if row['action']['kind'] not in NETWORK_ACTION_FIELDS]
        for kind in NETWORK_ACTION_FIELDS:
            del projected['families'][kind]
        del projected['decision_id']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current['schema'],
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + ['unit_work']
        transition['added_action_families'] = transition.get('added_action_families', []) + list(NETWORK_ACTION_FIELDS)
        return projected, transition
    if current.get('schema') == CAPABILITY_DISTRICT_SHOT_SCHEMA and saved.get('schema') != CAPABILITY_DISTRICT_SHOT_SCHEMA:
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('District-shot checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace
        from .city_ranged import LAN_UNQUALIFIED_REASON
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        del projected['district_shots']
        projected['schema'] = CAPABILITY_CITY_SHOT_SCHEMA
        projected['candidates'] = [row for row in projected['candidates']
                                   if row['action']['kind'] != 'district_range_attack']
        projected['families']['district_range_attack'] = dict(status='unqualified', reason=LAN_UNQUALIFIED_REASON)
        del projected['decision_id']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current['schema'],
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + ['district_shots']
        transition['added_action_families'] = transition.get('added_action_families', []) + ['district_range_attack']
        return projected, transition
    if current.get('schema') == CAPABILITY_CITY_SHOT_SCHEMA and saved.get('schema') != CAPABILITY_CITY_SHOT_SCHEMA:
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('City-shot checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace
        from .city_ranged import LAN_UNQUALIFIED_REASON
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        del projected['city_shots']
        projected['schema'] = (CAPABILITY_CITY_CONTROLS_SCHEMA if 'city_focus_catalogs' in projected
                               else CAPABILITY_COMBAT_READINESS_SCHEMA)
        projected['candidates'] = [row for row in projected['candidates']
                                   if row['action']['kind'] != 'city_range_attack']
        if 'city_range_attack' in saved['families']:
            projected['families']['city_range_attack'] = dict(status='unqualified', reason=LAN_UNQUALIFIED_REASON)
        else:
            del projected['families']['city_range_attack']
        del projected['decision_id']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current['schema'],
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + ['city_shots']
        transition['added_action_families'] = transition.get('added_action_families', []) + ['city_range_attack']
        return projected, transition
    if (current.get('schema')==CAPABILITY_COMBAT_READINESS_SCHEMA
            and saved.get('schema') in (CAPABILITY_COMBAT_PUBLIC_SCHEMA,
                CAPABILITY_UNIT_ATTACKS_SCHEMA,CAPABILITY_PLACEMENT_INVENTORY_SCHEMA,
                CAPABILITY_PLACEMENT_SCHEMA,CAPABILITY_PRODUCTION_QUEUE_SCHEMA,
                CAPABILITY_UNIT_ORDERS_SCHEMA)):
        from types import SimpleNamespace
        if combat_readiness_source_sha256!=readiness_pin:
            raise ValueError('Combat readiness transition requires its selected source pin')
        if core_sha256==_XP2_COMBAT_CORE and combat_source_sha256!=precision_pin:
            raise ValueError('XP2 combat transition requires its selected precision source pin')
        identity=SimpleNamespace(episode_id=current['episode_id'],game_generation=current['game_generation'])
        validate_capability_catalogue(current,identity,current['sequence'],observation['turn'],
            player_id=observation['player_id'],observation=observation)
        raw=None
        if saved['schema']==CAPABILITY_UNIT_ATTACKS_SCHEMA and current['unit_attacks'] is not None:
            from .capability_unit_attacks import PUBLIC_PRECISION_SHA256
            from .information import validate_administrative
            if combat_source_sha256!=precision_pin:
                raise ValueError('Legacy combat checkpoint requires its selected precision source pin')
            # Authenticate against the actual v11 response, before changing its
            # schema or excluding any offers from the historical comparison.
            response=dict(episode_id=current['episode_id'],game_generation=current['game_generation'],
                sequence=current['sequence'],observation=observation,decisions=current)
            raw=validate_administrative('combat',combat_evidence,response,
                                         source_sha256=combat_source_sha256)
        projected=copy.deepcopy(current)
        added=[]
        if saved['schema'] in (CAPABILITY_UNIT_ATTACKS_SCHEMA,CAPABILITY_COMBAT_PUBLIC_SCHEMA):
            added=_checkpoint_busy_attack_projection(current,saved,projected)
            added_gaps=_checkpoint_attack_gap_projection(current,saved,projected)
            projected.pop('decision_id');projected['schema']=saved['schema']
            if raw is not None:
                projected['unit_attacks']['cities']=copy.deepcopy(raw['cities'])
            projected['decision_id']=digest(projected)
            transition=dict(source_schema=saved['schema'],target_schema=CAPABILITY_COMBAT_READINESS_SCHEMA,
                added_public_fields=[],added_action_families=[],added_unqualified_routes=added_gaps,
                added_unit_attack_candidates=added,
                readiness_source_sha256=combat_readiness_source_sha256,
                historical_fields_unchanged=True)
            if saved['schema']==CAPABILITY_UNIT_ATTACKS_SCHEMA:
                transition.update(changed_public_fields=['unit_attacks.cities.defense_strength'],
                    legacy_raw_values_compared_from_administrative_readback=raw is not None,
                    precision_source_sha256=combat_source_sha256 if raw is not None else None)
            return projected,transition
        # Earlier checkpoints contain no attacks. Preserve their existing
        # validated family-addition chain without reconstructing raw values.
        projected.pop('decision_id');projected['schema']=CAPABILITY_COMBAT_PUBLIC_SCHEMA
        projected['decision_id']=digest(projected)
        projected,prior=checkpoint_catalogue(projected,saved,observation,
            production_evidence=production_evidence,combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,core_sha256=core_sha256)
        transition=dict(prior or {})
        transition.update(source_schema=saved['schema'],target_schema=CAPABILITY_COMBAT_READINESS_SCHEMA,
            added_unit_attack_candidates=added,
            readiness_source_sha256=combat_readiness_source_sha256,
            historical_fields_unchanged=True)
        transition.setdefault('added_public_fields',[])
        transition.setdefault('added_action_families',[])
        return projected,transition
    if (current.get('schema')==saved.get('schema')==CAPABILITY_COMBAT_PUBLIC_SCHEMA):
        projected=copy.deepcopy(current)
        added=_checkpoint_attack_gap_projection(current,saved,projected)
        if added:
            from types import SimpleNamespace
            identity=SimpleNamespace(episode_id=current['episode_id'],game_generation=current['game_generation'])
            validate_capability_catalogue(current,identity,current['sequence'],observation['turn'],
                player_id=observation['player_id'],observation=observation)
            projected.pop('decision_id');projected['decision_id']=digest(projected)
            return projected,dict(source_schema=saved['schema'],target_schema=current['schema'],
                added_public_fields=[],added_action_families=[],added_unqualified_routes=added,
                historical_fields_unchanged=True)
    if (current.get('schema')==CAPABILITY_COMBAT_PUBLIC_SCHEMA
            and saved.get('schema') in (CAPABILITY_UNIT_ATTACKS_SCHEMA,
                CAPABILITY_PLACEMENT_INVENTORY_SCHEMA,CAPABILITY_PLACEMENT_SCHEMA,
                CAPABILITY_PRODUCTION_QUEUE_SCHEMA,CAPABILITY_UNIT_ORDERS_SCHEMA)):
        from types import SimpleNamespace
        identity=SimpleNamespace(episode_id=current['episode_id'],game_generation=current['game_generation'])
        validate_capability_catalogue(current,identity,current['sequence'],observation['turn'],
            player_id=observation['player_id'],observation=observation)
        projected=copy.deepcopy(current);projected.pop('decision_id')
        if saved['schema']==CAPABILITY_UNIT_ATTACKS_SCHEMA:
            # v9 stored raw cities. Recover them from this exact live native
            # boundary, never invert rounding or change the historical receipt.
            if current['unit_attacks'] is not None:
                from .capability_unit_attacks import PUBLIC_PRECISION_SHA256
                from .information import validate_administrative
                if combat_source_sha256!=precision_pin:
                    raise ValueError('Legacy combat checkpoint requires its selected precision source pin')
                response=dict(episode_id=current['episode_id'],game_generation=current['game_generation'],
                    sequence=current['sequence'],observation=observation,decisions=current)
                raw=validate_administrative('combat',combat_evidence,response,
                                             source_sha256=combat_source_sha256)
                projected['unit_attacks']['cities']=copy.deepcopy(raw['cities'])
            added_gaps=_checkpoint_attack_gap_projection(current,saved,projected)
            projected['schema']=CAPABILITY_UNIT_ATTACKS_SCHEMA
            projected['decision_id']=digest(projected)
            return projected,dict(source_schema=saved['schema'],target_schema=CAPABILITY_COMBAT_PUBLIC_SCHEMA,
                added_public_fields=[],added_action_families=[],
                changed_public_fields=['unit_attacks.cities.defense_strength'],
                added_unqualified_routes=added_gaps,
                legacy_raw_values_compared_from_administrative_readback=current['unit_attacks'] is not None,
                precision_source_sha256=combat_source_sha256 if current['unit_attacks'] is not None else None,
                historical_fields_unchanged=True)
        # Older checkpoints have no combat field; no native raw value is needed
        # to remove the entire newly added family after full v10 validation.
        projected.pop('unit_attacks')
        projected['families'].pop('unit_attack')
        retained_xp2_family=(core_sha256==_XP2_COMBAT_CORE
            and saved['schema']==CAPABILITY_PLACEMENT_INVENTORY_SCHEMA)
        if retained_xp2_family:
            old=saved['families'].get('unit_attack')
            if old!={'status':'unqualified','reason':'xp2_family_profile_not_yet_qualified'}:
                raise ValueError('XP2 v8 combat transition has another historical family')
            projected['families']['unit_attack']=copy.deepcopy(old)
        projected['candidates']=[r for r in projected['candidates'] if r['action']['kind']!='unit_attack']
        projected['schema']=CAPABILITY_PLACEMENT_INVENTORY_SCHEMA
        projected['decision_id']=digest(projected)
        projected,prior=checkpoint_catalogue(projected,saved,observation,core_sha256=core_sha256)
        result=dict(source_schema=saved['schema'],target_schema=CAPABILITY_COMBAT_PUBLIC_SCHEMA,
            added_public_fields=([] if prior is None else prior['added_public_fields'])+['unit_attacks'],
            added_action_families=([] if prior is None else prior['added_action_families'])+['unit_attack'],
            historical_fields_unchanged=True)
        if retained_xp2_family:
            result.update(added_action_families=[],changed_action_families=['unit_attack'],
                retained_unqualified_families=['unit_attack'],core_sha256=core_sha256,
                precision_source_sha256=precision_pin)
        return projected,result
    capability_additions={
        CAPABILITY_UNIT_ATTACKS_SCHEMA:(CAPABILITY_PLACEMENT_INVENTORY_SCHEMA,
            ('unit_attacks',),('unit_attack',)),
        CAPABILITY_PLACEMENT_INVENTORY_SCHEMA:(CAPABILITY_PLACEMENT_SCHEMA,
            ('placement_inventory',),()),
        CAPABILITY_PLACEMENT_SCHEMA:(CAPABILITY_PRODUCTION_QUEUE_SCHEMA,
            ('placements','placement_offers','placement_observation_scope'),('production_placement','production_resume')),
        CAPABILITY_PRODUCTION_QUEUE_SCHEMA:(CAPABILITY_UNIT_ORDERS_SCHEMA,
            ('production_queues',),('queue_append','queue_remove','queue_swap')),
    }
    current_schema,saved_schema=current.get('schema'),saved.get('schema')
    if (current_schema in capability_additions
            and (saved_schema in (CAPABILITY_UNIT_ORDERS_SCHEMA,CAPABILITY_PRODUCTION_QUEUE_SCHEMA)
                 or current_schema==CAPABILITY_PLACEMENT_INVENTORY_SCHEMA and saved_schema==CAPABILITY_PLACEMENT_SCHEMA
                 or current_schema==CAPABILITY_UNIT_ATTACKS_SCHEMA and saved_schema in (CAPABILITY_PLACEMENT_SCHEMA,CAPABILITY_PLACEMENT_INVENTORY_SCHEMA))
            and current_schema!=saved_schema):
        from types import SimpleNamespace
        identity=SimpleNamespace(episode_id=current['episode_id'],game_generation=current['game_generation'])
        validate_capability_catalogue(current,identity,current['sequence'],observation['turn'],
                                      player_id=observation['player_id'],observation=observation)
        previous,fields,actions=capability_additions[current_schema]
        projected={k:v for k,v in current.items() if k not in (*fields,'decision_id')}
        projected['families']={k:v for k,v in current['families'].items() if k not in actions}
        projected['candidates']=[r for r in current['candidates'] if r['action']['kind'] not in actions]
        projected['schema']=previous;projected['decision_id']=digest(projected)
        projected,prior=checkpoint_catalogue(projected,saved,observation,core_sha256=core_sha256)
        return projected,dict(source_schema=saved_schema,target_schema=current_schema,
            added_public_fields=([] if prior is None else prior['added_public_fields'])+list(fields),
            added_action_families=([] if prior is None else prior['added_action_families'])+list(actions),
            historical_fields_unchanged=True)
    if current.get('schema')==PRODUCTION_SCHEMA and saved.get('schema') in (SCHEMA,WORK_SCHEMA,INFO_SCHEMA,GROWTH_SCHEMA):
        projected={k:v for k,v in current.items() if k!='decision_id'}
        if current.get('base_schema') is not None and current['base_schema'] not in DIALOGUE_SCHEMAS:
            from .production_inputs import project_quotes,validate_current
            e=production_evidence
            if (type(e) is not dict or e.get('actor_channel') is not False
                    or any(type(e.get(k)) is not type(current.get(k)) or e[k]!=current[k]
                           for k in ('episode_id','game_generation','player_id','sequence','turn'))):
                raise ValueError('Old checkpoint requires same-boundary native production evidence')
            pid,turn=observation['player_id'],observation['turn']
            if project_quotes(e['production_info'],pid,turn,observation=observation)!=current['production_info']:
                raise ValueError('Public production quotes differ from their native evidence')
            if validate_current(e['public_production'],pid,turn,observation=observation)!=current['production']:
                raise ValueError('Current production differs from its native evidence')
            # Use actual same-boundary reads, never invented raw getter values.
            projected['production']=e['production'];projected['production_info']=e['production_info']
        projected['schema']=GROWTH_SCHEMA;projected['decision_id']=digest(projected)
        projected,prior=checkpoint_catalogue(projected,saved,observation,core_sha256=core_sha256)
        return projected,dict(source_schema=saved['schema'],target_schema=PRODUCTION_SCHEMA,
            added_public_fields=[] if prior is None else prior['added_public_fields'],
            changed_public_fields=['production','production_info'],
            legacy_raw_values_compared_from_administrative_readback=True,historical_fields_unchanged=True)
    if current.get('schema') == GROWTH_SCHEMA and saved.get('schema') in (SCHEMA,WORK_SCHEMA,INFO_SCHEMA):
        growth=current.get('city_growth')
        if growth is not None:
            from .city_growth import validate as validate_growth
            validate_growth(growth,observation['player_id'],observation['turn'],observation=observation)
        elif current.get('base_schema') is not None and current.get('base_schema') not in DIALOGUE_SCHEMAS:
            raise ValueError('Checkpoint catalogue upgrade lacks public city growth')
        projected={k:v for k,v in current.items() if k not in ('city_growth','decision_id')}
        projected['schema']=INFO_SCHEMA
        projected['decision_id']=digest(projected)
        projected,prior=checkpoint_catalogue(projected,saved,observation,core_sha256=core_sha256)
        return projected,dict(source_schema=saved['schema'],target_schema=GROWTH_SCHEMA,
            added_public_fields=([] if prior is None else prior['added_public_fields'])+['city_growth'],
            historical_fields_unchanged=True)
    if current.get('schema') == INFO_SCHEMA and saved.get('schema') in (SCHEMA,WORK_SCHEMA):
        info=current.get('unit_work_info')
        if info is not None:
            from .unit_work_info import validate as validate_work_info
            validate_work_info(info,observation['player_id'],observation['turn'],
                observation=observation,work_catalog=current.get('unit_work'))
        elif current.get('base_schema') is not None and current.get('base_schema') not in DIALOGUE_SCHEMAS:
            raise ValueError('Checkpoint catalogue upgrade lacks its current work information')
        projected={k:v for k,v in current.items() if k not in ('unit_work_info','decision_id')}
        projected['schema']=WORK_SCHEMA
        projected['decision_id']=digest(projected)
        projected,prior=checkpoint_catalogue(projected,saved,observation,core_sha256=core_sha256)
        return projected,dict(source_schema=saved['schema'],target_schema=INFO_SCHEMA,
            added_public_fields=([] if prior is None else prior['added_public_fields'])+['unit_work_info'],
            historical_fields_unchanged=True)
    if current.get('schema') == WORK_SCHEMA and saved.get('schema') == SCHEMA:
        state = current.get('unit_work_state')
        if state is not None:
            from .unit_work_state import validate as validate_work_state
            validate_work_state(state,observation['player_id'],observation['turn'],
                observation=observation,work_catalog=current.get('unit_work'))
        elif current.get('base_schema') is not None and current.get('base_schema') not in DIALOGUE_SCHEMAS:
            raise ValueError('Checkpoint catalogue upgrade lacks its current own-unit state')
        projected = {key:item for key,item in current.items() if key not in ('unit_work_state','decision_id')}
        projected['schema'] = SCHEMA
        projected['decision_id'] = digest(projected)
        return projected, dict(source_schema=SCHEMA,target_schema=WORK_SCHEMA,
            added_public_fields=['unit_work_state'],historical_fields_unchanged=True)
    if core_sha256 == _XP2_COMBAT_CORE and is_capability_catalogue(current) and is_capability_catalogue(saved):
        from .city_ranged import LAN_UNQUALIFIED_KINDS, LAN_UNQUALIFIED_REASON
        additions = {kind for kind in LAN_UNQUALIFIED_KINDS
                     if kind not in saved['families'] and current['families'].get(kind) ==
                     {'status': 'unqualified', 'reason': LAN_UNQUALIFIED_REASON}}
        if additions:
            from types import SimpleNamespace
            identity = SimpleNamespace(episode_id=current['episode_id'],
                                       game_generation=current['game_generation'])
            validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                          player_id=observation['player_id'], observation=observation)
            projected = {key: item for key, item in current.items() if key != 'decision_id'}
            projected['families'] = {kind: family for kind, family in current['families'].items()
                                     if kind not in additions}
            projected['decision_id'] = digest(projected)
            return projected, dict(source_schema=saved['schema'], target_schema=current['schema'],
                added_public_fields=[], added_action_families=[],
                added_unqualified_families=sorted(additions), historical_fields_unchanged=True)
    return current, None


def validate_turn_controls(value, player_id, turn):
    fields = {'schema', 'player_id', 'turn', 'active', 'active_complete',
              'can_unready', 'timer_elapsed'}
    if type(value) is not dict or set(value) != fields:
        raise ValueError('Unexpected LAN turn-control fields')
    if (value['schema'] != TURN_CONTROLS_SCHEMA
            or type(value['player_id']) is not int or value['player_id'] != player_id
            or type(value['turn']) is not int or value['turn'] != turn
            or type(value['active']) is not bool
            or type(value['active_complete']) is not bool
            or type(value['can_unready']) is not bool
            or (value['timer_elapsed'] is not None
                and type(value['timer_elapsed']) is not bool)):
        raise ValueError('Invalid LAN turn-control values')
    return value


def is_waiting(controls):
    """Whether this actor needs only a native turn-control catalogue."""
    return (controls['can_unready']
            or not (controls['active'] and controls['active_complete']))


def unready_action_available(controls, *, actions_closed=False):
    if type(actions_closed) is not bool:
        raise ValueError('Action closure must be an exact boolean')
    return (not actions_closed and controls['can_unready']
            and controls['timer_elapsed'] is False)


def validate_catalogue(value, identity, sequence, turn, *, player_id,
                       actions_closed=False, observation=None):
    """Validate wrapper shape/digests and return its legacy base catalogue.

    A ``None`` result means the actor is waiting and the catalogue contains
    only turn controls. A dictionary result is the reconstructed, digest-bound
    legacy catalogue; the caller must pass it to native ``validate_decisions``.
    The explicit capability schema instead returns its validated catalogue;
    callers must route it with ``is_capability_catalogue``, not as legacy data.
    """
    if is_capability_catalogue(value):
        return validate_capability_catalogue(value, identity, sequence, turn,
            player_id=player_id, actions_closed=actions_closed, observation=observation)
    if type(actions_closed) is not bool:
        raise ValueError('Action closure must be an exact boolean')
    if type(value) is not dict or value.get('schema') not in SUPPORTED_SCHEMAS:
        raise ValueError('Unknown network decision catalogue schema')
    if value['schema'] == LEGACY_SCHEMA and 'diplomacy_overview' in value:
        raise ValueError('Initial diplomacy requires network-decisions.v2')
    if (value.get('episode_id') != identity.episode_id
            or value.get('game_generation') != identity.game_generation
            or type(value.get('sequence')) is not int or value['sequence'] != sequence
            or type(value.get('player_id')) is not int or value['player_id'] != player_id
            or type(value.get('turn')) is not int or value['turn'] != turn
            or type(value.get('complete_action_space')) is not bool
            or value['complete_action_space'] is not False
            or type(value.get('unsupported')) is not list
            or any(type(item) is not str for item in value['unsupported'])
            or type(value.get('player_map')) is not dict
            or type(value.get('candidates')) is not list):
        raise ValueError('Foreign or malformed network decision catalogue')
    controls = validate_turn_controls(value.get('turn_controls'), player_id, turn)
    if type(value.get('decision_id')) is not str or value['decision_id'] != digest(
            {key: item for key, item in value.items() if key != 'decision_id'}):
        raise ValueError('Network decision catalogue digest differs')

    base_schema = value.get('base_schema')
    work_state = value.get('unit_work_state')
    if value['schema'] in WORK_SCHEMAS:
        if 'unit_work_state' not in value:
            raise ValueError('Network v4 requires explicit unit-work state availability')
        if base_schema is None or base_schema in DIALOGUE_SCHEMAS:
            if work_state is not None:
                raise ValueError('Waiting/modal unit-work state is not qualified')
        else:
            from .unit_work_state import validate as validate_work_state
            validate_work_state(work_state,player_id,turn,work_catalog=value.get('unit_work'))
    elif 'unit_work_state' in value:
        raise ValueError('Unit-work state requires network-decisions.v4')
    if value['schema'] in INFO_SCHEMAS:
        if 'unit_work_info' not in value:
            raise ValueError('Network v5 requires explicit unit-work information availability')
        if base_schema is None or base_schema in DIALOGUE_SCHEMAS:
            if value['unit_work_info'] is not None:
                raise ValueError('Waiting/modal unit-work information is not qualified')
        else:
            from .unit_work_info import validate as validate_work_info
            validate_work_info(value['unit_work_info'],player_id,turn,work_catalog=value.get('unit_work'))
    elif 'unit_work_info' in value:
        raise ValueError('Unit-work information requires network-decisions.v5')
    if value['schema'] in GROWTH_SCHEMAS:
        if 'city_growth' not in value:raise ValueError('Network v6 requires explicit city-growth availability')
        if base_schema is None or base_schema in DIALOGUE_SCHEMAS:
            if value['city_growth'] is not None:raise ValueError('Waiting/modal city-growth projection is not qualified')
        else:
            from .city_growth import validate as validate_growth
            validate_growth(value['city_growth'],player_id,turn)
    elif 'city_growth' in value:
        raise ValueError('City growth requires network-decisions.v6')
    if base_schema is None:
        fields = (_WAITING_FIELDS | ({'unit_work_state'} if value['schema'] in WORK_SCHEMAS else set())
                  | ({'unit_work_info'} if value['schema'] in INFO_SCHEMAS else set())
                  | ({'city_growth'} if value['schema'] in GROWTH_SCHEMAS else set()))
        if set(value) != fields or not is_waiting(controls):
            raise ValueError('Waiting catalogue fields or turn-control phase differ')
        expected = []
        if unready_action_available(controls, actions_closed=actions_closed):
            action = {'kind': 'unready_turn'}
            expected = [dict(candidate_id=digest(action), action=action)]
        if value['candidates'] != expected:
            raise ValueError('Waiting catalogue offers an unavailable turn control')
        return None

    if type(base_schema) is not str or not base_schema:
        raise ValueError('Legacy catalogue schema must be an exact nonempty string')
    if value['schema']==PRODUCTION_SCHEMA and base_schema not in DIALOGUE_SCHEMAS:
        from .production_inputs import validate_current,validate_quotes
        validate_current(value.get('production'),player_id,turn,queues=value.get('production_queues'))
        validate_quotes(value.get('production_info'),player_id,turn,
                        candidates=value['candidates'],ended=actions_closed)
    dialogue = base_schema in DIALOGUE_SCHEMAS
    if is_waiting(controls) and not dialogue:
        raise ValueError('Waiting actor must use the turn-control catalogue')
    overview = value.get('diplomacy_overview')
    expected_initial = []
    if overview is not None:
        from .diplomacy_overview import validate as validate_overview, candidates
        if dialogue:
            raise ValueError('A pending dialogue cannot offer initial session actions')
        validate_overview(overview, player_id, turn)
        if not actions_closed:
            expected_initial = [dict(candidate_id=digest(action), action=action)
                                for action in candidates(overview)]
    elif 'diplomacy_overview' in value:
        raise ValueError('Missing diplomacy overview body')
    actual_initial = []
    legacy = {key: item for key, item in value.items()
              if key not in ('base_schema', 'turn_controls', 'decision_id', 'diplomacy_overview', 'unit_work_state','unit_work_info','city_growth')}
    legacy['schema'] = base_schema
    legacy['candidates'] = []
    for candidate in value['candidates']:
        if (type(candidate) is not dict or set(candidate) != {'candidate_id', 'action'}
                or type(candidate['candidate_id']) is not str
                or type(candidate['action']) is not dict):
            raise ValueError('Malformed network candidate')
        action = candidate['action']
        if dialogue and action.get('kind') != 'diplomacy_response':
            raise ValueError('Modal dialogue cannot offer unrelated LAN commands')
        if action.get('kind') == 'unready_turn':
            raise ValueError('Acting catalogue cannot offer unavailable Unready')
        if action.get('kind') == 'diplomacy_initiate':
            actual_initial.append(candidate)
            continue
        legacy['candidates'].append(candidate)
    if actual_initial != expected_initial:
        raise ValueError('Initial diplomacy choices differ from the public overview')
    from .action_budget import validate_action_count
    validate_action_count([row['action'] for row in legacy['candidates']],
                          world_input=value.get('world_input'),
                          map_coordinates=value['schema'] in MAP_SCHEMAS)
    legacy['decision_id'] = digest({key: item for key, item in legacy.items()
                                    if key != 'decision_id'})
    return legacy


__all__ = ['SCHEMA', 'WORK_SCHEMA', 'WORK_SCHEMAS', 'INFO_SCHEMA', 'INFO_SCHEMAS','GROWTH_SCHEMA','LATEST_SCHEMA', 'MAP_SCHEMAS', 'PREVIOUS_SCHEMA', 'LEGACY_SCHEMA', 'SUPPORTED_SCHEMAS',
           'TURN_CONTROLS_SCHEMA', 'digest', 'validate_turn_controls',
           'is_waiting', 'unready_action_available', 'validate_catalogue',
           'CAPABILITY_SCHEMA', 'CAPABILITY_CHOICES_SCHEMA', 'CAPABILITY_TURNS_SCHEMA', 'CAPABILITY_WORLD_SCHEMA', 'CAPABILITY_UNIT_ORDERS_SCHEMA', 'CAPABILITY_PRODUCTION_QUEUE_SCHEMA', 'CAPABILITY_PLACEMENT_SCHEMA', 'CAPABILITY_PLACEMENT_INVENTORY_SCHEMA', 'CAPABILITY_UNIT_ATTACKS_SCHEMA', 'CAPABILITY_COMBAT_PUBLIC_SCHEMA', 'CAPABILITY_COMBAT_READINESS_SCHEMA', 'CAPABILITY_CITY_CONTROLS_SCHEMA', 'CAPABILITY_CITY_SHOT_SCHEMA', 'CAPABILITY_DISTRICT_SHOT_SCHEMA', 'CAPABILITY_UNIT_WORK_SCHEMA', 'CAPABILITY_UNIT_WORK_STATE_SCHEMA', 'CAPABILITY_UNIT_WORK_INFO_SCHEMA', 'CAPABILITY_CURRENT_PRODUCTION_SCHEMA', 'COMBAT_READINESS_SOURCE_SHA256', 'is_capability_catalogue',
           'validate_capability_catalogue', 'select_capability']
