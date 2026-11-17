"""Build the exact Rise and Fall schema combinations on first use."""
from .network_turn import (
    CAPABILITY_XP1_CAPTURED_CITY_SCHEMA,
    CAPABILITY_XP1_CITY_SHOT_SCHEMA,
    CAPABILITY_XP1_DISTRICT_SHOT_SCHEMA,
    CAPABILITY_XP1_GOVERNORS_SCHEMA,
    CAPABILITY_XP1_CITY_STATE_ENVOYS_SCHEMA,
    CAPABILITY_XP1_ENVOY_CHOICES_SCHEMA,
    CAPABILITY_XP1_CITY_STATE_LEVIES_SCHEMA,
    CAPABILITY_XP1_UNIT_LEVIES_SCHEMA,
    CAPABILITY_XP1_DEDICATIONS_SCHEMA,
    CAPABILITY_XP1_TRADE_SCHEMA,
    CAPABILITY_XP1_TRADE_OVERVIEW_SCHEMA,
)

XP1_GOVERNMENT_SCHEMA_BY_BASE = {
    schema: schema + '.government.v1' for schema in (
        CAPABILITY_XP1_DEDICATIONS_SCHEMA, CAPABILITY_XP1_TRADE_SCHEMA, CAPABILITY_XP1_TRADE_OVERVIEW_SCHEMA)
}
_XP1_GOVERNMENT_BASE_BY_SCHEMA = {new: base for base, new in XP1_GOVERNMENT_SCHEMA_BY_BASE.items()}
XP1_PLOT_PURCHASE_SCHEMA_BY_BASE = {
    schema: schema + '.plot-purchase.v1'
    for schema in (*XP1_GOVERNMENT_SCHEMA_BY_BASE, *XP1_GOVERNMENT_SCHEMA_BY_BASE.values())
}
_XP1_PLOT_PURCHASE_BASE_BY_SCHEMA = {new: base for base, new in XP1_PLOT_PURCHASE_SCHEMA_BY_BASE.items()}
XP1_CITY_PURCHASE_SCHEMA_BY_BASE = {
    schema: schema.replace('.plot-purchase.v1', '.gold-purchase.v1')
    for schema in _XP1_PLOT_PURCHASE_BASE_BY_SCHEMA
}
_XP1_CITY_PURCHASE_BASE_BY_SCHEMA = {new: base for base, new in XP1_CITY_PURCHASE_SCHEMA_BY_BASE.items()}
XP1_FAITH_PURCHASE_SCHEMA_BY_BASE = {
    schema: schema + '.faith.v1' for schema in _XP1_CITY_PURCHASE_BASE_BY_SCHEMA
}
_XP1_FAITH_PURCHASE_BASE_BY_SCHEMA = {new: base for base, new in XP1_FAITH_PURCHASE_SCHEMA_BY_BASE.items()}


def _with_xp1_purchases(bases):
    plots = tuple(XP1_PLOT_PURCHASE_SCHEMA_BY_BASE[base] for base in bases)
    gold = tuple(XP1_CITY_PURCHASE_SCHEMA_BY_BASE[plot] for plot in plots)
    return (*bases, *plots, *gold, *(XP1_FAITH_PURCHASE_SCHEMA_BY_BASE[schema] for schema in gold))
_XP1_TRADE_BASES = (CAPABILITY_XP1_TRADE_SCHEMA, CAPABILITY_XP1_TRADE_OVERVIEW_SCHEMA)
_XP1_TRADE_WITH_GOVERNMENT = (*_XP1_TRADE_BASES,
                             *(XP1_GOVERNMENT_SCHEMA_BY_BASE[base] for base in _XP1_TRADE_BASES))
_XP1_DEDICATION_BASES = _with_xp1_purchases(
    (CAPABILITY_XP1_DEDICATIONS_SCHEMA, *_XP1_TRADE_BASES, *XP1_GOVERNMENT_SCHEMA_BY_BASE.values()))
XP1_CITY_BUILDINGS_SCHEMA_BY_BASE = {schema: schema+'.buildings.v1' for schema in _XP1_DEDICATION_BASES}
_XP1_CITY_BUILDINGS_BASE_BY_SCHEMA = {new: base for base,new in XP1_CITY_BUILDINGS_SCHEMA_BY_BASE.items()}


def _with_xp1_buildings(bases):
    return (*bases, *(XP1_CITY_BUILDINGS_SCHEMA_BY_BASE[base] for base in bases))


XP1_PROMOTION_SCHEMA_BY_BASE = {
    schema: schema+'.promotion.v1' for schema in _with_xp1_buildings(_XP1_DEDICATION_BASES)
}
_XP1_PROMOTION_BASE_BY_SCHEMA = {new:base for base,new in XP1_PROMOTION_SCHEMA_BY_BASE.items()}


def _with_xp1_promotions(bases):
    return (*bases, *(XP1_PROMOTION_SCHEMA_BY_BASE[base] for base in bases))


XP1_UPGRADE_SCHEMA_BY_BASE = {
    schema: schema+'.unit-upgrade.v1'
    for schema in _with_xp1_promotions(_with_xp1_buildings(_XP1_DEDICATION_BASES))
}
_XP1_UPGRADE_BASE_BY_SCHEMA = {new:base for base,new in XP1_UPGRADE_SCHEMA_BY_BASE.items()}


def _with_xp1_unit_upgrades(bases):
    return (*bases, *(XP1_UPGRADE_SCHEMA_BY_BASE[base] for base in bases))


_XP1_PRODUCTION_BASES = _with_xp1_unit_upgrades(_with_xp1_promotions(_with_xp1_buildings(_XP1_DEDICATION_BASES)))
XP1_PRODUCTION_INFO_SCHEMA_BY_BASE = {schema: schema+'.production-info.v1' for schema in _XP1_PRODUCTION_BASES}
_XP1_PRODUCTION_INFO_BASE_BY_SCHEMA = {new:base for base,new in XP1_PRODUCTION_INFO_SCHEMA_BY_BASE.items()}
XP1_CITY_RELIGION_SCHEMA_BY_BASE = {schema: schema+'.city-religion.v1'
    for schema in _XP1_PRODUCTION_INFO_BASE_BY_SCHEMA}
_XP1_CITY_RELIGION_BASE_BY_SCHEMA = {new:base for base,new in XP1_CITY_RELIGION_SCHEMA_BY_BASE.items()}
XP1_PANTHEON_SCHEMA_BY_BASE = {schema: schema+'.pantheon.v1'
    for schema in _XP1_CITY_RELIGION_BASE_BY_SCHEMA}
_XP1_PANTHEON_BASE_BY_SCHEMA = {new:base for base,new in XP1_PANTHEON_SCHEMA_BY_BASE.items()}
XP1_RELIGION_BELIEFS_SCHEMA_BY_BASE = {schema: schema+'.religion-beliefs.v1'
    for schema in (*_XP1_CITY_RELIGION_BASE_BY_SCHEMA, *_XP1_PANTHEON_BASE_BY_SCHEMA)}
_XP1_RELIGION_BELIEFS_BASE_BY_SCHEMA = {new:base for base,new in XP1_RELIGION_BELIEFS_SCHEMA_BY_BASE.items()}
XP1_RELIGION_FOUNDING_SCHEMA_BY_BASE = {schema: schema+'.religion-founding.v1'
    for schema in (*_XP1_CITY_RELIGION_BASE_BY_SCHEMA, *_XP1_PANTHEON_BASE_BY_SCHEMA,
                   *_XP1_RELIGION_BELIEFS_BASE_BY_SCHEMA)}
_XP1_RELIGION_FOUNDING_BASE_BY_SCHEMA = {new:base for base,new in XP1_RELIGION_FOUNDING_SCHEMA_BY_BASE.items()}
XP1_RELIGION_FOUNDING_SCHEMAS = tuple(_XP1_RELIGION_FOUNDING_BASE_BY_SCHEMA)
XP1_RELIGION_BELIEFS_SCHEMAS = (*_XP1_RELIGION_BELIEFS_BASE_BY_SCHEMA,
    *(XP1_RELIGION_FOUNDING_SCHEMA_BY_BASE[base] for base in _XP1_RELIGION_BELIEFS_BASE_BY_SCHEMA))
_XP1_PANTHEON_WITH_BELIEFS = (*_XP1_PANTHEON_BASE_BY_SCHEMA,
    *(XP1_RELIGION_BELIEFS_SCHEMA_BY_BASE[base] for base in _XP1_PANTHEON_BASE_BY_SCHEMA))
XP1_PANTHEON_SCHEMAS = (*_XP1_PANTHEON_WITH_BELIEFS,
    *(XP1_RELIGION_FOUNDING_SCHEMA_BY_BASE[base] for base in _XP1_PANTHEON_WITH_BELIEFS))
XP1_CITY_RELIGION_SCHEMAS = (*_XP1_CITY_RELIGION_BASE_BY_SCHEMA,
    *_XP1_PANTHEON_BASE_BY_SCHEMA, *_XP1_RELIGION_BELIEFS_BASE_BY_SCHEMA,
    *XP1_RELIGION_FOUNDING_SCHEMAS)
XP1_GREAT_PEOPLE_SCHEMA_BY_BASE = {schema: schema+'.great-people.v1'
    for schema in XP1_CITY_RELIGION_SCHEMAS}
_XP1_GREAT_PEOPLE_BASE_BY_SCHEMA = {new:base for base,new in XP1_GREAT_PEOPLE_SCHEMA_BY_BASE.items()}
XP1_GREAT_PEOPLE_SCHEMAS = tuple(_XP1_GREAT_PEOPLE_BASE_BY_SCHEMA)


def _with_xp1_great_people(bases):
    return (*bases, *(XP1_GREAT_PEOPLE_SCHEMA_BY_BASE[base] for base in bases))


XP1_RELIGION_FOUNDING_SCHEMAS = _with_xp1_great_people(XP1_RELIGION_FOUNDING_SCHEMAS)
XP1_RELIGION_BELIEFS_SCHEMAS = _with_xp1_great_people(XP1_RELIGION_BELIEFS_SCHEMAS)
XP1_PANTHEON_SCHEMAS = _with_xp1_great_people(XP1_PANTHEON_SCHEMAS)
XP1_CITY_RELIGION_SCHEMAS = _with_xp1_great_people(XP1_CITY_RELIGION_SCHEMAS)
XP1_PROPHET_ACTIVATION_SCHEMA_BY_BASE = {schema: schema+'.prophet-activation.v1'
    for schema in XP1_CITY_RELIGION_SCHEMAS}
_XP1_PROPHET_ACTIVATION_BASE_BY_SCHEMA = {new:base for base,new in XP1_PROPHET_ACTIVATION_SCHEMA_BY_BASE.items()}
XP1_PROPHET_ACTIVATION_SCHEMAS = tuple(_XP1_PROPHET_ACTIVATION_BASE_BY_SCHEMA)


def _with_xp1_prophet_activation(bases):
    return (*bases, *(XP1_PROPHET_ACTIVATION_SCHEMA_BY_BASE[base] for base in bases))


XP1_GREAT_PEOPLE_SCHEMAS = _with_xp1_prophet_activation(XP1_GREAT_PEOPLE_SCHEMAS)
XP1_RELIGION_FOUNDING_SCHEMAS = _with_xp1_prophet_activation(XP1_RELIGION_FOUNDING_SCHEMAS)
XP1_RELIGION_BELIEFS_SCHEMAS = _with_xp1_prophet_activation(XP1_RELIGION_BELIEFS_SCHEMAS)
XP1_PANTHEON_SCHEMAS = _with_xp1_prophet_activation(XP1_PANTHEON_SCHEMAS)
XP1_CITY_RELIGION_SCHEMAS = _with_xp1_prophet_activation(XP1_CITY_RELIGION_SCHEMAS)
XP1_GREAT_PEOPLE_ACTIONS_SCHEMA_BY_BASE = {schema: schema+'.great-people-actions.v1'
    for schema in XP1_GREAT_PEOPLE_SCHEMAS}
_XP1_GREAT_PEOPLE_ACTIONS_BASE_BY_SCHEMA = {new:base for base,new in XP1_GREAT_PEOPLE_ACTIONS_SCHEMA_BY_BASE.items()}
XP1_GREAT_PEOPLE_ACTIONS_SCHEMAS = tuple(_XP1_GREAT_PEOPLE_ACTIONS_BASE_BY_SCHEMA)


def _with_xp1_great_people_actions(bases):
    return (*bases, *(XP1_GREAT_PEOPLE_ACTIONS_SCHEMA_BY_BASE[base] for base in bases
                     if base in XP1_GREAT_PEOPLE_ACTIONS_SCHEMA_BY_BASE))


XP1_PROPHET_ACTIVATION_SCHEMAS = _with_xp1_great_people_actions(XP1_PROPHET_ACTIVATION_SCHEMAS)
XP1_GREAT_PEOPLE_SCHEMAS = _with_xp1_great_people_actions(XP1_GREAT_PEOPLE_SCHEMAS)
XP1_RELIGION_FOUNDING_SCHEMAS = _with_xp1_great_people_actions(XP1_RELIGION_FOUNDING_SCHEMAS)
XP1_RELIGION_BELIEFS_SCHEMAS = _with_xp1_great_people_actions(XP1_RELIGION_BELIEFS_SCHEMAS)
XP1_PANTHEON_SCHEMAS = _with_xp1_great_people_actions(XP1_PANTHEON_SCHEMAS)
XP1_CITY_RELIGION_SCHEMAS = _with_xp1_great_people_actions(XP1_CITY_RELIGION_SCHEMAS)
XP1_GREAT_PEOPLE_REJECT_SCHEMA_BY_BASE = {schema: schema+'.great-people-reject.v1'
    for schema in XP1_GREAT_PEOPLE_ACTIONS_SCHEMAS}
_XP1_GREAT_PEOPLE_REJECT_BASE_BY_SCHEMA = {new:base for base,new in XP1_GREAT_PEOPLE_REJECT_SCHEMA_BY_BASE.items()}
XP1_GREAT_PEOPLE_REJECT_SCHEMAS = tuple(_XP1_GREAT_PEOPLE_REJECT_BASE_BY_SCHEMA)


def _with_xp1_great_people_reject(bases):
    return (*bases, *(XP1_GREAT_PEOPLE_REJECT_SCHEMA_BY_BASE[base] for base in bases
                     if base in XP1_GREAT_PEOPLE_REJECT_SCHEMA_BY_BASE))


XP1_GREAT_PEOPLE_ACTIONS_SCHEMAS = _with_xp1_great_people_reject(XP1_GREAT_PEOPLE_ACTIONS_SCHEMAS)
XP1_PROPHET_ACTIVATION_SCHEMAS = _with_xp1_great_people_reject(XP1_PROPHET_ACTIVATION_SCHEMAS)
XP1_GREAT_PEOPLE_SCHEMAS = _with_xp1_great_people_reject(XP1_GREAT_PEOPLE_SCHEMAS)
XP1_RELIGION_FOUNDING_SCHEMAS = _with_xp1_great_people_reject(XP1_RELIGION_FOUNDING_SCHEMAS)
XP1_RELIGION_BELIEFS_SCHEMAS = _with_xp1_great_people_reject(XP1_RELIGION_BELIEFS_SCHEMAS)
XP1_PANTHEON_SCHEMAS = _with_xp1_great_people_reject(XP1_PANTHEON_SCHEMAS)
XP1_CITY_RELIGION_SCHEMAS = _with_xp1_great_people_reject(XP1_CITY_RELIGION_SCHEMAS)
XP1_RELIGION_CUSTOM_NAMES_SCHEMA_BY_BASE = {schema: schema+'.religion-custom-names.v1'
    for schema in XP1_RELIGION_FOUNDING_SCHEMAS}
_XP1_RELIGION_CUSTOM_NAMES_BASE_BY_SCHEMA = {new:base for base,new in XP1_RELIGION_CUSTOM_NAMES_SCHEMA_BY_BASE.items()}
XP1_RELIGION_CUSTOM_NAMES_SCHEMAS = tuple(_XP1_RELIGION_CUSTOM_NAMES_BASE_BY_SCHEMA)


def _with_xp1_religion_custom_names(bases):
    return (*bases, *(XP1_RELIGION_CUSTOM_NAMES_SCHEMA_BY_BASE[base] for base in bases
                     if base in XP1_RELIGION_CUSTOM_NAMES_SCHEMA_BY_BASE))


XP1_GREAT_PEOPLE_REJECT_SCHEMAS = _with_xp1_religion_custom_names(XP1_GREAT_PEOPLE_REJECT_SCHEMAS)
XP1_GREAT_PEOPLE_ACTIONS_SCHEMAS = _with_xp1_religion_custom_names(XP1_GREAT_PEOPLE_ACTIONS_SCHEMAS)
XP1_PROPHET_ACTIVATION_SCHEMAS = _with_xp1_religion_custom_names(XP1_PROPHET_ACTIVATION_SCHEMAS)
XP1_GREAT_PEOPLE_SCHEMAS = _with_xp1_religion_custom_names(XP1_GREAT_PEOPLE_SCHEMAS)
XP1_RELIGION_FOUNDING_SCHEMAS = _with_xp1_religion_custom_names(XP1_RELIGION_FOUNDING_SCHEMAS)
XP1_RELIGION_BELIEFS_SCHEMAS = _with_xp1_religion_custom_names(XP1_RELIGION_BELIEFS_SCHEMAS)
XP1_PANTHEON_SCHEMAS = _with_xp1_religion_custom_names(XP1_PANTHEON_SCHEMAS)
XP1_CITY_RELIGION_SCHEMAS = _with_xp1_religion_custom_names(XP1_CITY_RELIGION_SCHEMAS)
XP1_GREAT_PERSON_ACTIVATION_SCHEMA_BY_BASE = {schema: schema+'.great-person-activation.v1'
    for schema in XP1_CITY_RELIGION_SCHEMAS}
_XP1_GREAT_PERSON_ACTIVATION_BASE_BY_SCHEMA = {new:base for base,new in XP1_GREAT_PERSON_ACTIVATION_SCHEMA_BY_BASE.items()}
XP1_GREAT_PERSON_ACTIVATION_SCHEMAS = tuple(_XP1_GREAT_PERSON_ACTIVATION_BASE_BY_SCHEMA)


def _with_xp1_great_person_activation(bases):
    return (*bases, *(XP1_GREAT_PERSON_ACTIVATION_SCHEMA_BY_BASE[base] for base in bases
                     if base in XP1_GREAT_PERSON_ACTIVATION_SCHEMA_BY_BASE))


XP1_RELIGION_CUSTOM_NAMES_SCHEMAS = _with_xp1_great_person_activation(XP1_RELIGION_CUSTOM_NAMES_SCHEMAS)
XP1_GREAT_PEOPLE_REJECT_SCHEMAS = _with_xp1_great_person_activation(XP1_GREAT_PEOPLE_REJECT_SCHEMAS)
XP1_GREAT_PEOPLE_ACTIONS_SCHEMAS = _with_xp1_great_person_activation(XP1_GREAT_PEOPLE_ACTIONS_SCHEMAS)
XP1_PROPHET_ACTIVATION_SCHEMAS = _with_xp1_great_person_activation(XP1_PROPHET_ACTIVATION_SCHEMAS)
XP1_GREAT_PEOPLE_SCHEMAS = _with_xp1_great_person_activation(XP1_GREAT_PEOPLE_SCHEMAS)
XP1_RELIGION_FOUNDING_SCHEMAS = _with_xp1_great_person_activation(XP1_RELIGION_FOUNDING_SCHEMAS)
XP1_RELIGION_BELIEFS_SCHEMAS = _with_xp1_great_person_activation(XP1_RELIGION_BELIEFS_SCHEMAS)
XP1_PANTHEON_SCHEMAS = _with_xp1_great_person_activation(XP1_PANTHEON_SCHEMAS)
XP1_CITY_RELIGION_SCHEMAS = _with_xp1_great_person_activation(XP1_CITY_RELIGION_SCHEMAS)
XP1_RELIGIOUS_UNIT_OPERATIONS_SCHEMA_BY_BASE = {schema: schema+'.religious-unit-operations.v1'
    for schema in XP1_CITY_RELIGION_SCHEMAS}
_XP1_RELIGIOUS_UNIT_OPERATIONS_BASE_BY_SCHEMA = {new:base for base,new in XP1_RELIGIOUS_UNIT_OPERATIONS_SCHEMA_BY_BASE.items()}
XP1_RELIGIOUS_UNIT_OPERATIONS_SCHEMAS = tuple(_XP1_RELIGIOUS_UNIT_OPERATIONS_BASE_BY_SCHEMA)


def _with_xp1_religious_unit_operations(bases):
    return (*bases, *(XP1_RELIGIOUS_UNIT_OPERATIONS_SCHEMA_BY_BASE[base] for base in bases
                     if base in XP1_RELIGIOUS_UNIT_OPERATIONS_SCHEMA_BY_BASE))


XP1_GREAT_PERSON_ACTIVATION_SCHEMAS = _with_xp1_religious_unit_operations(XP1_GREAT_PERSON_ACTIVATION_SCHEMAS)
XP1_RELIGION_CUSTOM_NAMES_SCHEMAS = _with_xp1_religious_unit_operations(XP1_RELIGION_CUSTOM_NAMES_SCHEMAS)
XP1_GREAT_PEOPLE_REJECT_SCHEMAS = _with_xp1_religious_unit_operations(XP1_GREAT_PEOPLE_REJECT_SCHEMAS)
XP1_GREAT_PEOPLE_ACTIONS_SCHEMAS = _with_xp1_religious_unit_operations(XP1_GREAT_PEOPLE_ACTIONS_SCHEMAS)
XP1_PROPHET_ACTIVATION_SCHEMAS = _with_xp1_religious_unit_operations(XP1_PROPHET_ACTIVATION_SCHEMAS)
XP1_GREAT_PEOPLE_SCHEMAS = _with_xp1_religious_unit_operations(XP1_GREAT_PEOPLE_SCHEMAS)
XP1_RELIGION_FOUNDING_SCHEMAS = _with_xp1_religious_unit_operations(XP1_RELIGION_FOUNDING_SCHEMAS)
XP1_RELIGION_BELIEFS_SCHEMAS = _with_xp1_religious_unit_operations(XP1_RELIGION_BELIEFS_SCHEMAS)
XP1_PANTHEON_SCHEMAS = _with_xp1_religious_unit_operations(XP1_PANTHEON_SCHEMAS)
XP1_CITY_RELIGION_SCHEMAS = _with_xp1_religious_unit_operations(XP1_CITY_RELIGION_SCHEMAS)
XP1_CITY_RELIGION_DETAILS_SCHEMA_BY_BASE = {schema: schema+'.city-religion-details.v1'
    for schema in XP1_CITY_RELIGION_SCHEMAS}
_XP1_CITY_RELIGION_DETAILS_BASE_BY_SCHEMA = {new:base for base,new in XP1_CITY_RELIGION_DETAILS_SCHEMA_BY_BASE.items()}
XP1_CITY_RELIGION_DETAILS_SCHEMAS = tuple(_XP1_CITY_RELIGION_DETAILS_BASE_BY_SCHEMA)


def _with_xp1_city_religion_details(bases):
    return (*bases, *(XP1_CITY_RELIGION_DETAILS_SCHEMA_BY_BASE[base] for base in bases
                     if base in XP1_CITY_RELIGION_DETAILS_SCHEMA_BY_BASE))


XP1_RELIGIOUS_UNIT_OPERATIONS_SCHEMAS = _with_xp1_city_religion_details(XP1_RELIGIOUS_UNIT_OPERATIONS_SCHEMAS)
XP1_GREAT_PERSON_ACTIVATION_SCHEMAS = _with_xp1_city_religion_details(XP1_GREAT_PERSON_ACTIVATION_SCHEMAS)
XP1_RELIGION_CUSTOM_NAMES_SCHEMAS = _with_xp1_city_religion_details(XP1_RELIGION_CUSTOM_NAMES_SCHEMAS)
XP1_GREAT_PEOPLE_REJECT_SCHEMAS = _with_xp1_city_religion_details(XP1_GREAT_PEOPLE_REJECT_SCHEMAS)
XP1_GREAT_PEOPLE_ACTIONS_SCHEMAS = _with_xp1_city_religion_details(XP1_GREAT_PEOPLE_ACTIONS_SCHEMAS)
XP1_PROPHET_ACTIVATION_SCHEMAS = _with_xp1_city_religion_details(XP1_PROPHET_ACTIVATION_SCHEMAS)
XP1_GREAT_PEOPLE_SCHEMAS = _with_xp1_city_religion_details(XP1_GREAT_PEOPLE_SCHEMAS)
XP1_RELIGION_FOUNDING_SCHEMAS = _with_xp1_city_religion_details(XP1_RELIGION_FOUNDING_SCHEMAS)
XP1_RELIGION_BELIEFS_SCHEMAS = _with_xp1_city_religion_details(XP1_RELIGION_BELIEFS_SCHEMAS)
XP1_PANTHEON_SCHEMAS = _with_xp1_city_religion_details(XP1_PANTHEON_SCHEMAS)
XP1_CITY_RELIGION_SCHEMAS = _with_xp1_city_religion_details(XP1_CITY_RELIGION_SCHEMAS)
XP1_PRODUCTION_INFO_SCHEMAS = (*_XP1_PRODUCTION_INFO_BASE_BY_SCHEMA, *XP1_CITY_RELIGION_SCHEMAS)


def _with_xp1_production_info(bases):
    production = tuple(XP1_PRODUCTION_INFO_SCHEMA_BY_BASE[base] for base in bases)
    religion = tuple(XP1_CITY_RELIGION_SCHEMA_BY_BASE[base] for base in production)
    pantheons = tuple(XP1_PANTHEON_SCHEMA_BY_BASE[base] for base in religion)
    beliefs = tuple(XP1_RELIGION_BELIEFS_SCHEMA_BY_BASE[base] for base in (*religion,*pantheons))
    foundations = tuple(XP1_RELIGION_FOUNDING_SCHEMA_BY_BASE[base]
                        for base in (*religion,*pantheons,*beliefs))
    return (*bases, *production, *_with_xp1_city_religion_details(_with_xp1_religious_unit_operations(_with_xp1_great_person_activation(_with_xp1_religion_custom_names(_with_xp1_great_people_reject(_with_xp1_great_people_actions(_with_xp1_prophet_activation(
        _with_xp1_great_people((*religion, *pantheons, *beliefs, *foundations))))))))))


XP1_TRADE_SCHEMAS = _with_xp1_production_info(_with_xp1_unit_upgrades(
    _with_xp1_promotions(_with_xp1_buildings(_with_xp1_purchases(_XP1_TRADE_WITH_GOVERNMENT)))))
_XP1_DEDICATION_SCHEMAS = _with_xp1_production_info(_XP1_PRODUCTION_BASES)
XP1_LEVY_SCHEMAS = (CAPABILITY_XP1_CITY_STATE_LEVIES_SCHEMA, CAPABILITY_XP1_UNIT_LEVIES_SCHEMA,
                   *_XP1_DEDICATION_SCHEMAS)
XP1_ENVOY_CHOICE_SCHEMAS = (CAPABILITY_XP1_ENVOY_CHOICES_SCHEMA,
                            *XP1_LEVY_SCHEMAS)
XP1_CITY_STATE_ENVOY_SCHEMAS = (CAPABILITY_XP1_CITY_STATE_ENVOYS_SCHEMA,
                                *XP1_ENVOY_CHOICE_SCHEMAS)
_XP1_CAPTURE_SCHEMAS = (CAPABILITY_XP1_CAPTURED_CITY_SCHEMA, CAPABILITY_XP1_CITY_SHOT_SCHEMA,
                        CAPABILITY_XP1_DISTRICT_SHOT_SCHEMA, CAPABILITY_XP1_GOVERNORS_SCHEMA,
                        *XP1_CITY_STATE_ENVOY_SCHEMAS)


_XP1_OVERVIEW_BASES = (CAPABILITY_XP1_TRADE_OVERVIEW_SCHEMA,
                       XP1_GOVERNMENT_SCHEMA_BY_BASE[CAPABILITY_XP1_TRADE_OVERVIEW_SCHEMA])
XP1_TRADE_OVERVIEW_SCHEMAS = _with_xp1_production_info(_with_xp1_unit_upgrades(
    _with_xp1_promotions(_with_xp1_buildings(_with_xp1_purchases(_XP1_OVERVIEW_BASES)))))
