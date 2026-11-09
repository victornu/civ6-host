"""Exact Gathering Storm captured inputs for the private Init lifecycle.

The common ownership checker does not substitute XP1 databases or admit Load.
"""
from .xp2_bundle_inputs import REFERENCE
from .captured_saved_load import validate_candidate_inputs


def context_receipt_engine_fields(profile):
    """Return explicit execution/reference identities without rewriting legacy receipts."""
    actual = getattr(profile, 'core_sha256', None)
    image = getattr(profile, 'execution_image', None)
    if not isinstance(actual, str) or len(actual) != 64:
        raise ValueError('XP2 context profile has no actual Core identity')
    if image is None:
        return dict(core_sha256=actual, execution_image_sha256=None,
                    reference_core_sha256=None)
    reference = getattr(profile, 'source_core_sha256', None)
    if (getattr(image, 'image_sha256', None) != actual
            or getattr(image, 'reference_core_sha256', None) != reference):
        raise ValueError('XP2 context profile actual/reference identity pair differs')
    return dict(core_sha256=actual,
                execution_image_sha256=image.image_sha256,
                reference_core_sha256=reference)


def stamp_context_init_receipt(profile, receipt):
    """Keep `core_sha256` as actual Core; add a separate pair for selected images."""
    if type(receipt) is not dict:
        raise ValueError('XP2 context Init receipt is not a dictionary')
    fields = context_receipt_engine_fields(profile)
    if receipt.get('core_sha256') != fields['core_sha256']:
        raise ValueError('XP2 context Init receipt actual Core identity differs')
    receipt['execution_image_sha256'] = fields['execution_image_sha256']
    receipt['reference_core_sha256'] = fields['reference_core_sha256']
    return receipt


def validate_context_receipt_engine_identity(profile, receipt):
    """Accept absent optional fields only for the historical no-image profile."""
    if type(receipt) is not dict:
        raise ValueError('XP2 context lifecycle receipt is not a dictionary')
    fields = context_receipt_engine_fields(profile)
    if receipt.get('core_sha256') != fields['core_sha256']:
        raise ValueError('XP2 context lifecycle actual Core identity differs')
    for name in ('execution_image_sha256', 'reference_core_sha256'):
        expected = fields[name]
        actual = receipt.get(name)
        if expected is None:
            if actual is not None:
                raise ValueError('XP2 context lifecycle receipt has an undeclared image identity')
        elif actual != expected:
            raise ValueError('XP2 context lifecycle receipt actual/reference identity pair differs')

DATABASE_PINS = {
    'configuration': dict(sha256='670b41e41d565d9b021b4bdc043dd02ed35a778c1bbb530ff65610bd9bc65544', size_bytes=815104),
    'gameplay': dict(sha256='8fff3c3d0365ba2b6dd088d0f3c5f9a31ff069ec08613af99a8a4fe710b65331', size_bytes=8736768),
    'localization': dict(sha256='54e5bfd3937efcd3b5e853f68a7e168ee98f39bad791207fdb545be5891a3b69', size_bytes=94535680),
}


def input_identity(bundle):
    from . import xp2_bbg_inputs
    if xp2_bbg_inputs.is_reference(bundle.reference):
        return bundle.reference, xp2_bbg_inputs.database_pins(bundle.reference)
    return REFERENCE, DATABASE_PINS


def database_input_binding(bundle, host, configuration_path, gameplay_path, private_root):
    from .captured_init_inputs import database_input_binding as bind
    reference, pins = input_identity(bundle)
    return bind(bundle, host, configuration_path, gameplay_path, private_root,
        family='xp2-lan', reference=reference, database_pins=pins,
        validate_inputs=validate_candidate_inputs)


def validate_init_receipt_binding(bundle, host, receipt):
    from .captured_init_inputs import validate_init_receipt_binding as validate
    reference, pins = input_identity(bundle)
    return validate(bundle, host, receipt, family='xp2-lan', reference=reference,
        database_pins=pins, validate_inputs=validate_candidate_inputs)


def bind_candidate(bundle, profile, fixture):
    """Bind registered XP2 inputs before Database::Initialize; no saved Load."""
    from .saved_load_profiles import XP2_CORE_SHA256
    from .native.native_official_bundle import _reuse_prepared_bundle, validate_fixture
    if (getattr(profile, 'source_core_sha256', getattr(profile, 'core_sha256', None)) != XP2_CORE_SHA256
            or getattr(profile, 'ruleset', None) != 'xp2'
            or getattr(profile, 'mode', None) != 'context'):
        raise ValueError('XP2 Init requires the exact context-only engine profile')
    validate_candidate_inputs(getattr(bundle, 'inputs', None), bundle)
    _reuse_prepared_bundle(bundle, input_identity(bundle)[0], 'xp2-lan', _input_only=True)
    validate_fixture(bundle, fixture)
