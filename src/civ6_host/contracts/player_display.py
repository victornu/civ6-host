"""Candidate contract for two named human display flows, over retained raw v1.

This module performs no reads, native calls, gameplay estimates or UI rendering.
The schema versions changed numeric meaning without reinterpreting raw v1.
"""
from __future__ import annotations
import copy
import math
from civ6_host.contracts import yield_display982 as yields
from civ6_host.player_view import _validate_observation

RAW_OBSERVATION_SCHEMA='civ6rl-player-observation-v1'
PUBLIC_OBSERVATION_SCHEMA='civ6-host.player-observation-display.v2'
PUBLIC_VIEW_SCHEMA='civ6-host.player-view-display.v2'
INFORMATION_SCHEMA='civ6-host.player-display-information.v1'
SOURCE_SHA256='169cdc8a5dc1c3d21bc7f9935ce23c942784935d797606d70c03fc817adfffa2'
SCOPE={
 'city_yields':'CityPanel: CitySupport.UpdateYieldData -> Civ6Common.toPlusMinusString',
 'empire_science_culture':'TopPanel: FormatValuePerTurn',
 'gold_balance':'TopPanel: floor(GetGoldBalance())',
 'faith_balance':'TopPanel: Locale.ToNumber(balance, #,###.#)',
 'tooltip_precision_qualified':False,
 'combat_precision_changed':False,
 'estimate_bindings_added':False,
}


def validate_raw(raw):
    if type(raw) is not dict or raw.get('schema')!=RAW_OBSERVATION_SCHEMA:
        raise ValueError('Display projection requires the retained native observation v1')
    _validate_observation(raw,raw.get('player_id'),raw.get('turn'))
    return raw


def project_city_panel(raw):
    """Detach only the six values governed by the exact CityPanel flow."""
    validate_raw(raw)
    return [dict(city_id=city['id'],yields={key:yields._floor_tenth(value)
                for key,value in city['yields'].items()}) for city in raw['cities']]


def project_observation(raw,top_panel_text):
    """TopPanel text must already be authenticated by the owned runtime receipt."""
    validate_raw(raw)
    if type(top_panel_text) is not dict or set(top_panel_text)!={'science','culture','faith'}:
        raise ValueError('Missing complete source-bound TopPanel display text')
    shown={key:yields.public_number(value) for key,value in top_panel_text.items()}
    # Reuse the existing global display consistency envelope; it is not a
    # replacement rounding rule and does not authenticate the text's producer.
    for key,value in shown.items():
        if abs(value-raw['economy'][key])>yields._GLOBAL_TOLERANCE:
            raise ValueError('TopPanel text is outside the existing display envelope')
    public=copy.deepcopy(raw);public['schema']=PUBLIC_OBSERVATION_SCHEMA
    city_values={row['city_id']:row['yields'] for row in project_city_panel(raw)}
    for city in public['cities']:city['yields']=city_values[city['id']]
    public['economy']={**shown,'gold':math.floor(raw['economy']['gold'])}
    return public


def validate_public(view):
    fields={'schema','episode_id','game_generation','sequence','turn_mode','observation',
            'decisions','applied_action','outcome','locale','display_source_sha256',
            'display_scope','top_panel_text'}
    if type(view) is not dict or set(view)!=fields or view['schema']!=PUBLIC_VIEW_SCHEMA:
        raise ValueError('Unknown public display envelope')
    if (view['display_source_sha256']!=SOURCE_SHA256 or type(view['display_scope']) is not dict
            or set(view['display_scope'])!=set(SCOPE)
            or any(type(view['display_scope'][k]) is not type(v) or view['display_scope'][k]!=v for k,v in SCOPE.items())):
        raise ValueError('Display flow scope or source differs')
    observation=view['observation']
    if type(observation) is not dict or observation.get('schema')!=PUBLIC_OBSERVATION_SCHEMA:
        raise ValueError('Public display cannot relabel a raw observation v1')
    # This temporary copy reuses ownership/visibility/shape validation only.
    # It is never emitted, saved, compared as raw native data, or retained.
    shape=copy.deepcopy(observation);shape['schema']=RAW_OBSERVATION_SCHEMA
    _validate_observation(shape,shape.get('player_id'),shape.get('turn'))
    if type(observation['economy']['gold']) is not int:
        raise ValueError('TopPanel balance must have integer displayed precision')
    text=view['top_panel_text']
    if type(text) is not dict or set(text)!={'science','culture','faith'}:
        raise ValueError('Missing TopPanel labels')
    for key,value in text.items():
        if yields.public_number(value)!=observation['economy'][key]:
            raise ValueError('Public TopPanel label/number differs')
    for city in observation['cities']:
        if any(abs(v*10-round(v*10))>1e-9 for v in city['yields'].values()):
            raise ValueError('Public CityPanel yield exceeds its label precision')
    return view


def display_information(view):
    """One additional group in the existing cached information pipeline."""
    validate_public(view);o=view['observation']
    return dict(schema=INFORMATION_SCHEMA,episode_id=view['episode_id'],
        game_generation=view['game_generation'],player_id=o['player_id'],sequence=view['sequence'],
        turn=o['turn'],locale=view['locale'],source_sha256=view['display_source_sha256'],
        city_panel=projected_city_rows(o),top_panel=copy.deepcopy(o['economy']),
        top_panel_text=copy.deepcopy(view['top_panel_text']),display_scope=copy.deepcopy(SCOPE))


def projected_city_rows(observation):
    return [dict(city_id=city['id'],yields=copy.deepcopy(city['yields'])) for city in observation['cities']]


def validate_relation(raw, public_view):
    """Bind the detached public result to this exact private observation."""
    validate_public(public_view)
    if project_observation(raw,public_view['top_panel_text'])!=public_view['observation']:
        raise ValueError('Public display changed fields outside its governed projection')
    return public_view
