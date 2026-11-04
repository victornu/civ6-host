"""Explicit recruitment through the existing official Great Person adapter.

Only native CanRecruitPerson offers are exposed here. Rejecting, patronage and
activation are separate, still-unqualified actions; no replacement is chosen.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from civ6_host.runtime.native import native_great_people_actions as native
from civ6_host.runtime.native.native_player_observation import observe_player
FIELDS = {'kind', 'individual', 'cost'}

def validate_catalog(value, turn, *, player_id=0):
    native._pid(player_id)
    native._turn(turn)
    if type(value) is not dict:
        raise ValueError('Malformed Great Person catalogue')
    for key, expected in [('player_id', player_id), ('current_game_turn', turn)]:
        if type(value.get(key)) is not int or value[key] != expected:
            raise ValueError('Foreign Great Person catalogue')
    if value.get('status') == 'not_due':
        if set(value) != {'status', 'reason', 'player_id', 'current_game_turn'} or value['reason'] != 'no_recruitable_person':
            raise ValueError('Malformed Great Person absence')
    elif value.get('status') == 'catalog':
        choices = value.get('choices')
        if type(choices) is not list or not choices or len(choices) > native._MAX_CHOICES:
            raise ValueError('Malformed Great Person offers')
        if type(choices[0]) is not dict or 'individual' not in choices[0]:
            raise ValueError('Malformed first Great Person offer')
        native.choose(dict(value, choices=tuple(choices)), choices[0]['individual'])
    else:
        raise ValueError('Unknown Great Person catalogue status')
    return value

def catalog(prefix, turn, *, player_id=0):
    raw = prefix.runtime.evaluate_text(prefix.ui_child, native.catalog_source(player_id, turn), b'@explicit_great_people_catalog', capacity=native._MAX_RESPONSE + 1)
    value = native.parse_catalog(raw, player_id, turn)
    if 'choices' in value:
        value['choices'] = list(value['choices'])
    return validate_catalog(value, turn, player_id=player_id)

def actions(value):
    return [dict(kind='recruit_great_person', **r) for r in value.get('choices', [])]

def validate_action(action):
    if type(action) is not dict or set(action) != FIELDS or action.get('kind') != 'recruit_great_person':
        raise ValueError('Malformed Great Person recruitment')
    native._uint(action['individual'], 'individual index', 2147483647)
    native._uint(action['cost'], 'recruit cost', 2147483647)
    return action

def apply(owner, prefix, action, turn, before, *, player_id=0):
    validate_action(action)
    native._pid(player_id)
    native._turn(turn)
    if type(before) is not dict or before.get('player_id') != player_id or before.get('turn') != turn:
        raise ValueError('Great Person action lacks actor observation')
    fresh = catalog(prefix, turn, player_id=player_id)
    if fresh != getattr(owner, 'explicit_great_people', None) or action not in actions(fresh):
        raise RuntimeError('Great Person decision is stale or unavailable')
    choice = native.choose(dict(fresh, choices=tuple(fresh['choices'])), action['individual'])
    receipt = prefix.inspect_great_person_choice(player_id, selected_individual=action['individual'])
    raw = prefix.runtime.evaluate_text(prefix.ui_child, native.effect_source(choice), b'@explicit_great_person_effect', capacity=257)
    effect = native.parse_effect(raw, choice)
    if not effect['confirmed'] or receipt != effect:
        raise RuntimeError('Great Person recruitment lacks matching native grant readback')
    after = observe_player(prefix.runtime, prefix.ui_child, player_id)
    if after.get('player_id') != player_id or after.get('turn') != turn:
        raise RuntimeError('Great Person recruitment crossed actor/turn')
    owner.emit('official_explicit_great_person_effect', action=action, catalog_before=fresh, receipt=receipt, observation_before=before, observation_after=after, source_proof_sha256=native.PINNED_EVIDENCE_SHA256, automatic_choices_applied=False, strategic_training_ready=False)
    return after
