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
CAPABILITY_XP2_POLICIES_SCHEMA = 'civ6-host.network-capability-decisions.v25'
CAPABILITY_XP2_POLICY_UNLOCK_SCHEMA = 'civ6-host.network-capability-decisions.v26'
CAPABILITY_XP2_GOVERNMENT_SCHEMA = 'civ6-host.network-capability-decisions.v27'
CAPABILITY_XP2_POLICY_RELOCATION_SCHEMA = 'civ6-host.network-capability-decisions.v28'
CAPABILITY_XP2_POLICY_RECONFIRM_SCHEMA = 'civ6-host.network-capability-decisions.v29'
CAPABILITY_XP2_FAITH_PURCHASE_SCHEMA = 'civ6-host.network-capability-decisions.v30'
CAPABILITY_XP2_ENVOYS_SCHEMA = 'civ6-host.network-capability-decisions.v31'
CAPABILITY_XP2_GOVERNORS_SCHEMA = 'civ6-host.network-capability-decisions.v32'
CAPABILITY_XP2_INITIAL_DIPLOMACY_SCHEMA = 'civ6-host.network-capability-decisions.v33'
CAPABILITY_XP2_TRADE_SCHEMA = 'civ6-host.network-capability-decisions.v34'
CAPABILITY_XP2_ESPIONAGE_SCHEMA = 'civ6-host.network-capability-decisions.v35'
CAPABILITY_XP2_SPY_COMPLETION_SCHEMA = 'civ6-host.network-capability-decisions.v36'
CAPABILITY_XP2_WORLD_CONGRESS_SCHEMA = 'civ6-host.network-capability-decisions.v37'
CAPABILITY_XP2_WORLD_CONGRESS_REVIEW_SCHEMA = 'civ6-host.network-capability-decisions.v38'
CAPABILITY_NATIVE_COMMAND_PERMISSIONS_SCHEMA = 'civ6-host.network-capability-decisions.v39'
CAPABILITY_XP2_CONGRESS_ACTIVE_EFFECTS_SCHEMA = 'civ6-host.network-capability-decisions.v40'
CONGRESS_READ_ONLY_KINDS = frozenset((
    'government', 'retain_government', 'policies', 'policy_unlock',
    'appoint_governor', 'promote_governor', 'assign_governor', 'consider_governor_titles'))


def congress_action_read_only(value, kind):
    """The three official screens are read-only during native IsInSession.

    Great People has no admitted action kind yet; no future opcode is invented.
    Historical catalogues and the underlying observations retain their meaning.
    """
    return (value.get('schema') in WORLD_CONGRESS_CAPABILITY_SCHEMAS
            and type(value.get('world_congress')) is dict
            and value['world_congress'].get('in_session') is True
            and kind in CONGRESS_READ_ONLY_KINDS)
ESPIONAGE_GAPS = ('spy_completion_repeat_pending_identity',)
SPY_COMPLETION_GAPS = ('spy_popup_interface_mode_lifetime', 'spy_notification_reactivation')
INITIAL_DIPLOMACY_GAPS = ('deal_screens_and_non_direct_initial_choices',)
WORLD_WAR_DECISIONS_SCHEMA = 'civ6-host.network-world-war-decisions.v1'
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
    CAPABILITY_XP2_POLICIES_SCHEMA,
    CAPABILITY_XP2_POLICY_UNLOCK_SCHEMA,
    CAPABILITY_XP2_GOVERNMENT_SCHEMA,
    CAPABILITY_XP2_POLICY_RELOCATION_SCHEMA,
    CAPABILITY_XP2_POLICY_RECONFIRM_SCHEMA,
    CAPABILITY_XP2_FAITH_PURCHASE_SCHEMA,
    CAPABILITY_XP2_ENVOYS_SCHEMA,
    CAPABILITY_XP2_GOVERNORS_SCHEMA,
    CAPABILITY_XP2_INITIAL_DIPLOMACY_SCHEMA,
    CAPABILITY_XP2_TRADE_SCHEMA,
    CAPABILITY_XP2_ESPIONAGE_SCHEMA,
    CAPABILITY_XP2_SPY_COMPLETION_SCHEMA,
    CAPABILITY_XP2_WORLD_CONGRESS_SCHEMA,
    CAPABILITY_XP2_WORLD_CONGRESS_REVIEW_SCHEMA,
    CAPABILITY_NATIVE_COMMAND_PERMISSIONS_SCHEMA,
    CAPABILITY_XP2_CONGRESS_ACTIVE_EFFECTS_SCHEMA,
)


def _capability_schemas_from(first):
    return _CAPABILITY_SCHEMAS[_CAPABILITY_SCHEMAS.index(first):]


_TURN_CAPABILITY_SCHEMAS = _capability_schemas_from(CAPABILITY_TURNS_SCHEMA)
ATTACK_CAPABILITY_SCHEMAS = _capability_schemas_from(CAPABILITY_UNIT_ATTACKS_SCHEMA)
PUBLIC_COMBAT_CAPABILITY_SCHEMAS = _capability_schemas_from(CAPABILITY_COMBAT_PUBLIC_SCHEMA)
COMBAT_READINESS_CAPABILITY_SCHEMAS = _capability_schemas_from(CAPABILITY_COMBAT_READINESS_SCHEMA)
UNIT_WORK_STATE_CAPABILITY_SCHEMAS = _capability_schemas_from(CAPABILITY_UNIT_WORK_STATE_SCHEMA)
CURRENT_PRODUCTION_CAPABILITY_SCHEMAS = _capability_schemas_from(CAPABILITY_CURRENT_PRODUCTION_SCHEMA)
POLICY_RELOCATION_CAPABILITY_SCHEMAS = _capability_schemas_from(CAPABILITY_XP2_POLICY_RELOCATION_SCHEMA)
POLICY_RECONFIRM_CAPABILITY_SCHEMAS = _capability_schemas_from(CAPABILITY_XP2_POLICY_RECONFIRM_SCHEMA)
ESPIONAGE_CAPABILITY_SCHEMAS = _capability_schemas_from(CAPABILITY_XP2_ESPIONAGE_SCHEMA)
SPY_COMPLETION_CAPABILITY_SCHEMAS = _capability_schemas_from(CAPABILITY_XP2_SPY_COMPLETION_SCHEMA)
WORLD_CONGRESS_CAPABILITY_SCHEMAS = _capability_schemas_from(CAPABILITY_XP2_WORLD_CONGRESS_SCHEMA)
WORLD_CONGRESS_REVIEW_CAPABILITY_SCHEMAS = _capability_schemas_from(CAPABILITY_XP2_WORLD_CONGRESS_REVIEW_SCHEMA)
NATIVE_COMMAND_PERMISSIONS_SCHEMAS = _capability_schemas_from(CAPABILITY_NATIVE_COMMAND_PERMISSIONS_SCHEMA)
CONGRESS_ACTIVE_EFFECTS_CAPABILITY_SCHEMAS = _capability_schemas_from(CAPABILITY_XP2_CONGRESS_ACTIVE_EFFECTS_SCHEMA)
STRATEGIC_READER_FAMILIES = frozenset((
    'found_city', 'queue_append', 'queue_remove', 'queue_swap',
    'world_select_unit', 'world_deselect_unit', 'world_plot_click', 'unit_order', 'unit_attack',
    'upgrade_unit', 'policies', 'policy_unlock', 'government', 'retain_government',
    'send_envoy', 'retain_envoys', 'change_trade_origin',
    'city_range_attack', 'district_range_attack',
))
NATIVE_STRATEGIC_READER_UNAVAILABLE = 'native_strategic_command_permission_false_reader_unavailable'
_STRATEGIC_READER_FIELDS = {
    'production_queues': 'queue_append', 'production_current': 'queue_append',
    'world_input': 'world_select_unit', 'queued_orders': 'world_select_unit',
    'unit_orders': 'unit_order', 'unit_attacks': 'unit_attack',
    'unit_upgrades': 'upgrade_unit', 'policies': 'policies',
    'policy_unlock': 'policy_unlock', 'government': 'government',
    'envoys': 'send_envoy', 'trade_origins': 'change_trade_origin',
    'city_shots': 'city_range_attack', 'district_shots': 'district_range_attack',
}


def validate_native_command_permissions(value, player_id, turn, sequence):
    """Validate an exact native read; neither flag is inferred from turn state."""
    if (type(value) is not dict or set(value) != {
            'player_id', 'turn', 'sequence', 'allow_strategic', 'allow_tactical'}):
        raise ValueError('Malformed native command permissions')
    for key, expected in (('player_id', player_id), ('turn', turn), ('sequence', sequence)):
        if (type(expected) is not int or expected < 0 or key == 'player_id' and expected > 63
                or type(value[key]) is not int or value[key] != expected):
            raise ValueError('Foreign native command permissions boundary')
    if any(type(value[key]) is not bool for key in ('allow_strategic', 'allow_tactical')):
        raise ValueError('Native command permissions must be exact booleans')
    return value


def family_query_unavailable(value, family, *, actions_closed=False, native_command_permissions=None):
    """Current reader admission, separate from actual activity and human legality.

    Tactical permission remains an observation until a family-specific reader
    contract consumes it. Unlisted readers retain their historical activity gate.
    The explicit permissions argument supports construction before sealing v39.
    """
    if type(value) is not dict or type(family) is not str or type(actions_closed) is not bool:
        raise ValueError('Malformed native family query boundary')
    controls = validate_turn_controls(value['turn_controls'], value['player_id'], value['turn'])
    permissions = native_command_permissions
    if value.get('schema') in NATIVE_COMMAND_PERMISSIONS_SCHEMAS:
        retained = value['native_command_permissions']
        if permissions is not None and permissions != retained:
            raise ValueError('Conflicting native command permission reads')
        permissions = retained
    if permissions is not None:
        validate_native_command_permissions(permissions, value['player_id'], value['turn'], value['sequence'])
    return (actions_closed or is_waiting(controls)
            or permissions is not None and not permissions['allow_strategic']
               and family in STRATEGIC_READER_FAMILIES)

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


def is_world_war_decisions(value):
    return type(value) is dict and value.get('schema') == WORLD_WAR_DECISIONS_SCHEMA


def is_diplomacy_decisions(value):
    return (type(value) is dict
            and value.get('schema') == 'civ6-host.network-diplomacy-decisions.v1')


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
    policies_v25 = version >= 25
    policy_unlock_v26 = version >= 26
    government_v27 = version >= 27
    policy_relocation_v28 = version >= 28
    policy_reconfirm_v29 = version >= 29
    faith_purchase_v30 = version >= 30
    envoys_v31 = version >= 31
    governors_v32 = version >= 32
    initial_diplomacy_v33 = version >= 33
    xp2_trade_v34 = version >= 34
    espionage_v35 = version >= 35
    spy_completion_v36 = version >= 36
    world_congress_v37 = version >= 37
    world_congress_review_v38 = version >= 38
    command_permissions_v39 = version >= 39
    congress_active_effects_v40 = version >= 40
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
              | ({'policies'} if policies_v25 else set())
              | ({'policy_unlock'} if policy_unlock_v26 else set())
              | ({'government'} if government_v27 else set())
              | ({'envoys'} if envoys_v31 else set())
              | ({'governors'} if governors_v32 else set())
              | ({'diplomacy_overview'} if initial_diplomacy_v33 else set())
              | ({'trade_routes', 'trade_origins'} if xp2_trade_v34 else set())
              | ({'espionage'} if espionage_v35 else set())
              | ({'spy_completion'} if spy_completion_v36 else set())
              | ({'world_congress'} if world_congress_v37 else set())
              | ({'world_congress_review', 'world_congress_review_status'} if world_congress_review_v38 else set())
              | ({'native_command_permissions'} if command_permissions_v39 else set())
              | ({'world_congress_active_effects','world_congress_active_effects_status'} if congress_active_effects_v40 else set())
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
    if policies_v25:
        action_fields['policies'] = frozenset(('kind', 'slots'))
    if policy_unlock_v26:
        from . import policy_unlock
        action_fields['policy_unlock'] = frozenset(('kind', 'cost', 'currency'))
    if government_v27:
        action_fields['government'] = frozenset(('kind', 'index', 'hash'))
        action_fields['retain_government'] = frozenset(('kind', 'index'))
    if envoys_v31:
        from . import envoys
        action_fields.update(envoys.ACTION_FIELDS)
    if governors_v32:
        from . import governors
        action_fields.update(governors.ACTION_FIELDS)
    if initial_diplomacy_v33:
        from . import diplomacy_overview as initial_diplomacy
        action_fields.update(initial_diplomacy.ACTION_FIELDS)
    if xp2_trade_v34:
        from . import trade
        action_fields.update({
            'make_trade_route': frozenset(trade.ROUTE_FIELDS),
            'change_trade_origin': frozenset(trade.ORIGIN_FIELDS),
        })
    if espionage_v35:
        from . import espionage
        action_fields.update(espionage.ACTION_FIELDS)
    if spy_completion_v36:
        from . import spy_completion
        action_fields.update(spy_completion.ACTION_FIELDS)
    if world_congress_v37:
        from . import world_congress
        action_fields.update(world_congress.CANDIDATE_FIELDS)
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
    if command_permissions_v39:
        validate_native_command_permissions(value['native_command_permissions'], player_id, turn, sequence)
        if not value['native_command_permissions']['allow_strategic']:
            if any(value[field] is not None for field in _STRATEGIC_READER_FIELDS):
                raise ValueError('Strategic-gated reader must remain explicitly unavailable')
    if resources_v24:
        from . import strategic_resources
        resources = value['strategic_resources']
        if (resources is None) != actions_closed:
            raise ValueError('Strategic resources differ from the session closure')
        if resources is not None:
            strategic_resources.validate(resources, player_id, turn)
    if policies_v25:
        policy_catalogue = value['policies']
        unavailable = family_query_unavailable(value, 'policies', actions_closed=actions_closed)
        if (policy_catalogue is None) != unavailable:
            raise ValueError('Policy query differs from its native acting boundary')
        if policy_catalogue is not None:
            from . import capability_policies
            capability_policies.validate_catalogue(policy_catalogue, player_id, turn,
                allow_relocation=policy_relocation_v28)
    if government_v27:
        from . import government as capability_government
        government_catalogue = value['government']
        unavailable = family_query_unavailable(value, 'government', actions_closed=actions_closed)
        if (government_catalogue is None) != unavailable:
            raise ValueError('Government query differs from its native acting boundary')
        if government_catalogue is not None:
            capability_government.validate_catalogue(government_catalogue, player_id, turn)
    if envoys_v31:
        envoy_catalogue = value['envoys']
        unavailable = family_query_unavailable(value, 'send_envoy', actions_closed=actions_closed)
        if (envoy_catalogue is None) != unavailable:
            raise ValueError('Envoy query differs from its native acting boundary')
        if envoy_catalogue is not None:
            envoys.validate_catalogue(envoy_catalogue, player_id, turn)
    if governors_v32:
        governor_catalogue = value['governors']
        if actions_closed or is_waiting(value['turn_controls']):
            if governor_catalogue is not None:
                raise ValueError('Unavailable governor query must remain unknown')
        elif governor_catalogue is None:
            raise ValueError('Acting governor catalogue is unavailable')
        else:
            governors.validate_catalogue(governor_catalogue, player_id, turn)
    if initial_diplomacy_v33:
        diplomacy_catalogue = value['diplomacy_overview']
        if (diplomacy_catalogue is None) != (actions_closed or is_waiting(controls)):
            raise ValueError('Initial diplomacy query differs from its acting boundary')
        if diplomacy_catalogue is not None:
            initial_diplomacy.validate(diplomacy_catalogue, player_id, turn)
    if xp2_trade_v34:
        from . import trade
        unavailable = actions_closed or is_waiting(controls)
        origins_unavailable = family_query_unavailable(value, 'change_trade_origin', actions_closed=actions_closed)
        routes, origins = value['trade_routes'], value['trade_origins']
        if (routes is None) != unavailable or (origins is None) != origins_unavailable:
            raise ValueError('Trade queries differ from their native acting boundary')
        if not unavailable:
            trade.validate_routes(routes, player_id, turn)
            if observation is not None:
                trade.compare_routes(routes, observation)
        if not origins_unavailable:
            trade.validate_origins(origins, player_id, turn)
            if observation is not None:
                trade.compare_origins(origins, observation)
    if espionage_v35:
        espionage_catalogue = value['espionage']
        if (espionage_catalogue is None) != (actions_closed or is_waiting(controls)):
            raise ValueError('Espionage query differs from its native acting boundary')
        if espionage_catalogue is not None:
            espionage.validate_catalogue(espionage_catalogue, player_id, turn)
            if observation is not None:
                espionage.compare_own(espionage_catalogue, observation)
    if spy_completion_v36:
        completion_catalogue = value['spy_completion']
        if (completion_catalogue is None) != (actions_closed or is_waiting(controls)):
            raise ValueError('Spy completion query differs from its native acting boundary')
        if completion_catalogue is not None:
            spy_completion.validate_catalogue(completion_catalogue, player_id, turn)
            if observation is not None:
                spy_completion.compare_own(completion_catalogue, observation)
    if world_congress_v37:
        congress_catalogue = value['world_congress']
        if (congress_catalogue is None) != (actions_closed or is_waiting(controls)):
            raise ValueError('Congress query differs from its acting boundary')
        if congress_catalogue is not None:
            world_congress.validate_catalogue(congress_catalogue, player_id, turn, sequence)
            if observation is not None:
                world_congress.compare_own(congress_catalogue, observation, sequence)
    if world_congress_review_v38:
        from . import world_congress_review
        world_congress_review.validate_group(value['world_congress_review'],
            value['world_congress_review_status'], congress_catalogue, player_id, turn, sequence)
    if congress_active_effects_v40:
        from . import world_congress_active_effects
        world_congress_active_effects.validate_group(value['world_congress_active_effects'],
            value['world_congress_active_effects_status'], congress_catalogue, player_id, turn, sequence)
    if (type(value['decision_id']) is not str or value['decision_id'] != digest(
            {key: item for key, item in value.items() if key != 'decision_id'})):
        raise ValueError('Capability catalogue digest differs')
    families, candidates = value['families'], value['candidates']
    if (type(families) is not dict or not 1 <= len(families) <= 128
            or type(candidates) is not list
            or len(candidates) > (ORDINARY_ACTION_LIMIT + MAP_CELL_LIMIT if world_v4 else 4096)
            or actions_closed and candidates):
        raise ValueError('Malformed or closed capability catalogue')
    if envoys_v31:
        for kind in envoys.ACTION_FIELDS:
            family = families.get(kind, {})
            if family.get('status') != ('unqualified' if envoy_catalogue is None else 'queried_complete'):
                raise ValueError('Envoy family differs from its public query availability')
    if governors_v32:
        for kind in governors.ACTION_FIELDS:
            family = families.get(kind, {})
            if family.get('status') != ('unqualified' if governor_catalogue is None else 'queried_complete'):
                raise ValueError('Governor family differs from its public query availability')
    if initial_diplomacy_v33:
        family = families.get('diplomacy_initiate', {})
        if family.get('status') != ('unqualified' if diplomacy_catalogue is None else 'queried_partial'):
            raise ValueError('Initial diplomacy family differs from its public query')
        if diplomacy_catalogue is not None and family.get('unqualified') != list(INITIAL_DIPLOMACY_GAPS):
            raise ValueError('Initial diplomacy family has an unqualified source gap')
    if xp2_trade_v34:
        for kind in ('make_trade_route', 'change_trade_origin'):
            trade_available = not family_query_unavailable(value, kind, actions_closed=actions_closed)
            if families.get(kind, {}).get('status') != ('queried_complete' if trade_available else 'unqualified'):
                raise ValueError('Trade family differs from its native query availability')
    if espionage_v35:
        for kind in espionage.ACTION_FIELDS:
            expected_status = 'unqualified' if espionage_catalogue is None else 'queried_partial'
            family = families.get(kind, {})
            if family.get('status') != expected_status:
                raise ValueError('Espionage family differs from its native query availability')
            gaps = SPY_COMPLETION_GAPS if spy_completion_v36 else ESPIONAGE_GAPS
            if espionage_catalogue is not None and family.get('unqualified') != list(gaps):
                raise ValueError('Espionage family must retain its versioned source gaps')
    if spy_completion_v36:
        for kind in spy_completion.ACTION_FIELDS:
            family = families.get(kind, {})
            expected_status = 'unqualified' if completion_catalogue is None else 'queried_partial'
            if family.get('status') != expected_status:
                raise ValueError('Spy completion family differs from its native query availability')
            if completion_catalogue is not None and family.get('unqualified') != list(SPY_COMPLETION_GAPS):
                raise ValueError('Spy completion family must retain its exact source gaps')
    if world_congress_v37:
        for kind in world_congress.CANDIDATE_FIELDS:
            family = families.get(kind, {})
            expected_status = 'unqualified' if congress_catalogue is None else 'queried_partial'
            if family.get('status') != expected_status:
                raise ValueError('Congress family differs from its query availability')
            if congress_catalogue is not None and family.get('unqualified') != list(world_congress.GAPS):
                raise ValueError('Congress family must retain its source gaps')
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
            if command_permissions_v39 and family_query_unavailable(value, name, actions_closed=actions_closed) and name in STRATEGIC_READER_FAMILIES:
                raise ValueError('Native strategic permission does not admit this coupled reader')
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
                if policies_v25 and name == 'policies' and gaps != (
                        ['active_policy_relocation'] if policy_unlock_v26 else
                        ['paid_policy_unlock', 'active_policy_relocation']):
                    raise ValueError('Policy query must retain its exact unqualified branches')
                if government_v27 and name == 'government' and gaps != ['anarchy_transition']:
                    raise ValueError('Government query must retain its exact unqualified branch')
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
            gaps = (plot_purchases.CITY_FAITH_GAPS if faith_purchase_v30 else
                    plot_purchases.CITY_GAPS if city_purchase_v21 else plot_purchases.GAPS)
            if family.get('unqualified') != list(gaps):
                raise ValueError('Plot purchase family must retain its exact unqualified routes')
            plot_purchases.validate_catalogue(purchases, player_id, turn, width=dimensions['width'],
                                               height=dimensions['height'], own_cities=own_cities)
            if city_purchase_v21:
                plot_purchases.validate_catalogue(city_purchases, player_id, turn,
                    own_cities=[city['city_id'] for city in purchases], city_items=True,
                    allow_faith=faith_purchase_v30)
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
        unavailable = family_query_unavailable(value, 'upgrade_unit', actions_closed=actions_closed)
        upgrade_catalogue = value['unit_upgrades']
        if ((upgrade_catalogue is None) != unavailable
                or families.get('upgrade_unit', {}).get('status') !=
                   ('unqualified' if unavailable else 'queried_complete')):
            raise ValueError('Upgrade family differs from its native query availability')
        if not unavailable:
            unit_upgrades.validate_catalogue(upgrade_catalogue, player_id, turn, observation=observation)
    if policies_v25:
        unavailable = family_query_unavailable(value, 'policies', actions_closed=actions_closed)
        if families.get('policies', {}).get('status') != (
                'unqualified' if unavailable else
                'queried_complete' if policy_relocation_v28 else 'queried_partial'):
            raise ValueError('Policy family differs from its native query availability')
    if policy_unlock_v26:
        unavailable = family_query_unavailable(value, 'policy_unlock', actions_closed=actions_closed)
        if ((value['policy_unlock'] is None) != unavailable
                or families.get('policy_unlock', {}).get('status') != (
                    'unqualified' if unavailable else 'queried_complete')):
            raise ValueError('Policy unlock differs from its native acting boundary')
        if not unavailable:
            policy_unlock.validate(value['policy_unlock'], player_id, turn)
            unlock, window = value['policy_unlock'], policy_catalogue['reason']
            if ((window == 'already_changed') != (unlock['reason'] == 'already_changed')
                    or window == 'not_free' and unlock['cost'] == 0
                    or window in ('available', 'window_closed') and unlock['cost'] != 0):
                raise ValueError('Policy assignment and unlock queries disagree')
    if government_v27:
        unavailable = family_query_unavailable(value, 'government', actions_closed=actions_closed)
        if families.get('government', {}).get('status') != (
                'unqualified' if unavailable else 'queried_partial'):
            raise ValueError('Government family differs from its native query availability')
    seen = set()
    for row in candidates:
        if type(row) is not dict or set(row) != {'candidate_id', 'action'}:
            raise ValueError('Malformed capability candidate')
        action = row['action']
        if type(action) is not dict or type(action.get('kind')) is not str:
            raise ValueError('Malformed capability action')
        kind = action['kind']
        if congress_action_read_only(value, kind):
            raise ValueError('Congress makes this screen read-only')
        family_kind = ('government' if government_v27 and kind == 'retain_government' else kind)
        city_purchase = city_purchase_v21 and kind == 'purchase' and set(action) == plot_purchases.CITY_FIELDS
        if family_kind not in by_family or (set(action) != action_fields[kind] and not city_purchase):
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
            plot_purchases.validate_purchase_action(action, allow_faith=faith_purchase_v30)
        elif promotion_v22 and kind == 'promote_unit':
            unit_promotions.validate_action(action)
        elif upgrade_v23 and kind == 'upgrade_unit':
            unit_upgrades.validate_action(action)
        elif city_controls_v12 and kind in city_controls.ACTION_FIELDS:
            city_controls.validate_action(action)
        elif policies_v25 and kind == 'policies':
            # The catalogue-backed equality check below validates its slots.
            pass
        elif policy_unlock_v26 and kind == 'policy_unlock':
            policy_unlock.validate_action(action)
        elif government_v27 and kind in ('government', 'retain_government'):
            # The exact native offer list is rebuilt and compared below.
            pass
        elif envoys_v31 and kind in envoys.ACTION_FIELDS:
            envoys.validate_action(action)
        elif governors_v32 and kind in governors.ACTION_FIELDS:
            governors.validate_action(action)
        elif initial_diplomacy_v33 and kind == 'diplomacy_initiate':
            initial_diplomacy.validate_action(action)
        elif xp2_trade_v34 and kind == 'make_trade_route':
            trade.validate_route_action(action, value['trade_routes']['width'], value['trade_routes']['height'])
        elif xp2_trade_v34 and kind == 'change_trade_origin':
            trade.validate_origin_action(action, value['trade_origins']['width'], value['trade_origins']['height'])
        elif espionage_v35 and kind in espionage.ACTION_FIELDS:
            espionage.validate_action(action, espionage_catalogue['width'], espionage_catalogue['height'])
        elif spy_completion_v36 and kind in spy_completion.ACTION_FIELDS:
            spy_completion.validate_action(action, completion_catalogue['width'], completion_catalogue['height'])
        elif world_congress_v37 and kind in world_congress.CANDIDATE_FIELDS:
            world_congress.validate_candidate(action)
        elif not (turns_v3 and kind in _CAPABILITY_TURN_KINDS):
            validate_action(action, own_cities)
        candidate_id = row['candidate_id']
        if (type(candidate_id) is not str or candidate_id != digest(action)
                or candidate_id in seen):
            raise ValueError('Duplicate or mismatched capability candidate identity')
        seen.add(candidate_id)
        by_family[family_kind].append(candidate_id)
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
    if policies_v25:
        offered = [row['action'] for row in candidates if row['action']['kind'] == 'policies']
        from . import capability_policies
        expected_policy_actions = capability_policies.actions(policy_catalogue,
            allow_relocation=policy_relocation_v28,
            allow_unchanged=policy_reconfirm_v29)
        if congress_action_read_only(value, 'policies'):
            expected_policy_actions = []
        if offered != expected_policy_actions:
            raise ValueError('Policy candidates differ from their native slot catalogue')
    if policy_unlock_v26:
        offered = [row['action'] for row in candidates if row['action']['kind'] == 'policy_unlock']
        expected = [] if congress_action_read_only(value, 'policy_unlock') else policy_unlock.actions(value['policy_unlock'])
        if offered != expected:
            raise ValueError('Policy unlock candidates differ from their native query')
    if government_v27:
        offered = [row['action'] for row in candidates
                   if row['action']['kind'] in ('government', 'retain_government')]
        expected = [] if congress_action_read_only(value, 'government') else capability_government.actions(government_catalogue)
        if offered != expected:
            raise ValueError('Government candidates differ from their native query')
    if governors_v32:
        offered = [row['action'] for row in candidates if row['action']['kind'] in governors.ACTION_FIELDS]
        expected = [] if congress_action_read_only(value, 'appoint_governor') else governors.actions(governor_catalogue)
        if offered != expected:
            raise ValueError('Governor candidates differ from their exact public catalogue')
    if initial_diplomacy_v33:
        offered = [row['action'] for row in candidates if row['action']['kind'] == 'diplomacy_initiate']
        expected = [] if diplomacy_catalogue is None else initial_diplomacy.candidates(diplomacy_catalogue)
        if offered != expected:
            raise ValueError('Initial diplomacy candidates differ from their exact public catalogue')
    if xp2_trade_v34:
        from . import trade
        for kind, expected in (
                ('make_trade_route', [] if value['trade_routes'] is None else trade.route_actions(value['trade_routes'])),
                ('change_trade_origin', [] if value['trade_origins'] is None else trade.origin_actions(value['trade_origins']))):
            offered = [row['action'] for row in candidates if row['action']['kind'] == kind]
            if offered != expected:
                raise ValueError('Trade candidates differ from their exact native catalogue: ' + kind)
    if espionage_v35:
        offered = [row['action'] for row in candidates if row['action']['kind'] in espionage.ACTION_FIELDS]
        if offered != espionage.actions(espionage_catalogue):
            raise ValueError('Espionage candidates differ from their exact native catalogue')
    if spy_completion_v36:
        offered = [row['action'] for row in candidates if row['action']['kind'] in spy_completion.ACTION_FIELDS]
        if offered != spy_completion.actions(completion_catalogue):
            raise ValueError('Spy completion candidates differ from their exact native catalogue')
    if world_congress_v37:
        offered = [row['action'] for row in candidates if row['action']['kind'] in world_congress.CANDIDATE_FIELDS]
        if offered != world_congress.actions(congress_catalogue):
            raise ValueError('Congress candidates differ from their exact parameter domains')
    if envoys_v31:
        offered = [row['action'] for row in candidates if row['action']['kind'] in envoys.ACTION_FIELDS]
        if offered != envoys.actions(envoy_catalogue):
            raise ValueError('Envoy candidates differ from their native query')
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


def upgrade_espionage_catalogue(value, espionage, observation=None):
    """Add the explicit espionage query to a validated v34 decision boundary."""
    from . import espionage as espionage_contract
    if type(value) is not dict or value.get('schema') != CAPABILITY_XP2_TRADE_SCHEMA:
        raise ValueError('Espionage requires the complete XP2 v34 query group')
    unavailable = value.get('trade_routes') is None
    if (espionage is None) != unavailable:
        raise ValueError('Espionage query differs from its native acting boundary')
    if espionage is not None:
        espionage_contract.validate_catalogue(espionage, value['player_id'], value['turn'])
        if observation is not None:
            espionage_contract.compare_own(espionage, observation)
    result = copy.deepcopy(value)
    result['schema'] = CAPABILITY_XP2_ESPIONAGE_SCHEMA
    result['espionage'] = copy.deepcopy(espionage)
    rows = [dict(candidate_id=digest(action), action=action)
            for action in espionage_contract.actions(espionage)]
    result['candidates'].extend(rows)
    for kind in espionage_contract.ACTION_FIELDS:
        result['families'][kind] = (
            dict(status='unqualified', reason='native_espionage_acting_boundary_unavailable')
            if unavailable else dict(status='queried_partial', candidate_ids=[
                row['candidate_id'] for row in rows if row['action']['kind'] == kind],
                unqualified=list(ESPIONAGE_GAPS)))
    result.pop('decision_id', None)
    result['decision_id'] = digest(result)
    return result


def upgrade_spy_completion_catalogue(value, spy_completion, observation=None):
    """Add a separately offered current completion to a validated v35 boundary."""
    from . import espionage
    from . import spy_completion as completion_contract
    if type(value) is not dict or value.get('schema') != CAPABILITY_XP2_ESPIONAGE_SCHEMA:
        raise ValueError('Spy completion requires the complete XP2 v35 query group')
    unavailable = value.get('espionage') is None
    if (spy_completion is None) != unavailable:
        raise ValueError('Spy completion query differs from its native acting boundary')
    if spy_completion is not None:
        completion_contract.validate_catalogue(spy_completion, value['player_id'], value['turn'])
        if observation is not None:
            completion_contract.compare_own(spy_completion, observation)
    result = copy.deepcopy(value)
    result['schema'] = CAPABILITY_XP2_SPY_COMPLETION_SCHEMA
    result['spy_completion'] = copy.deepcopy(spy_completion)
    if not unavailable:
        for kind in espionage.ACTION_FIELDS:
            family = result['families'][kind]
            if (family.get('status') != 'queried_partial'
                    or family.get('unqualified') != list(ESPIONAGE_GAPS)):
                raise ValueError('Spy completion cannot substitute historical espionage source gaps')
            family['unqualified'] = list(SPY_COMPLETION_GAPS)
    rows = [dict(candidate_id=digest(action), action=action)
            for action in completion_contract.actions(spy_completion)]
    result['candidates'].extend(rows)
    for kind in completion_contract.ACTION_FIELDS:
        result['families'][kind] = (
            dict(status='unqualified', reason='native_spy_completion_acting_boundary_unavailable')
            if unavailable else dict(status='queried_partial', candidate_ids=[
                row['candidate_id'] for row in rows if row['action']['kind'] == kind],
                unqualified=list(SPY_COMPLETION_GAPS)))
    result.pop('decision_id', None)
    result['decision_id'] = digest(result)
    return result


def upgrade_world_congress_catalogue(value, congress, observation=None):
    """Append an explicitly queried Congress catalogue to the v36 boundary."""
    from . import world_congress
    if type(value) is not dict or value.get('schema') != CAPABILITY_XP2_SPY_COMPLETION_SCHEMA:
        raise ValueError('Congress requires the complete XP2 v36 query group')
    unavailable = value.get('spy_completion') is None
    if (congress is None) != unavailable:
        raise ValueError('Congress query differs from its native acting boundary')
    if congress is not None:
        world_congress.validate_catalogue(congress, value['player_id'], value['turn'], value['sequence'])
        if observation is not None:
            world_congress.compare_own(congress, observation, value['sequence'])
    result = copy.deepcopy(value)
    result['schema'] = CAPABILITY_XP2_WORLD_CONGRESS_SCHEMA
    result['world_congress'] = copy.deepcopy(congress)
    removed = {row['candidate_id'] for row in result['candidates']
               if congress_action_read_only(result, row['action']['kind'])}
    result['candidates'] = [row for row in result['candidates'] if row['candidate_id'] not in removed]
    for family in result['families'].values():
        if 'candidate_ids' in family:
            family['candidate_ids'] = [key for key in family['candidate_ids'] if key not in removed]
    rows = [dict(candidate_id=digest(action), action=action) for action in world_congress.actions(congress)]
    result['candidates'].extend(rows)
    for kind in world_congress.CANDIDATE_FIELDS:
        result['families'][kind] = (
            dict(status='unqualified', reason='native_congress_acting_boundary_unavailable')
            if unavailable else dict(status='queried_partial', candidate_ids=[
                row['candidate_id'] for row in rows if row['action']['kind'] == kind],
                unqualified=list(world_congress.GAPS)))
    result.pop('decision_id', None)
    result['decision_id'] = digest(result)
    return result


def upgrade_review_catalogue(value, review, observation=None, *, status=None):
    """Append historical public results; preserve every existing choice ID."""
    from . import world_congress_review
    if type(value) is not dict or value.get('schema') != CAPABILITY_XP2_WORLD_CONGRESS_SCHEMA:
        raise ValueError('Congress review requires the complete XP2 v37 query group')
    if status is None:
        if review is not None: status = 'available'
        elif value['world_congress'] is None: status = 'waiting_or_closed'
        else: raise ValueError('Unavailable Congress review requires an explicit status')
    world_congress_review.validate_group(review, status, value['world_congress'],
        value['player_id'], value['turn'], value['sequence'])
    if review is not None and observation is not None:
        world_congress_review.compare_own(review, observation, value['sequence'])
    result = copy.deepcopy(value)
    result['schema'] = CAPABILITY_XP2_WORLD_CONGRESS_REVIEW_SCHEMA
    result['world_congress_review'] = copy.deepcopy(review)
    result['world_congress_review_status'] = status
    result.pop('decision_id', None)
    result['decision_id'] = digest(result)
    return result


def upgrade_command_permissions_catalogue(value, permissions, observation=None, *, actions_closed=False):
    """Add the actual native permissions without manufacturing a query result."""
    if type(value) is not dict or value.get('schema') != CAPABILITY_XP2_WORLD_CONGRESS_REVIEW_SCHEMA:
        raise ValueError('Native command permissions require the complete v38 query group')
    validate_native_command_permissions(permissions, value['player_id'], value['turn'], value['sequence'])
    result = copy.deepcopy(value)
    result['schema'] = CAPABILITY_NATIVE_COMMAND_PERMISSIONS_SCHEMA
    result['native_command_permissions'] = copy.deepcopy(permissions)
    result.pop('decision_id', None)
    result['decision_id'] = digest(result)
    from types import SimpleNamespace
    identity = SimpleNamespace(episode_id=result['episode_id'], game_generation=result['game_generation'])
    validate_capability_catalogue(result, identity, result['sequence'], result['turn'],
        player_id=result['player_id'], observation=observation, actions_closed=actions_closed)
    return result


def upgrade_active_effects_catalogue(value, effects, observation=None, *, status=None):
    """Append public current effects without changing any action or candidate ID."""
    from . import world_congress_active_effects
    if type(value) is not dict or value.get('schema') != CAPABILITY_NATIVE_COMMAND_PERMISSIONS_SCHEMA:
        raise ValueError('Congress active effects require the complete v39 query group')
    if status is None:
        if effects is not None: status = 'available'
        elif value['world_congress'] is None: status = 'waiting_or_closed'
        else: raise ValueError('Unavailable Congress active effects require an explicit status')
    world_congress_active_effects.validate_group(effects,status,value['world_congress'],
        value['player_id'],value['turn'],value['sequence'])
    if effects is not None and observation is not None:
        world_congress_active_effects.compare_own(effects,observation,value['sequence'])
    result=copy.deepcopy(value)
    result['schema']=CAPABILITY_XP2_CONGRESS_ACTIVE_EFFECTS_SCHEMA
    result['world_congress_active_effects']=copy.deepcopy(effects)
    result['world_congress_active_effects_status']=status
    result.pop('decision_id',None);result['decision_id']=digest(result)
    return result


def select_capability(value, selection):
    """Resolve an exact choice from an already validated capability catalogue."""
    if (not is_capability_catalogue(value) or type(selection) is not dict
            or set(selection) not in ({'decision_id', 'candidate_id'},
                                      {'decision_id', 'candidate_id', 'parameters'})
            or selection['decision_id'] != value['decision_id']
            or type(selection['candidate_id']) is not str):
        raise ValueError('Malformed or stale capability selection')
    matches = [row['action'] for row in value['candidates']
               if row['candidate_id'] == selection['candidate_id']]
    if len(matches) != 1:
        raise ValueError('Choice is absent from the completed family queries')
    if (type(matches[0].get('kind')) is str and matches[0].get('kind').startswith('congress_')):
        from . import world_congress
        if value.get('schema') not in WORLD_CONGRESS_CAPABILITY_SCHEMAS:
            raise ValueError('Congress requires its explicit capability revision')
        has_parameters = matches[0]['kind'] in world_congress.PARAMETER_FIELDS
        if ('parameters' in selection) != has_parameters:
            raise ValueError('Congress selection parameters differ from its operation')
        return world_congress.choose(value['world_congress'], matches[0], selection.get('parameters'))
    if matches[0].get('kind') == 'policies':
        if set(selection) != {'decision_id', 'candidate_id', 'parameters'}:
            raise ValueError('Explicit policy assignment parameters required')
        parameters = selection['parameters']
        if type(parameters) is not dict or set(parameters) != {'assignments'}:
            raise ValueError('Malformed explicit policy assignment parameters')
        from . import policies
        candidate = policies.choose(matches[0]['slots'], parameters['assignments'],
                                    value['player_id'], value['turn'],
                                    allow_relocation=(
                                        _CAPABILITY_SCHEMAS.index(value['schema']) + 1 >= 28),
                                    allow_unchanged=(
                                        _CAPABILITY_SCHEMAS.index(value['schema']) + 1 >= 29))
        return dict(kind='policies', candidate=candidate)
    if set(selection) != {'decision_id', 'candidate_id'}:
        raise ValueError('Parameters are unsupported for this capability action')
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


def checkpoint_city_query_projection(current, saved, observation, *, requested=(False, False)):
    """Compare prior known fields when explicit city queries are first enabled.

    None means unqueried, not an empty city state. Only newly observed families
    are removed from this detached comparison copy; existing city data and all
    other decisions still have to match. The published catalogue is unchanged.
    """
    if (type(requested) is not tuple or len(requested)!=2
            or any(type(flag) is not bool for flag in requested)
            or requested[1] and not requested[0]):
        raise ValueError('City-query transition requires exact complete opt-ins')
    if not any(requested):
        return current, None
    pairs=(('city_focus','city_focus_catalogs'),('city_citizen','citizen_catalogs'))
    added=[(kind,key) for flag,(kind,key) in zip(requested,pairs)
           if flag and saved.get(key) is None and current.get(key) is not None]
    if not added:
        return current, None
    if (current.get('schema')!=saved.get('schema')
            or current.get('schema') not in _capability_schemas_from(CAPABILITY_CITY_CONTROLS_SCHEMA)):
        raise ValueError('City-query activation cannot substitute a catalogue version')
    from types import SimpleNamespace
    for value in (current,saved):
        identity=SimpleNamespace(episode_id=value['episode_id'],game_generation=value['game_generation'])
        validate_capability_catalogue(value,identity,value['sequence'],observation['turn'],
            player_id=observation['player_id'],observation=observation)
    projected=copy.deepcopy(current)
    kinds={kind for kind,_ in added}
    changed_fields=[]
    for flag,(kind,key) in zip(requested,pairs):
        if saved.get(key) is None and current.get(key) is not None and not flag:
            raise ValueError('An unrequested city query cannot be excluded from comparison')
        if kind in kinds:
            previous_family=saved['families'].get(kind)
            if previous_family is not None and previous_family['status']!='unqualified':
                raise ValueError('Known city state cannot be excluded from checkpoint comparison')
            changed_fields.append(key)
            if key in saved:projected[key]=None
        if key not in saved:
            projected.pop(key,None)
            if key not in changed_fields:changed_fields.append(key)
        if kind in kinds or key not in saved:
            if kind in saved['families']:projected['families'][kind]=copy.deepcopy(saved['families'][kind])
            else:projected['families'].pop(kind,None)
    projected['candidates']=[row for row in projected['candidates']
                             if row['action']['kind'] not in kinds]
    projected.pop('decision_id')
    projected['decision_id']=digest(projected)
    return projected,dict(source_schema=saved['schema'],target_schema=current['schema'],
        historical_fields_unchanged=True,explicit_city_query_opt_in=list(requested),
        added_public_fields=changed_fields,
        added_action_families=[kind for kind,_ in added])


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
    if current_schema == CAPABILITY_XP2_CONGRESS_ACTIVE_EFFECTS_SCHEMA and saved.get('schema') != current_schema:
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Congress active effects checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace
        identity=SimpleNamespace(episode_id=current['episode_id'],game_generation=current['game_generation'])
        validate_capability_catalogue(current,identity,current['sequence'],observation['turn'],
                                      player_id=observation['player_id'],observation=observation)
        projected=copy.deepcopy(current)
        projected['schema']=CAPABILITY_NATIVE_COMMAND_PERMISSIONS_SCHEMA
        projected.pop('world_congress_active_effects');projected.pop('world_congress_active_effects_status')
        projected.pop('decision_id');projected['decision_id']=digest(projected)
        projected,prior=checkpoint_catalogue(projected,saved,observation,
            production_evidence=production_evidence,combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256,core_sha256=core_sha256)
        transition=dict(prior or {},source_schema=saved['schema'],target_schema=current_schema,
                        historical_fields_unchanged=True)
        transition['added_public_fields']=transition.get('added_public_fields',[])+[
            'world_congress_active_effects','world_congress_active_effects_status']
        return projected,transition
    if current_schema == CAPABILITY_NATIVE_COMMAND_PERMISSIONS_SCHEMA and saved.get('schema') != current_schema:
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Native permissions checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = CAPABILITY_XP2_WORLD_CONGRESS_REVIEW_SCHEMA
        projected.pop('native_command_permissions')
        projected.pop('decision_id')
        projected['decision_id'] = digest(projected)
        # An unavailable coupled reader cannot masquerade as a historical v38
        # query. Only metadata is removed, and every old field remains strict.
        try:
            validate_capability_catalogue(projected, identity, projected['sequence'], observation['turn'],
                                          player_id=observation['player_id'], observation=observation)
        except ValueError as exc:
            raise ValueError('Native permissions checkpoint has no comparable historical query') from exc
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + ['native_command_permissions']
        return projected, transition
    if current_schema == CAPABILITY_XP2_WORLD_CONGRESS_REVIEW_SCHEMA and saved.get('schema') != current_schema:
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Congress review checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = CAPABILITY_XP2_WORLD_CONGRESS_SCHEMA
        projected.pop('world_congress_review')
        projected.pop('world_congress_review_status')
        projected.pop('decision_id')
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + [
            'world_congress_review', 'world_congress_review_status']
        return projected, transition
    if current_schema == CAPABILITY_XP2_WORLD_CONGRESS_SCHEMA and saved.get('schema') != current_schema:
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Congress checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace
        from . import world_congress
        identity = SimpleNamespace(episode_id=current['episode_id'],
                                   game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = CAPABILITY_XP2_SPY_COMPLETION_SCHEMA
        projected.pop('world_congress')
        for kind in world_congress.CANDIDATE_FIELDS:
            projected['families'].pop(kind)
        projected['candidates'] = [row for row in projected['candidates']
                                  if row['action']['kind'] not in world_congress.CANDIDATE_FIELDS]
        if current['world_congress'] is not None and current['world_congress']['in_session']:
            prior = [row for row in saved['candidates'] if row['action']['kind'] in CONGRESS_READ_ONLY_KINDS]
            present = [row for row in projected['candidates'] if row['action']['kind'] in CONGRESS_READ_ONLY_KINDS]
            if prior != present:
                raise ValueError('Congress checkpoint read-only action intersection differs from history')
        projected.pop('decision_id')
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + ['world_congress']
        transition['added_action_families'] = transition.get('added_action_families', []) + list(world_congress.CANDIDATE_FIELDS)
        return projected, transition
    if current_schema == CAPABILITY_XP2_SPY_COMPLETION_SCHEMA and saved.get('schema') != current_schema:
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Spy completion checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace
        from . import espionage, spy_completion
        identity = SimpleNamespace(episode_id=current['episode_id'],
                                   game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = CAPABILITY_XP2_ESPIONAGE_SCHEMA
        projected.pop('spy_completion')
        kinds = tuple(spy_completion.ACTION_FIELDS)
        for kind in kinds:
            projected['families'].pop(kind)
        for kind in espionage.ACTION_FIELDS:
            if projected['families'][kind]['status'] == 'queried_partial':
                projected['families'][kind]['unqualified'] = list(ESPIONAGE_GAPS)
        projected['candidates'] = [row for row in projected['candidates']
                                   if row['action']['kind'] not in kinds]
        projected.pop('decision_id')
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + ['spy_completion']
        transition['added_action_families'] = transition.get('added_action_families', []) + list(kinds)
        transition['espionage_comparison_gaps'] = list(ESPIONAGE_GAPS)
        return projected, transition
    if current_schema == CAPABILITY_XP2_ESPIONAGE_SCHEMA and saved.get('schema') != current_schema:
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Espionage checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace
        from . import espionage
        identity = SimpleNamespace(episode_id=current['episode_id'],
                                   game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = CAPABILITY_XP2_TRADE_SCHEMA
        projected.pop('espionage')
        kinds = tuple(espionage.ACTION_FIELDS)
        for kind in kinds:
            projected['families'].pop(kind)
        projected['candidates'] = [row for row in projected['candidates']
                                   if row['action']['kind'] not in kinds]
        projected.pop('decision_id')
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + ['espionage']
        transition['added_action_families'] = transition.get('added_action_families', []) + list(kinds)
        return projected, transition
    if current_schema == CAPABILITY_XP2_TRADE_SCHEMA and saved.get('schema') != current_schema:
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Trade checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],
                                   game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = CAPABILITY_XP2_INITIAL_DIPLOMACY_SCHEMA
        fields = ('trade_routes', 'trade_origins')
        kinds = ('make_trade_route', 'change_trade_origin')
        for field in fields:
            projected.pop(field)
        for kind in kinds:
            projected['families'].pop(kind)
        projected['candidates'] = [row for row in projected['candidates']
                                   if row['action']['kind'] not in kinds]
        projected.pop('decision_id')
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + list(fields)
        transition['added_action_families'] = transition.get('added_action_families', []) + list(kinds)
        return projected, transition
    if (current_schema == CAPABILITY_XP2_INITIAL_DIPLOMACY_SCHEMA
            and saved.get('schema') != CAPABILITY_XP2_INITIAL_DIPLOMACY_SCHEMA):
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Initial diplomacy checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],
                                   game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = CAPABILITY_XP2_GOVERNORS_SCHEMA
        projected.pop('diplomacy_overview')
        projected['families'].pop('diplomacy_initiate')
        projected['candidates'] = [row for row in projected['candidates']
                                   if row['action']['kind'] != 'diplomacy_initiate']
        projected.pop('decision_id')
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + ['diplomacy_overview']
        transition['added_action_families'] = transition.get('added_action_families', []) + ['diplomacy_initiate']
        return projected, transition
    if (current_schema == CAPABILITY_XP2_GOVERNORS_SCHEMA
            and saved.get('schema') != CAPABILITY_XP2_GOVERNORS_SCHEMA):
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Governor checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace
        from .governors import ACTION_FIELDS as governor_fields
        identity = SimpleNamespace(episode_id=current['episode_id'],
                                   game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = CAPABILITY_XP2_ENVOYS_SCHEMA
        projected.pop('governors')
        for kind in governor_fields:
            projected['families'].pop(kind)
        projected['candidates'] = [row for row in projected['candidates']
            if row['action']['kind'] not in governor_fields]
        projected.pop('decision_id')
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + ['governors']
        transition['added_action_families'] = transition.get('added_action_families', []) + list(governor_fields)
        return projected, transition
    if (current_schema == CAPABILITY_XP2_ENVOYS_SCHEMA
            and saved.get('schema') != CAPABILITY_XP2_ENVOYS_SCHEMA):
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Envoy checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],
                                   game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = CAPABILITY_XP2_FAITH_PURCHASE_SCHEMA
        projected.pop('envoys')
        for kind in ('send_envoy', 'retain_envoys'):
            projected['families'].pop(kind)
        projected['candidates'] = [row for row in projected['candidates']
            if row['action']['kind'] not in ('send_envoy', 'retain_envoys')]
        projected.pop('decision_id')
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + ['envoys']
        transition['added_action_families'] = transition.get('added_action_families', []) + [
            'send_envoy', 'retain_envoys']
        return projected, transition
    if (current_schema == CAPABILITY_XP2_FAITH_PURCHASE_SCHEMA
            and saved.get('schema') != CAPABILITY_XP2_FAITH_PURCHASE_SCHEMA):
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Faith-purchase checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],
                                   game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        from . import plot_purchases
        projected = copy.deepcopy(current)
        projected['schema'] = CAPABILITY_XP2_POLICY_RECONFIRM_SCHEMA
        if projected['city_purchases'] is not None:
            for city in projected['city_purchases']:
                city['offers'] = [row for row in city['offers']
                                  if row['action']['currency'] != 'YIELD_FAITH']
            faith_ids = {row['candidate_id'] for row in projected['candidates']
                         if row['action'].get('kind') == 'purchase'
                         and 'plot_id' not in row['action']
                         and row['action']['currency'] == 'YIELD_FAITH'}
            projected['candidates'] = [row for row in projected['candidates']
                                       if row['candidate_id'] not in faith_ids]
            family = projected['families']['purchase']
            if family['status'] == 'queried_partial':
                family['unqualified'] = list(plot_purchases.CITY_GAPS)
                family['candidate_ids'] = [key for key in family['candidate_ids']
                                           if key not in faith_ids]
        projected.pop('decision_id', None)
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'],
                          target_schema=current_schema, historical_fields_unchanged=True)
        transition['added_action_families'] = transition.get('added_action_families', []) + [
            'faith_unit_building_purchase']
        return projected, transition
    if (current_schema == CAPABILITY_XP2_POLICY_RECONFIRM_SCHEMA
            and saved.get('schema') != CAPABILITY_XP2_POLICY_RECONFIRM_SCHEMA):
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Policy reconfirm checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],
                                   game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        catalogue = projected['policies']
        if catalogue is not None:
            from . import capability_policies
            old_actions = capability_policies.actions(catalogue, allow_relocation=True)
            if not old_actions:
                projected['candidates'] = [row for row in projected['candidates']
                                           if row['action']['kind'] != 'policies']
            projected['families']['policies']['candidate_ids'] = [
                digest(action) for action in old_actions]
        projected['schema'] = CAPABILITY_XP2_POLICY_RELOCATION_SCHEMA
        projected.pop('decision_id', None)
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_action_families'] = transition.get('added_action_families', []) + [
            'unchanged_policy_confirmation']
        return projected, transition
    if (current_schema == CAPABILITY_XP2_POLICY_RELOCATION_SCHEMA
            and saved.get('schema') != CAPABILITY_XP2_POLICY_RELOCATION_SCHEMA):
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Policy relocation checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],
                                   game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        catalogue = projected['policies']
        if catalogue is not None:
            prior = {row['prior_index'] for row in catalogue['slots']
                     if row['prior_index'] != -1}
            for row in catalogue['slots']:
                row['options'] = [option for option in row['options']
                                  if option['index'] not in prior
                                  or option['index'] == row['prior_index']]
            from . import capability_policies
            actions = capability_policies.actions(catalogue)
            replacement = (dict(candidate_id=digest(actions[0]), action=actions[0])
                           if actions else None)
            rebuilt = []
            inserted = False
            for row in projected['candidates']:
                if row['action']['kind'] == 'policies':
                    if replacement is not None and not inserted:
                        rebuilt.append(replacement)
                        inserted = True
                else:
                    rebuilt.append(row)
            projected['candidates'] = rebuilt
            family = projected['families']['policies']
            family['status'] = 'queried_partial'
            family['unqualified'] = ['active_policy_relocation']
            family['candidate_ids'] = ([] if replacement is None else
                                       [replacement['candidate_id']])
        projected['schema'] = CAPABILITY_XP2_GOVERNMENT_SCHEMA
        projected.pop('decision_id', None)
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_action_families'] = transition.get('added_action_families', []) + [
            'active_policy_relocation']
        return projected, transition
    if (current_schema == CAPABILITY_XP2_GOVERNMENT_SCHEMA
            and saved.get('schema') != CAPABILITY_XP2_GOVERNMENT_SCHEMA):
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Government checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],
                                   game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        del projected['government'], projected['families']['government']
        projected['candidates'] = [row for row in projected['candidates']
                                   if row['action']['kind'] not in ('government', 'retain_government')]
        projected['schema'] = CAPABILITY_XP2_POLICY_UNLOCK_SCHEMA
        del projected['decision_id']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + ['government']
        transition['added_action_families'] = transition.get('added_action_families', []) + [
            'government', 'retain_government']
        return projected, transition
    if (current_schema == CAPABILITY_XP2_POLICY_UNLOCK_SCHEMA
            and saved.get('schema') != current_schema):
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Policy unlock transition requires Gathering Storm')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        del projected['policy_unlock'], projected['families']['policy_unlock'], projected['decision_id']
        projected['candidates'] = [row for row in projected['candidates']
                                   if row['action']['kind'] != 'policy_unlock']
        family = projected['families']['policies']
        if family['status'] == 'queried_partial':
            family['unqualified'] = ['paid_policy_unlock', 'active_policy_relocation']
        projected['schema'] = CAPABILITY_XP2_POLICIES_SCHEMA
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + ['policy_unlock']
        transition['added_action_families'] = transition.get('added_action_families', []) + ['policy_unlock']
        return projected, transition
    if (current_schema == CAPABILITY_XP2_POLICIES_SCHEMA
            and saved.get('schema') != CAPABILITY_XP2_POLICIES_SCHEMA):
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Policy checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],
                                   game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        del projected['policies'], projected['families']['policies']
        projected['candidates'] = [row for row in projected['candidates']
                                   if row['action']['kind'] != 'policies']
        projected['schema'] = CAPABILITY_XP2_STRATEGIC_RESOURCES_SCHEMA
        del projected['decision_id']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + ['policies']
        transition['added_action_families'] = transition.get('added_action_families', []) + ['policies']
        return projected, transition
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
                       actions_closed=False, observation=None,
                       expected_war_source_sha256=None):
    """Validate wrapper shape/digests and return its routed catalogue.

    A ``None`` result means the actor is waiting and the catalogue contains
    only turn controls. A legacy dictionary result is reconstructed and
    digest-bound; the caller must pass it to native ``validate_decisions``.
    Public dialogue, world-war and capability catalogues return their own
    validated contracts and must be routed by their schema predicates.
    """
    if is_diplomacy_decisions(value):
        from .diplomacy_decisions import validate as validate_diplomacy_decisions
        return validate_diplomacy_decisions(value, identity, sequence, turn,
            player_id=player_id, observation=observation,
            actions_closed=actions_closed)
    if is_world_war_decisions(value):
        if expected_war_source_sha256 is None:
            raise ValueError('World-war modal requires a pinned renderer source profile')
        from .world_war_decisions import validate as validate_world_war_decisions
        return validate_world_war_decisions(value, identity, sequence, turn,
            player_id=player_id, observation=observation,
            expected_source_sha256=expected_war_source_sha256,
            actions_closed=actions_closed)
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
           'CAPABILITY_SCHEMA', 'CAPABILITY_CHOICES_SCHEMA', 'CAPABILITY_TURNS_SCHEMA', 'CAPABILITY_WORLD_SCHEMA', 'CAPABILITY_UNIT_ORDERS_SCHEMA', 'CAPABILITY_PRODUCTION_QUEUE_SCHEMA', 'CAPABILITY_PLACEMENT_SCHEMA', 'CAPABILITY_PLACEMENT_INVENTORY_SCHEMA', 'CAPABILITY_UNIT_ATTACKS_SCHEMA', 'CAPABILITY_COMBAT_PUBLIC_SCHEMA', 'CAPABILITY_COMBAT_READINESS_SCHEMA', 'CAPABILITY_CITY_CONTROLS_SCHEMA', 'CAPABILITY_CITY_SHOT_SCHEMA', 'CAPABILITY_DISTRICT_SHOT_SCHEMA', 'CAPABILITY_UNIT_WORK_SCHEMA', 'CAPABILITY_UNIT_WORK_STATE_SCHEMA', 'CAPABILITY_UNIT_WORK_INFO_SCHEMA', 'CAPABILITY_CURRENT_PRODUCTION_SCHEMA', 'CAPABILITY_XP2_STRATEGIC_RESOURCES_SCHEMA', 'CAPABILITY_XP2_POLICIES_SCHEMA', 'CAPABILITY_XP2_GOVERNMENT_SCHEMA', 'CAPABILITY_XP2_POLICY_RELOCATION_SCHEMA', 'CAPABILITY_XP2_POLICY_RECONFIRM_SCHEMA', 'CAPABILITY_XP2_FAITH_PURCHASE_SCHEMA', 'CAPABILITY_XP2_ENVOYS_SCHEMA', 'CAPABILITY_XP2_GOVERNORS_SCHEMA', 'POLICY_RELOCATION_CAPABILITY_SCHEMAS', 'POLICY_RECONFIRM_CAPABILITY_SCHEMAS', 'COMBAT_READINESS_SOURCE_SHA256', 'is_capability_catalogue',
           'validate_capability_catalogue', 'select_capability',
            'WORLD_WAR_DECISIONS_SCHEMA', 'is_world_war_decisions',
            'is_diplomacy_decisions', 'CAPABILITY_XP2_INITIAL_DIPLOMACY_SCHEMA', 'CAPABILITY_XP2_TRADE_SCHEMA',
            'CAPABILITY_XP2_ESPIONAGE_SCHEMA', 'ESPIONAGE_CAPABILITY_SCHEMAS', 'ESPIONAGE_GAPS',
            'upgrade_espionage_catalogue', 'CAPABILITY_XP2_SPY_COMPLETION_SCHEMA',
            'SPY_COMPLETION_CAPABILITY_SCHEMAS', 'SPY_COMPLETION_GAPS', 'upgrade_spy_completion_catalogue',
            'CAPABILITY_XP2_WORLD_CONGRESS_SCHEMA', 'WORLD_CONGRESS_CAPABILITY_SCHEMAS',
            'upgrade_world_congress_catalogue', 'CAPABILITY_XP2_WORLD_CONGRESS_REVIEW_SCHEMA',
            'WORLD_CONGRESS_REVIEW_CAPABILITY_SCHEMAS', 'upgrade_review_catalogue']
