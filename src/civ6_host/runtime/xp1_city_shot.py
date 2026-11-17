"""City and district ranged commands on the installed Rise and Fall profile."""

import hashlib
from functools import partial
from pathlib import Path

from .configuration_profiles import XP1_CORE_SHA256, _source
from .execution_images import _XP1_PROFILE, identity
from .paths import resource_root
from .resource_resolution import resolve_path
from .xp1_saved_load import REFERENCE


SOURCE = (
    'evidence/host-xp1-installed-city-shot-source.json',
    '9f360b061f84eee1f8ecbcdc5ce29f748a68582cdb7ca96ce3ae57b3300adf8c',
)
DISTRICT_SOURCE = (
    'evidence/host-xp1-installed-district-shot-source.json',
    '313c4f1ec8fcdaa359b5979950fcf14cbd6afd3962a278e5737e0a1dc494cbff',
)


def source(image):
    if image is not _XP1_PROFILE:
        raise ValueError('City shots require the installed Rise and Fall execution image')
    proof = _source(SOURCE)
    origin = proof['official_capture']
    if (proof['schema'] != 'civ6-host.xp1-city-shot.source.v1'
            or proof['image'] != identity(image)
            or (Path(origin['path']).as_posix(), origin['sha256']) != REFERENCE
            or set(proof['registrations']) != {'CanStartCommand', 'RequestCommand', 'GetCommandTargets'}
            or {name: row['value'] for name, row in proof['enums'].items()} != {
                'CityCommandTypes.RANGE_ATTACK': -1967338303,
                'CityCommandResults.PLOTS': 1933683541,
                'CityCommandResults.MODIFIERS': 628984671,
                'CityCommandResults.MODIFIER_IS_TARGET': 889110605,
            }):
        raise ValueError('Rise and Fall city-shot source differs')
    return proof


def district_source(image):
    if image is not _XP1_PROFILE:
        raise ValueError('District shots require the installed Rise and Fall execution image')
    proof = _source(DISTRICT_SOURCE)
    city = proof['city_command_source']
    if (proof['schema'] != 'civ6-host.xp1-district-shot.source.v1'
            or proof['image'] != identity(image)
            or (Path(city['path']).as_posix(), city['sha256']) != SOURCE
            or proof['ui_matches_xp2_codec'] is not True
            or set(proof['district_registrations']) != {'GetCity', 'GetDefenseStrength', 'IsComplete'}):
        raise ValueError('Rise and Fall district-shot source differs')
    return proof


def source_dependencies(image):
    proof = source(image)
    district = district_source(image)
    pins = {str((resource_root() / ref[0]).resolve()): ref[1] for ref in (SOURCE, DISTRICT_SOURCE)}
    notification = district['district_notification_source']
    pins[str((resource_root() / notification['path']).resolve())] = notification['sha256']
    for row in proof['official_ui'].values():
        pins[str(resolve_path(Path(row['path'])).resolve())] = row['sha256']
    return pins


def bind(saved):
    continuation = saved.continuation
    continuation.check(active=False)
    core = saved.backend.core
    if (saved.inputs.official_bundle != REFERENCE
            or getattr(continuation, 'captured_city_core', None) is not core
            or getattr(continuation, 'city_shot_core', None) is not None):
        raise ValueError('Rise and Fall city shots require the bound native city manager')
    image = getattr(core, '_civ6_host_execution_image', None)
    proof = source(image)
    district = district_source(image)
    spans = [row['span'] for row in proof['enums'].values()]
    for registrations in (proof['registrations'], district['district_registrations']):
        for binding in registrations.values():
            spans.extend((binding['registration_span'], binding['entry_pdata_fragment']))
    for span in spans:
        raw = saved.backend.runtime.read(core._handle + span['rva'], span['bytes'])
        if type(raw) is not bytes or hashlib.sha256(raw).hexdigest() != span['sha256']:
            raise ValueError(f"Live Rise and Fall city-shot binding differs at {span['rva']:#x}")
    continuation.city_shot_core = core


def apply(saved, prefix, action, turn, observation):
    from .native import native_saved_city_shot, native_saved_district_shot

    continuation = saved.continuation
    core = saved.backend.core
    if getattr(continuation, 'city_shot_core', None) is not core:
        raise ValueError('Rise and Fall city-shot owner is not bound')
    image = core._civ6_host_execution_image
    kind = action['kind']
    shot, shooter, proof = {
        'city_range_attack': (native_saved_city_shot, 'city', SOURCE),
        'district_range_attack': (native_saved_district_shot, 'district', DISTRICT_SOURCE),
    }[kind]
    return native_saved_city_shot.execute(saved, prefix, action, turn, observation,
        player_id=observation['player_id'],
        expected_catalogue=continuation.explicit_ranged_shots[kind],
        expected_defenses=continuation.explicit_city_shot_defenses,
        validate=shot.validate_action, read_catalogue=partial(shot.catalog, execution_image=image),
        compare=shot.compare_own_cities, offers=shot.actions,
        request=partial(shot.request_source, execution_image=image), verify_effect=shot.effect,
        shooter=shooter, proof_sha=proof[1], defense_core_sha256=XP1_CORE_SHA256)
