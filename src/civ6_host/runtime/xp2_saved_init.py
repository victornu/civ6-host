"""Exact Gathering Storm captured inputs for the private Init lifecycle.

The common ownership checker does not substitute XP1 databases or admit Load.
"""
from .xp2_bundle_inputs import REFERENCE, validate_candidate_inputs

DATABASE_PINS = {
    'configuration': dict(sha256='670b41e41d565d9b021b4bdc043dd02ed35a778c1bbb530ff65610bd9bc65544', size_bytes=815104),
    'gameplay': dict(sha256='8fff3c3d0365ba2b6dd088d0f3c5f9a31ff069ec08613af99a8a4fe710b65331', size_bytes=8736768),
    'localization': dict(sha256='54e5bfd3937efcd3b5e853f68a7e168ee98f39bad791207fdb545be5891a3b69', size_bytes=94535680),
}


def database_input_binding(bundle, host, configuration_path, gameplay_path, private_root):
    from .captured_init_inputs import database_input_binding as bind
    return bind(bundle, host, configuration_path, gameplay_path, private_root,
        family='xp2-lan', reference=REFERENCE, database_pins=DATABASE_PINS,
        validate_inputs=validate_candidate_inputs)


def validate_init_receipt_binding(bundle, host, receipt):
    from .captured_init_inputs import validate_init_receipt_binding as validate
    return validate(bundle, host, receipt, family='xp2-lan', reference=REFERENCE,
        database_pins=DATABASE_PINS, validate_inputs=validate_candidate_inputs)


def bind_candidate(bundle, profile, fixture):
    """Bind registered XP2 inputs before Database::Initialize; no saved Load."""
    from .saved_load_profiles import XP2_CORE_SHA256
    from .native.native_official_bundle import _reuse_prepared_bundle, validate_fixture
    if (getattr(profile, 'core_sha256', None) != XP2_CORE_SHA256
            or getattr(profile, 'ruleset', None) != 'xp2'
            or getattr(profile, 'mode', None) != 'context'):
        raise ValueError('XP2 Init requires the exact context-only engine profile')
    validate_candidate_inputs(getattr(bundle, 'inputs', None), bundle)
    _reuse_prepared_bundle(bundle, REFERENCE, 'xp2-lan', _input_only=True)
    validate_fixture(bundle, fixture)
