"""Pure schema helpers for LAN per-player turn controls and catalogues."""
from __future__ import annotations

import hashlib
import json
import copy
import re
from collections.abc import Mapping, Sequence
from itertools import chain
from . import prophet_activation, religion_beliefs, religion_founding, religious_unit_operations

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
CAPABILITY_SECONDARY_UNIT_SCHEMA = 'civ6-host.network-secondary-unit-decisions.v1'
CAPABILITY_SECONDARY_UNIT_ORDERS_SCHEMA = 'civ6-host.network-secondary-unit-decisions.v2'
CAPABILITY_SECONDARY_TURN_SCHEMA = 'civ6-host.network-secondary-unit-decisions.v3'
CAPABILITY_SECONDARY_RESEARCH_SCHEMA = 'civ6-host.network-secondary-unit-decisions.v4'
CAPABILITY_SECONDARY_FOUNDERS_SCHEMA = 'civ6-host.network-secondary-unit-decisions.v5'
CAPABILITY_SECONDARY_PRODUCTION_SCHEMA = 'civ6-host.network-secondary-unit-decisions.v6'
CAPABILITY_SECONDARY_QUEUE_SCHEMA = 'civ6-host.network-secondary-unit-decisions.v7'
CAPABILITY_SECONDARY_CITY_CONTROLS_SCHEMA = 'civ6-host.network-secondary-unit-decisions.v8'
CAPABILITY_SECONDARY_WORLD_SCHEMA = 'civ6-host.network-secondary-unit-decisions.v9'
CAPABILITY_SECONDARY_DEVELOPMENT_SCHEMA = 'civ6-host.network-secondary-unit-decisions.v10'
CAPABILITY_SECONDARY_COMBAT_SCHEMA = 'civ6-host.network-secondary-unit-decisions.v11'
CAPABILITY_SECONDARY_OCCUPATION_SCHEMA = 'civ6-host.network-secondary-unit-decisions.v12'
CAPABILITY_SECONDARY_RANGED_SHOTS_SCHEMA = 'civ6-host.network-secondary-unit-decisions.v13'
CAPABILITY_SECONDARY_PURCHASE_SCHEMA = 'civ6-host.network-secondary-unit-decisions.v14'
CAPABILITY_SECONDARY_GOVERNMENT_SCHEMA = 'civ6-host.network-secondary-unit-decisions.v15'
CAPABILITY_SECONDARY_CITY_STATES_SCHEMA = 'civ6-host.network-secondary-unit-decisions.v16'
CAPABILITY_SECONDARY_UNIT_WORK_SCHEMA = 'civ6-host.network-secondary-unit-decisions.v17'
CAPABILITY_SECONDARY_ADJACENT_WORK_SCHEMA = 'civ6-host.network-secondary-unit-decisions.v18'
SECONDARY_CITY_PANEL_FIELDS = ('city_buildings', 'city_growth', 'city_loyalty', 'city_religion', 'rock_bands')
SECONDARY_UNIT_PANEL_KINDS = ('air_operation', 'build_route', 'designate_national_park', 'perform_rock_concert')
SECONDARY_CONGRESS_FIELDS = ('world_congress', 'world_congress_review', 'world_congress_review_status',
                            'world_congress_active_effects', 'world_congress_active_effects_status')
SECONDARY_RELIGION_CONTRACTS = {
    'prophet_activation': prophet_activation,
    'religion_founding': religion_founding,
    'religion_beliefs': religion_beliefs,
    'religious_unit_operations': religious_unit_operations,
}
SECONDARY_RELIGION_KINDS = {
    field: contract.KINDS if contract is religious_unit_operations else (contract.KIND,)
    for field, contract in SECONDARY_RELIGION_CONTRACTS.items()
}
_SECONDARY_WORK_SCHEMAS = (CAPABILITY_SECONDARY_UNIT_WORK_SCHEMA, CAPABILITY_SECONDARY_ADJACENT_WORK_SCHEMA)
_SECONDARY_CITY_STATE_SCHEMAS = (CAPABILITY_SECONDARY_CITY_STATES_SCHEMA, *_SECONDARY_WORK_SCHEMAS)
_SECONDARY_GOVERNMENT_SCHEMAS = (CAPABILITY_SECONDARY_GOVERNMENT_SCHEMA, *_SECONDARY_CITY_STATE_SCHEMAS)
_SECONDARY_PURCHASE_SCHEMAS = (CAPABILITY_SECONDARY_PURCHASE_SCHEMA, *_SECONDARY_GOVERNMENT_SCHEMAS)
_SECONDARY_RANGED_SCHEMAS = (CAPABILITY_SECONDARY_RANGED_SHOTS_SCHEMA, *_SECONDARY_PURCHASE_SCHEMAS)
_SECONDARY_OCCUPATION_SCHEMAS = (CAPABILITY_SECONDARY_OCCUPATION_SCHEMA, *_SECONDARY_RANGED_SCHEMAS)
_SECONDARY_COMBAT_SCHEMAS = (CAPABILITY_SECONDARY_COMBAT_SCHEMA, *_SECONDARY_OCCUPATION_SCHEMAS)
_SECONDARY_DEVELOPMENT_SCHEMAS = (CAPABILITY_SECONDARY_DEVELOPMENT_SCHEMA, *_SECONDARY_COMBAT_SCHEMAS)
_SECONDARY_WORLD_SCHEMAS = (CAPABILITY_SECONDARY_WORLD_SCHEMA, *_SECONDARY_DEVELOPMENT_SCHEMAS)
_SECONDARY_CITY_SCHEMAS = (CAPABILITY_SECONDARY_CITY_CONTROLS_SCHEMA, *_SECONDARY_WORLD_SCHEMAS)
_SECONDARY_QUEUE_SCHEMAS = (CAPABILITY_SECONDARY_QUEUE_SCHEMA, *_SECONDARY_CITY_SCHEMAS)
_SECONDARY_PRODUCTION_SCHEMAS = (CAPABILITY_SECONDARY_PRODUCTION_SCHEMA, *_SECONDARY_QUEUE_SCHEMAS)
_SECONDARY_FOUNDERS_SCHEMAS = (CAPABILITY_SECONDARY_FOUNDERS_SCHEMA, *_SECONDARY_PRODUCTION_SCHEMAS)
_SECONDARY_RESEARCH_SCHEMAS = (CAPABILITY_SECONDARY_RESEARCH_SCHEMA, *_SECONDARY_FOUNDERS_SCHEMAS)
_SECONDARY_TURN_SCHEMAS = (CAPABILITY_SECONDARY_TURN_SCHEMA, *_SECONDARY_RESEARCH_SCHEMAS)
_SECONDARY_UNIT_SCHEMAS = (CAPABILITY_SECONDARY_UNIT_SCHEMA, CAPABILITY_SECONDARY_UNIT_ORDERS_SCHEMA,
                           *_SECONDARY_TURN_SCHEMAS)
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
CAPABILITY_XP2_TRADE_OVERVIEW_SCHEMA = 'civ6-host.network-capability-decisions.v41'
CAPABILITY_XP2_CAPTURED_CITY_SCHEMA = 'civ6-host.network-capability-decisions.v42'
CAPABILITY_XP1_CAPTURED_CITY_SCHEMA = 'civ6-host.network-capability-decisions.v11.captured-city.v1'
CAPABILITY_XP1_CITY_SHOT_SCHEMA = 'civ6-host.network-capability-decisions.v11.captured-city.v2'
CAPABILITY_XP1_DISTRICT_SHOT_SCHEMA = 'civ6-host.network-capability-decisions.v11.captured-city.v3'
CAPABILITY_XP1_GOVERNORS_SCHEMA = 'civ6-host.network-capability-decisions.v11.captured-city.v4'
CAPABILITY_XP1_CITY_STATE_ENVOYS_SCHEMA = 'civ6-host.network-capability-decisions.v11.captured-city.v5'
CAPABILITY_XP1_ENVOY_CHOICES_SCHEMA = 'civ6-host.network-capability-decisions.v11.captured-city.v6'
CAPABILITY_XP1_CITY_STATE_LEVIES_SCHEMA = 'civ6-host.network-capability-decisions.v11.captured-city.v7'
CAPABILITY_XP1_UNIT_LEVIES_SCHEMA = 'civ6-host.network-capability-decisions.v11.captured-city.v8'
CAPABILITY_XP1_DEDICATIONS_SCHEMA = 'civ6-host.network-capability-decisions.v11.captured-city.v9'
CAPABILITY_XP1_TRADE_SCHEMA = 'civ6-host.network-capability-decisions.v11.captured-city.v10'
CAPABILITY_XP1_TRADE_OVERVIEW_SCHEMA = 'civ6-host.network-capability-decisions.v11.captured-city.v11'
class _XP1Registry:
    def __init__(self, name):
        self._name = name

    def _values(self):
        from . import network_turn_xp1_schemas

        return getattr(network_turn_xp1_schemas, self._name)

    def __iter__(self):
        return iter(self._values())

    def __len__(self):
        return len(self._values())

    def __contains__(self, schema):
        return (isinstance(schema, str)
                and schema.startswith(CAPABILITY_COMBAT_READINESS_SCHEMA + '.captured-city.')
                and schema in self._values())


class _XP1SchemaMap(_XP1Registry, Mapping):
    def __getitem__(self, schema):
        if schema not in self:
            raise KeyError(schema)
        return self._values()[schema]


class _XP1Schemas(_XP1Registry, Sequence):
    def __getitem__(self, index):
        return self._values()[index]


class _JoinedSchemas(Sequence):
    def __init__(self, *groups):
        self._groups = groups

    def __iter__(self):
        return chain.from_iterable(self._groups)

    def __len__(self):
        return sum(len(group) for group in self._groups)

    def __contains__(self, schema):
        return any(schema in group for group in self._groups)

    def __getitem__(self, index):
        return tuple(self)[index]


XP1_GOVERNMENT_SCHEMA_BY_BASE = _XP1SchemaMap('XP1_GOVERNMENT_SCHEMA_BY_BASE')
_XP1_GOVERNMENT_BASE_BY_SCHEMA = _XP1SchemaMap('_XP1_GOVERNMENT_BASE_BY_SCHEMA')
XP1_PLOT_PURCHASE_SCHEMA_BY_BASE = _XP1SchemaMap('XP1_PLOT_PURCHASE_SCHEMA_BY_BASE')
_XP1_PLOT_PURCHASE_BASE_BY_SCHEMA = _XP1SchemaMap('_XP1_PLOT_PURCHASE_BASE_BY_SCHEMA')
XP1_CITY_PURCHASE_SCHEMA_BY_BASE = _XP1SchemaMap('XP1_CITY_PURCHASE_SCHEMA_BY_BASE')
_XP1_CITY_PURCHASE_BASE_BY_SCHEMA = _XP1SchemaMap('_XP1_CITY_PURCHASE_BASE_BY_SCHEMA')
XP1_FAITH_PURCHASE_SCHEMA_BY_BASE = _XP1SchemaMap('XP1_FAITH_PURCHASE_SCHEMA_BY_BASE')
_XP1_FAITH_PURCHASE_BASE_BY_SCHEMA = _XP1SchemaMap('_XP1_FAITH_PURCHASE_BASE_BY_SCHEMA')
XP1_CITY_BUILDINGS_SCHEMA_BY_BASE = _XP1SchemaMap('XP1_CITY_BUILDINGS_SCHEMA_BY_BASE')
_XP1_CITY_BUILDINGS_BASE_BY_SCHEMA = _XP1SchemaMap('_XP1_CITY_BUILDINGS_BASE_BY_SCHEMA')
XP1_PROMOTION_SCHEMA_BY_BASE = _XP1SchemaMap('XP1_PROMOTION_SCHEMA_BY_BASE')
_XP1_PROMOTION_BASE_BY_SCHEMA = _XP1SchemaMap('_XP1_PROMOTION_BASE_BY_SCHEMA')
XP1_UPGRADE_SCHEMA_BY_BASE = _XP1SchemaMap('XP1_UPGRADE_SCHEMA_BY_BASE')
_XP1_UPGRADE_BASE_BY_SCHEMA = _XP1SchemaMap('_XP1_UPGRADE_BASE_BY_SCHEMA')
XP1_PRODUCTION_INFO_SCHEMA_BY_BASE = _XP1SchemaMap('XP1_PRODUCTION_INFO_SCHEMA_BY_BASE')
_XP1_PRODUCTION_INFO_BASE_BY_SCHEMA = _XP1SchemaMap('_XP1_PRODUCTION_INFO_BASE_BY_SCHEMA')
XP1_CITY_RELIGION_SCHEMA_BY_BASE = _XP1SchemaMap('XP1_CITY_RELIGION_SCHEMA_BY_BASE')
_XP1_CITY_RELIGION_BASE_BY_SCHEMA = _XP1SchemaMap('_XP1_CITY_RELIGION_BASE_BY_SCHEMA')
XP1_PANTHEON_SCHEMA_BY_BASE = _XP1SchemaMap('XP1_PANTHEON_SCHEMA_BY_BASE')
_XP1_PANTHEON_BASE_BY_SCHEMA = _XP1SchemaMap('_XP1_PANTHEON_BASE_BY_SCHEMA')
XP1_RELIGION_BELIEFS_SCHEMA_BY_BASE = _XP1SchemaMap('XP1_RELIGION_BELIEFS_SCHEMA_BY_BASE')
_XP1_RELIGION_BELIEFS_BASE_BY_SCHEMA = _XP1SchemaMap('_XP1_RELIGION_BELIEFS_BASE_BY_SCHEMA')
XP1_RELIGION_FOUNDING_SCHEMA_BY_BASE = _XP1SchemaMap('XP1_RELIGION_FOUNDING_SCHEMA_BY_BASE')
_XP1_RELIGION_FOUNDING_BASE_BY_SCHEMA = _XP1SchemaMap('_XP1_RELIGION_FOUNDING_BASE_BY_SCHEMA')
XP1_RELIGION_FOUNDING_SCHEMAS = _XP1Schemas('XP1_RELIGION_FOUNDING_SCHEMAS')
XP1_RELIGION_BELIEFS_SCHEMAS = _XP1Schemas('XP1_RELIGION_BELIEFS_SCHEMAS')
XP1_PANTHEON_SCHEMAS = _XP1Schemas('XP1_PANTHEON_SCHEMAS')
XP1_CITY_RELIGION_SCHEMAS = _XP1Schemas('XP1_CITY_RELIGION_SCHEMAS')
XP1_GREAT_PEOPLE_SCHEMA_BY_BASE = _XP1SchemaMap('XP1_GREAT_PEOPLE_SCHEMA_BY_BASE')
_XP1_GREAT_PEOPLE_BASE_BY_SCHEMA = _XP1SchemaMap('_XP1_GREAT_PEOPLE_BASE_BY_SCHEMA')
XP1_GREAT_PEOPLE_SCHEMAS = _XP1Schemas('XP1_GREAT_PEOPLE_SCHEMAS')
XP1_PROPHET_ACTIVATION_SCHEMA_BY_BASE = _XP1SchemaMap('XP1_PROPHET_ACTIVATION_SCHEMA_BY_BASE')
_XP1_PROPHET_ACTIVATION_BASE_BY_SCHEMA = _XP1SchemaMap('_XP1_PROPHET_ACTIVATION_BASE_BY_SCHEMA')
XP1_PROPHET_ACTIVATION_SCHEMAS = _XP1Schemas('XP1_PROPHET_ACTIVATION_SCHEMAS')
XP1_GREAT_PEOPLE_ACTIONS_SCHEMA_BY_BASE = _XP1SchemaMap('XP1_GREAT_PEOPLE_ACTIONS_SCHEMA_BY_BASE')
_XP1_GREAT_PEOPLE_ACTIONS_BASE_BY_SCHEMA = _XP1SchemaMap('_XP1_GREAT_PEOPLE_ACTIONS_BASE_BY_SCHEMA')
XP1_GREAT_PEOPLE_ACTIONS_SCHEMAS = _XP1Schemas('XP1_GREAT_PEOPLE_ACTIONS_SCHEMAS')
XP1_GREAT_PEOPLE_REJECT_SCHEMA_BY_BASE = _XP1SchemaMap('XP1_GREAT_PEOPLE_REJECT_SCHEMA_BY_BASE')
_XP1_GREAT_PEOPLE_REJECT_BASE_BY_SCHEMA = _XP1SchemaMap('_XP1_GREAT_PEOPLE_REJECT_BASE_BY_SCHEMA')
XP1_GREAT_PEOPLE_REJECT_SCHEMAS = _XP1Schemas('XP1_GREAT_PEOPLE_REJECT_SCHEMAS')
XP1_RELIGION_CUSTOM_NAMES_SCHEMA_BY_BASE = _XP1SchemaMap('XP1_RELIGION_CUSTOM_NAMES_SCHEMA_BY_BASE')
_XP1_RELIGION_CUSTOM_NAMES_BASE_BY_SCHEMA = _XP1SchemaMap('_XP1_RELIGION_CUSTOM_NAMES_BASE_BY_SCHEMA')
XP1_RELIGION_CUSTOM_NAMES_SCHEMAS = _XP1Schemas('XP1_RELIGION_CUSTOM_NAMES_SCHEMAS')
XP1_GREAT_PERSON_ACTIVATION_SCHEMA_BY_BASE = _XP1SchemaMap('XP1_GREAT_PERSON_ACTIVATION_SCHEMA_BY_BASE')
_XP1_GREAT_PERSON_ACTIVATION_BASE_BY_SCHEMA = _XP1SchemaMap('_XP1_GREAT_PERSON_ACTIVATION_BASE_BY_SCHEMA')
XP1_GREAT_PERSON_ACTIVATION_SCHEMAS = _XP1Schemas('XP1_GREAT_PERSON_ACTIVATION_SCHEMAS')
XP1_RELIGIOUS_UNIT_OPERATIONS_SCHEMA_BY_BASE = _XP1SchemaMap('XP1_RELIGIOUS_UNIT_OPERATIONS_SCHEMA_BY_BASE')
_XP1_RELIGIOUS_UNIT_OPERATIONS_BASE_BY_SCHEMA = _XP1SchemaMap('_XP1_RELIGIOUS_UNIT_OPERATIONS_BASE_BY_SCHEMA')
XP1_RELIGIOUS_UNIT_OPERATIONS_SCHEMAS = _XP1Schemas('XP1_RELIGIOUS_UNIT_OPERATIONS_SCHEMAS')
XP1_CITY_RELIGION_DETAILS_SCHEMA_BY_BASE = _XP1SchemaMap('XP1_CITY_RELIGION_DETAILS_SCHEMA_BY_BASE')
_XP1_CITY_RELIGION_DETAILS_BASE_BY_SCHEMA = _XP1SchemaMap('_XP1_CITY_RELIGION_DETAILS_BASE_BY_SCHEMA')
XP1_CITY_RELIGION_DETAILS_SCHEMAS = _XP1Schemas('XP1_CITY_RELIGION_DETAILS_SCHEMAS')
XP1_PRODUCTION_INFO_SCHEMAS = _XP1Schemas('XP1_PRODUCTION_INFO_SCHEMAS')
XP1_TRADE_SCHEMAS = _XP1Schemas('XP1_TRADE_SCHEMAS')
_XP1_DEDICATION_SCHEMAS = _XP1Schemas('_XP1_DEDICATION_SCHEMAS')
XP1_LEVY_SCHEMAS = _XP1Schemas('XP1_LEVY_SCHEMAS')
XP1_ENVOY_CHOICE_SCHEMAS = _XP1Schemas('XP1_ENVOY_CHOICE_SCHEMAS')
XP1_CITY_STATE_ENVOY_SCHEMAS = _XP1Schemas('XP1_CITY_STATE_ENVOY_SCHEMAS')
_XP1_CAPTURE_SCHEMAS = _XP1Schemas('_XP1_CAPTURE_SCHEMAS')
XP1_TRADE_OVERVIEW_SCHEMAS = _XP1Schemas('XP1_TRADE_OVERVIEW_SCHEMAS')


_XP1_SHOT_TRANSITIONS = {
    CAPABILITY_XP1_CITY_SHOT_SCHEMA: (CAPABILITY_XP1_CAPTURED_CITY_SCHEMA, 'city_shots', 'city_range_attack'),
    CAPABILITY_XP1_DISTRICT_SHOT_SCHEMA: (CAPABILITY_XP1_CITY_SHOT_SCHEMA, 'district_shots', 'district_range_attack'),
}
CAPABILITY_XP2_STANDARD_TRADE_SCHEMA = 'civ6-host.network-capability-decisions.standard-trade.v1'
CAPABILITY_XP2_STOCK_FORMATIONS_SCHEMA = 'civ6-host.network-capability-decisions.standard-trade.v2'
CAPABILITY_XP2_STOCK_DEDICATIONS_SCHEMA = 'civ6-host.network-capability-decisions.standard-trade.v3'
CAPABILITY_XP2_STOCK_CONGRESS_SCHEMA = 'civ6-host.network-capability-decisions.standard-trade.v4'
_STOCK_TRADE_BASE_SCHEMAS = (
    CAPABILITY_XP2_STANDARD_TRADE_SCHEMA, CAPABILITY_XP2_STOCK_FORMATIONS_SCHEMA,
    CAPABILITY_XP2_STOCK_DEDICATIONS_SCHEMA, CAPABILITY_XP2_STOCK_CONGRESS_SCHEMA,
)
_STOCK_CAPTURE_SCHEMA_BY_BASE = {
    schema: schema.replace('.standard-trade.', '.standard-trade-captured-city.')
    for schema in _STOCK_TRADE_BASE_SCHEMAS
}
_CAPTURE_BASE_SCHEMA = {
    CAPABILITY_XP1_CAPTURED_CITY_SCHEMA: CAPABILITY_COMBAT_READINESS_SCHEMA,
    CAPABILITY_XP2_CAPTURED_CITY_SCHEMA: CAPABILITY_XP2_TRADE_OVERVIEW_SCHEMA,
    **{extended: base for base, extended in _STOCK_CAPTURE_SCHEMA_BY_BASE.items()},
}
STOCK_CONGRESS_SCHEMAS = (
    CAPABILITY_XP2_STOCK_CONGRESS_SCHEMA, _STOCK_CAPTURE_SCHEMA_BY_BASE[CAPABILITY_XP2_STOCK_CONGRESS_SCHEMA])
STOCK_DEDICATION_SCHEMAS = (
    CAPABILITY_XP2_STOCK_DEDICATIONS_SCHEMA,
    _STOCK_CAPTURE_SCHEMA_BY_BASE[CAPABILITY_XP2_STOCK_DEDICATIONS_SCHEMA], *STOCK_CONGRESS_SCHEMAS)
STOCK_FORMATION_SCHEMAS = (
    CAPABILITY_XP2_STOCK_FORMATIONS_SCHEMA,
    _STOCK_CAPTURE_SCHEMA_BY_BASE[CAPABILITY_XP2_STOCK_FORMATIONS_SCHEMA], *STOCK_DEDICATION_SCHEMAS)
STOCK_TRADE_CAPABILITY_SCHEMAS = (
    CAPABILITY_XP2_STANDARD_TRADE_SCHEMA,
    _STOCK_CAPTURE_SCHEMA_BY_BASE[CAPABILITY_XP2_STANDARD_TRADE_SCHEMA], *STOCK_FORMATION_SCHEMAS)
CONGRESS_READ_ONLY_KINDS = frozenset((
    'government', 'retain_government', 'policies', 'policy_unlock',
    'appoint_governor', 'promote_governor', 'assign_governor', 'consider_governor_titles'))


def congress_action_read_only(value, kind):
    """Government and governor edits are read-only during native IsInSession.

    The Great People reader already applies its own official phase gate.
    Historical catalogues and the underlying observations retain their meaning.
    """
    schema = xp2_great_person_base_schema(value.get('schema'))
    return ((schema in WORLD_CONGRESS_CAPABILITY_SCHEMAS or schema in _SECONDARY_UNIT_SCHEMAS)
            and type(value.get('world_congress')) is dict
            and value['world_congress'].get('in_session') is True
            and kind in CONGRESS_READ_ONLY_KINDS)


def _remove_congress_read_only_candidates(value):
    removed = {row['candidate_id'] for row in value['candidates']
               if congress_action_read_only(value, row['action']['kind'])}
    if not removed:
        return
    value['candidates'] = [row for row in value['candidates'] if row['candidate_id'] not in removed]
    for family in value['families'].values():
        if 'candidate_ids' in family:
            family['candidate_ids'] = [key for key in family['candidate_ids'] if key not in removed]


ESPIONAGE_GAPS = ('spy_completion_repeat_pending_identity',)
SPY_COMPLETION_GAPS = ('spy_popup_interface_mode_lifetime', 'spy_notification_reactivation')
INITIAL_DIPLOMACY_GAPS = ('deal_screens_and_non_direct_initial_choices',)
STOCK_INITIAL_DIPLOMACY_GAPS = ('initial_choices_other_than_denunciation',)
STOCK_MAJOR_PEACE_GAPS = ('initial_choices_other_than_denunciation_and_major_peace',)
STOCK_NEGOTIATION_GAPS = ('initial_choices_other_than_denunciation_and_major_negotiation',)
STOCK_FRIENDSHIP_GAPS = ('initial_choices_other_than_denunciation_friendship_and_major_negotiation',)
STOCK_PROMISE_GAPS = ('initial_choices_other_than_denunciation_friendship_promises_and_major_negotiation',)
STOCK_CITY_STATE_PEACE_GAPS = (
    'initial_choices_other_than_denunciation_friendship_promises_major_negotiation_and_city_state_peace',)
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
    CAPABILITY_XP2_TRADE_OVERVIEW_SCHEMA,
    CAPABILITY_XP2_CAPTURED_CITY_SCHEMA,
)


# An additive family keeps the exact preceding XP2 branch (including stock,
# Congress and captured-city fields) in its wire identity.
_XP2_LEVY_SCHEMA_BY_BASE = {
    base: base + '.military-levies.v1'
    for base in (*_CAPABILITY_SCHEMAS[_CAPABILITY_SCHEMAS.index(CAPABILITY_XP2_ENVOYS_SCHEMA):],
                 *STOCK_TRADE_CAPABILITY_SCHEMAS)
}
_XP2_LEVY_BASE_SCHEMA = {schema: base for base, schema in _XP2_LEVY_SCHEMA_BY_BASE.items()}
XP2_LEVY_SCHEMAS = tuple(_XP2_LEVY_BASE_SCHEMA)


# These are the implemented XP2 v31-v42 and stock public branches. The runtime
# separately admits only the exact current image and captured stock/BBG inputs.
_XP2_RELIGIOUS_UNIT_BASES = (
    CAPABILITY_XP2_ENVOYS_SCHEMA, CAPABILITY_XP2_GOVERNORS_SCHEMA,
    CAPABILITY_XP2_INITIAL_DIPLOMACY_SCHEMA, CAPABILITY_XP2_TRADE_SCHEMA,
    CAPABILITY_XP2_ESPIONAGE_SCHEMA, CAPABILITY_XP2_SPY_COMPLETION_SCHEMA,
    CAPABILITY_XP2_WORLD_CONGRESS_SCHEMA, CAPABILITY_XP2_WORLD_CONGRESS_REVIEW_SCHEMA,
    CAPABILITY_NATIVE_COMMAND_PERMISSIONS_SCHEMA, CAPABILITY_XP2_CONGRESS_ACTIVE_EFFECTS_SCHEMA,
    CAPABILITY_XP2_TRADE_OVERVIEW_SCHEMA, CAPABILITY_XP2_CAPTURED_CITY_SCHEMA,
    *STOCK_TRADE_CAPABILITY_SCHEMAS,
)
XP2_RELIGIOUS_UNIT_OPERATIONS_SCHEMA_BY_BASE = {
    base: base+'.religious-unit-operations.v1'
    for base in (*_XP2_RELIGIOUS_UNIT_BASES,
                 *(_XP2_LEVY_SCHEMA_BY_BASE[base] for base in _XP2_RELIGIOUS_UNIT_BASES))
}
_XP2_RELIGIOUS_UNIT_OPERATIONS_BASE_BY_SCHEMA = {
    new:base for base,new in XP2_RELIGIOUS_UNIT_OPERATIONS_SCHEMA_BY_BASE.items()}
XP2_RELIGIOUS_UNIT_OPERATIONS_SCHEMAS = tuple(_XP2_RELIGIOUS_UNIT_OPERATIONS_BASE_BY_SCHEMA)

# Independent XP2 options follow the implemented public branches, with or
# without religious unit operations. Runtime admission still checks the exact
# installed image and captured stock/BBG profile; these maps only version data.
_XP2_RELIGIOUS_CHAIN_BASES = (*XP2_RELIGIOUS_UNIT_OPERATIONS_SCHEMA_BY_BASE,
                             *XP2_RELIGIOUS_UNIT_OPERATIONS_SCHEMAS)
XP2_PROPHET_ACTIVATION_SCHEMA_BY_BASE = {
    base: base+'.prophet-activation.v1' for base in _XP2_RELIGIOUS_CHAIN_BASES}
_XP2_PROPHET_ACTIVATION_BASE_BY_SCHEMA = {
    new:base for base,new in XP2_PROPHET_ACTIVATION_SCHEMA_BY_BASE.items()}
XP2_RELIGION_FOUNDING_SCHEMA_BY_BASE = {
    base: base+'.religion-founding.v1'
    for base in (*_XP2_RELIGIOUS_CHAIN_BASES, *_XP2_PROPHET_ACTIVATION_BASE_BY_SCHEMA)}
_XP2_RELIGION_FOUNDING_BASE_BY_SCHEMA = {
    new:base for base,new in XP2_RELIGION_FOUNDING_SCHEMA_BY_BASE.items()}
XP2_RELIGION_BELIEFS_SCHEMA_BY_BASE = {
    base: base+'.religion-beliefs.v1'
    for base in (*_XP2_RELIGIOUS_CHAIN_BASES, *_XP2_PROPHET_ACTIVATION_BASE_BY_SCHEMA,
                 *_XP2_RELIGION_FOUNDING_BASE_BY_SCHEMA)}
_XP2_RELIGION_BELIEFS_BASE_BY_SCHEMA = {
    new:base for base,new in XP2_RELIGION_BELIEFS_SCHEMA_BY_BASE.items()}


# Pantheon remains an independent final XP2 option over every implemented
# preceding combination; it does not enable any XP1 feature or choose a belief.
XP2_PANTHEON_SCHEMA_BY_BASE = {
    base: base+'.pantheon.v2'
    for base in (*_XP2_RELIGIOUS_CHAIN_BASES, *_XP2_PROPHET_ACTIVATION_BASE_BY_SCHEMA,
                 *_XP2_RELIGION_FOUNDING_BASE_BY_SCHEMA, *_XP2_RELIGION_BELIEFS_BASE_BY_SCHEMA)}
_XP2_PANTHEON_BASE_BY_SCHEMA = {new:base for base,new in XP2_PANTHEON_SCHEMA_BY_BASE.items()}
XP2_CITY_RELIGION_DETAILS_SCHEMA_BY_BASE = {
    base:base+'.city-religion-details.v1'
    for base in (*XP2_PANTHEON_SCHEMA_BY_BASE, *_XP2_PANTHEON_BASE_BY_SCHEMA)}
_XP2_CITY_RELIGION_DETAILS_BASE_BY_SCHEMA = {
    new:base for base,new in XP2_CITY_RELIGION_DETAILS_SCHEMA_BY_BASE.items()}

_XP2_STOCK_ROOTS = (*_STOCK_TRADE_BASE_SCHEMAS, *_STOCK_CAPTURE_SCHEMA_BY_BASE.values())
XP2_CITY_BUILDINGS_SCHEMA_BY_BASE = {
    base: base + '.city-buildings.v1'
    for base in (*_XP2_STOCK_ROOTS, *_XP2_LEVY_BASE_SCHEMA, *_XP2_RELIGIOUS_CHAIN_BASES,
                 *_XP2_PROPHET_ACTIVATION_BASE_BY_SCHEMA, *_XP2_RELIGION_FOUNDING_BASE_BY_SCHEMA,
                 *_XP2_RELIGION_BELIEFS_BASE_BY_SCHEMA, *_XP2_PANTHEON_BASE_BY_SCHEMA,
                 *_XP2_CITY_RELIGION_DETAILS_BASE_BY_SCHEMA)
}
_XP2_CITY_BUILDINGS_BASE_BY_SCHEMA = {
    new: base for base, new in XP2_CITY_BUILDINGS_SCHEMA_BY_BASE.items()}

XP2_GREAT_PEOPLE_SCHEMA_BY_BASE = {
    base: base + '.great-people.v1'
    for base in (*_XP2_RELIGIOUS_CHAIN_BASES, *_XP2_PROPHET_ACTIVATION_BASE_BY_SCHEMA,
                 *_XP2_RELIGION_FOUNDING_BASE_BY_SCHEMA, *_XP2_RELIGION_BELIEFS_BASE_BY_SCHEMA,
                 *_XP2_PANTHEON_BASE_BY_SCHEMA, *_XP2_CITY_RELIGION_DETAILS_BASE_BY_SCHEMA,
                 *_XP2_CITY_BUILDINGS_BASE_BY_SCHEMA)
}
_XP2_GREAT_PEOPLE_BASE_BY_SCHEMA = {
    new: base for base, new in XP2_GREAT_PEOPLE_SCHEMA_BY_BASE.items()}
XP2_GREAT_PEOPLE_ACTIONS_SCHEMA_BY_BASE = {
    base: base + '.great-people-actions.v1' for base in _XP2_GREAT_PEOPLE_BASE_BY_SCHEMA}
_XP2_GREAT_PEOPLE_ACTIONS_BASE_BY_SCHEMA = {
    new: base for base, new in XP2_GREAT_PEOPLE_ACTIONS_SCHEMA_BY_BASE.items()}
XP2_GREAT_PEOPLE_SCHEMAS = (*_XP2_GREAT_PEOPLE_BASE_BY_SCHEMA, *_XP2_GREAT_PEOPLE_ACTIONS_BASE_BY_SCHEMA)

XP2_GREAT_PERSON_ACTIVATION_SCHEMA_BY_BASE = {
    base: base + '.great-person-activation.v1'
    for base in (*XP2_CITY_BUILDINGS_SCHEMA_BY_BASE, *_XP2_CITY_BUILDINGS_BASE_BY_SCHEMA,
                 *XP2_GREAT_PEOPLE_SCHEMAS, *_SECONDARY_UNIT_SCHEMAS)
}
_XP2_GREAT_PERSON_ACTIVATION_BASE_BY_SCHEMA = {
    new: base for base, new in XP2_GREAT_PERSON_ACTIVATION_SCHEMA_BY_BASE.items()
}


def xp2_great_person_base_schema(schema):
    return _XP2_GREAT_PERSON_ACTIVATION_BASE_BY_SCHEMA.get(schema, schema) if type(schema) is str else schema


def _with_xp2_city_buildings(bases):
    schemas = (*bases, *(XP2_CITY_BUILDINGS_SCHEMA_BY_BASE[base] for base in bases
                         if base in XP2_CITY_BUILDINGS_SCHEMA_BY_BASE))
    great_people = tuple(XP2_GREAT_PEOPLE_SCHEMA_BY_BASE[base] for base in schemas
                         if base in XP2_GREAT_PEOPLE_SCHEMA_BY_BASE)
    return (*schemas, *great_people, *(XP2_GREAT_PEOPLE_ACTIONS_SCHEMA_BY_BASE[base] for base in great_people))


XP2_CITY_RELIGION_DETAILS_SCHEMAS = _with_xp2_city_buildings(_XP2_CITY_RELIGION_DETAILS_BASE_BY_SCHEMA)
CITY_RELIGION_SCHEMAS = _JoinedSchemas(
    XP1_CITY_RELIGION_SCHEMAS, XP2_CITY_RELIGION_DETAILS_SCHEMAS, _SECONDARY_UNIT_SCHEMAS)
CITY_RELIGION_DETAILS_SCHEMAS = _JoinedSchemas(
    XP1_CITY_RELIGION_DETAILS_SCHEMAS, XP2_CITY_RELIGION_DETAILS_SCHEMAS, _SECONDARY_UNIT_SCHEMAS)


def _with_xp2_city_religion_details(bases):
    return _with_xp2_city_buildings(
        (*bases, *(XP2_CITY_RELIGION_DETAILS_SCHEMA_BY_BASE[base] for base in bases
                   if base in XP2_CITY_RELIGION_DETAILS_SCHEMA_BY_BASE)))


XP2_PANTHEON_SCHEMAS = _with_xp2_city_religion_details(_XP2_PANTHEON_BASE_BY_SCHEMA)
PANTHEON_SCHEMAS = _JoinedSchemas(XP1_PANTHEON_SCHEMAS, XP2_PANTHEON_SCHEMAS)


def _with_xp2_pantheon(bases):
    return _with_xp2_city_religion_details(
        (*bases, *(XP2_PANTHEON_SCHEMA_BY_BASE[base] for base in bases
                   if base in XP2_PANTHEON_SCHEMA_BY_BASE)))


def _with_xp2_religious_chain(bases):
    schemas = tuple(bases)
    for mapping in (XP2_PROPHET_ACTIVATION_SCHEMA_BY_BASE,
                    XP2_RELIGION_FOUNDING_SCHEMA_BY_BASE,
                    XP2_RELIGION_BELIEFS_SCHEMA_BY_BASE):
        schemas += tuple(mapping[base] for base in schemas if base in mapping)
    return _with_xp2_pantheon(schemas)


XP2_PROPHET_ACTIVATION_SCHEMAS = _with_xp2_religious_chain(_XP2_PROPHET_ACTIVATION_BASE_BY_SCHEMA)
XP2_RELIGION_FOUNDING_SCHEMAS = _with_xp2_religious_chain(_XP2_RELIGION_FOUNDING_BASE_BY_SCHEMA)
XP2_RELIGION_BELIEFS_SCHEMAS = _with_xp2_pantheon(_XP2_RELIGION_BELIEFS_BASE_BY_SCHEMA)
PROPHET_ACTIVATION_SCHEMAS = _JoinedSchemas(XP1_PROPHET_ACTIVATION_SCHEMAS, XP2_PROPHET_ACTIVATION_SCHEMAS)
RELIGION_FOUNDING_SCHEMAS = _JoinedSchemas(XP1_RELIGION_FOUNDING_SCHEMAS, XP2_RELIGION_FOUNDING_SCHEMAS)
RELIGION_BELIEFS_SCHEMAS = _JoinedSchemas(XP1_RELIGION_BELIEFS_SCHEMAS, XP2_RELIGION_BELIEFS_SCHEMAS)
XP2_RELIGIOUS_UNIT_OPERATIONS_SCHEMAS = _with_xp2_religious_chain(XP2_RELIGIOUS_UNIT_OPERATIONS_SCHEMAS)
RELIGIOUS_UNIT_OPERATIONS_SCHEMAS = _JoinedSchemas(XP1_RELIGIOUS_UNIT_OPERATIONS_SCHEMAS, XP2_RELIGIOUS_UNIT_OPERATIONS_SCHEMAS)


def _xp2_religious_chain_base_schema(schema):
    schema = _XP2_GREAT_PEOPLE_ACTIONS_BASE_BY_SCHEMA.get(schema, schema)
    schema = _XP2_GREAT_PEOPLE_BASE_BY_SCHEMA.get(schema, schema)
    schema = _XP2_CITY_BUILDINGS_BASE_BY_SCHEMA.get(schema, schema)
    schema = _XP2_CITY_RELIGION_DETAILS_BASE_BY_SCHEMA.get(schema, schema)
    schema = _XP2_PANTHEON_BASE_BY_SCHEMA.get(schema, schema)
    for mapping in (_XP2_RELIGION_BELIEFS_BASE_BY_SCHEMA,
                    _XP2_RELIGION_FOUNDING_BASE_BY_SCHEMA,
                    _XP2_PROPHET_ACTIVATION_BASE_BY_SCHEMA):
        schema = mapping.get(schema, schema)
    return schema


def _with_xp2_religious_unit_operations(bases):
    return _with_xp2_religious_chain(
        (*bases, *(XP2_RELIGIOUS_UNIT_OPERATIONS_SCHEMA_BY_BASE[base] for base in bases
                   if base in XP2_RELIGIOUS_UNIT_OPERATIONS_SCHEMA_BY_BASE)))


XP2_LEVY_SCHEMAS = _with_xp2_religious_unit_operations(XP2_LEVY_SCHEMAS)
CITY_STATE_LEVY_SCHEMAS = _JoinedSchemas(XP1_LEVY_SCHEMAS, XP2_LEVY_SCHEMAS)
UNIT_LEVY_SCHEMAS = _JoinedSchemas(
    (CAPABILITY_XP1_UNIT_LEVIES_SCHEMA,), _XP1_DEDICATION_SCHEMAS, XP2_LEVY_SCHEMAS)


def xp2_levy_base_schema(schema):
    return _XP2_LEVY_BASE_SCHEMA.get(schema, schema) if type(schema) is str else schema


def _with_levy_schemas(schemas):
    return _with_xp2_religious_unit_operations(
        (*schemas, *(_XP2_LEVY_SCHEMA_BY_BASE[base] for base in schemas
                     if base in _XP2_LEVY_SCHEMA_BY_BASE)))


STOCK_CONGRESS_SCHEMAS = _with_levy_schemas(STOCK_CONGRESS_SCHEMAS)
STOCK_DEDICATION_SCHEMAS = _with_levy_schemas(STOCK_DEDICATION_SCHEMAS)
DEDICATION_SCHEMAS = _JoinedSchemas(_XP1_DEDICATION_SCHEMAS, STOCK_DEDICATION_SCHEMAS)
STOCK_FORMATION_SCHEMAS = _with_levy_schemas(STOCK_FORMATION_SCHEMAS)
STOCK_TRADE_CAPABILITY_SCHEMAS = _with_levy_schemas(STOCK_TRADE_CAPABILITY_SCHEMAS)


def _capability_schemas_from(first):
    schemas = _with_levy_schemas(_CAPABILITY_SCHEMAS[_CAPABILITY_SCHEMAS.index(first):])
    stock = STOCK_TRADE_CAPABILITY_SCHEMAS if CAPABILITY_XP2_ENVOYS_SCHEMA in schemas else ()
    if CAPABILITY_COMBAT_READINESS_SCHEMA in schemas:
        return _JoinedSchemas(schemas, _XP1_CAPTURE_SCHEMAS, stock)
    return (*schemas, *stock)


def _capability_version(schema):
    schema = _xp2_religious_chain_base_schema(schema)
    schema = _XP2_RELIGIOUS_UNIT_OPERATIONS_BASE_BY_SCHEMA.get(schema,schema)
    schema = xp2_levy_base_schema(schema)
    if schema in STOCK_TRADE_CAPABILITY_SCHEMAS:
        schema = CAPABILITY_XP2_ENVOYS_SCHEMA
    if schema in _XP1_CAPTURE_SCHEMAS:
        schema = CAPABILITY_COMBAT_READINESS_SCHEMA
    return _CAPABILITY_SCHEMAS.index(schema) + 1


_TURN_CAPABILITY_SCHEMAS = _capability_schemas_from(CAPABILITY_TURNS_SCHEMA)
ATTACK_CAPABILITY_SCHEMAS = _capability_schemas_from(CAPABILITY_UNIT_ATTACKS_SCHEMA)
PUBLIC_COMBAT_CAPABILITY_SCHEMAS = _JoinedSchemas(
    _capability_schemas_from(CAPABILITY_COMBAT_PUBLIC_SCHEMA), _SECONDARY_COMBAT_SCHEMAS)
COMBAT_READINESS_CAPABILITY_SCHEMAS = _capability_schemas_from(CAPABILITY_COMBAT_READINESS_SCHEMA)
UNIT_WORK_STATE_CAPABILITY_SCHEMAS = _JoinedSchemas(
    _capability_schemas_from(CAPABILITY_UNIT_WORK_STATE_SCHEMA), _SECONDARY_WORK_SCHEMAS)
CURRENT_PRODUCTION_CAPABILITY_SCHEMAS = _JoinedSchemas(
    _capability_schemas_from(CAPABILITY_CURRENT_PRODUCTION_SCHEMA), XP1_PRODUCTION_INFO_SCHEMAS)
POLICY_RELOCATION_CAPABILITY_SCHEMAS = _JoinedSchemas(
    _capability_schemas_from(CAPABILITY_XP2_POLICY_RELOCATION_SCHEMA), _SECONDARY_GOVERNMENT_SCHEMAS)
POLICY_RECONFIRM_CAPABILITY_SCHEMAS = _JoinedSchemas(
    _capability_schemas_from(CAPABILITY_XP2_POLICY_RECONFIRM_SCHEMA), _SECONDARY_GOVERNMENT_SCHEMAS)
ESPIONAGE_CAPABILITY_SCHEMAS = _capability_schemas_from(CAPABILITY_XP2_ESPIONAGE_SCHEMA)
SPY_COMPLETION_CAPABILITY_SCHEMAS = _capability_schemas_from(CAPABILITY_XP2_SPY_COMPLETION_SCHEMA)
WORLD_CONGRESS_CAPABILITY_SCHEMAS = (*_capability_schemas_from(CAPABILITY_XP2_WORLD_CONGRESS_SCHEMA), *STOCK_CONGRESS_SCHEMAS)
WORLD_CONGRESS_REVIEW_CAPABILITY_SCHEMAS = (*_capability_schemas_from(CAPABILITY_XP2_WORLD_CONGRESS_REVIEW_SCHEMA), *STOCK_CONGRESS_SCHEMAS)
NATIVE_COMMAND_PERMISSIONS_SCHEMAS = (*_capability_schemas_from(CAPABILITY_NATIVE_COMMAND_PERMISSIONS_SCHEMA), *STOCK_CONGRESS_SCHEMAS)
CONGRESS_ACTIVE_EFFECTS_CAPABILITY_SCHEMAS = (*_capability_schemas_from(CAPABILITY_XP2_CONGRESS_ACTIVE_EFFECTS_SCHEMA), *STOCK_CONGRESS_SCHEMAS)
STOCK_TRADE_OVERVIEW_SCHEMAS = _JoinedSchemas(
    XP1_TRADE_OVERVIEW_SCHEMAS, STOCK_TRADE_CAPABILITY_SCHEMAS)
TRADE_OVERVIEW_CAPABILITY_SCHEMAS = _JoinedSchemas(
    _with_levy_schemas((CAPABILITY_XP2_TRADE_OVERVIEW_SCHEMA, CAPABILITY_XP2_CAPTURED_CITY_SCHEMA)),
    STOCK_TRADE_OVERVIEW_SCHEMAS)
STRATEGIC_READER_FAMILIES = frozenset((
    'found_city', 'queue_append', 'queue_remove', 'queue_swap',
    'world_select_unit', 'world_deselect_unit', 'world_plot_click', 'unit_order', 'unit_attack', 'unit_formation',
    'upgrade_unit', 'policies', 'policy_unlock', 'government', 'retain_government',
    'send_envoy', 'retain_envoys', 'change_trade_origin',
    'city_range_attack', 'district_range_attack',
    'spread_religion', 'evangelize_belief', 'launch_inquisition', 'remove_heresy',
    'activate_prophet', 'found_religion', 'add_belief', 'pantheon',
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
    schema = xp2_great_person_base_schema(value.get('schema'))
    if schema in NATIVE_COMMAND_PERMISSIONS_SCHEMAS:
        retained = value['native_command_permissions']
        if permissions is not None and permissions != retained:
            raise ValueError('Conflicting native command permission reads')
        permissions = retained
    if permissions is not None:
        validate_native_command_permissions(permissions, value['player_id'], value['turn'], value['sequence'])
    return (actions_closed or is_waiting(controls)
            or family == 'activate_great_person' and schema in _SECONDARY_UNIT_SCHEMAS and value['unit_orders'] is None
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

SUPPORTED_SCHEMAS = _JoinedSchemas(
    (PRODUCTION_SCHEMA, GROWTH_SCHEMA, INFO_SCHEMA, WORK_SCHEMA,
     SCHEMA, PREVIOUS_SCHEMA, LEGACY_SCHEMA, *_SECONDARY_UNIT_SCHEMAS),
    _with_levy_schemas(_CAPABILITY_SCHEMAS), _XP1_CAPTURE_SCHEMAS,
    STOCK_TRADE_CAPABILITY_SCHEMAS, tuple(_XP2_GREAT_PERSON_ACTIVATION_BASE_BY_SCHEMA))
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
    return (type(value) is dict and (value.get('schema') in _CAPABILITY_SCHEMAS
            or value.get('schema') in _SECONDARY_UNIT_SCHEMAS
            or value.get('schema') in _XP1_CAPTURE_SCHEMAS
            or value.get('schema') in XP2_LEVY_SCHEMAS
            or value.get('schema') in XP2_RELIGIOUS_UNIT_OPERATIONS_SCHEMAS
            or value.get('schema') in XP2_PROPHET_ACTIVATION_SCHEMAS
            or value.get('schema') in XP2_RELIGION_FOUNDING_SCHEMAS
            or value.get('schema') in XP2_RELIGION_BELIEFS_SCHEMAS
            or value.get('schema') in XP2_PANTHEON_SCHEMAS
            or value.get('schema') in XP2_CITY_RELIGION_DETAILS_SCHEMAS
            or value.get('schema') in XP2_GREAT_PEOPLE_SCHEMAS
            or xp2_great_person_base_schema(value.get('schema')) != value.get('schema')
            or value.get('schema') in STOCK_TRADE_CAPABILITY_SCHEMAS))


def has_xp1_unit_work(value):
    schema = value.get('schema')
    return ('unit_work' in value and (schema == CAPABILITY_COMBAT_READINESS_SCHEMA
                                     or schema in _XP1_CAPTURE_SCHEMAS))


def has_adjacent_unit_work(value):
    from .unit_work import ADJACENT_KIND

    families = value.get('families')
    return type(families) is dict and ADJACENT_KIND in families


def is_world_war_decisions(value):
    return type(value) is dict and value.get('schema') == WORLD_WAR_DECISIONS_SCHEMA


def is_diplomacy_decisions(value):
    from .diplomacy_decisions import is_catalogue
    return is_catalogue(value)


def borrowed_dialogue_player(value, local_player_id):
    if is_diplomacy_decisions(value) and value['player_id'] != local_player_id:
        return value['player_id']
    return None


def offered_forced_turn(value, action):
    """Same inactive-player exception on client and server, after validation.

    This consumes an explicit native UI offer; it does not derive availability
    from activity flags or upgrade legacy catalogues.
    """
    return (type(value) is dict
            and (value.get('schema') in _SECONDARY_TURN_SCHEMAS
                 or value.get('schema') in _TURN_CAPABILITY_SCHEMAS)
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
    if xp2_great_person_base_schema(value['schema']) != value['schema']:
        previous = _xp2_great_person_projection(value, observation=observation, actions_closed=actions_closed)
        validate_capability_catalogue(previous, identity, sequence, turn, player_id=player_id,
                                      actions_closed=actions_closed, observation=observation)
        return value
    if value['schema'] in _SECONDARY_UNIT_SCHEMAS:
        fields = _CAPABILITY_FIELDS | {'unit_orders'}
        if value['schema'] in _SECONDARY_TURN_SCHEMAS:
            fields = fields | {'turn_availability'}
        if value['schema'] in _SECONDARY_RESEARCH_SCHEMAS:
            fields = fields | {'research_choices'}
        if value['schema'] in _SECONDARY_FOUNDERS_SCHEMAS:
            fields = fields | {'founders'}
        if value['schema'] in _SECONDARY_PRODUCTION_SCHEMAS:
            fields = fields | {'production_choices'}
        if value['schema'] in _SECONDARY_QUEUE_SCHEMAS:
            fields = fields | {'production_queues'}
        if value['schema'] in _SECONDARY_CITY_SCHEMAS:
            fields = fields | {'city_focus_catalogs', 'citizen_catalogs'}
        if value['schema'] in _SECONDARY_WORLD_SCHEMAS:
            fields = fields | {'world_input', 'queued_orders'}
        if value['schema'] in _SECONDARY_DEVELOPMENT_SCHEMAS:
            fields = fields | {'unit_promotions', 'unit_upgrades'}
        if value['schema'] in _SECONDARY_COMBAT_SCHEMAS:
            fields = fields | {'unit_attacks'}
        if value['schema'] in _SECONDARY_OCCUPATION_SCHEMAS:
            fields = fields | {'captured_city'}
        if value['schema'] in _SECONDARY_RANGED_SCHEMAS:
            fields = fields | {'city_shots', 'district_shots'}
        if value['schema'] in _SECONDARY_PURCHASE_SCHEMAS:
            fields = fields | {'plot_purchases', 'city_purchases'}
        if value['schema'] in _SECONDARY_GOVERNMENT_SCHEMAS:
            fields = fields | {'government', 'policies', 'policy_unlock'}
        if value['schema'] in _SECONDARY_CITY_STATE_SCHEMAS:
            fields = fields | {'envoys', 'city_state_levies', 'unit_levies'}
        if 'city_state_peace' in value:
            fields.add('city_state_peace')
        if 'world_score' in value:
            fields.add('world_score')
        if 'archaeology' in value:
            fields.add('archaeology')
        if value['schema'] in _SECONDARY_WORK_SCHEMAS:
            fields = fields | {'unit_work', 'unit_work_state', 'unit_work_info'}
        city_panels = {key: value[key] for key in SECONDARY_CITY_PANEL_FIELDS if key in value}
        fields.update(city_panels)
        great_people_mode = 'off'
        if 'great_people' in value:
            fields.update(('great_people', 'great_people_actions'))
            command_scope = value.get('great_people_actions')
            if type(command_scope) is not bool:
                raise ValueError('Borrowed Great People command scope requires an exact Boolean')
            great_people_mode = 'actions' if command_scope else 'read'
        if 'pantheon' in value:
            fields.add('pantheon')
        if 'governors' in value:
            fields.add('governors')
        if 'espionage' in value:
            fields.add('espionage')
        if 'spy_completion' in value:
            fields.add('spy_completion')
        religion = {key: value[key] for key in SECONDARY_RELIGION_CONTRACTS if key in value}
        fields.update(religion)
        trade_states = {key: value[key] for key in ('trade_routes', 'trade_origins') if key in value}
        fields.update(trade_states)
        if 'unit_formations' in value:
            fields.add('unit_formations')
        if 'dedications' in value:
            fields.add('dedications')
        congress = {key: value[key] for key in SECONDARY_CONGRESS_FIELDS if key in value}
        fields.update(congress)
        if set(value) != fields:
            raise ValueError('Unexpected borrowed unit-order catalogue fields')
        from . import archaeology

        excavations = [] if archaeology.EXCAVATE in value['families'] else None
        archaeology_mode = ('commands' if excavations is not None else
                            'read' if 'archaeology' in value else 'off')
        if archaeology_mode == 'off' and archaeology.KIND in value['families']:
            raise ValueError('Artifact commands require the borrowed archaeology state')
        panel_actions = {kind: [] for kind in SECONDARY_UNIT_PANEL_KINDS
                         if kind in value['families']}
        if panel_actions or excavations is not None:
            for row in value['candidates']:
                if type(row) is not dict or type(row.get('action')) is not dict:
                    raise ValueError('Malformed borrowed UnitPanel candidate')
                action = row['action']
                kind = action.get('kind')
                if type(kind) is str and kind in panel_actions:
                    panel_actions[kind].append(action)
                if excavations is not None and kind == archaeology.EXCAVATE:
                    excavations.append(action)
        expected = secondary_unit_catalogue(identity, sequence, turn, player_id,
            value['turn_controls'], value['unit_orders'], observation=observation,
            actions_closed=actions_closed, schema=value['schema'],
            turn_availability=value.get('turn_availability'),
            research_choices=value.get('research_choices'), founders=value.get('founders'),
            production_choices=value.get('production_choices'),
            production_queues=value.get('production_queues'),
            city_focus_catalogs=value.get('city_focus_catalogs'), citizen_catalogs=value.get('citizen_catalogs'),
            world_input=value.get('world_input'), queued_orders=value.get('queued_orders'),
            unit_promotions=value.get('unit_promotions'), unit_upgrades=value.get('unit_upgrades'),
            unit_attacks=value.get('unit_attacks'), occupation=value.get('captured_city'),
            city_shots=value.get('city_shots'), district_shots=value.get('district_shots'),
            plot_purchases=value.get('plot_purchases'), city_purchases=value.get('city_purchases'),
            government_state=value.get('government'), policy_state=value.get('policies'),
            unlock_state=value.get('policy_unlock'), envoy_state=value.get('envoys'),
            city_state_levies=value.get('city_state_levies'), unit_levies=value.get('unit_levies'),
            city_state_peace=value.get('city_state_peace'), city_state_peace_enabled='city_state_peace' in value,
            world_score_state=value.get('world_score'), world_score_enabled='world_score' in value,
            work_catalog=value.get('unit_work'), work_state=value.get('unit_work_state'),
            work_info=value.get('unit_work_info'), city_panels=city_panels,
            great_people_state=value.get('great_people'), great_people_mode=great_people_mode,
            pantheon_state=value.get('pantheon'), pantheon_enabled='pantheon' in value,
            governor_state=value.get('governors'), governors_enabled='governors' in value,
            espionage_state=value.get('espionage'), espionage_enabled='espionage' in value,
            completion_state=value.get('spy_completion'), spy_completion_enabled='spy_completion' in value,
            religion_states=religion, trade_states=trade_states,
            formation_state=value.get('unit_formations'), formation_enabled='unit_formations' in value,
            dedication_state=value.get('dedications'), dedication_enabled='dedications' in value,
            congress=congress, unit_panel_actions=panel_actions, archaeology_state=value.get('archaeology'),
            archaeology_mode=archaeology_mode, excavation_actions=excavations)
        if value != expected or any(type(value[key]) is not int for key in ('sequence', 'turn', 'player_id')):
            raise ValueError('Borrowed unit-order catalogue differs from its offers or identity')
        return value
    version = _capability_version(value['schema'])
    standard_trade = value['schema'] in STOCK_TRADE_CAPABILITY_SCHEMAS
    formations = value['schema'] in STOCK_FORMATION_SCHEMAS
    has_dedications = value['schema'] in DEDICATION_SCHEMAS
    stock_congress = value['schema'] in STOCK_CONGRESS_SCHEMAS
    resources_v24 = version >= 24
    xp1_city_religion_details = value['schema'] in _XP1_CITY_RELIGION_DETAILS_BASE_BY_SCHEMA
    xp2_city_religion_details = value['schema'] in XP2_CITY_RELIGION_DETAILS_SCHEMAS
    xp1_unit_religion_schema = _XP1_CITY_RELIGION_DETAILS_BASE_BY_SCHEMA.get(value['schema'],value['schema'])
    xp1_religious_unit_operations = xp1_unit_religion_schema in _XP1_RELIGIOUS_UNIT_OPERATIONS_BASE_BY_SCHEMA
    xp2_chain_base = _xp2_religious_chain_base_schema(value['schema'])
    xp2_religious_unit_operations = xp2_chain_base in _XP2_RELIGIOUS_UNIT_OPERATIONS_BASE_BY_SCHEMA
    has_religious_unit_operations = xp1_religious_unit_operations or xp2_religious_unit_operations
    xp1_gp_activation_schema = _XP1_RELIGIOUS_UNIT_OPERATIONS_BASE_BY_SCHEMA.get(xp1_unit_religion_schema,xp1_unit_religion_schema)
    xp1_great_person_activation = xp1_gp_activation_schema in _XP1_GREAT_PERSON_ACTIVATION_BASE_BY_SCHEMA
    xp1_custom_schema = _XP1_GREAT_PERSON_ACTIVATION_BASE_BY_SCHEMA.get(xp1_gp_activation_schema,xp1_gp_activation_schema)
    xp1_religion_custom_names = xp1_custom_schema in _XP1_RELIGION_CUSTOM_NAMES_BASE_BY_SCHEMA
    xp1_reject_schema = _XP1_RELIGION_CUSTOM_NAMES_BASE_BY_SCHEMA.get(xp1_custom_schema,xp1_custom_schema)
    xp1_great_people_reject = xp1_reject_schema in _XP1_GREAT_PEOPLE_REJECT_BASE_BY_SCHEMA
    xp1_actions_schema = _XP1_GREAT_PEOPLE_REJECT_BASE_BY_SCHEMA.get(xp1_reject_schema,xp1_reject_schema)
    xp1_great_people_actions = xp1_actions_schema in _XP1_GREAT_PEOPLE_ACTIONS_BASE_BY_SCHEMA
    xp1_activation_schema = _XP1_GREAT_PEOPLE_ACTIONS_BASE_BY_SCHEMA.get(xp1_actions_schema,xp1_actions_schema)
    has_prophet_activation = (xp1_activation_schema in _XP1_PROPHET_ACTIVATION_BASE_BY_SCHEMA
        or value['schema'] in XP2_PROPHET_ACTIVATION_SCHEMAS)
    xp1_gp_schema = _XP1_PROPHET_ACTIVATION_BASE_BY_SCHEMA.get(xp1_activation_schema,xp1_activation_schema)
    xp1_great_people = xp1_gp_schema in _XP1_GREAT_PEOPLE_BASE_BY_SCHEMA
    xp2_great_people_actions = value['schema'] in _XP2_GREAT_PEOPLE_ACTIONS_BASE_BY_SCHEMA
    xp2_query_schema = _XP2_GREAT_PEOPLE_ACTIONS_BASE_BY_SCHEMA.get(value['schema'], value['schema'])
    xp2_parent_schema = _XP2_GREAT_PEOPLE_BASE_BY_SCHEMA.get(xp2_query_schema)
    has_great_people = xp1_great_people or xp2_parent_schema is not None
    great_people_commands = xp1_great_people_actions or xp2_great_people_actions
    great_people_reject = xp1_great_people_reject or xp2_great_people_actions
    xp1_founding_schema = _XP1_GREAT_PEOPLE_BASE_BY_SCHEMA.get(xp1_gp_schema,xp1_gp_schema)
    has_religion_founding = (xp1_founding_schema in _XP1_RELIGION_FOUNDING_BASE_BY_SCHEMA
        or value['schema'] in XP2_RELIGION_FOUNDING_SCHEMAS)
    xp1_beliefs_schema = _XP1_RELIGION_FOUNDING_BASE_BY_SCHEMA.get(xp1_founding_schema,xp1_founding_schema)
    has_religion_beliefs = (xp1_beliefs_schema in _XP1_RELIGION_BELIEFS_BASE_BY_SCHEMA
        or value['schema'] in XP2_RELIGION_BELIEFS_SCHEMAS)
    xp1_pantheon_schema = _XP1_RELIGION_BELIEFS_BASE_BY_SCHEMA.get(xp1_beliefs_schema,xp1_beliefs_schema)
    xp2_pantheon = value['schema'] in XP2_PANTHEON_SCHEMAS
    has_pantheon = xp1_pantheon_schema in _XP1_PANTHEON_BASE_BY_SCHEMA or xp2_pantheon
    xp1_religion_schema = _XP1_PANTHEON_BASE_BY_SCHEMA.get(xp1_pantheon_schema,xp1_pantheon_schema)
    xp1_city_religion = xp1_religion_schema in _XP1_CITY_RELIGION_BASE_BY_SCHEMA
    has_city_religion = xp1_city_religion or xp2_city_religion_details
    xp1_production_schema = _XP1_CITY_RELIGION_BASE_BY_SCHEMA.get(xp1_religion_schema,xp1_religion_schema)
    xp1_production_info = xp1_production_schema in _XP1_PRODUCTION_INFO_BASE_BY_SCHEMA
    xp1_schema = _XP1_PRODUCTION_INFO_BASE_BY_SCHEMA.get(xp1_production_schema,xp1_production_schema)
    xp1_upgrade = xp1_schema in _XP1_UPGRADE_BASE_BY_SCHEMA
    xp1_promotion_schema = _XP1_UPGRADE_BASE_BY_SCHEMA.get(xp1_schema,xp1_schema)
    xp1_promotion = xp1_promotion_schema in _XP1_PROMOTION_BASE_BY_SCHEMA
    xp1_building_schema = _XP1_PROMOTION_BASE_BY_SCHEMA.get(xp1_promotion_schema,xp1_promotion_schema)
    xp2_city_buildings = (xp2_parent_schema or value['schema']) in _XP2_CITY_BUILDINGS_BASE_BY_SCHEMA
    has_city_buildings = xp1_building_schema in _XP1_CITY_BUILDINGS_BASE_BY_SCHEMA or xp2_city_buildings
    xp1_faith_schema = _XP1_CITY_BUILDINGS_BASE_BY_SCHEMA.get(xp1_building_schema,xp1_building_schema)
    xp1_faith_purchase = xp1_faith_schema in _XP1_FAITH_PURCHASE_BASE_BY_SCHEMA
    xp1_purchase_schema = _XP1_FAITH_PURCHASE_BASE_BY_SCHEMA.get(xp1_faith_schema, xp1_faith_schema)
    xp1_city_purchase = xp1_purchase_schema in _XP1_CITY_PURCHASE_BASE_BY_SCHEMA
    xp1_plot_schema = _XP1_CITY_PURCHASE_BASE_BY_SCHEMA.get(xp1_purchase_schema,xp1_purchase_schema)
    xp1_plot_purchase = xp1_plot_schema in _XP1_PLOT_PURCHASE_BASE_BY_SCHEMA
    xp1_base = _XP1_PLOT_PURCHASE_BASE_BY_SCHEMA.get(xp1_plot_schema, xp1_plot_schema)
    xp1_government = xp1_base in _XP1_GOVERNMENT_BASE_BY_SCHEMA
    policies_v25 = version >= 25 or xp1_government
    policy_unlock_v26 = version >= 26
    government_v27 = version >= 27 or xp1_government
    policy_relocation_v28 = version >= 28
    policy_reconfirm_v29 = version >= 29
    policy_gaps = (
        ['paid_policy_unlock', 'active_policy_relocation', 'unchanged_policy_confirmation']
        if xp1_government else
        ['active_policy_relocation'] if policy_unlock_v26 else
        ['paid_policy_unlock', 'active_policy_relocation']
    )
    faith_purchase_v30 = version >= 30 or xp1_faith_purchase
    envoys_v31 = version >= 31 or value['schema'] in XP1_ENVOY_CHOICE_SCHEMAS
    xp1_city_state_envoys = value['schema'] in XP1_CITY_STATE_ENVOY_SCHEMAS
    xp2_levies = value['schema'] in XP2_LEVY_SCHEMAS
    has_city_state_levies = value['schema'] in CITY_STATE_LEVY_SCHEMAS
    has_unit_levies = value['schema'] in UNIT_LEVY_SCHEMAS
    xp1_governors = value['schema'] == CAPABILITY_XP1_GOVERNORS_SCHEMA or xp1_city_state_envoys
    governors_v32 = version >= 32 or xp1_governors
    stock_diplomacy = (xp2_levy_base_schema(_xp2_religious_chain_base_schema(value['schema']))
                       in STOCK_TRADE_CAPABILITY_SCHEMAS and 'diplomacy_overview' in value)
    initial_diplomacy_v33 = version >= 33 or stock_diplomacy
    xp1_trade = value['schema'] in XP1_TRADE_SCHEMAS
    has_trade = version >= 34 or standard_trade or xp1_trade
    espionage_v35 = version >= 35
    spy_completion_v36 = version >= 36
    world_congress_v37 = version >= 37 or stock_congress
    world_congress_review_v38 = version >= 38 or stock_congress
    command_permissions_v39 = version >= 39 or stock_congress
    congress_active_effects_v40 = version >= 40 or stock_congress
    trade_overview_v41 = value['schema'] in TRADE_OVERVIEW_CAPABILITY_SCHEMAS
    xp1_city_shot = value['schema'] in _XP1_SHOT_TRANSITIONS or xp1_governors
    xp1_district_shot = value['schema'] == CAPABILITY_XP1_DISTRICT_SHOT_SCHEMA or xp1_governors
    xp2_capture_schema = _XP2_RELIGIOUS_UNIT_OPERATIONS_BASE_BY_SCHEMA.get(xp2_chain_base,xp2_chain_base)
    has_captured_city = xp2_levy_base_schema(xp2_capture_schema) in _CAPTURE_BASE_SCHEMA or xp1_city_shot
    upgrade_v23 = version >= 23 or xp1_upgrade
    promotion_v22 = version >= 22 or xp1_promotion
    city_purchase_v21 = version >= 21 or xp1_city_purchase
    purchase_v20 = version >= 20 or xp1_plot_purchase
    skip_v19 = version >= 19
    current_production_v18 = version >= 18 or xp1_production_info
    xp1_unit_work = has_xp1_unit_work(value)
    work_info_v17 = version >= 17 or xp1_unit_work
    work_state_v16 = version >= 16 or xp1_unit_work
    unit_work_v15 = version >= 15 or xp1_unit_work
    district_shot_v14 = version >= 14 or xp1_district_shot
    city_shot_v13 = version >= 13 or xp1_city_shot
    # v12 always includes the group. Other eligible views, including the
    # Rise and Fall branches of v11, include it only when explicitly queried.
    city_controls_v12 = version == 12 or (version >= 11 and 'city_focus_catalogs' in value)
    has_world_score = version >= 11 and 'world_score' in value
    has_archaeology = version >= 11 and 'archaeology' in value
    from . import air_operations, archaeology, national_parks, rock_bands, unit_work
    family_fields = value.get('families')
    has_air = version >= 11 and type(family_fields) is dict and air_operations.KIND in family_fields
    has_route = version >= 11 and type(family_fields) is dict and unit_work.BUILD_ROUTE in family_fields
    has_park = version >= 11 and type(family_fields) is dict and national_parks.DESIGNATE in family_fields
    has_rock_bands = version >= 11 and 'rock_bands' in value
    has_expansion_city_growth = version >= 11 and 'city_growth' in value
    has_expansion_city_loyalty = version >= 11 and 'city_loyalty' in value
    has_expansion_national_parks = version >= 11 and 'national_parks' in value
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
              | ({'city_buildings'} if has_city_buildings else set())
              | ({'city_religion'} if has_city_religion else set())
              | ({'pantheon'} if has_pantheon else set())
              | ({'religion_beliefs'} if has_religion_beliefs else set())
              | ({'religion_founding'} if has_religion_founding else set())
              | ({'religion_custom_names'} if xp1_religion_custom_names else set())
              | ({'great_person_activation'} if xp1_great_person_activation else set())
              | ({'religious_unit_operations'} if has_religious_unit_operations else set())
              | ({'great_people'} if has_great_people else set())
              | ({'prophet_activation'} if has_prophet_activation else set())
              | ({'unit_attacks'} if attacks_v9 else set())
              | ({'city_shots'} if city_shot_v13 else set())
              | ({'district_shots'} if district_shot_v14 else set())
              | ({'unit_work'} if unit_work_v15 else set())
              | ({'unit_work_state'} if work_state_v16 else set())
              | ({'unit_work_info'} if work_info_v17 else set())
              | ({'production_current'} if current_production_v18 else set())
              | ({'production_info'} if xp1_production_info else set())
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
              | ({'city_state_envoys'} if xp1_city_state_envoys else set())
              | ({'city_state_levies'} if has_city_state_levies else set())
              | ({'unit_levies'} if has_unit_levies else set())
              | ({'diplomacy_overview'} if initial_diplomacy_v33 else set())
              | ({'trade_routes', 'trade_origins'} if has_trade else set())
              | ({'espionage'} if espionage_v35 else set())
              | ({'spy_completion'} if spy_completion_v36 else set())
              | ({'world_congress'} if world_congress_v37 else set())
              | ({'world_congress_review', 'world_congress_review_status'} if world_congress_review_v38 else set())
              | ({'native_command_permissions'} if command_permissions_v39 else set())
              | ({'world_congress_active_effects','world_congress_active_effects_status'} if congress_active_effects_v40 else set())
              | ({'trade_overview', 'trade_overview_status'} if trade_overview_v41 else set())
              | ({'captured_city'} if has_captured_city else set())
              | ({'unit_formations'} if formations else set())
              | ({'dedications'} if has_dedications else set())
              | ({'city_focus_catalogs','citizen_catalogs'} if city_controls_v12 else set())
              | ({'world_score'} if has_world_score else set())
              | ({'archaeology'} if has_archaeology else set())
              | ({'city_growth'} if has_expansion_city_growth else set())
              | ({'city_loyalty'} if has_expansion_city_loyalty else set())
              | ({'national_parks'} if has_expansion_national_parks else set())
              | ({'rock_bands'} if has_rock_bands else set()))
    from .capability_choices import ACTION_FIELDS, validate_action, validate_state
    action_fields = dict(_CAPABILITY_ACTION_FIELDS)
    from . import city_buildings
    building_panel = value.get('city_buildings')
    great_work_commands = (has_city_buildings and type(building_panel) is dict
                           and building_panel.get('schema') in city_buildings.GREAT_WORK_COMMAND_SCHEMAS)
    if great_work_commands:
        action_fields[city_buildings.GREAT_WORK_MOVE] = city_buildings.GREAT_WORK_MOVE_FIELDS
    if has_archaeology:
        action_fields[archaeology.KIND] = archaeology.ACTION_FIELDS
        action_fields[archaeology.EXCAVATE] = archaeology.EXCAVATE_FIELDS
    if has_air:
        action_fields[air_operations.KIND] = air_operations.FIELDS
    if has_route:
        action_fields[unit_work.BUILD_ROUTE] = unit_work.ROUTE_FIELDS
    if has_park:
        action_fields[national_parks.DESIGNATE] = national_parks.DESIGNATION_FIELDS
    if has_rock_bands:
        action_fields[rock_bands.KIND] = rock_bands.FIELDS
    if has_pantheon:
        from . import pantheon
        action_fields[pantheon.KIND] = pantheon.FIELDS
    if has_religion_beliefs:
        from . import religion_beliefs
        action_fields[religion_beliefs.KIND] = religion_beliefs.FIELDS
    if has_religion_founding:
        from . import religion_founding
        action_fields[religion_founding.KIND] = religion_founding.FIELDS
    if xp1_religion_custom_names:
        from . import religion_custom_names
        action_fields[religion_custom_names.KIND] = religion_custom_names.FIELDS
    if xp1_great_person_activation:
        from . import great_person_activation
        action_fields[great_person_activation.KIND] = great_person_activation.FIELDS
    if has_religious_unit_operations:
        from . import religious_unit_operations
        action_fields.update({kind:religious_unit_operations.FIELDS for kind in religious_unit_operations.KINDS})
    if has_prophet_activation:
        from . import prophet_activation
        action_fields[prophet_activation.KIND] = prophet_activation.FIELDS
    if great_people_commands:
        from . import great_people_actions
        action_fields.update({kind:great_people_actions.FIELDS[kind] for kind in great_people_actions.LEGACY_KINDS})
        if great_people_reject:
            action_fields[great_people_actions.REJECT] = great_people_actions.FIELDS[great_people_actions.REJECT]
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
    if formations:
        from . import unit_formations
        action_fields[unit_formations.KIND] = unit_formations.FIELDS
    if has_dedications:
        from . import dedications
        action_fields[dedications.KIND] = frozenset(('kind',))
    if queues_v6:
        from . import production_queue as queues
        action_fields.update(queues.FIELDS)
    if placements_v7:
        from . import placement
        action_fields.update(placement.ACTION_FIELDS)
    if attacks_v9:
        from . import capability_unit_attacks as attacks
        action_fields.update(attacks.ACTION_FIELDS)
    if has_captured_city:
        from . import captured_city
        action_fields[captured_city.KIND] = captured_city.FIELDS
    if city_shot_v13:
        from . import city_ranged
        action_fields['city_range_attack'] = city_ranged.CITY_FIELDS
    if district_shot_v14:
        action_fields['district_range_attack'] = city_ranged.DISTRICT_FIELDS
    if unit_work_v15:
        from . import unit_work
        adjacent_work = has_adjacent_unit_work(value)
        if adjacent_work and version < _CAPABILITY_SCHEMAS.index(CAPABILITY_XP2_ENVOYS_SCHEMA) + 1:
            raise ValueError('Adjacent unit work requires a Gathering Storm capability catalogue')
        work_fields = (unit_work.ADJACENT_NETWORK_ACTION_FIELDS if adjacent_work
                       else unit_work.NETWORK_ACTION_FIELDS)
        work_gaps = unit_work.network_gaps(adjacent=adjacent_work)
        action_fields.update(work_fields)
    elif has_adjacent_unit_work(value):
        raise ValueError('Adjacent unit work requires the UnitPanel catalogue')
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
    if has_city_state_levies:
        from . import city_state_levies
        action_fields[city_state_levies.ACTION] = city_state_levies.ACTION_FIELDS
    if governors_v32:
        from . import governors
        action_fields.update(governors.ACTION_FIELDS)
    if initial_diplomacy_v33:
        from . import diplomacy_overview as initial_diplomacy
        action_fields.update(initial_diplomacy.ACTION_FIELDS)
    if has_trade:
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
    if xp1_city_state_envoys:
        from . import city_state_envoys
        influence = value['city_state_envoys']
        if (influence is None) != (actions_closed or is_waiting(value['turn_controls'])):
            raise ValueError('City-state envoy information differs from its native acting boundary')
        if influence is not None:
            city_state_envoys.validate(influence, player_id, turn)
            if envoys_v31 and envoy_catalogue is not None:
                targets = [{'player_id': row['target_player_id'], 'own_envoys': row['tokens_received']}
                           for row in envoy_catalogue['targets']]
                if influence['city_states'] != targets:
                    raise ValueError('Rise and Fall envoy targets differ from the native count readback')
    if has_city_state_levies:
        levies = value['city_state_levies']
        unavailable = family_query_unavailable(value, city_state_levies.ACTION, actions_closed=actions_closed)
        if (levies is None) != unavailable:
            raise ValueError('Military levy catalogue differs from its native acting boundary')
        if levies is not None:
            city_state_levies.validate(levies, player_id, turn)
            if xp2_levies:
                known = ([row['target_player_id'] for row in envoy_catalogue['targets']]
                         if envoy_catalogue is not None else None)
            else:
                known = [row['player_id'] for row in influence['city_states']]
            if (known is not None and levies['military_enabled']
                    and [row['player_id'] for row in levies['city_states']] != known):
                raise ValueError('Military levy catalogue differs from the met city-states')
        if has_unit_levies:
            flags = value['unit_levies']
            if (flags is None) != (actions_closed or is_waiting(value['turn_controls'])):
                raise ValueError('Unit levy flags differ from their native acting boundary')
            if flags is not None:
                city_state_levies.validate_unit_flags(flags, player_id, turn, observation=observation)
    if initial_diplomacy_v33:
        diplomacy_catalogue = value['diplomacy_overview']
        unavailable = actions_closed or is_waiting(controls)
        if stock_diplomacy and command_permissions_v39:
            permissions = validate_native_command_permissions(
                value['native_command_permissions'], player_id, turn, sequence)
            unavailable = unavailable or not permissions['allow_strategic']
        if (diplomacy_catalogue is None) != unavailable:
            raise ValueError('Initial diplomacy query differs from its acting boundary')
        if diplomacy_catalogue is not None:
            initial_diplomacy.validate(diplomacy_catalogue, player_id, turn)
            schema = diplomacy_catalogue['schema']
            if stock_diplomacy:
                if schema not in (initial_diplomacy.RELATIONSHIPS_SCHEMA, *initial_diplomacy.STOCK_SCHEMAS):
                    raise ValueError('Stock initial diplomacy requires its own overview')
                if schema == initial_diplomacy.RELATIONSHIPS_SCHEMA and any(
                        choice['supported'] and choice['key'] != initial_diplomacy.DENOUNCE
                        for target in diplomacy_catalogue['targets'] for choice in target['selections']):
                    raise ValueError('Stock initial diplomacy offers an unqualified choice')
            elif schema in initial_diplomacy.STOCK_SCHEMAS:
                raise ValueError('Stock diplomacy requires its own decision catalogue')
    if has_trade:
        from . import trade
        trade_closed = actions_closed or (standard_trade and value['trade_overview_status'] == 'ui_boundary_unavailable')
        unavailable = trade_closed or is_waiting(controls)
        origins_unavailable = family_query_unavailable(value, 'change_trade_origin', actions_closed=trade_closed)
        routes, origins = value['trade_routes'], value['trade_origins']
        if (routes is None) != unavailable or (origins is None) != origins_unavailable:
            raise ValueError('Trade queries differ from their native acting boundary')
        if xp1_trade:
            for kind, catalogue in (('make_trade_route', routes), ('change_trade_origin', origins)):
                expected_status = 'unqualified' if catalogue is None else 'queried_complete'
                if value['families'].get(kind, {}).get('status') != expected_status:
                    raise ValueError('Rise and Fall trade family differs from its native query')
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
        waiting = is_waiting(controls)
        if ((actions_closed and completion_catalogue is not None)
                or (not actions_closed and not waiting and completion_catalogue is None)):
            raise ValueError('Spy completion query differs from its session boundary')
        if completion_catalogue is not None:
            spy_completion.validate_catalogue(completion_catalogue, player_id, turn)
            if waiting and completion_catalogue['current'] is None:
                raise ValueError('Waiting spy completion requires a native occurrence')
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
    if trade_overview_v41:
        from . import trade_overview
        profile = (trade_overview.STOCK_PROFILE if value['schema'] in STOCK_TRADE_OVERVIEW_SCHEMAS
                   else trade_overview.PROFILE)
        trade_overview.validate_group(value['trade_overview'], value['trade_overview_status'], value,
                                      observation, profile=profile)
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
    if has_city_state_levies:
        family = families.get(city_state_levies.ACTION, {})
        if family.get('status') != ('unqualified' if levies is None else 'queried_complete'):
            raise ValueError('Military levy family differs from its public query availability')
    if governors_v32:
        for kind in governors.ACTION_FIELDS:
            family = families.get(kind, {})
            if family.get('status') != ('unqualified' if governor_catalogue is None else 'queried_complete'):
                raise ValueError('Governor family differs from its public query availability')
    if initial_diplomacy_v33:
        family = families.get('diplomacy_initiate', {})
        if family.get('status') != ('unqualified' if diplomacy_catalogue is None else 'queried_partial'):
            raise ValueError('Initial diplomacy family differs from its public query')
        gaps = INITIAL_DIPLOMACY_GAPS
        if stock_diplomacy and diplomacy_catalogue is not None:
            gaps = {
                initial_diplomacy.RELATIONSHIPS_SCHEMA: STOCK_INITIAL_DIPLOMACY_GAPS,
                initial_diplomacy.STOCK_MAJOR_PEACE_SCHEMA: STOCK_MAJOR_PEACE_GAPS,
                initial_diplomacy.STOCK_NEGOTIATION_SCHEMA: STOCK_NEGOTIATION_GAPS,
                initial_diplomacy.STOCK_FRIENDSHIP_SCHEMA: STOCK_FRIENDSHIP_GAPS,
                initial_diplomacy.STOCK_PROMISE_SCHEMA: STOCK_PROMISE_GAPS,
                initial_diplomacy.STOCK_PROMISE_STATUS_SCHEMA: STOCK_PROMISE_GAPS,
                initial_diplomacy.STOCK_CITY_STATE_PEACE_SCHEMA: STOCK_CITY_STATE_PEACE_GAPS,
            }[diplomacy_catalogue['schema']]
        if diplomacy_catalogue is not None and family.get('unqualified') != list(gaps):
            raise ValueError('Initial diplomacy family has an unqualified source gap')
    if has_trade:
        for kind in ('make_trade_route', 'change_trade_origin'):
            trade_available = not family_query_unavailable(value, kind, actions_closed=trade_closed)
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
    if has_captured_city:
        occupation = value['captured_city']
        unavailable = actions_closed or is_waiting(controls)
        family = families.get(captured_city.KIND, {})
        if ((occupation is None) != unavailable
                or family.get('status') != ('unqualified' if unavailable else 'queried_complete')):
            raise ValueError('Captured-city catalogue differs from its native acting boundary')
        if occupation is not None:
            captured_city.validate_public_catalog(occupation, player_id, turn, observation=observation)
    if formations:
        state = value['unit_formations']
        unavailable = family_query_unavailable(value, unit_formations.KIND, actions_closed=actions_closed)
        if ((state is None) != unavailable
                or families.get(unit_formations.KIND, {}).get('status') != (
                    'unqualified' if unavailable else 'queried_complete')):
            raise ValueError('Formation catalogue differs from its native acting boundary')
        if state is not None:
            unit_formations.validate(state, player_id, turn, observation=observation)
    if has_dedications:
        state = value['dedications']
        unavailable = family_query_unavailable(value, dedications.KIND, actions_closed=actions_closed)
        if ((state is None) != unavailable or families.get(dedications.KIND, {}).get('status') != (
                'unqualified' if unavailable else 'queried_complete')):
            raise ValueError('Dedication catalogue differs from its native acting boundary')
        if state is not None:
            dedications.validate_state(state, player_id, turn)
    if city_shot_v13:
        shots = value['city_shots']
        shot_family = families.get('city_range_attack', {})
        if shots is not None:
            if xp1_city_shot and (actions_closed or is_waiting(controls)):
                raise ValueError('Rise and Fall city shots require the native acting boundary')
            city_ranged.city_validate_catalog(shots, player_id, turn)
            if observation is not None:
                city_ranged.city_compare_own_cities(shots, observation)
        if shot_family.get('status') != ('unqualified' if shots is None else 'queried_complete'):
            raise ValueError('City-shot query and family status differ')
    if district_shot_v14:
        district_shots = value['district_shots']
        if district_shots is not None:
            if xp1_district_shot and (actions_closed or is_waiting(controls)):
                raise ValueError('Rise and Fall district shots require the native acting boundary')
            city_ranged.district_validate_catalog(district_shots, player_id, turn)
            if observation is not None:
                city_ranged.district_compare_own_cities(district_shots, observation)
        if families.get('district_range_attack', {}).get('status') != (
                'unqualified' if district_shots is None else 'queried_complete'):
            raise ValueError('District-shot query and family status differ')
    if unit_work_v15:
        work_catalogue = value['unit_work']
        def work_status(gaps):
            if work_catalogue is None:
                return 'unqualified'
            return 'queried_partial' if gaps else 'queried_complete'
        if any(families.get(kind, {}).get('status') != work_status(gaps)
               for kind, gaps in work_gaps.items()):
            raise ValueError('Unit-work query and family status differ')
        if work_catalogue is not None:
            if actions_closed or is_waiting(controls):
                raise ValueError('Unit-work query requires the native acting boundary')
            unit_work.validate_network_catalog(work_catalogue, player_id, turn, observation=observation,
                                               adjacent=adjacent_work)
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
                                   work_catalog=work_catalogue, work_state=state, visible_work=adjacent_work)
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
                if unit_work_v15 and name in work_gaps and gaps != list(work_gaps[name]):
                    raise ValueError('Unit-work query must retain its unqualified routes')
                if placements_v7 and name in placement.GAPS and gaps!=list(placement.GAPS[name]):
                    raise ValueError('Placement query must retain its exact unqualified branches')
                if policies_v25 and name == 'policies' and gaps != policy_gaps:
                    raise ValueError('Policy query must retain its exact unqualified branches')
                if government_v27 and name == 'government' and gaps != ['anarchy_transition']:
                    raise ValueError('Government query must retain its exact unqualified branch')
            waiting_choice = (turns_v3 and name in _CAPABILITY_TURN_KINDS
                              or spy_completion_v36 and name in spy_completion.ACTION_FIELDS)
            if actions_closed or (is_waiting(controls) and not waiting_choice):
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
        if xp1_production_info:
            quotes = value['production_info']
            if (quotes is None) != unavailable:
                raise ValueError('Production quotes and queue catalogue availability differ')
            if not unavailable:
                from .production_inputs import validate_quotes
                validate_quotes(quotes,player_id,turn,candidates=value['candidates'],observation=observation)
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
    if has_city_religion:
        from . import city_religion
        city_religion.validate(value['city_religion'],player_id,turn,observation=observation)
        expected_religion_schema = (city_religion.DETAILS_SCHEMA
            if xp1_city_religion_details or xp2_city_religion_details else city_religion.SCHEMA)
        if value['city_religion']['schema'] != expected_religion_schema:
            raise ValueError('City religion details require their explicit catalogue revision')
    if has_pantheon:
        unavailable = family_query_unavailable(value, pantheon.KIND, actions_closed=actions_closed)
        if (value['pantheon'] is None) != unavailable:
            raise ValueError('Pantheon query differs from its native acting boundary')
        if value['pantheon'] is not None:
            (pantheon.validate_state if xp2_pantheon else pantheon.validate)(value['pantheon'], player_id, turn)
        if families.get(pantheon.KIND, {}).get('status') != (
                'unqualified' if unavailable else 'queried_complete'):
            raise ValueError('Pantheon family differs from its native query')
    if has_religion_beliefs:
        unavailable = family_query_unavailable(value, religion_beliefs.KIND, actions_closed=actions_closed)
        if (value['religion_beliefs'] is None) != unavailable:
            raise ValueError('Belief query differs from its native acting boundary')
        if value['religion_beliefs'] is not None:
            religion_beliefs.validate(value['religion_beliefs'], player_id, turn, observation=observation)
        if families.get(religion_beliefs.KIND, {}).get('status') != (
                'unqualified' if unavailable else 'queried_complete'):
            raise ValueError('Belief family differs from its native query')
    if has_religion_founding:
        unavailable = family_query_unavailable(value, religion_founding.KIND, actions_closed=actions_closed)
        if (value['religion_founding'] is None) != unavailable:
            raise ValueError('Religion foundation query differs from its native acting boundary')
        if value['religion_founding'] is not None:
            religion_founding.validate(value['religion_founding'], player_id, turn, observation=observation)
        family = families.get(religion_founding.KIND, {})
        if (family.get('status') != ('unqualified' if unavailable else 'queried_partial')
                or not unavailable and family.get('unqualified') != list(religion_founding.UNQUALIFIED)):
            raise ValueError('Religion foundation family must retain its custom-name limit')
    if has_great_people:
        from . import great_people
        unavailable = family_query_unavailable(value, 'great_people', actions_closed=actions_closed)
        if (value['great_people'] is None) != unavailable:
            raise ValueError('Great People query differs from its native acting boundary')
        if value['great_people'] is not None:
            great_people.validate(value['great_people'], player_id, turn, observation=observation)
            expected_schema = great_people.SCHEMA_V2 if xp2_parent_schema is not None else great_people.SCHEMA
            if value['great_people']['schema'] != expected_schema:
                raise ValueError('Great People query schema differs from its engine')
    if xp1_religion_custom_names:
        unavailable = family_query_unavailable(value, religion_custom_names.KIND, actions_closed=actions_closed)
        state = value['religion_custom_names']
        if (state is None) != unavailable:
            raise ValueError('Custom religion choices differ from the native query boundary')
        if state is not None:
            religion_custom_names.validate(state, player_id, turn, observation=observation)
            if value['religion_founding'] is None or state['own'] != value['religion_founding']['own']:
                raise ValueError('Custom and predefined religion foundation own states differ')
        if families.get(religion_custom_names.KIND, {}).get('status') != (
                'unqualified' if unavailable else 'queried_complete'):
            raise ValueError('Custom religion family differs from its native query')
    if has_religious_unit_operations:
        unavailable = any(family_query_unavailable(value, kind, actions_closed=actions_closed)
                          for kind in religious_unit_operations.KINDS)
        if (value['religious_unit_operations'] is None) != unavailable:
            raise ValueError('Religious unit state differs from its native query boundary')
        if value['religious_unit_operations'] is not None:
            religious_unit_operations.validate(value['religious_unit_operations'], player_id, turn, observation=observation)
        if any(families.get(kind, {}).get('status') != ('unqualified' if unavailable else 'queried_complete')
               for kind in religious_unit_operations.KINDS):
            raise ValueError('Religious unit families differ from their native query')
    if xp1_great_person_activation:
        unavailable = family_query_unavailable(value, great_person_activation.KIND, actions_closed=actions_closed)
        if (value['great_person_activation'] is None) != unavailable:
            raise ValueError('Great Person activation differs from its native query boundary')
        if value['great_person_activation'] is not None:
            great_person_activation.validate(value['great_person_activation'], player_id, turn, observation=observation)
        if families.get(great_person_activation.KIND, {}).get('status') != (
                'unqualified' if unavailable else 'queried_complete'):
            raise ValueError('Great Person activation family differs from its native query')
    if has_prophet_activation:
        unavailable = family_query_unavailable(value, prophet_activation.KIND, actions_closed=actions_closed)
        if (value['prophet_activation'] is None) != unavailable:
            raise ValueError('Prophet activation query differs from its native acting boundary')
        if value['prophet_activation'] is not None:
            prophet_activation.validate(value['prophet_activation'], player_id, turn, observation=observation)
        if families.get(prophet_activation.KIND, {}).get('status') != (
                'unqualified' if unavailable else 'queried_complete'):
            raise ValueError('Prophet activation family differs from its native query')
    if great_people_commands:
        unavailable = family_query_unavailable(value, 'great_people', actions_closed=actions_closed)
        if (value['great_people'] is None) != unavailable:
            raise ValueError('Great Person commands differ from their native query boundary')
        for kind in (great_people_actions.KINDS if great_people_reject else great_people_actions.LEGACY_KINDS):
            if families.get(kind, {}).get('status') != (
                    'unqualified' if unavailable else 'queried_complete'):
                raise ValueError('Great Person command family differs from its native query')
    if has_city_buildings:
        buildings = city_buildings.validate(value['city_buildings'],player_id,turn,observation=observation)
        building_version = buildings['schema']
        if (not xp2_city_buildings and building_version in city_buildings.GREAT_WORK_SCHEMAS
                and (building_version not in city_buildings.GREAT_WORK_OVERVIEW_SCHEMAS
                     or (building_version == city_buildings.GREAT_WORK_OVERVIEW_SCHEMA
                         and buildings['great_work_moves_available']))):
            raise ValueError('Rise and Fall Great Work inventory has no admitted command route')
        if xp2_city_buildings and building_version == city_buildings.GREAT_WORK_XP1_COMMANDS_SCHEMA:
            raise ValueError('Great Work command panel belongs to Rise and Fall')
    if great_work_commands:
        kind = city_buildings.GREAT_WORK_MOVE
        if (building_panel['great_work_moves_available']
                and (actions_closed or is_waiting(controls) or congress_action_read_only(value, kind))):
            raise ValueError('Great Work commands require an active player')
        rows = [row['action'] for row in candidates
                if type(row) is dict and type(row.get('action')) is dict and row['action'].get('kind') == kind]
        if (families.get(kind) != _great_work_family(building_panel)
                or rows != city_buildings.great_work_actions(building_panel)):
            raise ValueError('Great Work choices differ from the exact panel')
    elif city_buildings.GREAT_WORK_MOVE in families:
        raise ValueError('Great Work commands require the Gathering Storm command panel')
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
    if has_world_score and value['world_score'] is not None:
        from . import world_score
        if actions_closed:
            raise ValueError('Closed decisions cannot publish a new world score')
        world_score.validate(value['world_score'], player_id, turn)
    if has_archaeology:
        if actions_closed:
            if value['archaeology'] is not None:
                raise ValueError('Closed decisions cannot publish archaeology')
        else:
            archaeology.validate(value['archaeology'], player_id, turn, observation=observation,
                                 panel=value.get('city_buildings'))
        if archaeology.KIND in families:
            expected, family = _archaeology_candidates(value, actions_closed=actions_closed)
            offered = [row for row in candidates if type(row) is dict and type(row.get('action')) is dict
                       and row['action'].get('kind') == archaeology.KIND]
            if offered != expected or families[archaeology.KIND] != family:
                raise ValueError('Artifact origin choices differ from the official popup')
        if archaeology.EXCAVATE in families:
            rows = [row for row in candidates if type(row) is dict and type(row.get('action')) is dict
                    and row['action'].get('kind') == archaeology.EXCAVATE]
            for row in rows:
                archaeology.validate_excavation(row['action'], observation=observation)
            expected, family = _archaeology_action_rows(value, [row['action'] for row in rows], actions_closed)
            units = [row['action']['unit_id'] for row in rows]
            if units != sorted(set(units)) or rows != expected or families[archaeology.EXCAVATE] != family:
                raise ValueError('Artifact excavation choices differ from their owned actor boundary')
    elif archaeology.KIND in families or archaeology.EXCAVATE in families:
        raise ValueError('Artifact commands require the public archaeology state')
    if has_air:
        rows = [row for row in candidates if type(row) is dict and type(row.get('action')) is dict
                and row['action'].get('kind') == air_operations.KIND]
        actions = [air_operations.validate(row['action'], observation) for row in rows]
        keys = [(action['unit_id'], action['operation'], action['plot_id']) for action in actions]
        expected, family = _unit_panel_rows(value, actions, actions_closed, air_operations.KIND,
                                            gaps=['unhighlighted_click_destinations'])
        if keys != sorted(set(keys)) or rows != expected or families[air_operations.KIND] != family:
            raise ValueError('Air operation choices differ from their actor boundary')
    elif air_operations.KIND in families:
        raise ValueError('Air operations require a compatible catalogue')
    if has_route:
        rows = [row for row in candidates if type(row) is dict and type(row.get('action')) is dict
                and row['action'].get('kind') == unit_work.BUILD_ROUTE]
        actions = [unit_work.validate_route(row['action'], observation) for row in rows]
        units = [action['unit_id'] for action in actions]
        expected, family = _unit_panel_rows(value, actions, actions_closed, unit_work.BUILD_ROUTE)
        if units != sorted(set(units)) or rows != expected or families[unit_work.BUILD_ROUTE] != family:
            raise ValueError('Route construction choices differ from their actor boundary')
    elif unit_work.BUILD_ROUTE in families:
        raise ValueError('Build Route requires a compatible catalogue')
    if has_park:
        rows = [row for row in candidates if type(row) is dict and type(row.get('action')) is dict
                and row['action'].get('kind') == national_parks.DESIGNATE]
        actions = [row['action'] for row in rows]
        national_parks.validate_designations(actions, observation)
        expected, family = _unit_panel_rows(value, actions, actions_closed, national_parks.DESIGNATE)
        if rows != expected or families[national_parks.DESIGNATE] != family:
            raise ValueError('Park designation choices differ from their actor boundary')
    elif national_parks.DESIGNATE in families:
        raise ValueError('Park designation requires a compatible catalogue')
    if has_rock_bands:
        panel = value['rock_bands']
        if panel is None:
            if not actions_closed:
                raise ValueError('Rock-band information is unavailable at an open boundary')
            actions = []
        else:
            rock_bands.validate(panel, player_id, turn, observation=observation)
            actions = rock_bands.actions(panel)
        rows = [row for row in candidates if row['action']['kind'] == rock_bands.KIND]
        expected, family = _unit_panel_rows(value, actions, actions_closed, rock_bands.KIND)
        if rows != expected or families.get(rock_bands.KIND) != family:
            raise ValueError('Concert choices differ from the native rock-band panel')
    elif rock_bands.KIND in families:
        raise ValueError('Rock concerts require their own public information')
    if has_expansion_city_growth:
        from . import city_growth
        growth = value['city_growth']
        if actions_closed:
            if growth is not None:
                raise ValueError('Closed decisions cannot publish city growth')
        elif type(growth) is not dict or growth.get('schema') != city_growth.EXPANSION_SCHEMA:
            raise ValueError('Expansion city growth requires the loyalty-aware panel')
        else:
            city_growth.validate(growth, player_id, turn, observation=observation)
    if has_expansion_city_loyalty:
        from . import city_loyalty
        loyalty = value['city_loyalty']
        if actions_closed:
            if loyalty is not None:
                raise ValueError('Closed decisions cannot publish city loyalty')
        else:
            city_loyalty.validate(loyalty, player_id, turn, observation=observation)
    if has_expansion_national_parks:
        from . import national_parks
        parks = value['national_parks']
        if actions_closed:
            if parks is not None:
                raise ValueError('Closed decisions cannot publish national parks')
        else:
            national_parks.validate(parks, player_id, turn, observation=observation)
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
            if xp1_upgrade and any(row['resource_type'] is not None for row in upgrade_catalogue['offers']):
                raise ValueError('Rise and Fall upgrade catalogue cannot contain Gathering Storm stockpile amounts')
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
            from .capability_choices import validate_founder_action
            validate_founder_action(action, own_units)
        elif world_v4 and kind in world.WORLD_KINDS:
            world.validate_action(action, width=value['world_input']['width'],
                                  height=value['world_input']['height'])
        elif orders_v5 and kind == 'unit_order':
            orders.validate_action(action)
        elif formations and kind == unit_formations.KIND:
            unit_formations.validate_action(action)
        elif attacks_v9 and kind=='unit_attack':
            attacks.validate_action(action,value['unit_attacks']['width'],value['unit_attacks']['height'])
        elif has_captured_city and kind == captured_city.KIND:
            captured_city.validate_action(action)
        elif queues_v6 and kind in queues.FIELDS:
            queues.validate_action(action)
        elif placements_v7 and kind in placement.ACTION_FIELDS:
            placement.validate_action(action,player_id=player_id)
        elif city_shot_v13 and kind == 'city_range_attack':
            city_ranged.city_validate_action(action, shots['width'], shots['height'])
        elif district_shot_v14 and kind == 'district_range_attack':
            city_ranged.district_validate_action(action, district_shots['width'], district_shots['height'])
        elif unit_work_v15 and kind in work_fields:
            unit_work.validate_action(action)
        elif purchase_v20 and kind == 'purchase':
            plot_purchases.validate_purchase_action(action, allow_faith=faith_purchase_v30)
        elif has_pantheon and kind == pantheon.KIND:
            pantheon.validate_action(action)
        elif has_religion_beliefs and kind == religion_beliefs.KIND:
            religion_beliefs.validate_action(action)
        elif has_religion_founding and kind == religion_founding.KIND:
            religion_founding.validate_action(action)
        elif xp1_religion_custom_names and kind == religion_custom_names.KIND:
            religion_custom_names.validate_template(action)
        elif xp1_great_person_activation and kind == great_person_activation.KIND:
            great_person_activation.validate_action(action)
        elif has_religious_unit_operations and kind in religious_unit_operations.KINDS:
            religious_unit_operations.validate_action(action)
        elif has_prophet_activation and kind == prophet_activation.KIND:
            prophet_activation.validate_action(action)
        elif great_people_commands and kind in great_people_actions.KINDS:
            great_people_actions.validate_action(action)
        elif great_work_commands and kind == city_buildings.GREAT_WORK_MOVE:
            city_buildings.validate_great_work_action(action)
        elif has_archaeology and kind == archaeology.KIND:
            archaeology.validate_action(action)
        elif has_archaeology and kind == archaeology.EXCAVATE:
            archaeology.validate_excavation(action, observation=observation)
        elif has_air and kind == air_operations.KIND:
            air_operations.validate(action, observation)
        elif has_route and kind == unit_work.BUILD_ROUTE:
            unit_work.validate_route(action, observation)
        elif has_park and kind == national_parks.DESIGNATE:
            national_parks.validate_designation(action, observation)
        elif has_rock_bands and kind == rock_bands.KIND:
            rock_bands.validate_action(action, observation)
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
        elif has_city_state_levies and kind == city_state_levies.ACTION:
            city_state_levies.validate_action(action)
        elif governors_v32 and kind in governors.ACTION_FIELDS:
            governors.validate_action(action)
        elif initial_diplomacy_v33 and kind == 'diplomacy_initiate':
            initial_diplomacy.validate_action(action)
        elif has_trade and kind == 'make_trade_route':
            trade.validate_route_action(action, value['trade_routes']['width'], value['trade_routes']['height'])
        elif has_trade and kind == 'change_trade_origin':
            trade.validate_origin_action(action, value['trade_origins']['width'], value['trade_origins']['height'])
        elif espionage_v35 and kind in espionage.ACTION_FIELDS:
            espionage.validate_action(action, espionage_catalogue['width'], espionage_catalogue['height'])
        elif spy_completion_v36 and kind in spy_completion.ACTION_FIELDS:
            spy_completion.validate_action(action, completion_catalogue['width'], completion_catalogue['height'])
        elif world_congress_v37 and kind in world_congress.CANDIDATE_FIELDS:
            world_congress.validate_candidate(action)
        elif has_dedications and kind == dedications.KIND:
            if action != dedications.CANDIDATE:
                raise ValueError('Malformed dedication confirmation candidate')
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
    if formations:
        offered = [row['action'] for row in candidates if row['action']['kind'] == unit_formations.KIND]
        if offered != unit_formations.actions(value['unit_formations']):
            raise ValueError('Formation candidates differ from the native partner choices')
    if has_dedications:
        offered = [row['action'] for row in candidates if row['action']['kind'] == dedications.KIND]
        if offered != dedications.candidates(value['dedications']):
            raise ValueError('Dedication confirmation differs from the native choices')
    if queues_v6:
        queues.validate_candidates(value['production_queues'],candidates)
    if placements_v7:
        placement.validate_candidates(value['placement_offers'],candidates)
    if attacks_v9:
        attacks.validate_candidates(value['unit_attacks'],candidates)
    if has_captured_city:
        offered = [row['action'] for row in candidates if row['action']['kind'] == captured_city.KIND]
        if offered != ([] if occupation is None else captured_city.public_actions(occupation)):
            raise ValueError('Captured-city candidates differ from the native directives')
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
    if has_trade:
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
    if has_city_state_levies:
        offered = [row['action'] for row in candidates if row['action']['kind'] == city_state_levies.ACTION]
        if offered != city_state_levies.actions(levies):
            raise ValueError('Military levy candidates differ from their native query')
    if unit_work_v15:
        offered = [row['action'] for row in candidates if row['action']['kind'] in work_fields]
        if offered != ([] if work_catalogue is None else unit_work.actions(work_catalogue)):
            raise ValueError('Unit-work candidates differ from their native catalogue')
    if has_pantheon:
        offered = [row['action'] for row in candidates if row['action']['kind'] == pantheon.KIND]
        if offered != (pantheon.state_actions if xp2_pantheon else pantheon.actions)(value['pantheon']):
            raise ValueError('Pantheon candidates differ from the exact native choices')
    if has_religion_beliefs:
        offered = [row['action'] for row in candidates if row['action']['kind'] == religion_beliefs.KIND]
        if offered != religion_beliefs.actions(value['religion_beliefs']):
            raise ValueError('Belief candidates differ from the exact native choices')
    if has_religion_founding:
        offered = [row['action'] for row in candidates if row['action']['kind'] == religion_founding.KIND]
        if offered != religion_founding.actions(value['religion_founding']):
            raise ValueError('Religion foundation candidates differ from the exact native choices')
    if xp1_religion_custom_names:
        offered = [row['action'] for row in candidates if row['action']['kind'] == religion_custom_names.KIND]
        if offered != religion_custom_names.actions(value['religion_custom_names']):
            raise ValueError('Custom religion candidates differ from the exact native icons')
    if has_religious_unit_operations:
        offered = [row['action'] for row in candidates if row['action']['kind'] in religious_unit_operations.KINDS]
        if offered != religious_unit_operations.actions(value['religious_unit_operations']):
            raise ValueError('Religious unit candidates differ from the exact native UI offers')
    if xp1_great_person_activation:
        offered = [row['action'] for row in candidates if row['action']['kind'] == great_person_activation.KIND]
        if offered != great_person_activation.actions(value['great_person_activation']):
            raise ValueError('Great Person activation candidates differ from the exact native flags')
    if has_prophet_activation:
        offered = [row['action'] for row in candidates if row['action']['kind'] == prophet_activation.KIND]
        if offered != prophet_activation.actions(value['prophet_activation']):
            raise ValueError('Prophet activation candidates differ from the exact native choices')
    if great_people_commands:
        offered = [row['action'] for row in candidates if row['action']['kind'] in great_people_actions.LEGACY_KINDS]
        if offered != great_people_actions.actions(value['great_people']):
            raise ValueError('Great Person candidates differ from the exact native offers and costs')
        if great_people_reject:
            offered = [row['action'] for row in candidates if row['action']['kind'] == great_people_actions.REJECT]
            expected = [action for action in great_people_actions.actions(value['great_people'], include_reject=True)
                        if action['kind'] == great_people_actions.REJECT]
            if offered != expected:
                raise ValueError('Great Person rejection candidates differ from the exact native offers and costs')
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
    espionage_available = value.get('espionage') is not None
    waiting = is_waiting(value['turn_controls'])
    if ((spy_completion is None and espionage_available)
            or (spy_completion is not None and not espionage_available and not waiting)):
        raise ValueError('Spy completion query differs from its session boundary')
    if spy_completion is not None:
        completion_contract.validate_catalogue(spy_completion, value['player_id'], value['turn'])
        if waiting and spy_completion['current'] is None:
            raise ValueError('Waiting spy completion requires a native occurrence')
        if observation is not None:
            completion_contract.compare_own(spy_completion, observation)
    result = copy.deepcopy(value)
    result['schema'] = CAPABILITY_XP2_SPY_COMPLETION_SCHEMA
    result['spy_completion'] = copy.deepcopy(spy_completion)
    if espionage_available:
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
            if spy_completion is None else dict(status='queried_partial', candidate_ids=[
                row['candidate_id'] for row in rows if row['action']['kind'] == kind],
                unqualified=list(SPY_COMPLETION_GAPS)))
    result.pop('decision_id', None)
    result['decision_id'] = digest(result)
    return result


def upgrade_world_congress_catalogue(value, congress, observation=None, *, stock_permissions=None, actions_closed=False):
    """Append an explicitly queried Congress catalogue to the v36 boundary."""
    from . import world_congress
    if type(value) is not dict or value.get('schema') not in (
            CAPABILITY_XP2_SPY_COMPLETION_SCHEMA, CAPABILITY_XP2_STOCK_DEDICATIONS_SCHEMA):
        raise ValueError('Congress requires its admitted XP2 decision profile')
    stock = value['schema'] == CAPABILITY_XP2_STOCK_DEDICATIONS_SCHEMA
    if stock:
        validate_native_command_permissions(stock_permissions, value['player_id'], value['turn'], value['sequence'])
        unavailable = actions_closed or is_waiting(value['turn_controls'])
    else:
        if stock_permissions is not None:
            raise ValueError('Stock permission readback requires the stock decision profile')
        unavailable = value.get('spy_completion') is None
    if (congress is None) != unavailable:
        raise ValueError('Congress query differs from its native acting boundary')
    if congress is not None:
        world_congress.validate_catalogue(congress, value['player_id'], value['turn'], value['sequence'])
        if observation is not None:
            world_congress.compare_own(congress, observation, value['sequence'])
    result = copy.deepcopy(value)
    result['schema'] = CAPABILITY_XP2_STOCK_CONGRESS_SCHEMA if stock else CAPABILITY_XP2_WORLD_CONGRESS_SCHEMA
    if stock:
        result['native_command_permissions'] = copy.deepcopy(stock_permissions)
    result['world_congress'] = copy.deepcopy(congress)
    _remove_congress_read_only_candidates(result)
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
    if type(value) is not dict or value.get('schema') not in (
            CAPABILITY_XP2_WORLD_CONGRESS_SCHEMA, CAPABILITY_XP2_STOCK_CONGRESS_SCHEMA):
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
    if result['schema'] != CAPABILITY_XP2_STOCK_CONGRESS_SCHEMA:
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
    if type(value) is not dict or value.get('schema') not in (
            CAPABILITY_NATIVE_COMMAND_PERMISSIONS_SCHEMA, CAPABILITY_XP2_STOCK_CONGRESS_SCHEMA):
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
    if result['schema'] != CAPABILITY_XP2_STOCK_CONGRESS_SCHEMA:
        result['schema']=CAPABILITY_XP2_CONGRESS_ACTIVE_EFFECTS_SCHEMA
    result['world_congress_active_effects']=copy.deepcopy(effects)
    result['world_congress_active_effects_status']=status
    result.pop('decision_id',None);result['decision_id']=digest(result)
    return result


def upgrade_trade_overview_catalogue(value, panel, *, observation, status):
    """Add only the new public information group to a current decision."""
    from . import trade_overview
    base = value.get('schema') if type(value) is dict else None
    if base == CAPABILITY_XP1_TRADE_SCHEMA:
        schema, profile = CAPABILITY_XP1_TRADE_OVERVIEW_SCHEMA, trade_overview.STOCK_PROFILE
    elif base == CAPABILITY_XP2_CONGRESS_ACTIVE_EFFECTS_SCHEMA:
        schema, profile = CAPABILITY_XP2_TRADE_OVERVIEW_SCHEMA, trade_overview.PROFILE
    else:
        raise ValueError('Trade overview requires its current trade query group')
    trade_overview.validate_group(panel, status, value, observation, profile=profile)
    result = copy.deepcopy(value)
    result['schema'] = schema
    result['trade_overview'] = copy.deepcopy(panel)
    result['trade_overview_status'] = status
    result.pop('decision_id')
    result['decision_id'] = digest(result)
    return result


def upgrade_captured_city_catalogue(value, occupation, *, actions_closed):
    """Extend the selected expansion view with the native pending city."""
    from . import captured_city
    base_schema = value['schema']
    if base_schema == CAPABILITY_COMBAT_READINESS_SCHEMA:
        schema = CAPABILITY_XP1_CAPTURED_CITY_SCHEMA
    elif base_schema == CAPABILITY_XP2_TRADE_OVERVIEW_SCHEMA:
        schema = CAPABILITY_XP2_CAPTURED_CITY_SCHEMA
    else:
        schema = _STOCK_CAPTURE_SCHEMA_BY_BASE.get(base_schema)
        if schema is None:
            raise ValueError('Captured city requires a supported expansion query group')
    result = copy.deepcopy(value)
    result['schema'] = schema
    result['captured_city'] = copy.deepcopy(occupation)
    if occupation is None:
        family = dict(status='unqualified', reason='session_closed' if actions_closed
                      else 'native_captured_city_acting_boundary_unavailable')
    else:
        candidates = [dict(candidate_id=digest(action), action=action)
                      for action in captured_city.public_actions(occupation)]
        result['candidates'].extend(candidates)
        family = dict(status='queried_complete',
                      candidate_ids=[row['candidate_id'] for row in candidates])
    result['families'][captured_city.KIND] = family
    result.pop('decision_id', None)
    result['decision_id'] = digest(result)
    return result


def upgrade_xp1_city_shot_catalogue(value, shots):
    """Add city-center fire to the installed Rise and Fall occupation view."""
    from .city_ranged import city_actions

    return _upgrade_xp1_shot_catalogue(value, shots, CAPABILITY_XP1_CITY_SHOT_SCHEMA, city_actions)


def upgrade_xp1_district_shot_catalogue(value, shots):
    """Add independent district fire to the Rise and Fall city-center view."""
    from .city_ranged import district_actions

    return _upgrade_xp1_shot_catalogue(value, shots, CAPABILITY_XP1_DISTRICT_SHOT_SCHEMA, district_actions)


def upgrade_xp1_governor_catalogue(value, catalogue):
    """Add the installed Rise and Fall governor panel to its decision view."""
    from . import governors

    if value['schema'] != CAPABILITY_XP1_DISTRICT_SHOT_SCHEMA:
        raise ValueError('Rise and Fall governors require its current district catalogue')
    result = copy.deepcopy(value)
    result['schema'] = CAPABILITY_XP1_GOVERNORS_SCHEMA
    result['governors'] = copy.deepcopy(catalogue)
    rows = [dict(candidate_id=digest(action), action=action) for action in governors.actions(catalogue)]
    result['candidates'].extend(rows)
    for kind in governors.ACTION_FIELDS:
        result['families'][kind] = (
            dict(status='queried_complete',
                 candidate_ids=[row['candidate_id'] for row in rows if row['action']['kind'] == kind])
            if catalogue is not None else
            dict(status='unqualified', reason='native_governor_acting_boundary_unavailable'))
    result.pop('decision_id', None)
    result['decision_id'] = digest(result)
    return result


def upgrade_xp1_city_state_envoys_catalogue(value, influence):
    """Add the read-only native count to the existing Rise and Fall choices."""
    if value['schema'] != CAPABILITY_XP1_GOVERNORS_SCHEMA:
        raise ValueError('Rise and Fall city-state envoys require its governor catalogue')
    result = dict(value, schema=CAPABILITY_XP1_CITY_STATE_ENVOYS_SCHEMA,
                  city_state_envoys=copy.deepcopy(influence))
    del result['decision_id']
    result['decision_id'] = digest(result)
    return result


def add_envoy_choices(value, catalogue, *, actions_closed):
    """Add native envoy actions to the catalogue being built by the saved owner."""
    from . import envoys

    value['envoys'] = catalogue
    rows = [dict(candidate_id=digest(action), action=action) for action in envoys.actions(catalogue)]
    value['candidates'].extend(rows)
    for kind in envoys.ACTION_FIELDS:
        value['families'][kind] = (
            dict(status='queried_complete',
                 candidate_ids=[row['candidate_id'] for row in rows if row['action']['kind'] == kind])
            if catalogue is not None else
            dict(status='unqualified', reason=(
                'session_closed' if actions_closed else 'native_envoy_acting_boundary_unavailable')))


def add_xp1_city_state_levies(value, catalogue):
    if value['schema'] != CAPABILITY_XP1_ENVOY_CHOICES_SCHEMA:
        raise ValueError('Military levies require the preceding Rise and Fall catalogue')
    value['schema'] = CAPABILITY_XP1_CITY_STATE_LEVIES_SCHEMA
    _add_city_state_levies(value, catalogue)


def add_xp2_levies(value, catalogue, unit_flags):
    base = value['schema']
    if base not in _XP2_LEVY_SCHEMA_BY_BASE:
        raise ValueError('Military levies require a Gathering Storm catalogue with envoys')
    value['schema'] = _XP2_LEVY_SCHEMA_BY_BASE[base]
    _add_city_state_levies(value, catalogue)
    value['unit_levies'] = unit_flags


def _add_city_state_levies(value, catalogue):
    from . import city_state_levies

    value['city_state_levies'] = catalogue
    rows = [dict(candidate_id=digest(action), action=action)
            for action in city_state_levies.actions(catalogue)]
    value['candidates'].extend(rows)
    value['families'][city_state_levies.ACTION] = (
        dict(status='queried_complete', candidate_ids=[row['candidate_id'] for row in rows])
        if catalogue is not None else
        dict(status='unqualified', reason='native_levy_acting_boundary_unavailable'))


def add_xp1_pantheon(value, catalogue, *, actions_closed=False):
    from . import pantheon

    schema = XP1_PANTHEON_SCHEMA_BY_BASE.get(value.get('schema'))
    if (schema is None or 'pantheon' in value or pantheon.KIND in value['families']):
        raise ValueError('Pantheon requires its preceding Rise and Fall catalogue')
    unavailable = family_query_unavailable(value, pantheon.KIND, actions_closed=actions_closed)
    if (catalogue is None) != unavailable:
        raise ValueError('Pantheon query differs from its native acting boundary')
    if catalogue is not None:
        pantheon.validate(catalogue, value['player_id'], value['turn'])
    rows = [dict(candidate_id=digest(action), action=action) for action in pantheon.actions(catalogue)]
    value['schema'] = schema
    value['pantheon'] = copy.deepcopy(catalogue)
    value['candidates'].extend(rows)
    value['families'][pantheon.KIND] = (
        dict(status='queried_complete', candidate_ids=[row['candidate_id'] for row in rows])
        if not unavailable else
        dict(status='unqualified', reason='session_closed' if actions_closed else 'native_pantheon_acting_boundary_unavailable'))


def add_xp2_pantheon(value, state, *, actions_closed=False):
    from . import pantheon

    schema = XP2_PANTHEON_SCHEMA_BY_BASE.get(value.get('schema'))
    if (schema is None or 'pantheon' in value or pantheon.KIND in value['families']):
        raise ValueError('Pantheon requires its preceding Gathering Storm state')
    unavailable = family_query_unavailable(value, pantheon.KIND, actions_closed=actions_closed)
    if (state is None) != unavailable:
        raise ValueError('Pantheon query differs from its native acting boundary')
    if state is not None:
        pantheon.validate_state(state, value['player_id'], value['turn'])
    rows = [dict(candidate_id=digest(action), action=action) for action in pantheon.state_actions(state)]
    value['schema'] = schema
    value['pantheon'] = copy.deepcopy(state)
    value['candidates'].extend(rows)
    value['families'][pantheon.KIND] = (
        dict(status='queried_complete', candidate_ids=[row['candidate_id'] for row in rows])
        if not unavailable else
        dict(status='unqualified', reason='session_closed' if actions_closed else 'native_pantheon_acting_boundary_unavailable'))


def add_xp1_religion_beliefs(value, state, *, actions_closed=False):
    return _add_religion_beliefs(value, state, XP1_RELIGION_BELIEFS_SCHEMA_BY_BASE,
        'Rise and Fall', actions_closed=actions_closed)


def add_xp2_religion_beliefs(value, state, *, actions_closed=False):
    return _add_religion_beliefs(value, state, XP2_RELIGION_BELIEFS_SCHEMA_BY_BASE,
        'Gathering Storm', actions_closed=actions_closed)


def _add_religion_beliefs(value, state, schemas, engine, *, actions_closed):
    from . import religion_beliefs

    schema = schemas.get(value.get('schema'))
    if (schema is None or 'religion_beliefs' in value or religion_beliefs.KIND in value['families']):
        raise ValueError('Belief requires its preceding ' + engine + ' state')
    unavailable = family_query_unavailable(value, religion_beliefs.KIND, actions_closed=actions_closed)
    if (state is None) != unavailable:
        raise ValueError('Belief query differs from its native acting boundary')
    if state is not None:
        religion_beliefs.validate(state, value['player_id'], value['turn'])
    rows = [dict(candidate_id=digest(action), action=action) for action in religion_beliefs.actions(state)]
    value['schema'] = schema
    value['religion_beliefs'] = copy.deepcopy(state)
    value['candidates'].extend(rows)
    value['families'][religion_beliefs.KIND] = (
        dict(status='queried_complete', candidate_ids=[row['candidate_id'] for row in rows])
        if not unavailable else
        dict(status='unqualified', reason='session_closed' if actions_closed else 'native_religion_beliefs_acting_boundary_unavailable'))


def add_xp1_religion_founding(value, state, *, actions_closed=False):
    return _add_religion_founding(value, state, XP1_RELIGION_FOUNDING_SCHEMA_BY_BASE,
        'Rise and Fall', actions_closed=actions_closed)


def add_xp2_religion_founding(value, state, *, actions_closed=False):
    return _add_religion_founding(value, state, XP2_RELIGION_FOUNDING_SCHEMA_BY_BASE,
        'Gathering Storm', actions_closed=actions_closed)


def _add_religion_founding(value, state, schemas, engine, *, actions_closed):
    from . import religion_founding

    schema = schemas.get(value.get('schema'))
    if (schema is None or 'religion_founding' in value or religion_founding.KIND in value['families']):
        raise ValueError('Religion foundation requires its preceding ' + engine + ' state')
    unavailable = family_query_unavailable(value, religion_founding.KIND, actions_closed=actions_closed)
    if (state is None) != unavailable:
        raise ValueError('Religion foundation query differs from its native acting boundary')
    if state is not None:
        religion_founding.validate(state, value['player_id'], value['turn'])
    rows = [dict(candidate_id=digest(action), action=action) for action in religion_founding.actions(state)]
    value['schema'] = schema
    value['religion_founding'] = copy.deepcopy(state)
    value['candidates'].extend(rows)
    value['families'][religion_founding.KIND] = (
        dict(status='queried_partial', candidate_ids=[row['candidate_id'] for row in rows],
             unqualified=list(religion_founding.UNQUALIFIED))
        if not unavailable else
        dict(status='unqualified', reason='session_closed' if actions_closed else 'native_religion_founding_acting_boundary_unavailable'))


def add_xp1_great_people(value, state, *, actions_closed=False):
    return _add_great_people(value, state, XP1_GREAT_PEOPLE_SCHEMA_BY_BASE,
                             'Rise and Fall', actions_closed=actions_closed)


def add_xp2_great_people(value, state, *, actions_closed=False):
    return _add_great_people(value, state, XP2_GREAT_PEOPLE_SCHEMA_BY_BASE,
                             'Gathering Storm', actions_closed=actions_closed)


def _add_great_people(value, state, schemas, engine, *, actions_closed):
    from . import great_people

    schema = schemas.get(value.get('schema'))
    if schema is None or 'great_people' in value:
        raise ValueError(f'Great People query requires its preceding {engine} state')
    unavailable = family_query_unavailable(value, 'great_people', actions_closed=actions_closed)
    if (state is None) != unavailable:
        raise ValueError('Great People query differs from its native acting boundary')
    projected = None if state is None else great_people.project(state, value['player_id'], value['turn'])
    value['schema'] = schema
    value['great_people'] = projected


def add_xp1_prophet_activation(value, state, *, actions_closed=False):
    return _add_prophet_activation(value, state, XP1_PROPHET_ACTIVATION_SCHEMA_BY_BASE,
        'Rise and Fall', actions_closed=actions_closed)


def add_xp2_prophet_activation(value, state, *, actions_closed=False):
    return _add_prophet_activation(value, state, XP2_PROPHET_ACTIVATION_SCHEMA_BY_BASE,
        'Gathering Storm', actions_closed=actions_closed)


def _add_prophet_activation(value, state, schemas, engine, *, actions_closed):
    from . import prophet_activation

    schema = schemas.get(value.get('schema'))
    if (schema is None or 'prophet_activation' in value or prophet_activation.KIND in value['families']):
        raise ValueError('Prophet activation requires its preceding ' + engine + ' state')
    unavailable = family_query_unavailable(value, prophet_activation.KIND, actions_closed=actions_closed)
    if (state is None) != unavailable:
        raise ValueError('Prophet activation query differs from its native acting boundary')
    if state is not None:
        prophet_activation.validate(state, value['player_id'], value['turn'])
    rows = [dict(candidate_id=digest(action), action=action) for action in prophet_activation.actions(state)]
    value['schema'] = schema
    value['prophet_activation'] = copy.deepcopy(state)
    value['candidates'].extend(rows)
    value['families'][prophet_activation.KIND] = (
        dict(status='queried_complete', candidate_ids=[row['candidate_id'] for row in rows])
        if not unavailable else
        dict(status='unqualified', reason='session_closed' if actions_closed else 'native_prophet_activation_acting_boundary_unavailable'))


def add_xp1_great_people_actions(value, *, actions_closed=False):
    _add_great_people_actions(value, XP1_GREAT_PEOPLE_ACTIONS_SCHEMA_BY_BASE, 'Rise and Fall',
                              include_reject=False, actions_closed=actions_closed)


def add_xp2_great_people_actions(value, *, actions_closed=False):
    _add_great_people_actions(value, XP2_GREAT_PEOPLE_ACTIONS_SCHEMA_BY_BASE, 'Gathering Storm',
                              include_reject=True, actions_closed=actions_closed)


def _add_great_people_actions(value, schemas, engine, *, include_reject, actions_closed):
    from . import great_people_actions

    schema = schemas.get(value.get('schema'))
    if (schema is None or 'great_people' not in value
            or any(kind in value['families'] for kind in great_people_actions.KINDS)):
        raise ValueError(f'Great Person commands require their preceding {engine} query')
    unavailable = family_query_unavailable(value, 'great_people', actions_closed=actions_closed)
    state = value['great_people']
    if (state is None) != unavailable:
        raise ValueError('Great Person commands differ from their native query boundary')
    rows = [dict(candidate_id=digest(action), action=action)
            for action in great_people_actions.actions(state, include_reject=include_reject)]
    value['schema'] = schema
    value['candidates'].extend(rows)
    for kind in (great_people_actions.KINDS if include_reject else great_people_actions.LEGACY_KINDS):
        value['families'][kind] = (
            dict(status='queried_complete', candidate_ids=[row['candidate_id'] for row in rows if row['action']['kind']==kind])
            if not unavailable else
            dict(status='unqualified', reason='session_closed' if actions_closed else 'native_great_people_acting_boundary_unavailable'))


def add_xp1_great_people_reject(value, *, actions_closed=False):
    from . import great_people_actions

    schema = XP1_GREAT_PEOPLE_REJECT_SCHEMA_BY_BASE.get(value.get('schema'))
    kind = great_people_actions.REJECT
    if (schema is None or 'great_people' not in value or kind in value['families']
            or any(legacy not in value['families'] for legacy in great_people_actions.LEGACY_KINDS)):
        raise ValueError('Great Person rejection requires the preceding Rise and Fall commands')
    unavailable = family_query_unavailable(value, 'great_people', actions_closed=actions_closed)
    state = value['great_people']
    if (state is None) != unavailable:
        raise ValueError('Great Person rejection differs from its native query boundary')
    rows = [dict(candidate_id=digest(action), action=action)
            for action in great_people_actions.actions(state, include_reject=True) if action['kind'] == kind]
    value['schema'] = schema
    value['candidates'].extend(rows)
    value['families'][kind] = (
        dict(status='queried_complete', candidate_ids=[row['candidate_id'] for row in rows])
        if not unavailable else
        dict(status='unqualified', reason='session_closed' if actions_closed else 'native_great_people_acting_boundary_unavailable'))


def add_xp1_religion_custom_names(value, state, *, actions_closed=False):
    from . import religion_custom_names

    schema = XP1_RELIGION_CUSTOM_NAMES_SCHEMA_BY_BASE.get(value.get('schema'))
    kind = religion_custom_names.KIND
    if (schema is None or 'religion_founding' not in value
            or 'religion_custom_names' in value or kind in value['families']):
        raise ValueError('Custom religion names require preceding Rise and Fall foundation choices')
    unavailable = family_query_unavailable(value, kind, actions_closed=actions_closed)
    if (state is None) != unavailable:
        raise ValueError('Custom religion names differ from their native query boundary')
    if state is not None:
        religion_custom_names.validate(state, value['player_id'], value['turn'])
        if value['religion_founding'] is None or state['own'] != value['religion_founding']['own']:
            raise ValueError('Custom and predefined religion foundation own states differ')
    rows = [dict(candidate_id=digest(action), action=action) for action in religion_custom_names.actions(state)]
    value['schema'] = schema
    value['religion_custom_names'] = copy.deepcopy(state)
    value['candidates'].extend(rows)
    value['families'][kind] = (
        dict(status='queried_complete', candidate_ids=[row['candidate_id'] for row in rows])
        if not unavailable else
        dict(status='unqualified', reason='session_closed' if actions_closed else 'native_religion_custom_names_acting_boundary_unavailable'))


def add_xp1_great_person_activation(value, state, *, actions_closed=False):
    return _add_great_person_activation(value, state, XP1_GREAT_PERSON_ACTIVATION_SCHEMA_BY_BASE,
                                        actions_closed=actions_closed)


def add_xp2_great_person_activation(value, state, *, actions_closed=False):
    return _add_great_person_activation(value, state, XP2_GREAT_PERSON_ACTIVATION_SCHEMA_BY_BASE,
                                        actions_closed=actions_closed)


def _add_great_person_activation(value, state, schema_map, *, actions_closed):
    from . import great_person_activation

    schema = schema_map.get(value.get('schema'))
    kind = great_person_activation.KIND
    if schema is None or 'great_person_activation' in value or kind in value['families']:
        raise ValueError('Great Person activation requires its preceding expansion public queries')
    unavailable = family_query_unavailable(value, kind, actions_closed=actions_closed)
    if (state is None) != unavailable:
        raise ValueError('Great Person activation differs from its native query boundary')
    if state is not None:
        great_person_activation.validate(state, value['player_id'], value['turn'])
    rows = [dict(candidate_id=digest(action), action=action) for action in great_person_activation.actions(state)]
    value['schema'] = schema
    value['great_person_activation'] = copy.deepcopy(state)
    value['candidates'].extend(rows)
    value['families'][kind] = (
        dict(status='queried_complete', candidate_ids=[row['candidate_id'] for row in rows])
        if not unavailable else
        dict(status='unqualified', reason='session_closed' if actions_closed else 'native_great_person_activation_acting_boundary_unavailable'))


def _xp2_great_person_projection(value, *, observation, actions_closed):
    from . import great_person_activation

    kind = great_person_activation.KIND
    if (type(value.get('families')) is not dict or type(value.get('candidates')) is not list
            or 'great_person_activation' not in value or kind not in value['families']
            or any(type(row) is not dict or type(row.get('action')) is not dict
                   for row in value['candidates'])):
        raise ValueError('Malformed Gathering Storm activation catalogue')
    old = dict(value, schema=xp2_great_person_base_schema(value['schema']),
               candidates=[row for row in value['candidates'] if row['action'].get('kind') != kind],
               families={k: row for k, row in value['families'].items() if k != kind})
    state = old.pop('great_person_activation')
    if state is not None:
        great_person_activation.validate(state, value['player_id'], value['turn'], observation=observation)
    for row in value['candidates']:
        if row['action'].get('kind') == kind:
            great_person_activation.validate_action(row['action'])
    expected = dict(old, candidates=list(old['candidates']), families=dict(old['families']))
    add_xp2_great_person_activation(expected, state, actions_closed=actions_closed)
    # Optional UnitPanel families can append choices after this overlay.
    # Preserve their placement while checking the exact activation row order.
    actual_rows = [row for row in value['candidates'] if row['action']['kind'] == kind]
    expected_rows = [row for row in expected['candidates'] if row['action']['kind'] == kind]
    if actual_rows != expected_rows:
        raise ValueError('Gathering Storm activation rows differ from their native choices')
    expected['candidates'] = list(value['candidates'])
    expected.pop('decision_id', None)
    expected['decision_id'] = digest(expected)
    if expected != value or value.get('decision_id') != digest({k: v for k, v in value.items() if k != 'decision_id'}):
        raise ValueError('Gathering Storm activation choices or public decision identity differ')
    old.pop('decision_id', None)
    old['decision_id'] = digest(old)
    return old


def add_xp1_city_religion_details(value, state):
    """Upgrade own religious information without changing existing choices."""
    from . import city_religion
    schema = XP1_CITY_RELIGION_DETAILS_SCHEMA_BY_BASE.get(value.get('schema'))
    if schema is None or 'city_religion' not in value:
        raise ValueError('City religion details require their exact preceding revision')
    city_religion.validate_details(state, value['player_id'], value['turn'])
    if city_religion.project_majority(state, value['player_id'], value['turn']) != value['city_religion']:
        raise ValueError('City religion details changed the existing majority readback')
    value['schema'] = schema
    value['city_religion'] = copy.deepcopy(state)
    value.pop('decision_id',None)
    value['decision_id'] = digest(value)
    return value


def add_xp2_city_religion_details(value, state):
    """Own-city observation; no action permission or strategic choice filter."""
    from . import city_religion
    schema = XP2_CITY_RELIGION_DETAILS_SCHEMA_BY_BASE.get(value.get('schema'))
    if schema is None or 'city_religion' in value:
        raise ValueError('City religion requires its preceding Gathering Storm catalogue')
    city_religion.validate_details(state,value['player_id'],value['turn'])
    value['schema'] = schema
    value['city_religion'] = copy.deepcopy(state)
    value.pop('decision_id',None)
    value['decision_id'] = digest(value)
    return value


def add_xp1_religious_unit_operations(value, state, *, actions_closed=False):
    return _add_religious_unit_operations(value, state, XP1_RELIGIOUS_UNIT_OPERATIONS_SCHEMA_BY_BASE,
                                         'Rise and Fall', actions_closed=actions_closed)


def add_xp2_religious_unit_operations(value, state, *, actions_closed=False):
    return _add_religious_unit_operations(value, state, XP2_RELIGIOUS_UNIT_OPERATIONS_SCHEMA_BY_BASE,
                                         'Gathering Storm', actions_closed=actions_closed)


def _add_religious_unit_operations(value, state, schemas, engine, *, actions_closed):
    from . import religious_unit_operations

    kinds = religious_unit_operations.KINDS
    schema = schemas.get(value.get('schema'))
    if schema is None or 'religious_unit_operations' in value or any(kind in value['families'] for kind in kinds):
        raise ValueError('Religious units require preceding ' + engine + ' public queries')
    unavailable = any(family_query_unavailable(value, kind, actions_closed=actions_closed) for kind in kinds)
    if (state is None) != unavailable:
        raise ValueError('Religious units differ from their native query boundary')
    if state is not None:
        religious_unit_operations.validate(state, value['player_id'], value['turn'])
    rows = [dict(candidate_id=digest(action), action=action) for action in religious_unit_operations.actions(state)]
    value['schema'] = schema
    value['religious_unit_operations'] = copy.deepcopy(state)
    value['candidates'].extend(rows)
    for kind in kinds:
        value['families'][kind] = (
            dict(status='queried_complete', candidate_ids=[row['candidate_id'] for row in rows if row['action']['kind'] == kind])
            if not unavailable else
            dict(status='unqualified', reason='session_closed' if actions_closed else 'native_religious_unit_operations_acting_boundary_unavailable'))


def add_xp1_unit_levies(value, flags):
    if value['schema'] != CAPABILITY_XP1_CITY_STATE_LEVIES_SCHEMA:
        raise ValueError('Unit levy flags require the preceding Rise and Fall catalogue')
    value['schema'] = CAPABILITY_XP1_UNIT_LEVIES_SCHEMA
    value['unit_levies'] = flags


def _upgrade_xp1_shot_catalogue(value, shots, schema, actions):
    base, field, kind = _XP1_SHOT_TRANSITIONS[schema]
    if value['schema'] != base:
        raise ValueError(f'Rise and Fall {field} requires its preceding catalogue')
    result = copy.deepcopy(value)
    result['schema'] = schema
    result[field] = copy.deepcopy(shots)
    rows = [dict(candidate_id=digest(action), action=action)
            for action in actions(shots)] if shots is not None else []
    result['candidates'].extend(rows)
    result['families'][kind] = (
        dict(status='queried_complete', candidate_ids=[row['candidate_id'] for row in rows])
        if shots is not None else dict(status='unqualified',
            reason=f"native_{field.removesuffix('s')}_acting_boundary_unavailable"))
    result.pop('decision_id', None)
    result['decision_id'] = digest(result)
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
    schema = xp2_great_person_base_schema(value['schema'])
    if (type(matches[0].get('kind')) is str and matches[0].get('kind').startswith('congress_')):
        from . import world_congress
        borrowed_congress = schema in _SECONDARY_UNIT_SCHEMAS and 'world_congress_review' in value
        if schema not in WORLD_CONGRESS_CAPABILITY_SCHEMAS and not borrowed_congress:
            raise ValueError('Congress requires its explicit capability revision')
        has_parameters = matches[0]['kind'] in world_congress.PARAMETER_FIELDS
        if ('parameters' in selection) != has_parameters:
            raise ValueError('Congress selection parameters differ from its operation')
        return world_congress.choose(value['world_congress'], matches[0], selection.get('parameters'))
    if matches[0].get('kind') == 'found_custom_religion':
        from . import religion_custom_names
        if schema not in XP1_RELIGION_CUSTOM_NAMES_SCHEMAS:
            raise ValueError('Custom religion names require their explicit capability revision')
        state = value['religion_custom_names']
        if state is None or ('parameters' in selection) != state['rename_allowed']:
            raise ValueError('Custom religion parameters differ from the native rename capability')
        return religion_custom_names.choose(state, matches[0], selection.get('parameters'))
    if matches[0].get('kind') == 'confirm_dedications':
        from . import dedications
        if (schema not in DEDICATION_SCHEMAS
                and not (schema in _SECONDARY_UNIT_SCHEMAS and 'dedications' in value)):
            raise ValueError('Dedications require their explicit capability revision')
        return dedications.choose(value['dedications'], matches[0], selection.get('parameters'))
    if matches[0].get('kind') == 'policies':
        if set(selection) != {'decision_id', 'candidate_id', 'parameters'}:
            raise ValueError('Explicit policy assignment parameters required')
        parameters = selection['parameters']
        if type(parameters) is not dict or set(parameters) != {'assignments'}:
            raise ValueError('Malformed explicit policy assignment parameters')
        from . import policies
        candidate = policies.choose(matches[0]['slots'], parameters['assignments'],
                                    value['player_id'], value['turn'],
                                    allow_relocation=schema in POLICY_RELOCATION_CAPABILITY_SCHEMAS,
                                    allow_unchanged=schema in POLICY_RECONFIRM_CAPABILITY_SCHEMAS)
        return dict(kind='policies', candidate=candidate)
    if set(selection) != {'decision_id', 'candidate_id'}:
        raise ValueError('Parameters are unsupported for this capability action')
    return copy.deepcopy(matches[0])


def _great_work_family(panel):
    from . import city_buildings
    if not panel['great_work_moves_available']:
        return dict(status='unqualified', reason='native_great_work_acting_boundary_unavailable')
    return dict(status='queried_complete',
                candidate_ids=[digest(action) for action in city_buildings.great_work_actions(panel)])


def add_great_work_choices(value, panel):
    from . import city_buildings
    choices = city_buildings.great_work_actions(panel)
    value['families'][city_buildings.GREAT_WORK_MOVE] = _great_work_family(panel)
    value['candidates'].extend(dict(candidate_id=digest(action), action=action) for action in choices)


def _remove_great_work_choices(value):
    from .city_buildings import GREAT_WORK_MOVE
    del value['families'][GREAT_WORK_MOVE]
    value['candidates'] = [row for row in value['candidates'] if row['action']['kind'] != GREAT_WORK_MOVE]
    return GREAT_WORK_MOVE


def project_city_building_version(value, target_schema):
    """Project a validated live decision to a specific recorded panel version."""
    from . import city_buildings
    panel = value['city_buildings']
    current_schema = panel['schema']
    versions = (city_buildings.SCHEMA, *city_buildings.GREAT_WORK_SCHEMAS)
    if target_schema not in versions or versions.index(target_schema) > versions.index(current_schema):
        raise ValueError('Unsupported city building checkpoint version')
    if current_schema == target_schema:
        return value, [], []
    projected = copy.deepcopy(value)
    panel = projected['city_buildings']
    panel['schema'] = target_schema
    removed = []
    for version, field in zip(versions[1:], ('great_work_slots', 'great_work_move_targets',
                                           'great_work_moves_available', 'great_work_building_bonuses', None), strict=True):
        if field is not None and versions.index(target_schema) < versions.index(version) <= versions.index(current_schema):
            del panel[field]
            removed.append('city_buildings.' + field)
    families = ([_remove_great_work_choices(projected)]
                if current_schema in city_buildings.GREAT_WORK_COMMAND_SCHEMAS
                and target_schema not in city_buildings.GREAT_WORK_COMMAND_SCHEMAS else [])
    if (current_schema == city_buildings.GREAT_WORK_XP1_COMMANDS_SCHEMA
            and target_schema == city_buildings.GREAT_WORK_OVERVIEW_SCHEMA):
        _remove_great_work_choices(projected)
        panel['great_work_moves_available'] = False
        add_great_work_choices(projected, panel)
    del projected['decision_id']
    projected['decision_id'] = digest(projected)
    return projected, removed, families


def secondary_unit_catalogue(identity, sequence, turn, player_id, controls, catalogue, *,
                             observation=None, actions_closed=False,
                             schema=CAPABILITY_SECONDARY_UNIT_ORDERS_SCHEMA,
                             turn_availability=None, research_choices=None, founders=None,
                             production_choices=None, production_queues=None,
                             city_focus_catalogs=None, citizen_catalogs=None,
                             world_input=None, queued_orders=None,
                             unit_promotions=None, unit_upgrades=None, unit_attacks=None, occupation=None,
                             city_shots=None, district_shots=None,
                             plot_purchases=None, city_purchases=None, government_state=None,
                             policy_state=None, unlock_state=None, envoy_state=None,
                             city_state_levies=None, unit_levies=None, work_catalog=None,
                             work_state=None, work_info=None, city_panels=None,
                             great_people_state=None, great_people_mode='off',
                             pantheon_state=None, pantheon_enabled=False, governor_state=None,
                             governors_enabled=False, espionage_state=None, espionage_enabled=False,
                             completion_state=None, spy_completion_enabled=False, religion_states=None,
                             trade_states=None, formation_state=None, formation_enabled=False,
                             dedication_state=None, dedication_enabled=False, congress=None,
                             unit_panel_actions=None, city_state_peace=None, city_state_peace_enabled=False,
                             world_score_state=None, world_score_enabled=False,
                             archaeology_state=None, archaeology_mode='off', excavation_actions=None):
    """Build the explicit partial catalogue for one additional LAN human."""
    from . import capability_unit_orders as orders

    if schema not in _SECONDARY_UNIT_SCHEMAS:
        raise ValueError('Unknown secondary unit-order schema')
    controls = validate_turn_controls(controls, player_id, turn)
    unavailable = catalogue is None or actions_closed or is_waiting(controls)
    allow_operations = schema != CAPABILITY_SECONDARY_UNIT_SCHEMA
    orders.validate_catalog(catalogue, player_id, turn, observation=observation,
                            unavailable=unavailable, allow_skip=allow_operations)
    candidates = []
    if catalogue is not None:
        if not allow_operations and any(row['action']['route'] != 'command' for row in catalogue['offers']):
            raise ValueError('Borrowed unit-order catalogue contains an unsupported route')
        candidates = [dict(candidate_id=digest(action), action=action)
                      for action in orders.actions(catalogue)]
    order_family = (dict(status='unqualified', reason='native_unit_commands_unavailable')
                    if unavailable else dict(status='queried_partial',
                        candidate_ids=[row['candidate_id'] for row in candidates],
                        unqualified=list(orders.UNQUALIFIED_UNIT_ORDERS)))
    value = dict(schema=schema, episode_id=identity.episode_id,
        game_generation=identity.game_generation, sequence=sequence, turn=turn, player_id=player_id,
        turn_controls=controls, unit_orders=catalogue, candidates=candidates,
        families=dict(unit_order=order_family, other_human_actions=dict(
            status='unqualified', reason='secondary_seat_gameplay_routes_not_yet_qualified')),
        family_inventory_complete=False, complete_action_space=False)
    if schema in _SECONDARY_TURN_SCHEMAS:
        if turn_availability is None:
            turn_availability = dict.fromkeys(_CAPABILITY_TURN_KINDS)
        if (type(turn_availability) is not dict or set(turn_availability) != _CAPABILITY_TURN_KINDS
                or any(flag is not None and type(flag) is not bool for flag in turn_availability.values())
                or (actions_closed and any(flag is not None for flag in turn_availability.values()))
                or (turn_availability['end_turn'] is True and is_waiting(controls))
                or (turn_availability['unready_turn'] is True and not unready_action_available(controls))):
            raise ValueError('Invalid borrowed native turn availability')
        value['turn_availability'] = dict(turn_availability)
        for kind in sorted(_CAPABILITY_TURN_KINDS):
            available = turn_availability[kind]
            if available is None:
                value['families'][kind] = dict(status='unqualified', reason='native_turn_ui_gate_unknown')
                continue
            ids = []
            if available:
                action = dict(kind=kind)
                ids = [digest(action)]
                candidates.append(dict(candidate_id=ids[0], action=action))
            value['families'][kind] = dict(status='queried_complete', candidate_ids=ids)
    elif turn_availability is not None:
        raise ValueError('Legacy borrowed unit schema does not carry turn availability')
    if schema in _SECONDARY_RESEARCH_SCHEMAS:
        from .capability_choices import RESEARCH_KINDS, research_actions
        value['research_choices'] = research_choices
        if research_choices is None:
            for kind in RESEARCH_KINDS:
                value['families'][kind] = dict(status='unqualified',
                                              reason='native_research_unavailable')
        else:
            if actions_closed or is_waiting(controls):
                raise ValueError('Borrowed research choices require a native acting boundary')
            for kind, actions in research_actions(research_choices).items():
                rows = [dict(candidate_id=digest(action), action=action) for action in actions]
                candidates.extend(rows)
                value['families'][kind] = dict(status='queried_complete',
                    candidate_ids=[row['candidate_id'] for row in rows])
    elif research_choices is not None:
        raise ValueError('Legacy borrowed unit schema does not carry research choices')
    if schema in _SECONDARY_FOUNDERS_SCHEMAS:
        value['founders'] = founders
        if founders is None:
            value['families']['found_city'] = dict(status='unqualified', reason='native_foundation_unavailable')
        else:
            from .capability_choices import validate_founder_action
            if type(founders) is not list or len(founders) > 4096 or actions_closed or is_waiting(controls):
                raise ValueError('Borrowed founders require a native acting boundary')
            own_units = None if observation is None else {
                row['id']: row for row in observation['units'] if row['owner'] == player_id}
            previous, rows = -1, []
            for action in founders:
                validate_founder_action(action, own_units)
                if action['unit_id'] <= previous:
                    raise ValueError('Borrowed founders are unordered or duplicate')
                rows.append(dict(candidate_id=digest(action), action=action))
                previous = action['unit_id']
            candidates.extend(rows)
            value['families']['found_city'] = dict(status='queried_complete',
                candidate_ids=[row['candidate_id'] for row in rows])
    elif founders is not None:
        raise ValueError('Legacy borrowed unit schema does not carry founder choices')
    if schema in _SECONDARY_PRODUCTION_SCHEMAS:
        from .capability_choices import validate_action, validate_production_state
        value['production_choices'] = production_choices
        family = dict(status='unqualified', reason='native_production_unavailable')
        if production_choices is not None:
            if (type(production_choices) is not dict or set(production_choices) != {'current', 'actions'}
                    or type(production_choices['actions']) is not list
                    or len(production_choices['actions']) > 256 * 256
                    or actions_closed or is_waiting(controls)):
                raise ValueError('Borrowed production requires a native acting boundary')
            current = production_choices['current']
            own_cities = None if observation is None else {
                city['id'] for city in observation['cities'] if city['owner'] == player_id}
            validate_production_state(current, own_cities)
            known_cities = {row['city_id'] for row in current}
            rows, seen = [], set()
            for action in production_choices['actions']:
                if type(action) is not dict or action.get('kind') != 'production':
                    raise ValueError('Borrowed production offers must be replacement actions')
                validate_action(action, known_cities)
                key = (action['city_id'], action['category'], action['index'])
                if key in seen:
                    raise ValueError('Duplicate borrowed production choice')
                seen.add(key)
                rows.append(dict(candidate_id=digest(action), action=action))
            candidates.extend(rows)
            gaps = ['placement', 'formations', 'purchases']
            if schema == CAPABILITY_SECONDARY_PRODUCTION_SCHEMA:
                gaps.insert(1, 'queue_edits')
            family = dict(status='queried_partial', candidate_ids=[row['candidate_id'] for row in rows],
                          unqualified=gaps)
        value['families']['production'] = family
    elif production_choices is not None:
        raise ValueError('Legacy borrowed unit schema does not carry production choices')
    if schema in _SECONDARY_QUEUE_SCHEMAS:
        from . import production_queue as queues
        heads = None if production_choices is None else dict(production=production_choices['current'])
        queues.validate_public(production_queues, player_id, turn, observation=observation,
                               choice_state=heads, unavailable=heads is None)
        gates = {city['enabled'] for city in production_queues or ()}
        if len(gates) > 1:
            raise ValueError('Borrowed city queues disagree about UI admission')
        value['production_queues'] = production_queues
        offers = {kind: [] for kind in queues.FIELDS}
        for city in production_queues or ():
            for action in city['offers']:
                row = dict(candidate_id=digest(action), action=action)
                offers[action['kind']].append(row['candidate_id'])
                candidates.append(row)
        for kind, ids in offers.items():
            if production_queues is None or False in gates:
                family = dict(status='unqualified', reason='native_queue_unavailable')
            elif kind == 'queue_append':
                family = dict(status='queried_partial', candidate_ids=ids,
                              unqualified=list(queues.UNQUALIFIED_APPEND))
            else:
                family = dict(status='queried_complete', candidate_ids=ids)
            value['families'][kind] = family
    elif production_queues is not None:
        raise ValueError('Legacy borrowed unit schema does not carry production queues')
    if schema in _SECONDARY_CITY_SCHEMAS:
        from .capability_city_controls import validate_catalogs

        fields = {'city_focus': 'city_focus_catalogs', 'city_citizen': 'citizen_catalogs'}
        state = {'city_focus': city_focus_catalogs, 'city_citizen': citizen_catalogs}
        own_ids = None if production_choices is None else [r['city_id'] for r in production_choices['current']]
        offers = validate_catalogs(city_focus_catalogs, citizen_catalogs, player_id, turn,
            observation=observation, unavailable=unavailable or own_ids is None, own_city_ids=own_ids)
        for kind, field in fields.items():
            value[field] = state[kind]
            rows = [dict(candidate_id=digest(action), action=action) for action in offers[kind]]
            candidates.extend(rows)
            value['families'][kind] = (
                dict(status='unqualified', reason='native_city_control_unavailable') if state[kind] is None
                else dict(status='queried_complete', candidate_ids=[row['candidate_id'] for row in rows]))
    elif city_focus_catalogs is not None or citizen_catalogs is not None:
        raise ValueError('Legacy borrowed unit schema does not carry city controls')
    if schema in _SECONDARY_DEVELOPMENT_SCHEMAS:
        from . import unit_promotions as promotions, unit_upgrades as upgrades

        value.update(unit_promotions=unit_promotions, unit_upgrades=unit_upgrades)
        for kind, state in (('promote_unit', unit_promotions), ('upgrade_unit', unit_upgrades)):
            if state is None:
                value['families'][kind] = dict(status='unqualified', reason='native_unit_development_unavailable')
                continue
            if actions_closed or is_waiting(controls) or (kind == 'upgrade_unit' and unavailable):
                raise ValueError('Borrowed unit development requires its native acting boundary')
            if kind == 'promote_unit':
                offers = promotions.validate_catalogue(state, player_id, turn, observation=observation)['offers']
            else:
                offers = upgrades.actions(upgrades.validate_catalogue(state, player_id, turn, observation=observation))
            rows = [dict(candidate_id=digest(action), action=action) for action in offers]
            candidates.extend(rows)
            value['families'][kind] = dict(status='queried_complete', candidate_ids=[row['candidate_id'] for row in rows])
    elif unit_promotions is not None or unit_upgrades is not None:
        raise ValueError('Legacy borrowed unit schema does not carry promotion or upgrade choices')
    if schema in _SECONDARY_COMBAT_SCHEMAS:
        from . import capability_unit_attacks as attacks

        if unit_attacks is not None and queued_orders is None:
            raise ValueError('Borrowed attacks require a native queued-order observation')
        attacks.validate_public_catalog(unit_attacks, player_id, turn, observation=observation,
            queued_orders=queued_orders, unavailable=unavailable or unit_attacks is None)
        value['unit_attacks'] = unit_attacks
        if unit_attacks is None:
            value['families']['unit_attack'] = dict(status='unqualified', reason='native_unit_attack_unavailable')
        else:
            rows = [dict(candidate_id=digest(action), action=action) for action in unit_attacks['offers']]
            candidates.extend(rows)
            value['families']['unit_attack'] = dict(status='queried_partial',
                candidate_ids=[row['candidate_id'] for row in rows],
                unqualified=list(attacks.UNQUALIFIED_UNIT_ATTACKS))
    elif unit_attacks is not None:
        raise ValueError('Legacy borrowed unit schema does not carry attack choices')
    if schema in _SECONDARY_OCCUPATION_SCHEMAS:
        from . import captured_city

        value['captured_city'] = occupation
        if occupation is None:
            value['families'][captured_city.KIND] = dict(
                status='unqualified', reason='native_captured_city_acting_boundary_unavailable')
        else:
            if actions_closed or is_waiting(controls):
                raise ValueError('Borrowed city choices require their native acting boundary')
            captured_city.validate_public_catalog(occupation, player_id, turn, observation=observation)
            rows = [dict(candidate_id=digest(action), action=action)
                    for action in captured_city.public_actions(occupation)]
            candidates.extend(rows)
            value['families'][captured_city.KIND] = dict(
                status='queried_complete', candidate_ids=[row['candidate_id'] for row in rows])
    elif occupation is not None:
        raise ValueError('Legacy borrowed unit schema does not carry captured-city choices')
    if schema in _SECONDARY_RANGED_SCHEMAS:
        from . import city_ranged as ranged

        value.update(city_shots=city_shots, district_shots=district_shots)
        groups = (
            ('city', city_shots, ranged.city_validate_catalog, ranged.city_compare_own_cities, ranged.city_actions),
            ('district', district_shots, ranged.district_validate_catalog,
             ranged.district_compare_own_cities, ranged.district_actions),
        )
        for shooter, shots, validate, compare_own, actions in groups:
            kind = shooter + '_range_attack'
            if shots is None:
                value['families'][kind] = dict(status='unqualified',
                    reason='native_' + shooter + '_shot_acting_boundary_unavailable')
                continue
            if unavailable:
                raise ValueError('Borrowed ranged shots require their native acting boundary')
            validate(shots, player_id, turn)
            if observation is not None:
                compare_own(shots, observation)
            rows = [dict(candidate_id=digest(action), action=action) for action in actions(shots)]
            candidates.extend(rows)
            value['families'][kind] = dict(status='queried_complete',
                                           candidate_ids=[row['candidate_id'] for row in rows])
    elif city_shots is not None or district_shots is not None:
        raise ValueError('Legacy borrowed unit schema does not carry city or district shots')
    if schema in _SECONDARY_PURCHASE_SCHEMAS:
        from . import plot_purchases as purchases

        value.update(plot_purchases=plot_purchases, city_purchases=city_purchases)
        if plot_purchases is None and city_purchases is None:
            value['families']['purchase'] = dict(status='unqualified', reason='native_purchase_unavailable')
        else:
            if unavailable or plot_purchases is None or city_purchases is None:
                raise ValueError('Borrowed purchase quotes require their complete native acting boundary')
            dimensions = observation if observation is not None else world_input
            if dimensions is None:
                raise ValueError('Borrowed purchase quotes require native map dimensions')
            own = None if observation is None else [row['id'] for row in observation['cities']]
            purchases.validate_catalogue(plot_purchases, player_id, turn, width=dimensions['width'],
                height=dimensions['height'], own_cities=own)
            purchases.validate_catalogue(city_purchases, player_id, turn, own_cities=own,
                city_items=True, allow_faith=True)
            offers = purchases.actions(plot_purchases + city_purchases)
            rows = [dict(candidate_id=digest(action), action=action) for action in offers]
            candidates.extend(rows)
            value['families']['purchase'] = dict(status='queried_partial',
                candidate_ids=[row['candidate_id'] for row in rows], unqualified=list(purchases.CITY_FAITH_GAPS))
    elif plot_purchases is not None or city_purchases is not None:
        raise ValueError('Legacy borrowed unit schema does not carry purchase quotes')
    if schema in _SECONDARY_GOVERNMENT_SCHEMAS:
        from . import capability_policies, government, policy_unlock

        value.update(government=government_state, policies=policy_state, policy_unlock=unlock_state)
        if unavailable and any(state is not None for state in (government_state, policy_state, unlock_state)):
            raise ValueError('Borrowed government decisions require their native acting boundary')
        if government_state is not None:
            government.validate_catalogue(government_state, player_id, turn)
        if policy_state is not None:
            capability_policies.validate_catalogue(policy_state, player_id, turn, allow_relocation=True)
        if unlock_state is not None:
            policy_unlock.validate(unlock_state, player_id, turn)
        options = (
            ('government', government_state, government.actions(government_state)),
            ('policies', policy_state, capability_policies.actions(
                policy_state, allow_relocation=True, allow_unchanged=True)),
            ('policy_unlock', unlock_state, policy_unlock.actions(unlock_state)),
        )
        for kind, state, offers in options:
            if state is None:
                value['families'][kind] = dict(status='unqualified',
                    reason='native_' + kind + '_acting_boundary_unavailable')
                continue
            rows = [dict(candidate_id=digest(action), action=action) for action in offers]
            candidates.extend(rows)
            family = dict(status='queried_complete', candidate_ids=[row['candidate_id'] for row in rows])
            if kind == 'government':
                family.update(status='queried_partial', unqualified=['anarchy_transition'])
            value['families'][kind] = family
    elif any(state is not None for state in (government_state, policy_state, unlock_state)):
        raise ValueError('Legacy borrowed unit schema does not carry government or policy choices')
    if schema in _SECONDARY_CITY_STATE_SCHEMAS:
        from . import city_state_levies as levies, envoys

        value.update(envoys=envoy_state, city_state_levies=city_state_levies, unit_levies=unit_levies)
        if envoy_state is not None:
            if unavailable:
                raise ValueError('Borrowed envoys require native strategic command permission')
            envoys.validate_catalogue(envoy_state, player_id, turn)
        if city_state_levies is not None or unit_levies is not None:
            if (actions_closed or is_waiting(controls) or city_state_levies is None or unit_levies is None):
                raise ValueError('Borrowed levies require their native acting boundary')
            levies.validate(city_state_levies, player_id, turn)
            levies.validate_unit_flags(unit_levies, player_id, turn, observation=observation)
        envoy_actions = envoys.actions(envoy_state)
        for kind, state, offers in (
                ('send_envoy', envoy_state, (a for a in envoy_actions if a['kind'] == 'send_envoy')),
                ('retain_envoys', envoy_state, (a for a in envoy_actions if a['kind'] == 'retain_envoys')),
                (levies.ACTION, city_state_levies, levies.actions(city_state_levies))):
            if state is None:
                value['families'][kind] = dict(status='unqualified',
                    reason='native_city_state_acting_boundary_unavailable')
            else:
                rows = [dict(candidate_id=digest(action), action=action) for action in offers]
                candidates.extend(rows)
                value['families'][kind] = dict(status='queried_complete',
                    candidate_ids=[row['candidate_id'] for row in rows])
    elif any(state is not None for state in (envoy_state, city_state_levies, unit_levies)):
        raise ValueError('Legacy borrowed unit schema does not carry city-state choices')
    if (type(city_state_peace_enabled) is not bool
            or (city_state_peace_enabled and schema not in _SECONDARY_CITY_STATE_SCHEMAS)
            or (city_state_peace is not None and (not city_state_peace_enabled or unavailable))):
        raise ValueError('Invalid borrowed city-state peace availability')
    if city_state_peace_enabled:
        from .diplomacy_overview import city_state_peace_actions

        value['city_state_peace'] = city_state_peace
        if city_state_peace is None:
            value['families']['diplomacy_initiate'] = dict(
                status='unqualified', reason='native_city_state_peace_acting_boundary_unavailable')
        else:
            rows = [dict(candidate_id=digest(action), action=action)
                    for action in city_state_peace_actions(city_state_peace, player_id)]
            candidates.extend(rows)
            value['families']['diplomacy_initiate'] = dict(
                status='queried_partial', unqualified=['other_initial_diplomacy_choices'],
                candidate_ids=[row['candidate_id'] for row in rows])
    if schema in _SECONDARY_WORK_SCHEMAS:
        from . import unit_work, unit_work_info, unit_work_state

        value.update(unit_work=work_catalog, unit_work_state=work_state, unit_work_info=work_info)
        adjacent = schema == CAPABILITY_SECONDARY_ADJACENT_WORK_SCHEMA
        work_available = work_catalog is not None
        if work_available:
            if actions_closed or is_waiting(controls):
                raise ValueError('Borrowed unit work requires native turn activity')
            unit_work.validate_network_catalog(work_catalog, player_id, turn, observation=observation,
                                               adjacent=adjacent)
            unit_work_state.validate(work_state, player_id, turn, observation=observation,
                                     work_catalog=work_catalog, include_plot=True)
            unit_work_info.validate(work_info, player_id, turn, observation=observation,
                                    work_catalog=work_catalog, work_state=work_state, visible_work=adjacent)
            rows = [dict(candidate_id=digest(action), action=action) for action in unit_work.actions(work_catalog)]
            candidates.extend(rows)
        elif work_info is not None or work_state is not None:
            raise ValueError('Borrowed unit work cannot publish data without the native catalogue')
        value['families'].update(unit_work.network_families(work_catalog, rows if work_available else [],
            adjacent=adjacent, unavailable_reason='native_unit_work_acting_boundary_unavailable'))
    elif any(state is not None for state in (work_catalog, work_state, work_info)):
        raise ValueError('Legacy borrowed unit schema does not carry unit work')
    if schema in _SECONDARY_WORLD_SCHEMAS:
        from . import capability_world_input as world
        from .action_budget import validate_action_count

        world_unavailable = unavailable or world_input is None
        world.validate_state(world_input, player_id, turn, observation=observation,
                             unavailable=world_unavailable)
        world.validate_queued_orders(queued_orders, player_id, turn, observation=observation,
                                     world_input=world_input, unavailable=world_unavailable)
        value.update(world_input=world_input, queued_orders=queued_orders)
        families = {kind: [] for kind in sorted(world.WORLD_KINDS)}
        for action in world.actions(world_input) if world_input is not None else ():
            candidate_id = digest(action)
            families[action['kind']].append(candidate_id)
            candidates.append(dict(candidate_id=candidate_id, action=action))
        for kind, ids in families.items():
            if world_unavailable:
                family = dict(status='unqualified', reason='native_world_input_unavailable')
            elif kind == 'world_plot_click':
                family = dict(status='queried_partial', candidate_ids=ids,
                              unqualified=['other_world_click_operations', 'war_confirmation'])
            else:
                family = dict(status='queried_complete', candidate_ids=ids)
            value['families'][kind] = family
        validate_action_count([row['action'] for row in candidates], world_input=world_input, map_coordinates=True)
    elif world_input is not None or queued_orders is not None:
        raise ValueError('Legacy borrowed unit schema does not carry world input')
    if city_panels is not None:
        if type(city_panels) is not dict or set(city_panels) - set(SECONDARY_CITY_PANEL_FIELDS):
            raise ValueError('Invalid borrowed city panel group')
        if city_panels and actions_closed:
            raise ValueError('Closed secondary decisions cannot publish city panels')
        if 'city_growth' in city_panels:
            from . import city_growth
            state = city_growth.validate(city_panels['city_growth'], player_id, turn, observation=observation)
            if state['schema'] != city_growth.EXPANSION_SCHEMA:
                raise ValueError('Borrowed city growth requires the expansion display')
        if 'rock_bands' in city_panels:
            from . import rock_bands
            rock_bands.validate(city_panels['rock_bands'], player_id, turn, observation=observation)
        if 'city_loyalty' in city_panels:
            from . import city_loyalty
            city_loyalty.validate(city_panels['city_loyalty'], player_id, turn, observation=observation)
        if 'city_buildings' in city_panels:
            from . import city_buildings
            buildings = city_buildings.validate(city_panels['city_buildings'], player_id, turn, observation=observation)
            if buildings['schema'] == city_buildings.GREAT_WORK_XP1_COMMANDS_SCHEMA:
                raise ValueError('Borrowed Great Work panels require the Gathering Storm route')
            if buildings['schema'] in city_buildings.GREAT_WORK_COMMAND_SCHEMAS:
                if unavailable and buildings['great_work_moves_available']:
                    raise ValueError('Borrowed Great Work commands require their native acting boundary')
                add_great_work_choices(value, buildings)
        if 'city_religion' in city_panels:
            from . import city_religion
            city_religion.validate_details(city_panels['city_religion'], player_id, turn, observation=observation)
        value.update(city_panels)
    if (type(world_score_enabled) is not bool or (actions_closed and world_score_enabled)
            or (world_score_state is not None and not world_score_enabled)):
        raise ValueError('Invalid borrowed world score availability')
    if world_score_enabled:
        from . import world_score

        value['world_score'] = (None if world_score_state is None
                                else world_score.validate(world_score_state, player_id, turn))
    if great_people_mode not in ('off', 'read', 'actions') or (
            great_people_state is not None and (great_people_mode == 'off' or actions_closed or is_waiting(controls))):
        raise ValueError('Invalid borrowed Great People availability')
    if great_people_mode != 'off':
        from . import great_people, great_people_actions

        if great_people_state is not None:
            great_people.validate(great_people_state, player_id, turn, observation=observation)
            if great_people_state['schema'] != great_people.SCHEMA_V2:
                raise ValueError('Borrowed Great People require the Gathering Storm panel')
        can_act = great_people_mode == 'actions'
        value.update(great_people=great_people_state, great_people_actions=can_act)
        if can_act:
            rows = [dict(candidate_id=digest(action), action=action)
                    for action in great_people_actions.actions(great_people_state, include_reject=True)]
            candidates.extend(rows)
            for kind in great_people_actions.KINDS:
                value['families'][kind] = (
                    dict(status='unqualified', reason='native_great_people_acting_boundary_unavailable')
                    if great_people_state is None else dict(status='queried_complete',
                        candidate_ids=[row['candidate_id'] for row in rows if row['action']['kind'] == kind]))
    if type(pantheon_enabled) is not bool or (pantheon_state is not None and (
            not pantheon_enabled or unavailable)):
        raise ValueError('Invalid borrowed pantheon availability')
    if pantheon_enabled:
        from . import pantheon

        if pantheon_state is not None:
            pantheon.validate_state(pantheon_state, player_id, turn)
        value['pantheon'] = pantheon_state
        rows = [dict(candidate_id=digest(action), action=action) for action in pantheon.state_actions(pantheon_state)]
        candidates.extend(rows)
        value['families'][pantheon.KIND] = (
            dict(status='unqualified', reason='native_pantheon_acting_boundary_unavailable')
            if pantheon_state is None else dict(status='queried_complete',
                candidate_ids=[row['candidate_id'] for row in rows]))
    if type(governors_enabled) is not bool or (governor_state is not None and (
            not governors_enabled or unavailable)):
        raise ValueError('Invalid borrowed governor availability')
    if governors_enabled:
        from . import governors

        if governor_state is not None:
            governors.validate_catalogue(governor_state, player_id, turn)
        value['governors'] = governor_state
        rows = [dict(candidate_id=digest(action), action=action) for action in governors.actions(governor_state)]
        candidates.extend(rows)
        for kind in governors.ACTION_FIELDS:
            value['families'][kind] = (
                dict(status='unqualified', reason='native_governor_acting_boundary_unavailable')
                if governor_state is None else dict(status='queried_complete',
                    candidate_ids=[row['candidate_id'] for row in rows if row['action']['kind'] == kind]))
    if type(espionage_enabled) is not bool or (espionage_state is not None and (
            not espionage_enabled or actions_closed or is_waiting(controls))):
        raise ValueError('Invalid borrowed espionage availability')
    if espionage_enabled:
        from . import espionage

        if espionage_state is not None:
            espionage.validate_catalogue(espionage_state, player_id, turn)
            if observation is not None:
                espionage.compare_own(espionage_state, observation)
        value['espionage'] = espionage_state
        rows = [dict(candidate_id=digest(action), action=action) for action in espionage.actions(espionage_state)]
        candidates.extend(rows)
        for kind in espionage.ACTION_FIELDS:
            value['families'][kind] = (
                dict(status='unqualified', reason='native_spy_acting_boundary_unavailable')
                if espionage_state is None else dict(status='queried_complete',
                    candidate_ids=[row['candidate_id'] for row in rows if row['action']['kind'] == kind]))
    if type(spy_completion_enabled) is not bool or (completion_state is not None and (
            not spy_completion_enabled or actions_closed)):
        raise ValueError('Invalid borrowed spy completion availability')
    if spy_completion_enabled:
        from . import spy_completion

        if completion_state is not None:
            spy_completion.validate_catalogue(completion_state, player_id, turn)
            if is_waiting(controls) and completion_state['current'] is None:
                raise ValueError('Waiting spy completion requires a native occurrence')
            if observation is not None:
                spy_completion.compare_own(completion_state, observation)
        value['spy_completion'] = completion_state
        rows = [dict(candidate_id=digest(action), action=action) for action in spy_completion.actions(completion_state)]
        candidates.extend(rows)
        for kind in spy_completion.ACTION_FIELDS:
            value['families'][kind] = (
                dict(status='unqualified', reason='native_spy_completion_acting_boundary_unavailable')
                if completion_state is None else dict(status='queried_partial', unqualified=list(SPY_COMPLETION_GAPS),
                    candidate_ids=[row['candidate_id'] for row in rows if row['action']['kind'] == kind]))
    if religion_states is not None:
        if type(religion_states) is not dict or religion_states.keys() - SECONDARY_RELIGION_CONTRACTS.keys():
            raise ValueError('Invalid borrowed religion group')
        for field, contract in SECONDARY_RELIGION_CONTRACTS.items():
            if field not in religion_states:
                continue
            state = religion_states[field]
            value[field] = state
            kinds = SECONDARY_RELIGION_KINDS[field]
            if state is None:
                for kind in kinds:
                    value['families'][kind] = dict(status='unqualified',
                        reason='native_religion_acting_boundary_unavailable')
                continue
            if unavailable:
                raise ValueError('Borrowed religion state requires the native acting boundary')
            contract.validate(state, player_id, turn, observation=observation)
            choices = [dict(candidate_id=digest(action), action=action) for action in contract.actions(state)]
            candidates.extend(choices)
            for kind in kinds:
                family = dict(status='queried_complete', candidate_ids=[
                    row['candidate_id'] for row in choices if row['action']['kind'] == kind])
                if contract is religion_founding:
                    family.update(status='queried_partial', unqualified=list(contract.UNQUALIFIED))
                value['families'][kind] = family
    if trade_states:
        from . import trade

        if type(trade_states) is not dict or set(trade_states) != {'trade_routes', 'trade_origins'}:
            raise ValueError('Borrowed trade requires both reader fields')
        value.update(trade_states)
        for field, kind, choices in (
                ('trade_routes', 'make_trade_route', trade.route_actions),
                ('trade_origins', 'change_trade_origin', trade.origin_actions)):
            state = trade_states[field]
            if state is None:
                value['families'][kind] = dict(status='unqualified',
                    reason='native_trade_acting_boundary_unavailable')
                continue
            if (actions_closed or is_waiting(controls)
                    or field == 'trade_origins' and unavailable):
                raise ValueError('Borrowed trade fields require the native acting boundary')
            rows = [dict(candidate_id=digest(action), action=action) for action in choices(state)]
            candidates.extend(rows)
            value['families'][kind] = dict(status='queried_complete',
                                          candidate_ids=[row['candidate_id'] for row in rows])
        trade.validate_decisions(value, observation, actions_closed=actions_closed)
    if type(formation_enabled) is not bool or (formation_state is not None and (
            not formation_enabled or unavailable)):
        raise ValueError('Borrowed formations require the native acting boundary')
    if formation_enabled:
        from . import unit_formations

        value['unit_formations'] = formation_state
        if formation_state is None:
            value['families'][unit_formations.KIND] = dict(status='unqualified',
                reason='native_unit_formation_boundary_unavailable')
        else:
            unit_formations.validate(formation_state, player_id, turn, observation=observation)
            rows = [dict(candidate_id=digest(action), action=action)
                    for action in unit_formations.actions(formation_state)]
            candidates.extend(rows)
            value['families'][unit_formations.KIND] = dict(status='queried_complete',
                candidate_ids=[row['candidate_id'] for row in rows])
    if type(dedication_enabled) is not bool or (dedication_state is not None and (
            not dedication_enabled or actions_closed or is_waiting(controls))):
        raise ValueError('Borrowed dedications require the native acting boundary')
    if dedication_enabled:
        from . import dedications

        value['dedications'] = dedication_state
        if dedication_state is None:
            value['families'][dedications.KIND] = dict(status='unqualified',
                reason='native_dedication_acting_boundary_unavailable')
        else:
            dedications.validate_state(dedication_state, player_id, turn)
            rows = [dict(candidate_id=digest(action), action=action)
                    for action in dedications.candidates(dedication_state)]
            candidates.extend(rows)
            value['families'][dedications.KIND] = dict(status='queried_complete',
                candidate_ids=[row['candidate_id'] for row in rows])
    if congress is not None and type(congress) is not dict:
        raise ValueError('Invalid borrowed Congress information scope')
    if congress:
        from . import world_congress, world_congress_active_effects, world_congress_review

        fields = set(congress)
        if fields not in ({'world_congress'}, set(SECONDARY_CONGRESS_FIELDS)):
            raise ValueError('Invalid borrowed Congress information scope')
        public = world_congress.validate_catalogue(congress['world_congress'], player_id, turn, sequence)
        congress_actions = world_congress.actions(public)
        if ((public['presentation'] != 'closed' or congress_actions)
                and ('world_congress_review' not in congress or actions_closed or is_waiting(controls))):
            raise ValueError('Borrowed Congress actions have no qualified command route')
        if 'world_congress_review' in congress:
            world_congress_review.validate_group(congress['world_congress_review'],
                congress['world_congress_review_status'], public, player_id, turn, sequence)
            world_congress_active_effects.validate_group(congress['world_congress_active_effects'],
                congress['world_congress_active_effects_status'], public, player_id, turn, sequence)
        value.update(congress)
        _remove_congress_read_only_candidates(value)
        rows = [dict(candidate_id=digest(action), action=action) for action in congress_actions]
        value['candidates'].extend(rows)
        for kind in world_congress.CANDIDATE_FIELDS:
            value['families'][kind] = dict(status='unqualified',
                reason='secondary_congress_command_route_unqualified')
        for row in rows:
            value['families'][row['action']['kind']] = dict(status='queried_partial',
                candidate_ids=[row['candidate_id']], unqualified=list(world_congress.GAPS))
    if unit_panel_actions is not None:
        from . import air_operations, national_parks, rock_bands, unit_work

        if (type(unit_panel_actions) is not dict
                or not unit_panel_actions.keys() <= set(SECONDARY_UNIT_PANEL_KINDS)):
            raise ValueError('Unknown borrowed UnitPanel command family')
        for kind in SECONDARY_UNIT_PANEL_KINDS:
            if kind not in unit_panel_actions:
                continue
            actions = unit_panel_actions[kind]
            if type(actions) is not list or len(actions) > 4096:
                raise ValueError('Malformed borrowed UnitPanel choices')
            if actions and (actions_closed or is_waiting(controls)):
                raise ValueError('Borrowed UnitPanel choices require an active seat')
            if kind == air_operations.KIND:
                for action in actions:
                    air_operations.validate(action, observation)
                keys = [(action['unit_id'], action['operation'], action['plot_id']) for action in actions]
                if keys != sorted(set(keys)):
                    raise ValueError('Borrowed air destinations are unordered or repeated')
                add_air_choices(value, actions, actions_closed)
            elif kind == unit_work.BUILD_ROUTE:
                for action in actions:
                    unit_work.validate_route(action, observation)
                units = [action['unit_id'] for action in actions]
                if units != sorted(set(units)):
                    raise ValueError('Borrowed route constructors are unordered or repeated')
                add_build_route_choices(value, actions, actions_closed)
            elif kind == national_parks.DESIGNATE:
                national_parks.validate_designations(actions, observation)
                add_park_designation_choices(value, actions, actions_closed)
            else:
                panel = value.get('rock_bands')
                if actions != ([] if panel is None else rock_bands.actions(panel)):
                    raise ValueError('Borrowed concert choices differ from their own unit information')
                if panel is not None or actions_closed:
                    add_rock_band_choices(value, panel, actions_closed)
    if (archaeology_mode not in ('off', 'read', 'commands')
            or (archaeology_state is not None) != (archaeology_mode != 'off')
            or (excavation_actions is not None) != (archaeology_mode == 'commands')
            or (actions_closed and archaeology_mode != 'off')):
        raise ValueError('Invalid borrowed archaeology availability')
    if archaeology_mode != 'off':
        from . import archaeology

        value['archaeology'] = archaeology.validate(archaeology_state, player_id, turn,
            observation=observation, panel=value.get('city_buildings'))
        if archaeology_mode == 'commands':
            if (type(excavation_actions) is not list or len(excavation_actions) > 4096
                    or excavation_actions and is_waiting(controls)):
                raise ValueError('Borrowed excavations require their active seat')
            units = [archaeology.validate_excavation(action, observation=observation)['unit_id']
                     for action in excavation_actions]
            if units != sorted(set(units)):
                raise ValueError('Borrowed excavations are unordered or repeated')
            add_archaeology_choices(value, actions_closed=actions_closed, excavations=excavation_actions)
    value['decision_id'] = digest(value)
    return value


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
    introduced_fields={key for _,key in pairs if key in current and key not in saved}
    if not added and not introduced_fields:
        return current, None
    if (current.get('schema')!=saved.get('schema')
            or current.get('schema') not in COMBAT_READINESS_CAPABILITY_SCHEMAS):
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


def checkpoint_xp1_unit_work_projection(current, saved, observation):
    """Keep new UnitPanel queries out of comparison with pre-query saves."""
    if not has_xp1_unit_work(current) or 'unit_work' in saved:
        return current, None
    if current['schema'] != saved.get('schema'):
        raise ValueError('Unit work query activation cannot substitute a catalogue version')
    from types import SimpleNamespace
    from .unit_work import NETWORK_ACTION_FIELDS
    for value in (current, saved):
        identity = SimpleNamespace(episode_id=value['episode_id'], game_generation=value['game_generation'])
        validate_capability_catalogue(value, identity, value['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
    fields = ('unit_work', 'unit_work_state', 'unit_work_info')
    if any(field in saved for field in fields) or any(kind in saved['families'] for kind in NETWORK_ACTION_FIELDS):
        raise ValueError('Known unit work state cannot be excluded from checkpoint comparison')
    projected = copy.deepcopy(current)
    for field in fields:
        del projected[field]
    for kind in NETWORK_ACTION_FIELDS:
        del projected['families'][kind]
    projected['candidates'] = [row for row in projected['candidates']
                               if row['action']['kind'] not in NETWORK_ACTION_FIELDS]
    del projected['decision_id']
    projected['decision_id'] = digest(projected)
    return projected, dict(source_schema=saved['schema'], target_schema=current['schema'],
                           historical_fields_unchanged=True, explicit_xp1_unit_work_query=True,
                           added_public_fields=list(fields), added_action_families=list(NETWORK_ACTION_FIELDS))


def checkpoint_world_score_projection(current, saved, observation):
    if 'world_score' not in current or 'world_score' in saved:
        return current, None
    if current.get('schema') != saved.get('schema'):
        raise ValueError('World score opt-in cannot substitute a catalogue version')
    from types import SimpleNamespace
    for value in (current, saved):
        identity = SimpleNamespace(episode_id=value['episode_id'], game_generation=value['game_generation'])
        validate_capability_catalogue(value, identity, value['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
    projected = copy.deepcopy(current)
    del projected['world_score'], projected['decision_id']
    projected['decision_id'] = digest(projected)
    return projected, dict(source_schema=saved['schema'], target_schema=current['schema'],
                           historical_fields_unchanged=True, explicit_world_score_query=True,
                           added_public_fields=['world_score'], added_action_families=[])


def _archaeology_candidates(value, *, actions_closed):
    from . import archaeology

    return _archaeology_action_rows(value, archaeology.actions(value['archaeology']), actions_closed)


def _archaeology_action_rows(value, actions, actions_closed):
    if actions_closed or is_waiting(value['turn_controls']):
        reason = 'session_closed' if actions_closed else 'native_archaeology_actor_waiting'
        return [], dict(status='unqualified', reason=reason)
    rows = [dict(candidate_id=digest(action), action=action) for action in actions]
    return rows, dict(status='queried_complete', candidate_ids=[row['candidate_id'] for row in rows])


def add_archaeology_choices(value, *, actions_closed=False, excavations=None):
    from .archaeology import EXCAVATE, KIND

    rows, family = _archaeology_candidates(value, actions_closed=actions_closed)
    value['candidates'].extend(rows)
    value['families'][KIND] = family
    if excavations is not None:
        rows, family = _archaeology_action_rows(value, excavations, actions_closed)
        value['candidates'].extend(rows)
        value['families'][EXCAVATE] = family


def _unit_panel_rows(value, actions, actions_closed, kind, *, gaps=()):
    if actions_closed or is_waiting(value['turn_controls']):
        reason = 'session_closed' if actions_closed else f'native_{kind}_actor_waiting'
        return [], dict(status='unqualified', reason=reason)
    rows = [dict(candidate_id=digest(action), action=action) for action in actions]
    family = dict(status='queried_partial' if gaps else 'queried_complete',
                  candidate_ids=[row['candidate_id'] for row in rows])
    if gaps:
        family['unqualified'] = list(gaps)
    return rows, family


def add_air_choices(value, actions, actions_closed=False):
    from .air_operations import KIND

    rows, family = _unit_panel_rows(value, actions, actions_closed, KIND,
                                    gaps=['unhighlighted_click_destinations'])
    value['candidates'].extend(rows)
    value['families'][KIND] = family


def add_build_route_choices(value, actions, actions_closed=False):
    from .unit_work import BUILD_ROUTE

    rows, family = _unit_panel_rows(value, actions, actions_closed, BUILD_ROUTE)
    value['candidates'].extend(rows)
    value['families'][BUILD_ROUTE] = family


def add_park_designation_choices(value, actions, actions_closed=False):
    from .national_parks import DESIGNATE

    rows, family = _unit_panel_rows(value, actions, actions_closed, DESIGNATE)
    value['candidates'].extend(rows)
    value['families'][DESIGNATE] = family


def add_rock_band_choices(value, panel, actions_closed=False):
    from .rock_bands import KIND, actions

    value['rock_bands'] = panel
    choices = [] if panel is None else actions(panel)
    rows, family = _unit_panel_rows(value, choices, actions_closed, KIND)
    value['candidates'].extend(rows)
    value['families'][KIND] = family


def _remove_city_purchase_choices(projected):
    from .plot_purchases import GAPS

    del projected['city_purchases']
    removed = {row['candidate_id'] for row in projected['candidates']
               if row['action']['kind'] == 'purchase' and 'plot_id' not in row['action']}
    family = projected['families']['purchase']
    if family['status'] == 'queried_partial':
        family['unqualified'] = list(GAPS)
        family['candidate_ids'] = [key for key in family['candidate_ids'] if key not in removed]
    projected['candidates'] = [row for row in projected['candidates'] if row['candidate_id'] not in removed]


def _faith_purchase_checkpoint(current, saved, observation, *, target_base, required_core, **options):
    if options['core_sha256'] != required_core or not is_capability_catalogue(saved):
        engine = 'Rise and Fall' if required_core == _XP1_COMBAT_CORE else 'Gathering Storm'
        raise ValueError('Faith-purchase checkpoint transition requires ' + engine)
    from types import SimpleNamespace
    from . import plot_purchases
    identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
    validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                  player_id=observation['player_id'], observation=observation)
    projected = copy.deepcopy(current)
    projected['schema'] = target_base
    if projected['city_purchases'] is not None:
        for city in projected['city_purchases']:
            city['offers'] = [row for row in city['offers'] if row['action']['currency'] != 'YIELD_FAITH']
        faith_ids = {row['candidate_id'] for row in projected['candidates']
                    if row['action'].get('kind') == 'purchase' and 'plot_id' not in row['action']
                    and row['action']['currency'] == 'YIELD_FAITH'}
        projected['candidates'] = [row for row in projected['candidates'] if row['candidate_id'] not in faith_ids]
        family = projected['families']['purchase']
        if family['status'] == 'queried_partial':
            family['unqualified'] = list(plot_purchases.CITY_GAPS)
            family['candidate_ids'] = [key for key in family['candidate_ids'] if key not in faith_ids]
    projected.pop('decision_id', None)
    projected['decision_id'] = digest(projected)
    projected, prior = checkpoint_catalogue(projected, saved, observation, **options)
    transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current['schema'],
                      historical_fields_unchanged=True)
    transition['added_action_families'] = transition.get('added_action_families', []) + [
        'faith_unit_building_purchase']
    return projected, transition


def _city_buildings_checkpoint_base(current_schema, saved_schema):
    direct_base = _XP2_CITY_BUILDINGS_BASE_BY_SCHEMA.get(current_schema)
    if direct_base is not None:
        return direct_base
    commands = _XP2_GREAT_PEOPLE_ACTIONS_BASE_BY_SCHEMA.get(current_schema)
    people = _XP2_GREAT_PEOPLE_BASE_BY_SCHEMA.get(commands or current_schema)
    bare = _XP2_CITY_BUILDINGS_BASE_BY_SCHEMA.get(people)
    if bare not in XP2_GREAT_PEOPLE_SCHEMA_BY_BASE:
        return None
    base = XP2_GREAT_PEOPLE_SCHEMA_BY_BASE[bare]
    if commands is not None:
        base = XP2_GREAT_PEOPLE_ACTIONS_SCHEMA_BY_BASE[base]
    return base if base == saved_schema else None


def checkpoint_catalogue(current, saved, observation, *, production_evidence=None, combat_evidence=None, combat_source_sha256=None, combat_readiness_source_sha256=None, core_sha256=None):
    """Explicit source-bound readback transitions; never rewrite old data.

    All historical fields/actions still have to compare exactly in the caller.
    New families and the proven not-ready unit attack offers are excluded only
    from a validated comparison copy. Other schema changes remain mismatches.
    """
    current_orders, saved_orders = current.get('unit_orders'), saved.get('unit_orders')
    if (type(current_orders) is dict and 'extensions' in current_orders
            and type(saved_orders) is dict and 'extensions' not in saved_orders):
        if core_sha256 != _XP2_COMBAT_CORE:
            raise ValueError('Additional unit-order transition requires Gathering Storm')
        from types import SimpleNamespace
        from .capability_unit_orders import EXTENDED_OPERATIONS

        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        validate_catalogue(current, identity, current['sequence'], observation['turn'],
                           player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        del projected['unit_orders']['extensions']
        projected['unit_orders']['offers'] = [row for row in current_orders['offers']
            if row['action']['item_type'] not in EXTENDED_OPERATIONS]
        removed = {row['candidate_id'] for row in current['candidates']
                   if row['action']['kind'] == 'unit_order'
                   and row['action']['item_type'] in EXTENDED_OPERATIONS}
        projected['candidates'] = [row for row in current['candidates'] if row['candidate_id'] not in removed]
        family = projected['families'].get('unit_order')
        if family is not None:
            family['candidate_ids'] = [identifier for identifier in family['candidate_ids'] if identifier not in removed]
        del projected['decision_id']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current['schema'],
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = list(transition.get('added_public_fields', []))+['unit_orders.extensions']
        transition['added_action_variants'] = list(transition.get('added_action_variants', []))+[
            'unit_order.'+name for name in EXTENDED_OPERATIONS]
        return projected, transition
    precision_pin,readiness_pin=(combat_checkpoint_sources(core_sha256)
        if core_sha256 is None or core_sha256 in (_XP1_COMBAT_CORE,_XP2_COMBAT_CORE)
        else (None,None))
    if core_sha256 is not None and core_sha256 not in (_XP1_COMBAT_CORE,_XP2_COMBAT_CORE,
            'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
        raise ValueError('Unknown checkpoint transition engine')
    from . import air_operations, archaeology, national_parks, rock_bands, unit_work
    added_archaeology = 'archaeology' in current and 'archaeology' not in saved
    added_rock_bands = 'rock_bands' in current and 'rock_bands' not in saved
    current_archaeology, saved_archaeology = current.get('archaeology'), saved.get('archaeology')
    added_museum = (type(current_archaeology) is dict and current_archaeology.get('schema') == archaeology.MUSEUM_SCHEMA
                    and type(saved_archaeology) is dict and saved_archaeology.get('schema') == archaeology.SCHEMA)
    added_expansion_actions = [kind for kind in (archaeology.KIND, archaeology.EXCAVATE,
                                                 air_operations.KIND, unit_work.BUILD_ROUTE, national_parks.DESIGNATE,
                                                 rock_bands.KIND)
                               if kind in current.get('families', {}) and kind not in saved.get('families', {})]
    if added_archaeology or added_museum or added_expansion_actions or added_rock_bands:
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Optional action checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace

        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = dict(current)
        del projected['decision_id']
        if added_archaeology:
            del projected['archaeology']
        if added_rock_bands:
            del projected['rock_bands']
        if added_museum:
            projected['archaeology'] = dict(current_archaeology, schema=archaeology.SCHEMA)
            del projected['archaeology']['museum_artifacts']
        if added_expansion_actions:
            projected['families'] = {key: family for key, family in current['families'].items()
                                     if key not in added_expansion_actions}
            projected['candidates'] = [row for row in current['candidates']
                                       if row['action']['kind'] not in added_expansion_actions]
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current['schema'],
                          historical_fields_unchanged=True)
        fields = ['archaeology'] if added_archaeology else []
        if added_rock_bands:
            fields.append('rock_bands')
        if added_museum:
            fields.append('archaeology.museum_artifacts')
        transition['added_public_fields'] = transition.get('added_public_fields', []) + fields
        transition['added_action_families'] = transition.get('added_action_families', []) + added_expansion_actions
        return projected, transition
    if (xp2_great_person_base_schema(current['schema']) != current['schema']
            and xp2_great_person_base_schema(saved['schema']) == saved['schema']):
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Gathering Storm activation checkpoint transition requires its engine')
        from .great_person_activation import KIND
        projected = _xp2_great_person_projection(current, observation=observation, actions_closed=False)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current['schema'],
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + ['great_person_activation']
        transition['added_action_families'] = transition.get('added_action_families', []) + [KIND]
        return projected, transition
    from . import city_buildings, diplomacy_overview
    current_buildings, saved_buildings = current.get('city_buildings'), saved.get('city_buildings')
    building_schemas = (city_buildings.SCHEMA, *city_buildings.GREAT_WORK_SCHEMAS)
    current_panel = current_buildings.get('schema') if type(current_buildings) is dict else None
    saved_panel = saved_buildings.get('schema') if type(saved_buildings) is dict else None
    if (current_panel in building_schemas and saved_panel in building_schemas
            and building_schemas.index(current_panel) > building_schemas.index(saved_panel)):
        if core_sha256 not in (_XP1_COMBAT_CORE, _XP2_COMBAT_CORE) or not is_capability_catalogue(saved):
            raise ValueError('Great Work checkpoint transition requires an expansion')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        pid, turn = observation['player_id'], observation['turn']
        validate_capability_catalogue(current, identity, current['sequence'], turn,
                                      player_id=pid, observation=observation)
        city_buildings.validate(saved_buildings, pid, turn, observation=observation)
        projected, added, added_families = project_city_building_version(current, saved_panel)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current['schema'],
                          historical_fields_unchanged=True)
        transition.setdefault('added_public_fields', []).extend(added)
        transition.setdefault('added_action_families', []).extend(added_families)
        if (current_panel == city_buildings.GREAT_WORK_XP1_COMMANDS_SCHEMA
                and saved_panel == city_buildings.GREAT_WORK_OVERVIEW_SCHEMA):
            transition.setdefault('added_action_variants', []).append(city_buildings.GREAT_WORK_MOVE)
        return projected, transition
    current_overview, saved_overview = current.get('diplomacy_overview'), saved.get('diplomacy_overview')
    stock_base = xp2_levy_base_schema(_xp2_religious_chain_base_schema(current['schema']))
    if (stock_base in STOCK_TRADE_CAPABILITY_SCHEMAS and 'diplomacy_overview' in current
            and 'diplomacy_overview' not in saved):
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Stock diplomacy checkpoint opt-in requires Gathering Storm')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        del projected['diplomacy_overview']
        del projected['families']['diplomacy_initiate']
        projected['candidates'] = [row for row in projected['candidates']
                                   if row['action']['kind'] != 'diplomacy_initiate']
        del projected['decision_id']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current['schema'],
                          historical_fields_unchanged=True)
        transition['added_action_families'] = transition.get('added_action_families', []) + ['diplomacy_initiate']
        transition['added_public_fields'] = transition.get('added_public_fields', []) + ['diplomacy_overview']
        return projected, transition
    current_diplo = current_overview.get('schema') if type(current_overview) is dict else None
    saved_diplo = saved_overview.get('schema') if type(saved_overview) is dict else None
    if (current_diplo in diplomacy_overview.SCHEMAS and saved_diplo in diplomacy_overview.SCHEMAS
            and diplomacy_overview.SCHEMAS.index(current_diplo) > diplomacy_overview.SCHEMAS.index(saved_diplo)):
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Diplomatic relationship checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        pid, turn = observation['player_id'], observation['turn']
        validate_capability_catalogue(current, identity, current['sequence'], turn,
                                      player_id=pid, observation=observation)
        diplomacy_overview.validate(saved_overview, pid, turn)
        projected = copy.deepcopy(current)
        projected['diplomacy_overview'] = diplomacy_overview.project_legacy(
            projected['diplomacy_overview'], pid, turn, schema=saved_diplo)
        adds_city_state = (current_diplo in diplomacy_overview.CITY_STATE_SCHEMAS
                           and saved_diplo not in diplomacy_overview.CITY_STATE_SCHEMAS)
        adds_draft = current_diplo in diplomacy_overview.DRAFT_SCHEMAS and saved_diplo not in diplomacy_overview.DRAFT_SCHEMAS
        adds_demand = (current_diplo in diplomacy_overview.DEMAND_SCHEMAS
                       and saved_diplo not in diplomacy_overview.DEMAND_SCHEMAS)
        adds_major_peace = (current_diplo in diplomacy_overview.MAJOR_PEACE_SCHEMAS
                            and saved_diplo not in diplomacy_overview.MAJOR_PEACE_SCHEMAS)
        stock_direct = diplomacy_overview.STOCK_DIRECT_AI_CHOICES
        added_direct = stock_direct.get(current_diplo, frozenset()).difference(stock_direct.get(saved_diplo, ()))
        peace_targets = {row['player_id'] for row in current_overview['targets']} if adds_major_peace else set()
        if adds_city_state:
            peace_targets.update(row['player_id'] for row in current_overview['city_state_peace']['targets'])
        added_variants = set()
        if adds_draft:
            added_variants.add(diplomacy_overview.OPEN_DEAL)
        if adds_demand:
            added_variants.add(diplomacy_overview.OPEN_DEMAND)
        added_variants.update(added_direct)
        if added_variants or adds_major_peace or adds_city_state:
            removed = {row['candidate_id'] for row in projected['candidates']
                       if row['action']['kind'] == 'diplomacy_initiate'
                       and (row['action']['choice'] in added_variants
                            or (row['action']['choice'] == diplomacy_overview.MAKE_PEACE
                                and row['action']['target_player_id'] in peace_targets))}
            projected['candidates'] = [row for row in projected['candidates'] if row['candidate_id'] not in removed]
            family = projected['families']['diplomacy_initiate']
            family['candidate_ids'] = [key for key in family['candidate_ids'] if key not in removed]
            if current_diplo in diplomacy_overview.STOCK_SCHEMAS:
                family['unqualified'] = list({
                    diplomacy_overview.STOCK_MAJOR_PEACE_SCHEMA: STOCK_MAJOR_PEACE_GAPS,
                    diplomacy_overview.STOCK_NEGOTIATION_SCHEMA: STOCK_NEGOTIATION_GAPS,
                    diplomacy_overview.STOCK_FRIENDSHIP_SCHEMA: STOCK_FRIENDSHIP_GAPS,
                    diplomacy_overview.STOCK_PROMISE_SCHEMA: STOCK_PROMISE_GAPS,
                    diplomacy_overview.STOCK_PROMISE_STATUS_SCHEMA: STOCK_PROMISE_GAPS,
                }.get(saved_diplo, STOCK_INITIAL_DIPLOMACY_GAPS))
        del projected['decision_id']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current['schema'],
                          historical_fields_unchanged=True)
        fields = transition.setdefault('added_public_fields', [])
        if saved_diplo == diplomacy_overview.SCHEMA:
            fields.append('diplomacy_overview.targets[].relationship')
        if adds_city_state:
            fields.append('diplomacy_overview.city_state_peace')
            transition.setdefault('added_action_variants', []).append('diplomacy_initiate.city_state_peace')
        if current_diplo in diplomacy_overview.MAJOR_DEAL_SCHEMAS and saved_diplo not in diplomacy_overview.MAJOR_DEAL_SCHEMAS:
            fields.append('diplomacy_overview.major_deals')
        if adds_draft:
            if saved_diplo != diplomacy_overview.STOCK_MAJOR_PEACE_SCHEMA:
                fields.append('diplomacy_overview.major_deals[].counterparty_is_human')
            transition.setdefault('added_action_variants', []).append('diplomacy_initiate.open_deal_draft')
        if current_diplo in diplomacy_overview.BORDERS_SCHEMAS and saved_diplo not in diplomacy_overview.BORDERS_SCHEMAS:
            fields.append('diplomacy_overview.major_deals[].open_borders')
        if (current_diplo in diplomacy_overview.STOCK_PROMISE_STATUS_SCHEMAS
                and saved_diplo not in diplomacy_overview.STOCK_PROMISE_STATUS_SCHEMAS):
            fields.append('diplomacy_overview.targets[].active_promises')
        if adds_demand:
            transition.setdefault('added_action_variants', []).append('diplomacy_initiate.open_demand')
        if adds_major_peace:
            transition.setdefault('added_action_variants', []).append('diplomacy_initiate.open_major_peace')
        if diplomacy_overview.DECLARE_FRIENDSHIP in added_direct:
            transition.setdefault('added_action_variants', []).append('diplomacy_initiate.declare_friendship')
        if added_direct.intersection(diplomacy_overview.PROMISE_CHOICES):
            transition.setdefault('added_action_variants', []).append('diplomacy_initiate.demand_promise')
        transition.setdefault('added_action_families', [])
        transition['public_schema_upgrades'] = transition.get('public_schema_upgrades', []) + [
            dict(field='diplomacy_overview', source_schema=saved_diplo, target_schema=current_diplo)]
        return projected, transition
    if (has_adjacent_unit_work(current) and not has_adjacent_unit_work(saved)
            and current.get('schema') not in _SECONDARY_UNIT_SCHEMAS):
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Adjacent unit-work checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace
        from . import unit_work, unit_work_info

        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        kind = unit_work.ADJACENT_KIND
        del projected['families'][kind], projected['decision_id']
        projected['candidates'] = [row for row in projected['candidates'] if row['action']['kind'] != kind]
        if projected['unit_work'] is not None:
            work, info = projected['unit_work'], projected['unit_work_info']
            for group in (work, info):
                group['offers'] = [row for row in group['offers'] if row['action']['kind'] != kind]
            del info['visible_plots_with_work']
            info['schema'] = unit_work_info.SCHEMA
            projected['families'].update(unit_work.network_families(work, projected['candidates'],
                adjacent=False, unavailable_reason='native_unit_work_acting_boundary_unavailable'))
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current['schema'],
                          historical_fields_unchanged=True)
        transition['added_action_families'] = transition.get('added_action_families', []) + [kind]
        transition['added_public_fields'] = transition.get('added_public_fields', []) + [
            'unit_work_info.visible_plots_with_work']
        transition['public_schema_upgrades'] = transition.get('public_schema_upgrades', []) + [
            dict(field='unit_work_info', source_schema=unit_work_info.SCHEMA,
                 target_schema=unit_work_info.VISIBLE_WORK_SCHEMA)]
        return projected, transition
    added_views = [name for name in ('city_growth', 'city_loyalty', 'national_parks')
                   if name in current and name not in saved]
    if added_views and is_capability_catalogue(current):
        if core_sha256 not in (_XP1_COMBAT_CORE, _XP2_COMBAT_CORE) or not is_capability_catalogue(saved):
            raise ValueError('Public view opt-in requires an expansion checkpoint')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        for name in added_views:
            del projected[name]
        del projected['decision_id']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current['schema'],
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + added_views
        transition.setdefault('added_action_families', [])
        return projected, transition
    additions = {
        CAPABILITY_XP1_UNIT_LEVIES_SCHEMA: (CAPABILITY_XP1_CITY_STATE_LEVIES_SCHEMA, 'unit_levies'),
        CAPABILITY_XP1_CITY_STATE_ENVOYS_SCHEMA: (CAPABILITY_XP1_GOVERNORS_SCHEMA, 'city_state_envoys'),
        CAPABILITY_XP2_STRATEGIC_RESOURCES_SCHEMA: (CAPABILITY_XP2_UNIT_UPGRADE_SCHEMA, 'strategic_resources'),
        CAPABILITY_CURRENT_PRODUCTION_SCHEMA: (CAPABILITY_UNIT_WORK_INFO_SCHEMA, 'production_current'),
        CAPABILITY_UNIT_WORK_INFO_SCHEMA: (CAPABILITY_UNIT_WORK_STATE_SCHEMA, 'unit_work_info'),
        CAPABILITY_UNIT_WORK_STATE_SCHEMA: (CAPABILITY_UNIT_WORK_SCHEMA, 'unit_work_state'),
    }
    current_schema = current.get('schema')
    preceding_schema = _city_buildings_checkpoint_base(current_schema, saved.get('schema'))
    if preceding_schema is not None:
        added_field, group = 'city_buildings', 'City buildings'
    elif current_schema in _XP2_CITY_RELIGION_DETAILS_BASE_BY_SCHEMA:
        preceding_schema = _XP2_CITY_RELIGION_DETAILS_BASE_BY_SCHEMA[current_schema]
        added_field, group = 'city_religion', 'City religion'
    if preceding_schema is not None and saved.get('schema') != current_schema:
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError(f'{group} checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace
        identity=SimpleNamespace(episode_id=current['episode_id'],game_generation=current['game_generation'])
        validate_capability_catalogue(current,identity,current['sequence'],observation['turn'],
                                      player_id=observation['player_id'],observation=observation)
        projected=copy.deepcopy(current)
        projected['schema'] = preceding_schema
        del projected[added_field], projected['decision_id']
        added_actions = ([_remove_great_work_choices(projected)] if added_field == 'city_buildings'
                         and current_panel in city_buildings.GREAT_WORK_COMMAND_SCHEMAS else [])
        projected['decision_id']=digest(projected)
        projected,prior=checkpoint_catalogue(projected,saved,observation,
            production_evidence=production_evidence,combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256,core_sha256=core_sha256)
        transition=dict(prior or {},source_schema=saved['schema'],target_schema=current_schema,
                        historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + [added_field]
        transition.setdefault('added_action_families', []).extend(added_actions)
        return projected,transition
    from . import placement_inventory
    current_inventory,saved_inventory=current.get('placement_inventory'),saved.get('placement_inventory')
    if (type(current_inventory) is dict and current_inventory.get('schema')==placement_inventory.DETAILS_SCHEMA
            and type(saved_inventory) is dict and saved_inventory.get('schema')==placement_inventory.SCHEMA):
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Placement pillage checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace
        identity=SimpleNamespace(episode_id=current['episode_id'],game_generation=current['game_generation'])
        validate_capability_catalogue(current,identity,current['sequence'],observation['turn'],
                                      player_id=observation['player_id'],observation=observation)
        placement_inventory.validate(saved_inventory,observation['player_id'],observation['turn'],
                                     observation=observation)
        projected=copy.deepcopy(current)
        projected['placement_inventory']=placement_inventory.project_legacy(
            current_inventory,observation['player_id'],observation['turn'],observation=observation)
        del projected['decision_id']
        projected['decision_id']=digest(projected)
        projected,prior=checkpoint_catalogue(projected,saved,observation,
            production_evidence=production_evidence,combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256,core_sha256=core_sha256)
        transition=dict(prior or {},source_schema=saved['schema'],target_schema=current_schema,
                        historical_fields_unchanged=True)
        transition['added_public_fields']=transition.get('added_public_fields',[])+['placement_inventory.rows[].pillaged']
        transition.setdefault('added_action_families',[])
        transition['public_schema_upgrades']=transition.get('public_schema_upgrades',[])+[
            dict(field='placement_inventory',source_schema=placement_inventory.SCHEMA,
                 target_schema=placement_inventory.DETAILS_SCHEMA)]
        return projected,transition
    if current_schema in _XP2_PANTHEON_BASE_BY_SCHEMA and saved.get('schema') != current_schema:
        if core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Pantheon state checkpoint transition requires Gathering Storm')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],game_generation=current['game_generation'])
        validate_capability_catalogue(current,identity,current['sequence'],observation['turn'],
                                      player_id=observation['player_id'],observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = _XP2_PANTHEON_BASE_BY_SCHEMA[current_schema]
        del projected['pantheon'], projected['families']['pantheon'], projected['decision_id']
        projected['candidates'] = [row for row in projected['candidates'] if row['action']['kind'] != 'pantheon']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected,saved,observation,
            production_evidence=production_evidence,combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256,core_sha256=core_sha256)
        transition = dict(prior or {},source_schema=saved['schema'],target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields',[]) + ['pantheon']
        transition['added_action_families'] = transition.get('added_action_families',[]) + ['pantheon']
        return projected,transition
    if current_schema in _XP1_CITY_RELIGION_DETAILS_BASE_BY_SCHEMA and saved.get('schema') != current_schema:
        if core_sha256 != _XP1_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('City religion details checkpoint transition requires Rise and Fall')
        from . import city_religion
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],game_generation=current['game_generation'])
        validate_capability_catalogue(current,identity,current['sequence'],observation['turn'],
                                      player_id=observation['player_id'],observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = _XP1_CITY_RELIGION_DETAILS_BASE_BY_SCHEMA[current_schema]
        projected['city_religion'] = city_religion.project_majority(
            current['city_religion'], observation['player_id'], observation['turn'], observation=observation)
        del projected['decision_id']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected,saved,observation,
            production_evidence=production_evidence,combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256,core_sha256=core_sha256)
        transition = dict(prior or {},source_schema=saved['schema'],target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields',[]) + ['city_religion.cities[].religions']
        transition['public_schema_upgrades'] = transition.get('public_schema_upgrades',[]) + [
            dict(field='city_religion',source_schema=city_religion.SCHEMA,target_schema=city_religion.DETAILS_SCHEMA)]
        return projected,transition
    religion_base = (_XP1_RELIGIOUS_UNIT_OPERATIONS_BASE_BY_SCHEMA.get(current_schema)
                     or _XP2_RELIGIOUS_UNIT_OPERATIONS_BASE_BY_SCHEMA.get(current_schema))
    if religion_base is not None and saved.get('schema') != current_schema:
        religion_core = (_XP1_COMBAT_CORE if current_schema in _XP1_RELIGIOUS_UNIT_OPERATIONS_BASE_BY_SCHEMA
                         else _XP2_COMBAT_CORE)
        if core_sha256 != religion_core or not is_capability_catalogue(saved):
            engine = 'Rise and Fall' if religion_core == _XP1_COMBAT_CORE else 'Gathering Storm'
            raise ValueError('Religious unit operation checkpoint transition requires ' + engine)
        from .religious_unit_operations import KINDS
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],game_generation=current['game_generation'])
        validate_capability_catalogue(current,identity,current['sequence'],observation['turn'],
                                      player_id=observation['player_id'],observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = religion_base
        del projected['religious_unit_operations']
        for kind in KINDS: del projected['families'][kind]
        projected['candidates'] = [row for row in projected['candidates'] if row['action']['kind'] not in KINDS]
        del projected['decision_id']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected,saved,observation,
            production_evidence=production_evidence,combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256,core_sha256=core_sha256)
        transition = dict(prior or {},source_schema=saved['schema'],target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields',[]) + ['religious_unit_operations']
        transition['added_action_families'] = transition.get('added_action_families',[]) + list(KINDS)
        return projected,transition
    if current_schema in _XP1_GREAT_PERSON_ACTIVATION_BASE_BY_SCHEMA and saved.get('schema') != current_schema:
        if core_sha256 != _XP1_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Great Person activation checkpoint transition requires Rise and Fall')
        from .great_person_activation import KIND
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],game_generation=current['game_generation'])
        validate_capability_catalogue(current,identity,current['sequence'],observation['turn'],
                                      player_id=observation['player_id'],observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = _XP1_GREAT_PERSON_ACTIVATION_BASE_BY_SCHEMA[current_schema]
        del projected['great_person_activation'], projected['families'][KIND]
        projected['candidates'] = [row for row in projected['candidates'] if row['action']['kind'] != KIND]
        del projected['decision_id']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected,saved,observation,
            production_evidence=production_evidence,combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256,core_sha256=core_sha256)
        transition = dict(prior or {},source_schema=saved['schema'],target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields',[]) + ['great_person_activation']
        transition['added_action_families'] = transition.get('added_action_families',[]) + [KIND]
        return projected,transition
    if current_schema in _XP1_RELIGION_CUSTOM_NAMES_BASE_BY_SCHEMA and saved.get('schema') != current_schema:
        if core_sha256 != _XP1_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Custom religion checkpoint transition requires Rise and Fall')
        from .religion_custom_names import KIND
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],game_generation=current['game_generation'])
        validate_capability_catalogue(current,identity,current['sequence'],observation['turn'],
                                      player_id=observation['player_id'],observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = _XP1_RELIGION_CUSTOM_NAMES_BASE_BY_SCHEMA[current_schema]
        del projected['religion_custom_names'], projected['families'][KIND]
        projected['candidates'] = [row for row in projected['candidates'] if row['action']['kind'] != KIND]
        del projected['decision_id']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected,saved,observation,
            production_evidence=production_evidence,combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256,core_sha256=core_sha256)
        transition = dict(prior or {},source_schema=saved['schema'],target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields',[]) + ['religion_custom_names']
        transition['added_action_families'] = transition.get('added_action_families',[]) + [KIND]
        return projected,transition
    if current_schema in _XP1_GREAT_PEOPLE_REJECT_BASE_BY_SCHEMA and saved.get('schema') != current_schema:
        if core_sha256 != _XP1_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Great Person rejection checkpoint transition requires Rise and Fall')
        from .great_people_actions import REJECT
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],game_generation=current['game_generation'])
        validate_capability_catalogue(current,identity,current['sequence'],observation['turn'],
                                      player_id=observation['player_id'],observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = _XP1_GREAT_PEOPLE_REJECT_BASE_BY_SCHEMA[current_schema]
        del projected['families'][REJECT]
        projected['candidates'] = [row for row in projected['candidates'] if row['action']['kind'] != REJECT]
        del projected['decision_id']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected,saved,observation,
            production_evidence=production_evidence,combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256,core_sha256=core_sha256)
        transition = dict(prior or {},source_schema=saved['schema'],target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_action_families'] = transition.get('added_action_families',[]) + [REJECT]
        return projected,transition
    gp_command_base = (_XP1_GREAT_PEOPLE_ACTIONS_BASE_BY_SCHEMA.get(current_schema)
                       or _XP2_GREAT_PEOPLE_ACTIONS_BASE_BY_SCHEMA.get(current_schema))
    if gp_command_base is not None and saved.get('schema') != current_schema:
        xp2 = current_schema in _XP2_GREAT_PEOPLE_ACTIONS_BASE_BY_SCHEMA
        if core_sha256 != (_XP2_COMBAT_CORE if xp2 else _XP1_COMBAT_CORE) or not is_capability_catalogue(saved):
            engine = 'Gathering Storm' if xp2 else 'Rise and Fall'
            raise ValueError(f'Great Person command checkpoint transition requires {engine}')
        from .great_people_actions import KINDS, LEGACY_KINDS
        from types import SimpleNamespace
        kinds = KINDS if xp2 else LEGACY_KINDS
        identity = SimpleNamespace(episode_id=current['episode_id'],game_generation=current['game_generation'])
        validate_capability_catalogue(current,identity,current['sequence'],observation['turn'],
                                      player_id=observation['player_id'],observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = gp_command_base
        for kind in kinds:
            del projected['families'][kind]
        projected['candidates'] = [row for row in projected['candidates'] if row['action']['kind'] not in kinds]
        del projected['decision_id']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected,saved,observation,
            production_evidence=production_evidence,combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256,core_sha256=core_sha256)
        transition = dict(prior or {},source_schema=saved['schema'],target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_action_families'] = transition.get('added_action_families',[]) + list(kinds)
        return projected,transition
    prophet_activation_base = (_XP1_PROPHET_ACTIVATION_BASE_BY_SCHEMA.get(current_schema)
        or _XP2_PROPHET_ACTIVATION_BASE_BY_SCHEMA.get(current_schema))
    if prophet_activation_base is not None and saved.get('schema') != current_schema:
        expected_core = (_XP2_COMBAT_CORE if current_schema in _XP2_PROPHET_ACTIVATION_BASE_BY_SCHEMA
                         else _XP1_COMBAT_CORE)
        if core_sha256 != expected_core or not is_capability_catalogue(saved):
            engine = 'Gathering Storm' if expected_core == _XP2_COMBAT_CORE else 'Rise and Fall'
            raise ValueError('Prophet activation checkpoint transition requires ' + engine)
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],game_generation=current['game_generation'])
        validate_capability_catalogue(current,identity,current['sequence'],observation['turn'],
                                      player_id=observation['player_id'],observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = prophet_activation_base
        del projected['prophet_activation'], projected['families']['activate_prophet'], projected['decision_id']
        projected['candidates'] = [row for row in projected['candidates'] if row['action']['kind']!='activate_prophet']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected,saved,observation,
            production_evidence=production_evidence,combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256,core_sha256=core_sha256)
        transition = dict(prior or {},source_schema=saved['schema'],target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields',[]) + ['prophet_activation']
        transition['added_action_families'] = transition.get('added_action_families',[]) + ['activate_prophet']
        return projected,transition
    great_people_base = (_XP1_GREAT_PEOPLE_BASE_BY_SCHEMA.get(current_schema)
                         or _XP2_GREAT_PEOPLE_BASE_BY_SCHEMA.get(current_schema))
    if great_people_base is not None and saved.get('schema') != current_schema:
        xp2 = current_schema in _XP2_GREAT_PEOPLE_BASE_BY_SCHEMA
        if core_sha256 != (_XP2_COMBAT_CORE if xp2 else _XP1_COMBAT_CORE) or not is_capability_catalogue(saved):
            engine = 'Gathering Storm' if xp2 else 'Rise and Fall'
            raise ValueError(f'Great People checkpoint transition requires {engine}')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],game_generation=current['game_generation'])
        validate_capability_catalogue(current,identity,current['sequence'],observation['turn'],
                                      player_id=observation['player_id'],observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = great_people_base
        del projected['great_people'], projected['decision_id']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected,saved,observation,
            production_evidence=production_evidence,combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256,core_sha256=core_sha256)
        transition = dict(prior or {},source_schema=saved['schema'],target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields',[]) + ['great_people']
        transition.setdefault('added_action_families', [])
        return projected,transition
    religion_founding_base = (_XP1_RELIGION_FOUNDING_BASE_BY_SCHEMA.get(current_schema)
        or _XP2_RELIGION_FOUNDING_BASE_BY_SCHEMA.get(current_schema))
    if religion_founding_base is not None and saved.get('schema') != current_schema:
        expected_core = (_XP2_COMBAT_CORE if current_schema in _XP2_RELIGION_FOUNDING_BASE_BY_SCHEMA
                         else _XP1_COMBAT_CORE)
        if core_sha256 != expected_core or not is_capability_catalogue(saved):
            engine = 'Gathering Storm' if expected_core == _XP2_COMBAT_CORE else 'Rise and Fall'
            raise ValueError('Religion foundation checkpoint transition requires ' + engine)
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],game_generation=current['game_generation'])
        validate_capability_catalogue(current,identity,current['sequence'],observation['turn'],
                                      player_id=observation['player_id'],observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = religion_founding_base
        del projected['religion_founding'], projected['families']['found_religion'], projected['decision_id']
        projected['candidates'] = [row for row in projected['candidates'] if row['action']['kind']!='found_religion']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected,saved,observation,
            production_evidence=production_evidence,combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256,core_sha256=core_sha256)
        transition = dict(prior or {},source_schema=saved['schema'],target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields',[]) + ['religion_founding']
        transition['added_action_families'] = transition.get('added_action_families',[]) + ['found_religion']
        return projected,transition
    religion_beliefs_base = (_XP1_RELIGION_BELIEFS_BASE_BY_SCHEMA.get(current_schema)
        or _XP2_RELIGION_BELIEFS_BASE_BY_SCHEMA.get(current_schema))
    if religion_beliefs_base is not None and saved.get('schema') != current_schema:
        expected_core = (_XP2_COMBAT_CORE if current_schema in _XP2_RELIGION_BELIEFS_BASE_BY_SCHEMA
                         else _XP1_COMBAT_CORE)
        if core_sha256 != expected_core or not is_capability_catalogue(saved):
            engine = 'Gathering Storm' if expected_core == _XP2_COMBAT_CORE else 'Rise and Fall'
            raise ValueError('Belief checkpoint transition requires ' + engine)
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],game_generation=current['game_generation'])
        validate_capability_catalogue(current,identity,current['sequence'],observation['turn'],
                                      player_id=observation['player_id'],observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = religion_beliefs_base
        del projected['religion_beliefs'], projected['families']['add_belief'], projected['decision_id']
        projected['candidates'] = [row for row in projected['candidates'] if row['action']['kind']!='add_belief']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected,saved,observation,
            production_evidence=production_evidence,combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256,core_sha256=core_sha256)
        transition = dict(prior or {},source_schema=saved['schema'],target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields',[]) + ['religion_beliefs']
        transition['added_action_families'] = transition.get('added_action_families',[]) + ['add_belief']
        return projected,transition
    if current_schema in _XP1_PANTHEON_BASE_BY_SCHEMA and saved.get('schema') != current_schema:
        if core_sha256 != _XP1_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Pantheon checkpoint transition requires Rise and Fall')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],game_generation=current['game_generation'])
        validate_capability_catalogue(current,identity,current['sequence'],observation['turn'],
                                      player_id=observation['player_id'],observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = _XP1_PANTHEON_BASE_BY_SCHEMA[current_schema]
        del projected['pantheon'], projected['families']['pantheon'], projected['decision_id']
        projected['candidates'] = [row for row in projected['candidates'] if row['action']['kind']!='pantheon']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected,saved,observation,
            production_evidence=production_evidence,combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256,core_sha256=core_sha256)
        transition = dict(prior or {},source_schema=saved['schema'],target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields',[]) + ['pantheon']
        transition['added_action_families'] = transition.get('added_action_families',[]) + ['pantheon']
        return projected,transition
    if current_schema in _XP1_CITY_RELIGION_BASE_BY_SCHEMA and saved.get('schema') != current_schema:
        if core_sha256 != _XP1_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('City religion checkpoint transition requires Rise and Fall')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],game_generation=current['game_generation'])
        validate_capability_catalogue(current,identity,current['sequence'],observation['turn'],
                                      player_id=observation['player_id'],observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = _XP1_CITY_RELIGION_BASE_BY_SCHEMA[current_schema]
        del projected['city_religion'], projected['decision_id']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected,saved,observation,
            production_evidence=production_evidence,combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256,core_sha256=core_sha256)
        transition = dict(prior or {},source_schema=saved['schema'],target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields',[]) + ['city_religion']
        return projected,transition
    if current_schema in _XP1_PRODUCTION_INFO_BASE_BY_SCHEMA and saved.get('schema') != current_schema:
        if core_sha256 != _XP1_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Production information checkpoint transition requires Rise and Fall')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],game_generation=current['game_generation'])
        validate_capability_catalogue(current,identity,current['sequence'],observation['turn'],
                                      player_id=observation['player_id'],observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = _XP1_PRODUCTION_INFO_BASE_BY_SCHEMA[current_schema]
        del projected['production_current'], projected['production_info'], projected['decision_id']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected,saved,observation,
            production_evidence=production_evidence,combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256,core_sha256=core_sha256)
        transition = dict(prior or {},source_schema=saved['schema'],target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields',[]) + ['production_current','production_info']
        return projected,transition
    if current_schema in _XP1_UPGRADE_BASE_BY_SCHEMA and saved.get('schema') != current_schema:
        if core_sha256 != _XP1_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Unit upgrade checkpoint transition requires Rise and Fall')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],game_generation=current['game_generation'])
        validate_capability_catalogue(current,identity,current['sequence'],observation['turn'],
                                      player_id=observation['player_id'],observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = _XP1_UPGRADE_BASE_BY_SCHEMA[current_schema]
        del projected['unit_upgrades'], projected['families']['upgrade_unit'], projected['decision_id']
        projected['candidates'] = [row for row in projected['candidates'] if row['action']['kind']!='upgrade_unit']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected,saved,observation,
            production_evidence=production_evidence,combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256,core_sha256=core_sha256)
        transition = dict(prior or {},source_schema=saved['schema'],target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields',[]) + ['unit_upgrades']
        transition['added_action_families'] = transition.get('added_action_families',[]) + ['upgrade_unit']
        return projected,transition
    if current_schema in _XP1_PROMOTION_BASE_BY_SCHEMA and saved.get('schema') != current_schema:
        if core_sha256 != _XP1_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Unit promotion checkpoint transition requires Rise and Fall')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        validate_capability_catalogue(current,identity,current['sequence'],observation['turn'],
                                      player_id=observation['player_id'],observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = _XP1_PROMOTION_BASE_BY_SCHEMA[current_schema]
        del projected['unit_promotions'], projected['families']['promote_unit'], projected['decision_id']
        projected['candidates'] = [row for row in projected['candidates'] if row['action']['kind']!='promote_unit']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected,saved,observation,
            production_evidence=production_evidence,combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256,core_sha256=core_sha256)
        transition = dict(prior or {},source_schema=saved['schema'],target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields',[]) + ['unit_promotions']
        transition['added_action_families'] = transition.get('added_action_families',[]) + ['promote_unit']
        return projected,transition
    if current_schema in _XP1_CITY_BUILDINGS_BASE_BY_SCHEMA and saved.get('schema') != current_schema:
        if core_sha256 != _XP1_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('City building checkpoint transition requires Rise and Fall')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        validate_capability_catalogue(current,identity,current['sequence'],observation['turn'],
                                      player_id=observation['player_id'],observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = _XP1_CITY_BUILDINGS_BASE_BY_SCHEMA[current_schema]
        del projected['city_buildings'], projected['decision_id']
        added_actions = ([_remove_great_work_choices(projected)]
                         if current_panel in city_buildings.GREAT_WORK_COMMAND_SCHEMAS else [])
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected,saved,observation,
            production_evidence=production_evidence,combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256,core_sha256=core_sha256)
        transition = dict(prior or {},source_schema=saved['schema'],target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields',[]) + ['city_buildings']
        transition.setdefault('added_action_families', []).extend(added_actions)
        return projected,transition
    if current_schema in _XP1_FAITH_PURCHASE_BASE_BY_SCHEMA and saved.get('schema') != current_schema:
        return _faith_purchase_checkpoint(current, saved, observation,
            target_base=_XP1_FAITH_PURCHASE_BASE_BY_SCHEMA[current_schema], required_core=_XP1_COMBAT_CORE,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
    if current_schema in _XP1_CITY_PURCHASE_BASE_BY_SCHEMA and saved.get('schema') != current_schema:
        if core_sha256 != _XP1_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Gold purchase checkpoint transition requires Rise and Fall')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = _XP1_CITY_PURCHASE_BASE_BY_SCHEMA[current_schema]
        _remove_city_purchase_choices(projected)
        del projected['decision_id']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + ['city_purchases']
        transition['added_action_families'] = transition.get('added_action_families', []) + [
            'standard_gold_unit_building_purchase']
        return projected, transition
    if current_schema in _XP1_PLOT_PURCHASE_BASE_BY_SCHEMA and saved.get('schema') != current_schema:
        if core_sha256 != _XP1_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Plot purchase checkpoint transition requires Rise and Fall')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],
                                   game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = _XP1_PLOT_PURCHASE_BASE_BY_SCHEMA[current_schema]
        del projected['plot_purchases'], projected['families']['purchase']
        projected['candidates'] = [row for row in projected['candidates'] if row['action']['kind'] != 'purchase']
        del projected['decision_id']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + ['plot_purchases']
        transition['added_action_families'] = transition.get('added_action_families', []) + ['purchase']
        return projected, transition
    if current_schema in _XP1_GOVERNMENT_BASE_BY_SCHEMA and saved.get('schema') != current_schema:
        if core_sha256 != _XP1_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Government and policy checkpoint transition requires Rise and Fall')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],
                                   game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        fields = ('government', 'policies')
        projected = copy.deepcopy(current)
        projected['schema'] = _XP1_GOVERNMENT_BASE_BY_SCHEMA[current_schema]
        for field in fields:
            del projected[field]
            del projected['families'][field]
        kinds = (*fields, 'retain_government')
        projected['candidates'] = [row for row in projected['candidates'] if row['action']['kind'] not in kinds]
        del projected['decision_id']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + list(fields)
        transition['added_action_families'] = transition.get('added_action_families', []) + list(fields)
        return projected, transition
    if current_schema == CAPABILITY_XP2_STOCK_CONGRESS_SCHEMA and saved.get('schema') != current_schema:
        if core_sha256 != _XP2_COMBAT_CORE or saved.get('schema') != CAPABILITY_XP2_STOCK_DEDICATIONS_SCHEMA:
            raise ValueError('Congress transition requires the previous stock dedication checkpoint')
        from types import SimpleNamespace
        from . import world_congress
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        fields = ('world_congress', 'world_congress_review', 'world_congress_review_status',
                  'native_command_permissions', 'world_congress_active_effects', 'world_congress_active_effects_status')
        projected = copy.deepcopy(current)
        projected['schema'] = CAPABILITY_XP2_STOCK_DEDICATIONS_SCHEMA
        for field in fields:
            del projected[field]
        for kind in world_congress.CANDIDATE_FIELDS:
            del projected['families'][kind]
        projected['candidates'] = [row for row in projected['candidates']
                                   if row['action']['kind'] not in world_congress.CANDIDATE_FIELDS]
        del projected['decision_id']
        projected['decision_id'] = digest(projected)
        return projected, dict(source_schema=saved['schema'], target_schema=current_schema,
            historical_fields_unchanged=True, added_public_fields=list(fields),
            added_action_families=list(world_congress.CANDIDATE_FIELDS))
    dedication_predecessors = {
        CAPABILITY_XP1_DEDICATIONS_SCHEMA: (_XP1_COMBAT_CORE, CAPABILITY_XP1_UNIT_LEVIES_SCHEMA),
        CAPABILITY_XP2_STOCK_DEDICATIONS_SCHEMA: (_XP2_COMBAT_CORE, CAPABILITY_XP2_STOCK_FORMATIONS_SCHEMA),
    }
    if current_schema in dedication_predecessors and saved.get('schema') != current_schema:
        expected_core, previous_schema = dedication_predecessors[current_schema]
        if core_sha256 != expected_core or not is_capability_catalogue(saved):
            raise ValueError('Dedication transition requires its exact expansion checkpoint')
        if core_sha256 == _XP2_COMBAT_CORE and saved.get('schema') != previous_schema:
            raise ValueError('Dedication transition requires its previous stock formation checkpoint')
        from types import SimpleNamespace
        from . import dedications
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = previous_schema
        del projected['dedications']
        del projected['families'][dedications.KIND]
        projected['candidates'] = [row for row in projected['candidates']
                                   if row['action']['kind'] != dedications.KIND]
        del projected['decision_id']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + ['dedications']
        transition['added_action_families'] = transition.get('added_action_families', []) + [dedications.KIND]
        return projected, transition
    if current_schema == CAPABILITY_XP2_STOCK_FORMATIONS_SCHEMA and saved.get('schema') != current_schema:
        if core_sha256 != _XP2_COMBAT_CORE or saved.get('schema') != CAPABILITY_XP2_STANDARD_TRADE_SCHEMA:
            raise ValueError('Formation transition requires the previous stock trade checkpoint')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = CAPABILITY_XP2_STANDARD_TRADE_SCHEMA
        del projected['unit_formations']
        del projected['families']['unit_formation']
        projected['candidates'] = [row for row in projected['candidates'] if row['action']['kind'] != 'unit_formation']
        del projected['decision_id']
        projected['decision_id'] = digest(projected)
        return projected, dict(source_schema=saved['schema'], target_schema=current_schema,
            historical_fields_unchanged=True, added_public_fields=['unit_formations'],
            added_action_families=['unit_formation'])
    if current_schema == CAPABILITY_XP2_STANDARD_TRADE_SCHEMA and saved.get('schema') != current_schema:
        if core_sha256 != _XP2_COMBAT_CORE or saved.get('schema') != CAPABILITY_XP2_ENVOYS_SCHEMA:
            raise ValueError('Standard trade transition requires its Gathering Storm v31 checkpoint')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        fields = ('trade_routes', 'trade_origins', 'trade_overview', 'trade_overview_status')
        kinds = ('make_trade_route', 'change_trade_origin')
        for field in fields:
            del projected[field]
        for kind in kinds:
            del projected['families'][kind]
        projected['candidates'] = [row for row in projected['candidates'] if row['action']['kind'] not in kinds]
        projected['schema'] = CAPABILITY_XP2_ENVOYS_SCHEMA
        del projected['decision_id']
        projected['decision_id'] = digest(projected)
        return projected, dict(source_schema=saved['schema'], target_schema=current_schema,
            historical_fields_unchanged=True, added_public_fields=list(fields), added_action_families=list(kinds))
    if current_schema == CAPABILITY_XP1_GOVERNORS_SCHEMA and saved.get('schema') != current_schema:
        if core_sha256 != _XP1_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Governor checkpoint transition requires the Rise and Fall catalogue')
        from .governors import ACTION_FIELDS
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = CAPABILITY_XP1_DISTRICT_SHOT_SCHEMA
        del projected['governors'], projected['decision_id']
        for kind in ACTION_FIELDS:
            del projected['families'][kind]
        projected['candidates'] = [row for row in projected['candidates'] if row['action']['kind'] not in ACTION_FIELDS]
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + ['governors']
        transition['added_action_families'] = transition.get('added_action_families', []) + list(ACTION_FIELDS)
        return projected, transition
    if current_schema in _XP1_SHOT_TRANSITIONS and saved.get('schema') != current_schema:
        if core_sha256 != _XP1_COMBAT_CORE or not is_capability_catalogue(saved):
            raise ValueError('Ranged-shot checkpoint transition requires the Rise and Fall catalogue')
        base, field, kind = _XP1_SHOT_TRANSITIONS[current_schema]
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = base
        del projected[field], projected['families'][kind], projected['decision_id']
        projected['candidates'] = [row for row in projected['candidates']
                                   if row['action']['kind'] != kind]
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + [field]
        transition['added_action_families'] = transition.get('added_action_families', []) + [kind]
        return projected, transition
    if current_schema in _CAPTURE_BASE_SCHEMA and saved.get('schema') != current_schema:
        from . import captured_city
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        capture_core = (_XP1_COMBAT_CORE if current_schema == CAPABILITY_XP1_CAPTURED_CITY_SCHEMA
                        else _XP2_COMBAT_CORE)
        if core_sha256 != capture_core or not is_capability_catalogue(saved):
            raise ValueError('Captured-city checkpoint transition requires its exact expansion')
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        if current['captured_city'] is None or current['captured_city']['city'] is not None:
            raise ValueError('Historical checkpoint cannot establish a pending captured-city boundary')
        projected = copy.deepcopy(current)
        projected['schema'] = _CAPTURE_BASE_SCHEMA[current_schema]
        del projected['captured_city'], projected['families'][captured_city.KIND], projected['decision_id']
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + ['captured_city']
        transition['added_action_families'] = transition.get('added_action_families', []) + [captured_city.KIND]
        return projected, transition
    overview_predecessors = {
        CAPABILITY_XP1_TRADE_OVERVIEW_SCHEMA: (_XP1_COMBAT_CORE, CAPABILITY_XP1_TRADE_SCHEMA),
        CAPABILITY_XP2_TRADE_OVERVIEW_SCHEMA: (_XP2_COMBAT_CORE, CAPABILITY_XP2_CONGRESS_ACTIVE_EFFECTS_SCHEMA),
    }
    if current_schema in overview_predecessors and saved.get('schema') != current_schema:
        expected_core, previous_schema = overview_predecessors[current_schema]
        if core_sha256 != expected_core or not is_capability_catalogue(saved):
            raise ValueError('Trade overview checkpoint transition requires its exact expansion engine')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = previous_schema
        projected.pop('trade_overview')
        projected.pop('trade_overview_status')
        projected.pop('decision_id')
        projected['decision_id'] = digest(projected)
        projected, prior = checkpoint_catalogue(projected, saved, observation,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
        transition = dict(prior or {}, source_schema=saved['schema'], target_schema=current_schema,
                          historical_fields_unchanged=True)
        transition['added_public_fields'] = transition.get('added_public_fields', []) + [
            'trade_overview', 'trade_overview_status']
        return projected, transition
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
    trade_predecessors = {
        CAPABILITY_XP1_TRADE_SCHEMA: (_XP1_COMBAT_CORE, CAPABILITY_XP1_DEDICATIONS_SCHEMA),
        CAPABILITY_XP2_TRADE_SCHEMA: (_XP2_COMBAT_CORE, CAPABILITY_XP2_INITIAL_DIPLOMACY_SCHEMA),
    }
    if current_schema in trade_predecessors and saved.get('schema') != current_schema:
        expected_core, previous_schema = trade_predecessors[current_schema]
        if core_sha256 != expected_core or not is_capability_catalogue(saved):
            raise ValueError('Trade checkpoint transition requires its exact expansion engine')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],
                                   game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = previous_schema
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
    city_state_additions = {
        CAPABILITY_XP1_CITY_STATE_LEVIES_SCHEMA: (CAPABILITY_XP1_ENVOY_CHOICES_SCHEMA,
            _XP1_COMBAT_CORE, ('city_state_levies',), ('levy_city_state_military',)),
        CAPABILITY_XP1_ENVOY_CHOICES_SCHEMA: (CAPABILITY_XP1_CITY_STATE_ENVOYS_SCHEMA,
            _XP1_COMBAT_CORE, ('envoys',), ('send_envoy', 'retain_envoys')),
        CAPABILITY_XP2_ENVOYS_SCHEMA: (CAPABILITY_XP2_FAITH_PURCHASE_SCHEMA,
            _XP2_COMBAT_CORE, ('envoys',), ('send_envoy', 'retain_envoys')),
        **{schema: (base, _XP2_COMBAT_CORE, ('city_state_levies', 'unit_levies'),
                    ('levy_city_state_military',)) for schema, base in _XP2_LEVY_BASE_SCHEMA.items()},
    }
    if current_schema in city_state_additions and saved.get('schema') != current_schema:
        previous_schema, required_core, fields, kinds = city_state_additions[current_schema]
        if core_sha256 != required_core or not is_capability_catalogue(saved):
            raise ValueError('Envoy checkpoint transition requires its exact engine')
        from types import SimpleNamespace
        identity = SimpleNamespace(episode_id=current['episode_id'],
                                   game_generation=current['game_generation'])
        validate_capability_catalogue(current, identity, current['sequence'], observation['turn'],
                                      player_id=observation['player_id'], observation=observation)
        projected = copy.deepcopy(current)
        projected['schema'] = previous_schema
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
    if (current_schema == CAPABILITY_XP2_FAITH_PURCHASE_SCHEMA
            and saved.get('schema') != CAPABILITY_XP2_FAITH_PURCHASE_SCHEMA):
        return _faith_purchase_checkpoint(current, saved, observation,
            target_base=CAPABILITY_XP2_POLICY_RECONFIRM_SCHEMA, required_core=_XP2_COMBAT_CORE,
            production_evidence=production_evidence, combat_evidence=combat_evidence,
            combat_source_sha256=combat_source_sha256,
            combat_readiness_source_sha256=combat_readiness_source_sha256, core_sha256=core_sha256)
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
            projected['schema'] = CAPABILITY_XP2_PLOT_PURCHASE_SCHEMA
            _remove_city_purchase_choices(projected)
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
        if current_schema in (CAPABILITY_XP1_CITY_STATE_ENVOYS_SCHEMA, CAPABILITY_XP1_UNIT_LEVIES_SCHEMA):
            if core_sha256 != _XP1_COMBAT_CORE or not is_capability_catalogue(saved):
                raise ValueError('City-state information checkpoint transition requires Rise and Fall')
        elif core_sha256 != _XP2_COMBAT_CORE or not is_capability_catalogue(saved):
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
